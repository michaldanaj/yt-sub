"""Thumbnail download, caching and Kitty Graphics Protocol rendering.

The TUI displays a thumbnail of the selected video in the right pane.
Images are downloaded on demand (with atomic temp-file → rename to
survive interrupted writes — see ``encode_kitty``), resized to fit the
reserved cell area in PIL, and transmitted to the terminal as APC
escape sequences understood by Kitty / WezTerm / Konsole / Ghostty.

This module is intentionally state-light: callers (``YouTubeTUI``) own
the per-session encode cache and pass it in, which keeps the TUI class
in charge of its own lifecycle without making this module a stateful
singleton.
"""

from __future__ import annotations

import base64
import fcntl
import io
import os
import struct
import sys
import termios
import urllib.request
from typing import Any, Dict, Optional, Tuple

from . import paths
from .models import Video

# Fallback terminal cell size used when TIOCGWINSZ returns zeroes.
# 16px tall × 8px wide matches most common terminal font defaults.
CELL_H_PX_FALLBACK = 16
CELL_W_PX_FALLBACK = 8

THUMB_CACHE_DIR = str(paths.thumb_cache_dir())

EncodeCache = Dict[Tuple[str, int, int, int, int], Optional[bytes]]


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


def encode_kitty(video: Video, cols: int, rows: int,
                 cell_w: int, cell_h: int,
                 cache: EncodeCache) -> Optional[bytes]:
    """Encodes a video thumbnail as Kitty terminal graphics protocol bytes.

    Downloads ``maxresdefault.jpg`` (1280×720) if not already cached,
    resizes it to ``cols * cell_w`` px wide (preserving aspect ratio) and
    encodes it as a sequence of APC escape sequences. Results are cached
    in ``cache`` keyed by ``(video_id, cols, rows, cell_w, cell_h)``.

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
        thumbnail cannot be loaded or PIL is not available.
    """
    cache_key = (video.id, cols, rows, cell_w, cell_h)
    if cache_key in cache:
        return cache[cache_key]

    if cols < 4:
        cache[cache_key] = None
        return None

    os.makedirs(THUMB_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(THUMB_CACHE_DIR, f"{video.id}_max.jpg")
    url = f"https://i.ytimg.com/vi/{video.id}/maxresdefault.jpg"

    if not os.path.exists(cache_path):
        # Download to a temp file and atomically rename, so an interrupted
        # urlretrieve never leaves a truncated *_max.jpg behind that would
        # then poison every subsequent render attempt.
        tmp_path = cache_path + ".tmp"
        try:
            urllib.request.urlretrieve(url, tmp_path)
            os.replace(tmp_path, cache_path)
        except Exception:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except OSError: pass
            # fallback to stored thumbnail_url
            if not video.thumbnail_url:
                return None
            try:
                urllib.request.urlretrieve(video.thumbnail_url, tmp_path)
                os.replace(tmp_path, cache_path)
            except Exception:
                if os.path.exists(tmp_path):
                    try: os.remove(tmp_path)
                    except OSError: pass
                return None

    try:
        from PIL import Image
        img = Image.open(cache_path).convert("RGB")

        # Scale to target pixel width using actual cell dimensions
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

        cache[cache_key] = result
        return result
    except Exception:
        # The on-disk file is unusable (truncated download, decoder error).
        # Remove it so the next render attempt re-downloads instead of
        # repeatedly hitting the same broken bytes. Do NOT cache None,
        # otherwise a single bad fetch would hide the thumbnail until
        # the process restarts.
        try: os.remove(cache_path)
        except OSError: pass
        return None


def draw_kitty(abs_row: int, abs_col: int, cols: int, rows: int,
               video: Video, cell_w: int, cell_h: int,
               cache: EncodeCache) -> None:
    """Renders the thumbnail at an absolute terminal position.

    First deletes any existing Kitty image (``a=d,d=A``), then moves the
    cursor and sends the encoded image bytes. The cursor position is saved
    and restored with ``\\033[s`` / ``\\033[u`` so ncurses internal state
    stays in sync.

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
