"""Thumbnail download, caching and Kitty Graphics Protocol rendering.

The TUI displays a thumbnail of the selected video in the right pane.
Images are downloaded on demand (with atomic temp-file → rename to
survive interrupted writes), resized to fit the reserved cell area in
PIL, and transmitted to the terminal as APC escape sequences understood
by Kitty / WezTerm / Konsole / Ghostty.

Downloads run in a small background thread pool so the curses main
loop never blocks on the network — the user can scroll smoothly even
when many thumbnails are missing from disk. When a download finishes,
:func:`take_redraw_event` returns ``True`` once, prompting the main
loop to repaint and pick up the freshly cached image.

This module is mostly state-light: callers (``YouTubeTUI``) own the
per-session encode cache and pass it in. The download executor and
in-flight tracking are module-level singletons because they are
process-wide infrastructure with no per-instance state.
"""

from __future__ import annotations

import base64
import fcntl
import io
import os
import struct
import sys
import termios
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional, Tuple

from . import paths
from .models import Video

# Fallback terminal cell size used when TIOCGWINSZ returns zeroes.
# 16px tall × 8px wide matches most common terminal font defaults.
CELL_H_PX_FALLBACK = 16
CELL_W_PX_FALLBACK = 8

THUMB_CACHE_DIR = str(paths.thumb_cache_dir())

EncodeCache = Dict[Tuple[str, int, int, int, int], Optional[bytes]]

# --- Async download infrastructure ---------------------------------------

# Small pool — too many parallel downloads hammer i.ytimg.com without
# helping the user, who only sees one thumb at a time.
_DOWNLOAD_WORKERS = 4
_executor: Optional[ThreadPoolExecutor] = None
_download_in_flight: set = set()
_encode_in_flight: set = set()
_in_flight_lock = threading.Lock()
_redraw_event = threading.Event()


def _get_executor() -> ThreadPoolExecutor:
    """Lazily creates the shared download pool on first use."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=_DOWNLOAD_WORKERS,
                                       thread_name_prefix="yt-sub-thumb")
    return _executor


def take_redraw_event() -> bool:
    """Returns ``True`` once if a background download has completed.

    The TUI main loop calls this on every iteration and triggers a full
    redraw when ``True`` is returned, which lets the just-downloaded
    thumbnail appear without further user input. The event auto-resets
    on consume.
    """
    if _redraw_event.is_set():
        _redraw_event.clear()
        return True
    return False


def _download_to_disk(video: Video) -> None:
    """Worker job: fetches a thumbnail to disk via atomic temp-file rename.

    Tries ``maxresdefault.jpg`` first, then the stored ``thumbnail_url``
    fallback. Any partial file is removed on failure so a future attempt
    is not poisoned by a truncated cache file.
    """
    cache_path = os.path.join(THUMB_CACHE_DIR, f"{video.id}_max.jpg")
    if os.path.exists(cache_path):
        return  # raced with another worker; nothing to do.
    tmp_path = cache_path + ".tmp"
    urls = [f"https://i.ytimg.com/vi/{video.id}/maxresdefault.jpg"]
    if video.thumbnail_url:
        urls.append(video.thumbnail_url)
    for url in urls:
        try:
            urllib.request.urlretrieve(url, tmp_path)
            os.replace(tmp_path, cache_path)
            return
        except Exception:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except OSError: pass
            continue


def _schedule_download(video: Video) -> None:
    """Submits a download for ``video`` if one is not already in flight."""
    with _in_flight_lock:
        if video.id in _download_in_flight:
            return
        _download_in_flight.add(video.id)

    def _runner() -> None:
        try:
            _download_to_disk(video)
        finally:
            with _in_flight_lock:
                _download_in_flight.discard(video.id)
            _redraw_event.set()

    _get_executor().submit(_runner)


def _schedule_encode(video: Video, cols: int, rows: int,
                     cell_w: int, cell_h: int,
                     cache: EncodeCache) -> None:
    """Runs PIL encode in a worker, populating ``cache`` on completion.

    Encoding (Image.open + resize LANCZOS + PNG + base64) takes
    ~50–200 ms per frame on a typical machine. Doing it on the main
    thread stalls the curses redraw loop and produces visible lag when
    the user navigates the list. Defer it to the same pool that handles
    downloads; the next redraw will pick the bytes up from ``cache``.

    Args:
        video: Video whose thumbnail should be encoded.
        cols, rows, cell_w, cell_h: Geometry parameters; together with
            the video ID they form the cache key.
        cache: Per-session memoization dict; the worker writes here on
            success.
    """
    cache_key = (video.id, cols, rows, cell_w, cell_h)
    with _in_flight_lock:
        if cache_key in _encode_in_flight:
            return
        _encode_in_flight.add(cache_key)

    cache_path = os.path.join(THUMB_CACHE_DIR, f"{video.id}_max.jpg")

    def _runner() -> None:
        try:
            result = _encode_from_disk(cache_path, cols, rows, cell_w)
            if result is not None:
                cache[cache_key] = result
        finally:
            with _in_flight_lock:
                _encode_in_flight.discard(cache_key)
            _redraw_event.set()

    _get_executor().submit(_runner)


# --- Synchronous helpers (terminal sizing, encoding) ---------------------

def get_cell_px() -> Tuple[int, int]:
    """Queries the terminal for the pixel size of a single character cell.

    Uses the ``TIOCGWINSZ`` ioctl to read pixel dimensions reported by the
    terminal emulator.

    Returns:
        ``(cell_height_px, cell_width_px)``. Falls back to
        ``(CELL_H_PX_FALLBACK, CELL_W_PX_FALLBACK)`` when the ioctl fails
        or returns zeroes.
    """
    try:
        buf = struct.pack('HHHH', 0, 0, 0, 0)
        res = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, buf)
        rows, cols, xpx, ypx = struct.unpack('HHHH', res)
        if rows > 0 and cols > 0 and xpx > 0 and ypx > 0:
            return ypx // rows, xpx // cols
    except Exception:
        pass
    return CELL_H_PX_FALLBACK, CELL_W_PX_FALLBACK


def _encode_from_disk(cache_path: str, cols: int, rows: int,
                      cell_w: int) -> Optional[bytes]:
    """Reads ``cache_path`` and returns its Kitty APC byte stream.

    Returns ``None`` (and removes the cache file) if PIL cannot decode
    the bytes, so the next render attempt re-downloads instead of
    hitting the same broken image.
    """
    try:
        from PIL import Image
        img = Image.open(cache_path).convert("RGB")
        target_w = cols * cell_w
        ratio = target_w / img.width
        target_h = round(img.height * ratio)
        img = img.resize((target_w, target_h), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.standard_b64encode(buf.getvalue()).decode('ascii')

        chunk_size = 4096
        chunks = [b64[i:i + chunk_size] for i in range(0, len(b64), chunk_size)]
        result = b''
        for i, chunk in enumerate(chunks):
            more = 1 if i < len(chunks) - 1 else 0
            if i == 0:
                # c=/r= clip the image to exactly the reserved cell area,
                # preventing overflow regardless of rounding differences.
                payload = f'a=T,f=100,c={cols},r={rows},q=2,m={more};{chunk}'
            else:
                payload = f'm={more};{chunk}'
            result += f'\033_G{payload}\033\\'.encode('ascii')
        return result
    except Exception:
        # Truncated download or decoder error — drop the file so the
        # next iteration re-downloads. Don't cache None: doing so would
        # silently hide the thumbnail until the process restarts.
        try: os.remove(cache_path)
        except OSError: pass
        return None


def encode_kitty(video: Video, cols: int, rows: int,
                 cell_w: int, cell_h: int,
                 cache: EncodeCache) -> Optional[bytes]:
    """Returns Kitty APC bytes for a thumbnail, or schedules a download.

    Three paths, all non-blocking:
    1. Encode result is in ``cache`` → return cached bytes immediately.
    2. The JPEG is on disk but not yet encoded → schedule encode in a
       worker, return ``None``. The encode populates ``cache``; the
       next redraw (triggered by :func:`take_redraw_event`) hits path 1.
    3. The JPEG is missing → schedule a background download, return
       ``None``. After download finishes the next redraw lands in
       path 2.

    The image is transmitted with explicit ``c=`` / ``r=`` cell-size
    parameters so the terminal clips the image to exactly the reserved
    area, preventing overflow when navigating between items.

    Args:
        video: Video whose thumbnail should be encoded.
        cols: Target width in terminal columns.
        rows: Target height in terminal rows.
        cell_w: Width of a single terminal cell in pixels.
        cell_h: Height of a single terminal cell in pixels.
        cache: Per-session memoization dict owned by the caller.

    Returns:
        Raw bytes containing the Kitty APC sequences, or ``None`` if the
        image is not yet available (or PIL cannot load it).
    """
    cache_key = (video.id, cols, rows, cell_w, cell_h)
    if cache_key in cache:
        return cache[cache_key]

    if cols < 4:
        cache[cache_key] = None
        return None

    os.makedirs(THUMB_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(THUMB_CACHE_DIR, f"{video.id}_max.jpg")

    if not os.path.exists(cache_path):
        # No file yet; let a worker fetch it. Caller renders an empty slot.
        _schedule_download(video)
        return None

    # File present but no encode cached: schedule encoding off the main
    # thread. ~50–200 ms PIL work would otherwise block the redraw cycle
    # while the user is scrolling.
    _schedule_encode(video, cols, rows, cell_w, cell_h, cache)
    return None


def clear_kitty() -> None:
    """Sends a Kitty Graphics Protocol delete-all command to the terminal.

    Removes every image currently displayed by the terminal, leaving the
    cell grid intact.  Call this before handing the screen to a non-Kitty
    renderer (e.g. a full-screen overlay or a different TUI view) so that
    ghost thumbnails do not bleed through.
    """
    sys.stdout.buffer.write(b'\033_Ga=d,d=A\033\\')
    sys.stdout.buffer.flush()


def draw_kitty(abs_row: int, abs_col: int, cols: int, rows: int,
               video: Video, cell_w: int, cell_h: int,
               cache: EncodeCache) -> None:
    """Renders the thumbnail at an absolute terminal position.

    First deletes any existing Kitty image (``a=d,d=A``), then moves the
    cursor and sends the encoded image bytes. The cursor position is saved
    and restored with ``\\033[s`` / ``\\033[u`` so ncurses internal state
    stays in sync.

    If the image is not yet available locally only the delete escape is
    emitted; a redraw triggered by :func:`take_redraw_event` will paint
    the actual image once the download completes.

    Args:
        abs_row: Terminal row (0-based) for the top-left corner.
        abs_col: Terminal column (0-based) for the top-left corner.
        cols: Width in columns used when encoding the image.
        rows: Height in rows for the image area.
        video: Video whose thumbnail should be rendered.
        cell_w: Width of a single terminal cell in pixels.
        cell_h: Height of a single terminal cell in pixels.
        cache: Per-session memoization dict owned by the caller.
    """
    delete = b'\033_Ga=d,d=A\033\\'
    data = encode_kitty(video, cols, rows, cell_w, cell_h, cache)
    if not data:
        sys.stdout.buffer.write(delete)
        sys.stdout.buffer.flush()
        return
    cursor_pos = f'\033[{abs_row + 1};{abs_col + 1}H'.encode('ascii')
    # \033[s / \033[u — save and restore cursor position so ncurses internal
    # tracking stays in sync with the actual terminal cursor after our write.
    sys.stdout.buffer.write(b'\033[s' + delete + cursor_pos + data + b'\033[u')
    sys.stdout.buffer.flush()
