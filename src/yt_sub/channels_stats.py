import curses
import json
from typing import Any, Callable, Dict, List, Optional

from .database import Database
from .models import ChannelStatRow
from . import paths

CONFIG_PATH = str(paths.config_file())

# Sentinel returned by run() when the user presses q (quit the whole app).
QUIT_SENTINEL = "__quit__"

# Fixed column widths (including one leading space of padding).
_W_NUM = 4       # row number
_W_AVG = 8       # Avg/mo
_W_NSHORT = 14   # Non-short/mo
_W_MED = 11      # Median dur

_COL_HEADERS = ["Channel", "Avg/mo", "Non-short/mo", "Median dur"]

_SORT_KEYS: List[Callable[[ChannelStatRow], Any]] = [
    lambda r: r.channel_title.lower(),
    lambda r: r.avg_per_month,
    lambda r: r.avg_non_short_per_month,
    lambda r: r.median_duration_seconds if r.median_duration_seconds is not None else -1.0,
]


def _format_median(seconds: Optional[float]) -> str:
    """Format a duration in seconds as right-justified ``M:SS`` / ``H:MM:SS`` (7 chars).

    Args:
        seconds: Duration in seconds, or ``None`` for missing data.

    Returns:
        7-character string (e.g. ``"   8:42"`` or ``"      —"``).
    """
    if seconds is None:
        return "      —"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}".rjust(7)
    return f"{m}:{sec:02d}".rjust(7)


def _safe_addstr(
    win: "curses.window",
    y: int,
    x: int,
    text: str,
    attr: int = curses.A_NORMAL,
) -> None:
    """Write *text* to *win* at (*y*, *x*), clipping to window bounds.

    Args:
        win: Target curses window.
        y: Row (0-based).
        x: Column (0-based).
        text: String to write.
        attr: Curses attribute bitmask.
    """
    try:
        h, w = win.getmaxyx()
        if y < 0 or y >= h or x < 0 or x >= w:
            return
        win.addstr(y, x, str(text)[: w - x - 1], attr)
    except curses.error:
        pass


class ChannelsStatsView:
    """Tabular view showing per-channel video statistics.

    Columns: channel name, average videos/month (all), average non-short
    videos/month, and median duration of non-short videos.  Supports sorting
    by any column (h/l/←/→), live search (/), and vim-style navigation
    (gg, G, [n]G, [n]j, [n]k, PageUp, PageDown, zz).

    Attributes:
        db: Open database connection.
        config: Parsed application config dict (mutated in place when the user
            changes period or shorts threshold).
    """

    def __init__(self, db: Database, config: Dict[str, Any]) -> None:
        """Loads data and initialises sort state.

        Args:
            db: Open database connection.
            config: Parsed application config dict.
        """
        self.db = db
        self.config = config
        self._sort_col = 0
        self._sort_asc = True
        self._selected = 0
        self._top_line = 0
        self._rows: List[ChannelStatRow] = []
        self._input_buffer = ""
        self._last_key = 0
        self._is_searching = False
        self._search_query = ""
        self._reload_data()

    def _reload_data(self) -> None:
        """Reloads statistics from the database using current config values."""
        months = self.config.get("ui", {}).get("stats_months", 3)
        threshold = self.config.get("ui", {}).get("shorts_threshold_seconds", 90)
        self._rows = self.db.get_channels_stats_table(months, threshold)
        self._selected = min(self._selected, max(0, len(self._rows) - 1))

    def _sorted_rows(self) -> List[ChannelStatRow]:
        """Returns rows sorted by the active column and direction.

        Returns:
            Sorted copy of :attr:`_rows`.
        """
        return sorted(
            self._rows,
            key=_SORT_KEYS[self._sort_col],
            reverse=not self._sort_asc,
        )

    def _filtered_rows(self, rows: List[ChannelStatRow]) -> List[ChannelStatRow]:
        """Filters rows by the active search query (case-insensitive substring on channel name).

        Args:
            rows: Pre-sorted list to filter.

        Returns:
            Filtered list; full list when query is empty.
        """
        if not self._search_query:
            return rows
        q = self._search_query.lower()
        return [r for r in rows if q in r.channel_title.lower()]

    def run(self, stdscr: "curses.window") -> Optional[str]:
        """Runs the event loop for this view.

        Args:
            stdscr: Root curses window.

        Returns:
            - :data:`QUIT_SENTINEL` when the user presses ``q``.
            - A ``channel_id`` string when the user presses ``Enter``.
            - ``None`` when the user presses ``ESC`` or ``a`` to go back.
        """
        curses.curs_set(0)
        stdscr.timeout(-1)  # blocking — undo the 100ms timeout set by the main TUI loop
        while True:
            rows = self._filtered_rows(self._sorted_rows())
            self._draw(stdscr, rows)
            key = stdscr.getch()
            if key == -1:
                continue

            # --- Search mode ---
            if self._is_searching:
                if key in (curses.KEY_BACKSPACE, 127, 8):
                    self._search_query = self._search_query[:-1]
                elif key == 27:  # ESC — exit search and clear filter
                    self._is_searching = False
                    self._search_query = ""
                elif key in (curses.KEY_ENTER, 10, 13):  # Enter — exit search, keep filter
                    self._is_searching = False
                elif key == curses.KEY_DOWN:
                    self._selected = min(self._selected + 1, max(0, len(rows) - 1))
                    self._ensure_visible(stdscr)
                elif key == curses.KEY_UP:
                    self._selected = max(self._selected - 1, 0)
                    self._ensure_visible(stdscr)
                elif 32 <= key <= 126:
                    self._search_query += chr(key)
                self._last_key = key
                continue

            # --- Digit buffering for numeric prefix ---
            if ord("0") <= key <= ord("9"):
                self._input_buffer += chr(key)
                self._last_key = key
                continue

            had_prefix = bool(self._input_buffer)
            count = int(self._input_buffer) if had_prefix else 1
            self._input_buffer = ""

            # --- Key dispatch ---
            if key == ord("q"):
                return QUIT_SENTINEL

            elif key == 27:  # ESC — clear filter if active, else go back
                if self._search_query:
                    self._search_query = ""
                else:
                    return None

            elif key == ord("a"):
                return None

            elif key in (curses.KEY_ENTER, 10, 13):
                if rows:
                    return rows[self._selected].channel_id
                return None

            elif key in (curses.KEY_DOWN, ord("j")):
                self._selected = min(self._selected + count, max(0, len(rows) - 1))
                self._ensure_visible(stdscr)

            elif key in (curses.KEY_UP, ord("k")):
                self._selected = max(self._selected - count, 0)
                self._ensure_visible(stdscr)

            elif key == ord("g"):
                if self._last_key == ord("g"):
                    self._selected = 0
                    self._top_line = 0

            elif key == ord("G"):
                if had_prefix:
                    self._selected = max(0, min(count - 1, len(rows) - 1))
                else:
                    self._selected = max(0, len(rows) - 1)
                self._ensure_visible(stdscr)

            elif key == ord("z"):
                if self._last_key == ord("z"):
                    self._center_view(stdscr)
                else:
                    self._last_key = key
                    continue

            elif key in (curses.KEY_PPAGE, 2):  # PageUp / Ctrl+b
                sh, _ = stdscr.getmaxyx()
                page = max(1, sh - 3)
                self._selected = max(0, self._selected - page)
                self._ensure_visible(stdscr)

            elif key in (curses.KEY_NPAGE, 6):  # PageDown / Ctrl+f
                sh, _ = stdscr.getmaxyx()
                page = max(1, sh - 3)
                self._selected = min(max(0, len(rows) - 1), self._selected + page)
                self._ensure_visible(stdscr)

            elif key in (ord("h"), curses.KEY_LEFT):
                self._change_sort_col(-1)

            elif key in (ord("l"), curses.KEY_RIGHT):
                self._change_sort_col(1)

            elif key == ord(" "):
                self._sort_asc = not self._sort_asc

            elif key == ord("m"):
                self._prompt_months(stdscr)

            elif key == ord("S"):
                self._prompt_shorts_threshold(stdscr)

            elif key == ord("/"):
                self._is_searching = True
                self._search_query = ""

            self._last_key = key

    def _change_sort_col(self, direction: int) -> None:
        """Changes the active sort column left or right, toggling direction on same column.

        Args:
            direction: +1 for next column, -1 for previous column.
        """
        new_col = (self._sort_col + direction) % 4
        if new_col == self._sort_col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = new_col
            self._sort_asc = True
        self._selected = 0
        self._top_line = 0
        self._input_buffer = ""
        self._search_query = ""
        self._is_searching = False

    def _ensure_visible(self, stdscr: "curses.window") -> None:
        """Adjusts :attr:`_top_line` so the selected row stays on screen.

        Args:
            stdscr: Root curses window (used to read terminal height).
        """
        sh, _ = stdscr.getmaxyx()
        visible = sh - 3  # header line + separator + status bar
        if self._selected < self._top_line:
            self._top_line = self._selected
        elif self._selected >= self._top_line + visible:
            self._top_line = self._selected - visible + 1

    def _center_view(self, stdscr: "curses.window") -> None:
        """Centers :attr:`_top_line` so the selected row appears mid-screen.

        Args:
            stdscr: Root curses window.
        """
        sh, _ = stdscr.getmaxyx()
        visible = sh - 3
        self._top_line = max(0, self._selected - visible // 2)

    def _chan_w(self, sw: int) -> int:
        """Computes the channel-name column width for a given screen width.

        Args:
            sw: Total screen width in columns.

        Returns:
            Width in columns (at least 10).
        """
        return max(10, sw - _W_NUM - _W_AVG - _W_NSHORT - _W_MED)

    def _draw(self, stdscr: "curses.window", rows: List[ChannelStatRow]) -> None:
        """Renders the full view: header, separator, data rows, status bar.

        Args:
            stdscr: Root curses window.
            rows: Pre-sorted and pre-filtered list of rows to display.
        """
        stdscr.erase()
        sh, sw = stdscr.getmaxyx()
        chan_w = self._chan_w(sw)
        months = self.config.get("ui", {}).get("stats_months", 3)
        threshold = self.config.get("ui", {}).get("shorts_threshold_seconds", 90)

        x_num = 0
        x_chan = _W_NUM
        x_avg = x_chan + chan_w
        x_nshort = x_avg + _W_AVG
        x_med = x_nshort + _W_NSHORT

        # Header
        col_specs = [
            (_COL_HEADERS[0], x_chan, chan_w, False),   # left-aligned
            (_COL_HEADERS[1], x_avg, _W_AVG, True),
            (_COL_HEADERS[2], x_nshort, _W_NSHORT, True),
            (_COL_HEADERS[3], x_med, _W_MED, True),
        ]
        for i, (header, x, w, right_align) in enumerate(col_specs):
            indicator = ("▲" if self._sort_asc else "▼") if i == self._sort_col else " "
            label = indicator + header
            text = f"{label:>{w}}" if right_align else f"{label:<{w}}"
            _safe_addstr(stdscr, 0, x, text, curses.A_BOLD)

        # Separator
        _safe_addstr(stdscr, 1, 0, "─" * (sw - 1))

        # Data rows
        visible = sh - 3
        for screen_i in range(visible):
            row_i = self._top_line + screen_i
            y = screen_i + 2
            if row_i >= len(rows):
                break
            row = rows[row_i]
            attr = curses.A_REVERSE if row_i == self._selected else curses.A_NORMAL

            _safe_addstr(stdscr, y, 0, " " * (sw - 1), attr)
            _safe_addstr(stdscr, y, x_num, f"{row_i + 1:>{_W_NUM - 1}} ", attr)
            _safe_addstr(stdscr, y, x_chan, row.channel_title[: chan_w - 1], attr)
            _safe_addstr(
                stdscr, y, x_avg,
                f"{row.avg_per_month:.1f}".rjust(_W_AVG - 1).rjust(_W_AVG),
                attr,
            )
            _safe_addstr(
                stdscr, y, x_nshort,
                f"{row.avg_non_short_per_month:.1f}".rjust(_W_NSHORT - 1).rjust(_W_NSHORT),
                attr,
            )
            _safe_addstr(
                stdscr, y, x_med,
                _format_median(row.median_duration_seconds).rjust(_W_MED),
                attr,
            )

        # Status bar
        _safe_addstr(stdscr, sh - 1, 0, " " * (sw - 1), curses.A_REVERSE)
        if self._is_searching:
            status = f" SEARCH: {self._search_query}_"
        else:
            status = (
                f" [a/ESC] back  [m] period: {months}mo"
                f"  [S] shorts: {threshold}s  [h/l/←/→] sort  [spc] reverse  [/] search  [Enter] filter"
            )
        _safe_addstr(stdscr, sh - 1, 0, status, curses.A_REVERSE)

        stdscr.refresh()

    def _prompt_int(
        self,
        stdscr: "curses.window",
        prompt: str,
        min_val: int,
        max_val: int,
    ) -> Optional[int]:
        """Shows an inline status-bar prompt and returns a validated integer.

        Args:
            stdscr: Root curses window.
            prompt: Label displayed before the input field.
            min_val: Minimum accepted value (inclusive).
            max_val: Maximum accepted value (inclusive).

        Returns:
            Parsed integer within ``[min_val, max_val]``, or ``None`` on
            cancel or invalid input.
        """
        sh, sw = stdscr.getmaxyx()
        _safe_addstr(stdscr, sh - 1, 0, " " * (sw - 1), curses.A_REVERSE)
        _safe_addstr(stdscr, sh - 1, 0, prompt, curses.A_REVERSE)
        stdscr.refresh()
        curses.echo()
        curses.curs_set(1)
        result = None
        try:
            input_win = curses.newwin(1, max(1, sw - len(prompt) - 1), sh - 1, len(prompt))
            input_win.attron(curses.A_REVERSE)
            val_str = input_win.getstr().decode("utf-8").strip()
            if val_str.isdigit() and min_val <= int(val_str) <= max_val:
                result = int(val_str)
        except Exception:
            pass
        finally:
            curses.noecho()
            curses.curs_set(0)
        return result

    def _save_config(self) -> None:
        """Persists the current config dict to :data:`CONFIG_PATH`."""
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(self.config, f, indent=4)
        except IOError:
            pass

    def _prompt_months(self, stdscr: "curses.window") -> None:
        """Prompts for a new statistics period and reloads data.

        Args:
            stdscr: Root curses window.
        """
        val = self._prompt_int(stdscr, "Stats period (months, 1-24): ", 1, 24)
        if val is not None:
            self.config.setdefault("ui", {})["stats_months"] = val
            self._save_config()
            self._reload_data()

    def _prompt_shorts_threshold(self, stdscr: "curses.window") -> None:
        """Prompts for a new Shorts threshold and reloads data.

        Args:
            stdscr: Root curses window.
        """
        val = self._prompt_int(stdscr, "Shorts threshold (seconds): ", 1, 3600)
        if val is not None:
            self.config.setdefault("ui", {})["shorts_threshold_seconds"] = val
            self._save_config()
            self._reload_data()
