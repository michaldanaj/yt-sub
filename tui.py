import curses
import subprocess
import textwrap
import json
import os
import queue
import re
import sys
import math
import struct
import fcntl
import termios
import base64
import io
import urllib.request
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from models import Video
from database import Database

CONFIG_PATH = "config.json"
THUMB_CACHE_DIR = ".thumb_cache"

# Fallback terminal cell size used when TIOCGWINSZ returns zeroes.
# 16px tall × 8px wide matches most common terminal font defaults.
_CELL_H_PX_FALLBACK = 16
_CELL_W_PX_FALLBACK = 8

class YouTubeTUI:
    """Dual-pane terminal UI for browsing YouTube subscriptions.

    Left pane: date-grouped video list with vim-style navigation.
    Right pane: details for the selected video plus an inline thumbnail
    rendered via the Kitty terminal graphics protocol.

    Attributes:
        videos: Master list of all known videos, sorted newest-first.
        selected_id: YouTube ID of the currently highlighted video.
        display_items: Filtered and grouped items currently visible in the
            left pane; each entry is ``{"type": "header"|"video", "content": ...}``.
    """

    def __init__(self, videos: List[Video], db: Database, sync_queue: Optional[queue.Queue] = None) -> None:
        """Initialises state from the pre-loaded video list.

        Args:
            videos: Videos loaded from the database before the TUI starts.
            db: Open database connection used to persist watch-later changes.
            sync_queue: Queue from which background sync messages are read.
                Pass ``None`` to start without a sync in progress.
        """
        self.db = db
        self.videos = videos
        self.selected_id: Optional[str] = videos[0].id if videos else None
        self.top_line = 0
        self.show_shorts = True
        self.show_watch_later = False
        self.filter_channel_id = None
        self.filter_query = ""
        self.config = self._load_config()
        self.display_items = self._get_display_list()
        self.input_buffer = ""
        self.is_searching = False
        self.show_help = False
        self.sync_queue = sync_queue
        self.is_syncing = False if sync_queue is None else True
        self.sync_progress = ""
        self._thumb_kitty_cache: Dict[tuple, Any] = {}  # (video_id, cols, rows) -> bytes or None

    def _load_config(self) -> Dict[str, Any]:
        """Loads TUI configuration from :data:`CONFIG_PATH`.

        Returns:
            Parsed config dict.  Falls back to built-in defaults when the file
            is missing or contains invalid JSON.
        """
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "colors": {"header": 103, "dot": 210, "duration": 150, "channel": 117, "title": 231, "selected_bg": 238, "detail_label": 103, "detail_value": 231},
            "ui": {"pane_split_ratio": 0.5, "page_scroll_ratio": 0.8, "shorts_threshold_seconds": 90}
        }

    def _init_colors(self) -> None:
        """Initialises curses color pairs from the ``colors`` section of config."""
        curses.start_color()
        curses.use_default_colors()
        
        c = self.config["colors"]
        bg = c["selected_bg"]
        
        # Normal pairs
        curses.init_pair(1, c["header"], -1)
        curses.init_pair(2, c["dot"], -1)
        curses.init_pair(3, c["duration"], -1)
        curses.init_pair(4, c["channel"], -1)
        curses.init_pair(5, c["title"], -1)
        curses.init_pair(7, c["detail_label"], -1)
        curses.init_pair(8, c["detail_value"], -1)
        
        # Status bar separator color: define as (Default, Red)
        # so that A_REVERSE results in (Red, Default) to match the rest of the bar
        curses.init_pair(9, -1, 210) 
        
        # Selected pairs
        curses.init_pair(12, c["dot"], bg)
        curses.init_pair(13, c["duration"], bg)
        curses.init_pair(14, c["channel"], bg)
        curses.init_pair(15, c["title"], bg)

    def _get_display_list(self) -> List[Dict[str, Any]]:
        """Builds the filtered, date-grouped list of items for the left pane.

        Applies the active filters (shorts threshold, channel filter, search
        query, watch-later mode) and inserts date header entries between groups
        of videos published on different days.

        Returns:
            List of dicts, each with a ``"type"`` key (``"header"`` or
            ``"video"``) and a ``"content"`` key (date string or
            :class:`~models.Video`).
        """
        items = []
        current_date = None
        threshold = self.config["ui"].get("shorts_threshold_seconds", 90)
        
        filtered_videos = []
        q = self.filter_query.lower()
        for video in self.videos:
            # If we are in "Watch Later" mode, ONLY show watch later videos.
            if self.show_watch_later:
                if video.watch_later:
                    filtered_videos.append(video)
                continue

            # Apply normal filters
            if not self.show_shorts and video.duration_seconds < threshold:
                continue
            if self.filter_channel_id and video.channel_id != self.filter_channel_id:
                continue
            if q and q not in video.title.lower() and q not in video.channel_title.lower():
                continue

            filtered_videos.append(video)

        for video in filtered_videos:
            try:
                # Convert UTC timestamp to local time so date headers match the user's clock
                utc_dt = datetime.strptime(video.published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                pub_date = utc_dt.astimezone().strftime("%Y-%m-%d")
            except ValueError:
                pub_date = video.published_at[:10] if video.published_at else "Unknown"
            if pub_date != current_date:
                items.append({"type": "header", "content": pub_date})
                current_date = pub_date
            items.append({"type": "video", "content": video})
        return items

    def _get_selected_video(self) -> Optional[Video]:
        """Looks up the currently selected video by ID.

        Returns:
            The :class:`~models.Video` whose ``id`` matches
            :attr:`selected_id`, or ``None`` if the list is empty or the ID
            is no longer present.
        """
        if not self.selected_id:
            return None
        for v in self.videos:
            if v.id == self.selected_id:
                return v
        return None

    def _find_current_display_index(self) -> int:
        """Finds the position of the selected video in :attr:`display_items`.

        Returns:
            Zero-based index of the selected video entry, or ``-1`` if it is
            not present (e.g. filtered out).
        """
        for idx, item in enumerate(self.display_items):
            if item["type"] == "video" and item["content"].id == self.selected_id:
                return idx
        return -1

    def _reselect_nearest_visible(self, prev_selected_id: Optional[str]) -> None:
        """Keeps the selection visually anchored after the display list changes.

        Called after a filter toggle (e.g. shorts on/off) when the previously
        selected video may have been filtered out.  Walks ``self.videos``
        upwards from the previous selection (towards newer entries, the
        direction the user perceives as "above" in the pane) looking for the
        first video that still passes the active filters; falls back to the
        first one downwards if none above remains visible.

        Args:
            prev_selected_id: ID of the video that was selected before the
                filter change.  ``None`` means there was no prior selection,
                in which case nothing is done.
        """
        if not prev_selected_id or self._find_current_display_index() != -1:
            return
        visible_ids = {item["content"].id for item in self.display_items
                       if item["type"] == "video"}
        if not visible_ids:
            return
        prev_idx = next((i for i, v in enumerate(self.videos)
                         if v.id == prev_selected_id), -1)
        if prev_idx == -1:
            return
        for offset in range(1, len(self.videos)):
            up = prev_idx - offset
            if up >= 0 and self.videos[up].id in visible_ids:
                self.selected_id = self.videos[up].id
                return
            down = prev_idx + offset
            if down < len(self.videos) and self.videos[down].id in visible_ids:
                self.selected_id = self.videos[down].id
                return

    def _safe_addstr(self, win: "curses.window", y: int, x: int, text: str, attr: int = curses.A_NORMAL) -> None:
        """Writes a string to a curses window, clipping to window boundaries.

        Silently ignores writes that fall outside the window or that curses
        raises an error for (e.g. writing to the last cell of the last line).

        Args:
            win: Target curses window.
            y: Row coordinate (0-based).
            x: Column coordinate (0-based).
            text: String to write.
            attr: Curses attribute bitmask (color pair, bold, etc.).
        """
        try:
            h, w = win.getmaxyx()
            if y < 0 or y >= h or x < 0 or x >= w:
                return
            available = w - x
            win.addstr(y, x, str(text)[:available-1], attr)
        except curses.error:
            pass

    def _play_video(self, video: Video) -> None:
        """Launches mpv for the given video and blocks until playback ends.

        Saves and restores the terminal shell mode so that curses can redraw
        correctly after mpv exits.

        Args:
            video: Video to play.
        """
        curses.def_shell_mode()
        subprocess.run(
            ["mpv", "--autofit-larger=90%x90%", video.url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        curses.reset_shell_mode()

    def _copy_to_clipboard(self, text: str) -> None:
        """Copies text to the system clipboard using xclip or wl-copy.

        Tries ``xclip`` first (X11), then ``wl-copy`` (Wayland).  Silently
        does nothing if neither tool is installed.

        Args:
            text: String to place on the clipboard.
        """
        try:
            process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            process.communicate(input=text.encode('utf-8'))
            if process.returncode == 0: return
        except FileNotFoundError: pass

        try:
            process = subprocess.Popen(['wl-copy'], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            process.communicate(input=text.encode('utf-8'))
            if process.returncode == 0: return
        except FileNotFoundError: pass

    def _open_in_browser(self, video: Video) -> None:
        """Opens the video URL in the system default browser via ``xdg-open``.

        Args:
            video: Video whose URL should be opened.
        """
        try:
            subprocess.run(["xdg-open", video.url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

    def _set_shorts_threshold(self, stdscr: "curses.window") -> None:
        """Prompts the user to enter a new Shorts duration threshold.

        Reads an integer from an inline input field in the status bar, updates
        :attr:`config` and persists the new value to :data:`CONFIG_PATH`.

        Args:
            stdscr: Root curses window used for the prompt.
        """
        sh, sw = stdscr.getmaxyx()
        prompt = "Shorts threshold (seconds): "
        
        self._safe_addstr(stdscr, sh - 1, 0, " " * (sw - 1), curses.A_REVERSE)
        self._safe_addstr(stdscr, sh - 1, 0, prompt, curses.A_REVERSE)
        stdscr.refresh()
        
        curses.echo()
        curses.curs_set(1)
        query_win = curses.newwin(1, sw - len(prompt) - 1, sh - 1, len(prompt))
        query_win.attron(curses.A_REVERSE)
        try:
            val = query_win.getstr().decode('utf-8')
            if val.isdigit():
                self.config["ui"]["shorts_threshold_seconds"] = int(val)
                with open(CONFIG_PATH, "w") as f:
                    json.dump(self.config, f, indent=4)
        except:
            pass
        curses.noecho()
        curses.curs_set(0)

    def _show_message(self, stdscr: "curses.window", message: str, seconds: float = 1) -> None:
        """Displays a centred message box for the given duration.

        Uses ``noutrefresh`` / ``doupdate`` so the box is composited onto
        the existing screen without a full redraw.

        Args:
            stdscr: Root curses window.
            message: Text to display inside the box.
            seconds: How long to show the message before returning.
        """
        sh, sw = stdscr.getmaxyx()
        h, w = 3, len(message) + 4
        y, x = (sh - h) // 2, (sw - w) // 2
        
        msg_win = curses.newwin(h, w, y, x)
        msg_win.box()
        self._safe_addstr(msg_win, 1, 2, message, curses.A_BOLD)
        msg_win.noutrefresh()
        curses.doupdate()
        curses.napms(int(seconds * 1000))

    def _get_cell_px(self) -> Tuple[int, int]:
        """Queries the terminal for the pixel size of a single character cell.

        Uses the ``TIOCGWINSZ`` ioctl to read pixel dimensions reported by the
        terminal emulator.

        Returns:
            ``(cell_height_px, cell_width_px)``.  Falls back to
            ``(_CELL_H_PX_FALLBACK, _CELL_W_PX_FALLBACK)`` when the ioctl
            fails or returns zeroes.
        """
        try:
            buf = struct.pack('HHHH', 0, 0, 0, 0)
            res = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, buf)
            rows, cols, xpx, ypx = struct.unpack('HHHH', res)
            if rows > 0 and cols > 0 and xpx > 0 and ypx > 0:
                return ypx // rows, xpx // cols
        except Exception:
            pass
        return _CELL_H_PX_FALLBACK, _CELL_W_PX_FALLBACK

    def _kitty_encode(self, video: Video, cols: int, rows: int,
                      cell_w: int, cell_h: int) -> Optional[bytes]:
        """Encodes a video thumbnail as Kitty terminal graphics protocol bytes.

        Downloads ``maxresdefault.jpg`` (1280×720) if not already cached,
        resizes it to ``cols * cell_w`` px wide (preserving aspect ratio) and
        encodes it as a sequence of APC escape sequences suitable for the Kitty
        graphics protocol.  Results are cached in :attr:`_thumb_kitty_cache`
        keyed by ``(video_id, cols, rows, cell_w, cell_h)``.

        The image is transmitted with explicit ``c=`` / ``r=`` cell-size
        parameters so the terminal clips the image to exactly the reserved
        area, preventing overflow when navigating between items.

        Args:
            video: Video whose thumbnail should be encoded.
            cols: Target width in terminal columns.
            rows: Target height in terminal rows.
            cell_w: Width of a single terminal cell in pixels.
            cell_h: Height of a single terminal cell in pixels.

        Returns:
            Raw bytes containing the Kitty APC sequences, or ``None`` if the
            thumbnail cannot be loaded or PIL is not available.
        """
        cache_key = (video.id, cols, rows, cell_w, cell_h)
        if cache_key in self._thumb_kitty_cache:
            return self._thumb_kitty_cache[cache_key]

        if cols < 4:
            self._thumb_kitty_cache[cache_key] = None
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

            self._thumb_kitty_cache[cache_key] = result
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

    def _draw_thumbnail_kitty(self, abs_row: int, abs_col: int, cols: int, rows: int,
                              video: Video, cell_w: int, cell_h: int) -> None:
        """Renders the thumbnail at an absolute terminal position using the Kitty protocol.

        First deletes any existing Kitty image (``a=d,d=A``), then moves the
        cursor and sends the encoded image bytes.  The cursor position is saved
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
        """
        delete = b'\033_Ga=d,d=A\033\\'
        data = self._kitty_encode(video, cols, rows, cell_w, cell_h)
        if not data:
            sys.stdout.buffer.write(delete)
            sys.stdout.buffer.flush()
            return
        cursor_pos = f'\033[{abs_row + 1};{abs_col + 1}H'.encode('ascii')
        # \033[s / \033[u — save and restore cursor position so ncurses internal
        # tracking stays in sync with the actual terminal cursor after our write.
        sys.stdout.buffer.write(b'\033[s' + delete + cursor_pos + data + b'\033[u')
        sys.stdout.buffer.flush()

    def _draw_left_pane(self, win: "curses.window", width: int, height: int) -> None:
        """Renders the video list in the left pane.

        Draws relative line numbers (vim-style), date headers and per-video
        rows with duration, channel name and title.  Scrolls automatically to
        keep the selected item visible.

        Args:
            win: Curses window for the left pane.
            width: Usable column count.
            height: Usable row count.
        """
        win.erase()
        if not self.display_items:
            self._safe_addstr(win, 0, 0, "No videos match filters.", curses.A_DIM)
            return

        current_display_idx = self._find_current_display_index()
        found = current_display_idx != -1

        if not found and self.display_items:
            for idx, item in enumerate(self.display_items):
                if item["type"] == "video":
                    self.selected_id = item["content"].id
                    current_display_idx = idx
                    break

        if current_display_idx < self.top_line:
            self.top_line = current_display_idx
            if self.top_line > 0 and self.display_items[self.top_line - 1]["type"] == "header":
                self.top_line -= 1
        elif current_display_idx >= self.top_line + height:
            self.top_line = max(0, current_display_idx - height + 1)

        for i in range(height):
            idx = self.top_line + i
            if idx >= len(self.display_items):
                break
            
            rel_num = abs(idx - current_display_idx)
            num_str = f"{rel_num:2} " if rel_num != 0 else f"{idx + 1:2} "
            self._safe_addstr(win, i, 0, num_str, curses.A_DIM)
            
            item = self.display_items[idx]
            if item["type"] == "header":
                text = f"--- {item['content']} ---".center(width - 3)
                self._safe_addstr(win, i, 3, text, curses.color_pair(1))
            else:
                video = item["content"]
                is_sel = (video.id == self.selected_id)
                p = lambda base: curses.color_pair(base + 10 if is_sel else base)
                
                x = 3
                dot_str = "• " if is_sel else "  "
                self._safe_addstr(win, i, x, dot_str, p(2))
                x += len(dot_str)
                
                dur_str = f"[{video.duration}] "
                self._safe_addstr(win, i, x, dur_str, p(3))
                x += len(dur_str)
                
                chan_str = f"{video.channel_title} "
                self._safe_addstr(win, i, x, chan_str, p(4))
                x += len(chan_str)
                
                title_str = f"- {video.title}"
                if is_sel:
                    self._safe_addstr(win, i, x, " " * (width - x), p(5))
                self._safe_addstr(win, i, x, title_str, p(5))
                
    def _draw_right_pane(self, win: "curses.window", width: int, height: int, reserved_rows: int = 0) -> None:
        """Renders the video detail view in the right pane.

        Shows the title, channel, publication date, duration, view/like counts
        and the full description.  The bottom ``reserved_rows`` rows are left
        blank for the Kitty thumbnail.

        Args:
            win: Curses window for the right pane.
            width: Usable column count.
            height: Total row count of the pane.
            reserved_rows: Number of rows to leave blank at the bottom.
        """
        win.erase()
        video = self._get_selected_video()
        if video is None or width < 5:
            return
        height = height - reserved_rows
        if height < 1:
            return
        y = 0
        
        def add_detail(label, value):
            nonlocal y
            if y < height:
                self._safe_addstr(win, y, 0, f"{label}: ", curses.color_pair(7))
                self._safe_addstr(win, y, len(label) + 2, str(value), curses.color_pair(8))
                y += 1

        title_lines = textwrap.wrap(video.title, width)
        for line in title_lines:
            if y < height:
                self._safe_addstr(win, y, 0, line, curses.A_BOLD | curses.color_pair(8))
                y += 1
        y += 1
        
        add_detail("Channel", video.channel_title)
        def fmt_local(utc_str: str) -> str:
            try:
                utc_dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                return utc_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return utc_str.replace('T', ' ').replace('Z', '')

        add_detail("Published", fmt_local(video.published_at))
        if video.last_synced:
            add_detail("Synced", fmt_local(video.last_synced))
        add_detail("Duration", video.duration.strip())
        add_detail("Views", f"{video.view_count:,}" if video.view_count is not None else "N/A")
        add_detail("Likes", f"{video.like_count:,}" if video.like_count is not None else "N/A")
        
        y += 1
        if y < height:
            self._safe_addstr(win, y, 0, "-" * (width - 1), curses.A_DIM)
            y += 1
        
        if video.description:
            lines = video.description.splitlines()
            for line in lines:
                if y >= height: break
                if not line.strip():
                    y += 1
                    continue
                wrapped = textwrap.wrap(line, max(1, width - 2))
                for w_line in wrapped:
                    if y < height:
                        self._safe_addstr(win, y, 0, w_line, curses.color_pair(8))
                        y += 1

    def _draw_help_overlay(self, stdscr: "curses.window") -> None:
        """Renders a centred help overlay listing all keyboard shortcuts.

        Blocks until the user presses any key, then sets :attr:`show_help` to
        ``False``.

        Args:
            stdscr: Root curses window.
        """
        """Renders a help overlay in the center of the screen."""
        sh, sw = stdscr.getmaxyx()
        h, w = 19, 60
        y, x = (sh - h) // 2, (sw - w) // 2

        win = curses.newwin(h, w, y, x)
        win.box()
        win.attron(curses.A_BOLD)
        self._safe_addstr(win, 0, (w - 6) // 2, " HELP ")
        win.attroff(curses.A_BOLD)

        shortcuts = [
            ("j/k/arrows", "Move up/down (supports counts, e.g. 5j)"),
            ("J / K", "Jump 1 day down / up (supports counts)"),
            ("gg / G", "Jump to top / bottom (or [n]G to line)"),
            ("zz", "Center view on selection"),
            ("/", "Search/Filter videos"),
            ("Enter", "Play video in mpv"),
            ("o", "Open in browser"),
            ("l", "Add to Watch Later list"),
            ("L", "Toggle Watch Later list view"),
            ("d", "Remove from Watch Later list"),
            ("y", "Yank (copy) video URL to clipboard"),
            ("s", "Toggle Shorts visibility"),
            ("S", "Set Shorts threshold"),
            ("b", "Toggle filter by current channel"),
            ("Ctrl+f / b", "Page down / up"),
            ("?", "Toggle this help screen"),
            ("ESC", "Return to main list / Clear all filters"),
            ("q", "Quit")
        ]

        for i, (key, desc) in enumerate(shortcuts):
            self._safe_addstr(win, i + 2, 2, f"{key:12} : {desc}")

        self._safe_addstr(win, h - 2, (w - 22) // 2, "Press any key to close", curses.A_DIM)
        win.refresh()
        win.getch()
        self.show_help = False

    def _poll_sync_queue(self, stdscr: "curses.window") -> bool:
        """Drains all pending messages from the sync queue and applies them.

        Handles three message types posted by :func:`~main.background_sync`:

        - ``"progress"``: updates :attr:`sync_progress`.
        - ``"videos"``: merges new videos into :attr:`videos`, preserving
          watch-later flags, and re-sorts by publication date.
        - ``"done"``: sets :attr:`is_syncing` to ``False``.

        Args:
            stdscr: Root curses window; passed to :meth:`_show_message` when
                new videos arrive.

        Returns:
            ``"full"`` if the video list changed and a full redraw
            (including thumbnail) is needed, ``"status"`` if only the
            status bar text changed, or ``None`` if there is nothing to
            redraw.
        """
        if not self.sync_queue:
            return None
        redraw_level = None  # None < "status" < "full"
        try:
            while True:
                msg = self.sync_queue.get_nowait()
                if not isinstance(msg, dict):
                    continue
                mtype = msg.get("type")
                if mtype == "done":
                    self.is_syncing = False
                    self.sync_progress = "Complete"
                    if redraw_level is None:
                        redraw_level = "status"
                elif mtype == "progress":
                    self.sync_progress = msg.get("message", "")
                    if redraw_level is None:
                        redraw_level = "status"
                elif mtype == "videos":
                    new_batch = msg.get("data", [])
                    if new_batch:
                        sel_vid_id = self.selected_id

                        # Merge and deduplicate by ID, preserving watch_later status
                        video_dict = {v.id: v for v in self.videos}
                        for v in new_batch:
                            if v.id in video_dict:
                                v.watch_later = video_dict[v.id].watch_later
                            video_dict[v.id] = v  # Update with new data (metadata, duration, etc)

                        self.videos = sorted(video_dict.values(), key=lambda x: x.published_at, reverse=True)

                        # Restore selection by ID (no index arithmetic needed)
                        if sel_vid_id and any(v.id == sel_vid_id for v in self.videos):
                            self.selected_id = sel_vid_id
                        elif self.videos:
                            self.selected_id = self.videos[0].id

                        self.display_items = self._get_display_list()
                        self._show_message(stdscr, f"Sync complete: {len(new_batch)} items updated/added", 2)
                        redraw_level = "full"
        except queue.Empty:
            pass
        return redraw_level

    def _draw_status_bar(self, stdscr: "curses.window", sh: int, sw: int) -> None:
        """Renders the bottom status bar with key hints and active filter state.

        In search mode the bar shows the live query instead of the normal
        shortcuts.  Segments are separated by ``|`` drawn in a contrasting
        color.  The bar is clipped automatically when the terminal is too
        narrow to fit all segments.

        Args:
            stdscr: Root curses window.
            sh: Terminal height in rows.
            sw: Terminal width in columns.
        """
        wl_count = sum(1 for v in self.videos if v.watch_later)
        threshold = self.config['ui'].get('shorts_threshold_seconds', 90)
        wl_label = "IST" if self.show_watch_later else "ist"
        wl_part = f"[l]ater [L]{wl_label} ({wl_count})"
        shorts_label = "HORTS" if not self.show_shorts else "horts"
        shorts_part = f"[s]{shorts_label} thre[S]hold ({threshold}s)"

        chan_filter = "Filter: OFF"
        if self.filter_channel_id:
            chan_name = "Unknown"
            for item in self.display_items:
                if item["type"] == "video" and item["content"].channel_id == self.filter_channel_id:
                    chan_name = item["content"].channel_title
                    break
            chan_filter = f"Filter: {chan_name}"

        search_status = f" | Query: {self.filter_query}" if self.filter_query else ""

        x_footer = 1

        def seg(text, attr=curses.A_REVERSE):
            nonlocal x_footer
            if x_footer >= sw:
                return
            self._safe_addstr(stdscr, sh - 1, x_footer, text, attr)
            x_footer += len(text)

        def sep():
            seg("|", curses.color_pair(9) | curses.A_REVERSE)

        stdscr.move(sh - 1, 0)
        stdscr.clrtoeol()

        if self.is_searching:
            seg(f" SEARCH: {self.filter_query}_ ", curses.A_REVERSE | curses.A_BOLD)
            sep()
        else:
            seg(f"[q]uit "); sep()
            seg(f" [?] help "); sep()
            seg(f" [/] find "); sep()
            seg(f" [y]ank "); sep()
            seg(f" [o]pen "); sep()
            seg(f" {wl_part} "); sep()
            seg(f" [d]el "); sep()
            seg(f" {shorts_part} "); sep()
            seg(f" [b]y channel "); sep()
            seg(f" {chan_filter}{search_status}")

        if self.is_syncing:
            sep()
            seg(f" [SYNC: {self.sync_progress}]")

        if self.input_buffer:
            sep()
            seg(f" :{self.input_buffer}")

    def _handle_key(self, key: int, count: int, stdscr: "curses.window") -> bool:
        """Dispatches a single keypress to the appropriate action.

        Supports vim-style navigation (``j``/``k``/``J``/``K``/``gg``/``G``/
        ``zz``/``Ctrl-f``/``Ctrl-b``), playback (``Enter``), clipboard
        (``y``), browser (``o``), watch-later management (``l``/``L``/``d``),
        filter toggles (``s``/``S``/``b``/``/``/``ESC``) and quit (``q``).

        Numeric prefixes accumulated in :attr:`input_buffer` are consumed as
        *count* before this method is called.

        Args:
            key: Curses key code as returned by ``getch()``.
            count: Numeric prefix (1 when no prefix was typed).
            stdscr: Root curses window; passed to action helpers that need it.

        Returns:
            ``True`` if the application should exit, ``False`` otherwise.
        """
        if key == ord('q'):
            return True
        elif key == 27:  # ESC
            self.show_watch_later = False
            self.filter_channel_id = None
            self.filter_query = ""
            self.input_buffer = ""
            self.display_items = self._get_display_list()
        elif key == ord('?'):
            self.show_help = True
        elif key == ord('/'):
            self.is_searching = True
            self.input_buffer = ""
        elif key == ord('y'):
            v = self._get_selected_video()
            if v: self._copy_to_clipboard(v.url)
            self.input_buffer = ""
        elif key == ord('o'):
            v = self._get_selected_video()
            if v: self._open_in_browser(v)
            self.input_buffer = ""
        elif key == ord('l'):
            v = self._get_selected_video()
            if v:
                v.watch_later = True
                self.db.update_watch_later(v.id, True)
                self._show_message(stdscr, f"Added to Watch Later: {v.title[:30]}...")
                self.display_items = self._get_display_list()
            self.input_buffer = ""
        elif key == ord('L'):
            prev_id = self.selected_id
            self.show_watch_later = not self.show_watch_later
            self.display_items = self._get_display_list()
            if self.show_watch_later:
                video_count = sum(1 for v in self.videos if v.watch_later)
                if not any(item["type"] == "video" for item in self.display_items):
                    self._show_message(stdscr, f"Watch Later list is empty (Total: {video_count})")
            self._reselect_nearest_visible(prev_id)
            self.input_buffer = ""
        elif key == ord('d'):
            v = self._get_selected_video()
            if v and v.watch_later:
                prev_id = self.selected_id
                v.watch_later = False
                self.db.update_watch_later(v.id, False)
                self._show_message(stdscr, "Removed from Watch Later")
                self.display_items = self._get_display_list()
                self._reselect_nearest_visible(prev_id)
            self.input_buffer = ""
        elif key == ord('s'):
            prev_id = self.selected_id
            self.show_shorts = not self.show_shorts
            self.display_items = self._get_display_list()
            self._reselect_nearest_visible(prev_id)
            self.input_buffer = ""
        elif key == ord('S'):
            prev_id = self.selected_id
            self._set_shorts_threshold(stdscr)
            self.display_items = self._get_display_list()
            self._reselect_nearest_visible(prev_id)
            self.input_buffer = ""
        elif key == ord('b'):
            prev_id = self.selected_id
            if self.filter_channel_id:
                self.filter_channel_id = None
            else:
                v = self._get_selected_video()
                if v: self.filter_channel_id = v.channel_id
            self.display_items = self._get_display_list()
            self._reselect_nearest_visible(prev_id)
            self.input_buffer = ""
        elif key in [curses.KEY_UP, ord('k')]:
            curr = self._find_current_display_index()
            moves = count
            target = curr
            while moves > 0 and target > 0:
                target -= 1
                if self.display_items[target]["type"] == "video":
                    self.selected_id = self.display_items[target]["content"].id
                    moves -= 1
            self.input_buffer = ""
        elif key in [curses.KEY_DOWN, ord('j')]:
            curr = self._find_current_display_index()
            moves = count
            target = curr
            while moves > 0 and target < len(self.display_items) - 1:
                target += 1
                if self.display_items[target]["type"] == "video":
                    self.selected_id = self.display_items[target]["content"].id
                    moves -= 1
            self.input_buffer = ""
        elif key == ord('J'):
            curr = self._find_current_display_index()
            days = count
            target = curr
            while days > 0 and target < len(self.display_items) - 1:
                target += 1
                if self.display_items[target]["type"] == "header": days -= 1
            # target now points at the destination header; scroll it to the top
            self.top_line = target
            for idx in range(target, len(self.display_items)):
                if self.display_items[idx]["type"] == "video":
                    self.selected_id = self.display_items[idx]["content"].id; break
            self.input_buffer = ""
        elif key == ord('K'):
            curr = self._find_current_display_index()
            days = count
            target = curr
            if target > 0 and self.display_items[target - 1]["type"] == "header": target -= 1
            while days > 0 and target > 0:
                target -= 1
                if self.display_items[target]["type"] == "header": days -= 1
            # target now points at the destination header; scroll it to the top
            self.top_line = target
            for idx in range(target, len(self.display_items)):
                if self.display_items[idx]["type"] == "video":
                    self.selected_id = self.display_items[idx]["content"].id; break
            self.input_buffer = ""
        elif key == ord('G'):
            if self.input_buffer:
                line = min(count, len(self.display_items))
                idx = max(0, line - 1)
                for sub in range(idx, len(self.display_items)):
                    if self.display_items[sub]["type"] == "video":
                        self.selected_id = self.display_items[sub]["content"].id; break
            else:
                for idx in range(len(self.display_items) - 1, -1, -1):
                    if self.display_items[idx]["type"] == "video":
                        self.selected_id = self.display_items[idx]["content"].id; break
            self.input_buffer = ""
        elif key == ord('g'):
            if self.input_buffer == "g":
                for idx in range(len(self.display_items)):
                    if self.display_items[idx]["type"] == "video":
                        self.selected_id = self.display_items[idx]["content"].id; break
                self.input_buffer = ""
            else:
                self.input_buffer = "g"
        elif key == ord('z'):
            if self.input_buffer == "z":
                curr = self._find_current_display_index()
                if curr != -1:
                    self.top_line = max(0, curr - (self._last_sh - 1) // 2)
                self.input_buffer = ""
            else:
                self.input_buffer = "z"
        elif key in [curses.KEY_PPAGE, 2]:
            curr = self._find_current_display_index()
            target = max(0, curr - max(1, self._last_sh - 2))
            for idx in range(target, len(self.display_items)):
                if self.display_items[idx]["type"] == "video":
                    self.selected_id = self.display_items[idx]["content"].id; break
            self.input_buffer = ""
        elif key in [curses.KEY_NPAGE, 6]:
            curr = self._find_current_display_index()
            target = min(len(self.display_items) - 1, curr + max(1, self._last_sh - 2))
            for idx in range(target, -1, -1):
                if self.display_items[idx]["type"] == "video":
                    self.selected_id = self.display_items[idx]["content"].id; break
            self.input_buffer = ""
        elif key in [ord('\n'), curses.KEY_ENTER]:
            v = self._get_selected_video()
            if v: self._play_video(v)
            self.input_buffer = ""
        else:
            self.input_buffer = ""
        return False

    def run(self, stdscr: "curses.window") -> None:
        """Main event loop — called by :func:`curses.wrapper`.

        Initialises colors, then repeatedly:

        1. Polls the sync queue via :meth:`_poll_sync_queue`.
        2. Redraws both panes, the status bar and the Kitty thumbnail when
           needed.
        3. Reads a keypress and dispatches it via :meth:`_handle_key`.

        The loop exits when :meth:`_handle_key` returns ``True`` (``q`` key).

        Args:
            stdscr: Root curses window provided by :func:`curses.wrapper`.
        """
        self._init_colors()
        curses.curs_set(0)
        stdscr.clear()
        self._last_sh = 24  # fallback for _handle_key before first frame

        force_redraw = True
        left_win = None
        right_win = None

        while True:
            sh, sw = stdscr.getmaxyx()
            self._last_sh = sh
            if sh < 5 or sw < 10:
                stdscr.erase()
                self._safe_addstr(stdscr, 0, 0, "Terminal too small")
                stdscr.refresh()
                if stdscr.getch() == ord('q'): break
                continue

            sync_redraw = self._poll_sync_queue(stdscr)
            needs_redraw = force_redraw or sync_redraw == "full"
            force_redraw = False

            # Status-only sync updates: just repaint the status bar, skip thumbnail
            if not needs_redraw and sync_redraw == "status" and left_win is not None:
                self._draw_status_bar(stdscr, sh, sw)
                stdscr.noutrefresh()
                curses.doupdate()

            if needs_redraw or left_win is None:
                split_ratio = self.config["ui"].get("pane_split_ratio", 0.5)
                left_width = int(sw * split_ratio)
                right_width = sw - left_width - 1

                # Thumbnail geometry using actual cell pixel size from TIOCGWINSZ.
                # Image is PIL-resized to thumb_cols * cell_w px wide (see _kitty_encode),
                # so rows = ceil(target_h_px / cell_h_px) for 16:9 source.
                thumb_cols = max(0, right_width - 1)
                _cell_h, _cell_w = self._get_cell_px()
                _target_w_px = thumb_cols * _cell_w
                _target_h_px = round(_target_w_px * 9 / 16)   # maxresdefault is 16:9
                thumb_rows = max(0, math.ceil(_target_h_px / _cell_h))
                if sh - 1 - thumb_rows < 8:
                    thumb_rows = 0

                if left_win is None:
                    left_win = curses.newwin(sh - 1, left_width, 0, 0)
                    right_win = curses.newwin(sh - 1, right_width, 0, left_width + 1)

                self._draw_left_pane(left_win, left_width, sh - 1)
                self._draw_right_pane(right_win, right_width, sh - 1, thumb_rows)

                stdscr.erase()
                for y in range(sh - 1):
                    try: stdscr.addch(y, left_width, curses.ACS_VLINE, curses.A_DIM)
                    except: pass

                self._draw_status_bar(stdscr, sh, sw)

                stdscr.noutrefresh()
                left_win.noutrefresh()
                # touchwin forces curses to rewrite all right-pane cells (including
                # the blank thumbnail rows), so doupdate() sends spaces to the terminal
                # and clears the previous Kitty image before we draw the new one.
                right_win.touchwin()
                right_win.noutrefresh()
                curses.doupdate()

                # Draw thumbnail via Kitty protocol after curses flushes to screen
                thumb_video = self._get_selected_video()
                if thumb_rows > 0 and thumb_video:
                    thumb_abs_row = sh - 1 - thumb_rows
                    _img_cols = math.ceil(_target_w_px / _cell_w)
                    _h_offset = max(0, (right_width - _img_cols) // 2)
                    thumb_abs_col = left_width + 1 + _h_offset
                    self._draw_thumbnail_kitty(thumb_abs_row, thumb_abs_col, thumb_cols, thumb_rows, thumb_video, _cell_w, _cell_h)

                if self.show_help:
                    self._draw_help_overlay(stdscr)
                    force_redraw = True
                    continue

            stdscr.timeout(100)
            key = stdscr.getch()
            if key == -1: continue

            if key == curses.KEY_RESIZE:
                left_win = None
                force_redraw = True
                continue

            force_redraw = True

            # Live search mode
            if self.is_searching:
                if key in [curses.KEY_UP, curses.KEY_DOWN]:
                    self._handle_key(key, 1, stdscr)
                elif key == 27:  # ESC — exit search and clear all filters
                    self.is_searching = False
                    self.filter_query = ""
                    self.filter_channel_id = None
                    self.show_watch_later = False
                    self.display_items = self._get_display_list()
                elif key in [ord('\n'), curses.KEY_ENTER]:  # Enter — keep filter
                    self.is_searching = False
                elif key in [curses.KEY_BACKSPACE, 127, 8]:   # Backspace
                    self.filter_query = self.filter_query[:-1]
                    self.display_items = self._get_display_list()
                elif 32 <= key <= 126:                         # Typable characters
                    self.filter_query += chr(key)
                    self.display_items = self._get_display_list()
                continue

            # Numeric prefix accumulation
            if ord('0') <= key <= ord('9'):
                if self.input_buffer == "" and key == ord('0'): pass
                else:
                    self.input_buffer += chr(key)
                    continue

            count = int(self.input_buffer) if self.input_buffer and self.input_buffer.isdigit() else 1

            if self._handle_key(key, count, stdscr):
                break

def start_tui(videos: List[Video], db: Database, sync_queue: Optional[queue.Queue] = None) -> None:
    """Launches the TUI via :func:`curses.wrapper`.

    Sets ``TERM`` and ``ESCDELAY`` environment variables if not already
    present, then hands control to :meth:`YouTubeTUI.run`.

    Args:
        videos: Pre-loaded videos to display immediately on startup.
        db: Open database connection passed through to the TUI.
        sync_queue: Queue for background sync messages; ``None`` if no sync
            is running.
    """
    if not videos: videos = []
    os.environ.setdefault('TERM', 'xterm-256color')
    os.environ.setdefault('ESCDELAY', '25')
    curses.wrapper(lambda stdscr: YouTubeTUI(videos, db, sync_queue).run(stdscr))
