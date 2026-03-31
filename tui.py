import curses
import subprocess
import textwrap
import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from models import Video

CONFIG_PATH = "config.json"

class YouTubeTUI:
    """A dual-pane terminal interface with customizable pastel colors and navigation."""
    def __init__(self, videos: List[Video]):
        self.videos = videos
        self.selected_index = 0
        self.top_line = 0
        self.show_shorts = True
        self.filter_channel_id = None
        self.filter_query = ""
        self.config = self._load_config()
        self.display_items = self._get_display_list()
        self.input_buffer = ""
        self.show_help = False

    def _load_config(self) -> Dict[str, Any]:
        """Loads TUI configuration from file."""
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

    def _init_colors(self):
        """Initializes curses color pairs based on config."""
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
        
        # Selected pairs
        curses.init_pair(12, c["dot"], bg)
        curses.init_pair(13, c["duration"], bg)
        curses.init_pair(14, c["channel"], bg)
        curses.init_pair(15, c["title"], bg)

    def _get_display_list(self) -> List:
        """Processes videos into a list of display items with headers and filters."""
        items = []
        current_date = None
        threshold = self.config["ui"].get("shorts_threshold_seconds", 90)
        
        filtered_videos = []
        q = self.filter_query.lower()
        for i, video in enumerate(self.videos):
            # Apply shorts filter
            if not self.show_shorts and video.duration_seconds < threshold:
                continue
            # Apply channel filter
            if self.filter_channel_id and video.channel_id != self.filter_channel_id:
                continue
            # Apply search query filter
            if q and q not in video.title.lower() and q not in video.channel_title.lower():
                continue
                
            filtered_videos.append((i, video))

        for orig_idx, video in filtered_videos:
            pub_date = datetime.strptime(video.published_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
            if pub_date != current_date:
                items.append({"type": "header", "content": pub_date})
                current_date = pub_date
            items.append({"type": "video", "content": video, "original_index": orig_idx})
        return items

    def _safe_addstr(self, win, y, x, text, attr=curses.A_NORMAL):
        """Safely adds a string to a window, handling boundaries."""
        try:
            h, w = win.getmaxyx()
            if y < 0 or y >= h or x < 0 or x >= w:
                return
            available = w - x
            win.addstr(y, x, str(text)[:available-1], attr)
        except curses.error:
            pass

    def _play_video(self, video: Video):
        """Plays the selected video in mpv."""
        curses.def_shell_mode()
        subprocess.run(
            ["mpv", "--autofit-larger=90%x90%", video.url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        curses.reset_shell_mode()

    def _copy_to_clipboard(self, text: str):
        """Copies text to clipboard using xclip or wl-copy."""
        # Try xclip (X11)
        try:
            process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            process.communicate(input=text.encode('utf-8'))
            if process.returncode == 0: return
        except FileNotFoundError: pass

        # Try wl-copy (Wayland)
        try:
            process = subprocess.Popen(['wl-copy'], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            process.communicate(input=text.encode('utf-8'))
            if process.returncode == 0: return
        except FileNotFoundError: pass

    def _draw_left_pane(self, win, width, height):
        """Renders the video list pane."""
        win.clear()
        if not self.display_items:
            self._safe_addstr(win, 0, 0, "No videos match filters.", curses.A_DIM)
            win.refresh()
            return

        current_display_idx = 0
        found = False
        for idx, item in enumerate(self.display_items):
            if item["type"] == "video" and item["original_index"] == self.selected_index:
                current_display_idx = idx
                found = True
                break
        
        if not found and self.display_items:
            for idx, item in enumerate(self.display_items):
                if item["type"] == "video":
                    self.selected_index = item["original_index"]
                    current_display_idx = idx
                    break

        if current_display_idx < self.top_line:
            self.top_line = current_display_idx
            # If there's a header right above the selection, show it too
            if self.top_line > 0 and self.display_items[self.top_line - 1]["type"] == "header":
                self.top_line -= 1
        elif current_display_idx >= self.top_line + height:
            self.top_line = max(0, current_display_idx - height + 1)

        for i in range(height):
            idx = self.top_line + i
            if idx >= len(self.display_items):
                break
            
            # Draw relative line number
            rel_num = abs(idx - current_display_idx)
            num_str = f"{rel_num:2} " if rel_num != 0 else f"{idx + 1:2} "
            self._safe_addstr(win, i, 0, num_str, curses.A_DIM)
            
            item = self.display_items[idx]
            if item["type"] == "header":
                text = f"--- {item['content']} ---".center(width - 3)
                self._safe_addstr(win, i, 3, text, curses.color_pair(1))
            else:
                video = item["content"]
                is_sel = (item["original_index"] == self.selected_index)
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
                
        win.refresh()

    def _draw_right_pane(self, win, width, height):
        """Renders the video details pane."""
        win.clear()
        if not self.videos or self.selected_index >= len(self.videos) or width < 5:
            win.refresh()
            return
            
        video = self.videos[self.selected_index]
        y = 0
        
        def add_detail(label, value):
            nonlocal y
            if y < height:
                self._safe_addstr(win, y, 0, f"{label}: ", curses.color_pair(7))
                self._safe_addstr(win, y, len(label) + 2, str(value), curses.color_pair(8))
                y += 1

        self._safe_addstr(win, y, 0, video.title, curses.A_BOLD | curses.color_pair(8))
        y += 2
        
        add_detail("Channel", video.channel_title)
        add_detail("Published", video.published_at.replace('T', ' ').replace('Z', ''))
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
        win.refresh()

    def _draw_help_overlay(self, stdscr):
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
            ("d / D", "Jump 1 day down / up (supports counts)"),
            ("gg / G", "Jump to top / bottom (or [n]G to line)"),
            ("zz", "Center view on selection"),
            ("/", "Search/Filter videos"),
            ("Enter", "Play video in mpv"),
            ("y", "Copy video URL to clipboard"),
            ("s", "Toggle Shorts (filter by duration)"),
            ("b", "Toggle filter by current channel"),
            ("Ctrl+f / b", "Page down / up"),
            ("?", "Toggle this help screen"),
            ("q / ESC", "Quit")
        ]

        for i, (key, desc) in enumerate(shortcuts):
            self._safe_addstr(win, i + 2, 2, f"{key:12} : {desc}")

        self._safe_addstr(win, h - 2, (w - 22) // 2, "Press any key to close", curses.A_DIM)
        win.refresh()
        win.getch()
        self.show_help = False

    def _get_search_query(self, stdscr):
        """Opens a search prompt and returns the user input."""
        sh, sw = stdscr.getmaxyx()
        prompt = "Search: "
        
        # Clear footer and show prompt
        self._safe_addstr(stdscr, sh - 1, 0, " " * (sw - 1), curses.A_REVERSE)
        self._safe_addstr(stdscr, sh - 1, 0, prompt, curses.A_REVERSE)
        stdscr.refresh()
        
        curses.echo()
        curses.curs_set(1)
        query_win = curses.newwin(1, sw - len(prompt) - 1, sh - 1, len(prompt))
        query_win.attron(curses.A_REVERSE)
        try:
            query = query_win.getstr().decode('utf-8')
        except:
            query = ""
        curses.noecho()
        curses.curs_set(0)
        return query

    def run(self, stdscr):
        self._init_colors()
        curses.curs_set(0)
        stdscr.clear()
        
        while True:
            sh, sw = stdscr.getmaxyx()
            if sh < 5 or sw < 10:
                stdscr.addstr(0, 0, "Terminal too small")
                stdscr.refresh()
                if stdscr.getch() == ord('q'): break
                continue

            split_ratio = self.config["ui"].get("pane_split_ratio", 0.5)
            left_width = int(sw * split_ratio)
            right_width = sw - left_width - 1
            
            left_win = curses.newwin(sh - 1, left_width, 0, 0)
            right_win = curses.newwin(sh - 1, right_width, 0, left_width + 1)
            
            self._draw_left_pane(left_win, left_width, sh - 1)
            self._draw_right_pane(right_win, right_width, sh - 1)
            
            for y in range(sh - 1):
                try: stdscr.addch(y, left_width, curses.ACS_VLINE, curses.A_DIM)
                except: pass
            
            shorts_status = "Shorts: ON" if self.show_shorts else "Shorts: OFF"
            chan_filter = "Filter: OFF"
            if self.filter_channel_id:
                chan_name = "Unknown"
                if self.display_items:
                    for item in self.display_items:
                        if item["type"] == "video" and item["content"].channel_id == self.filter_channel_id:
                            chan_name = item["content"].channel_title
                            break
                chan_filter = f"Filter: {chan_name}"
            
            search_status = f" | Query: {self.filter_query}" if self.filter_query else ""
            footer = f" [q]uit | [?] help | [/] find | [y] copy | [s]horts | [b]y channel | [j/k] move | [Enter] play | {shorts_status} | {chan_filter}{search_status}"
            if self.input_buffer:
                footer += f" | :{self.input_buffer}"
            self._safe_addstr(stdscr, sh - 1, 0, footer, curses.A_REVERSE)
            stdscr.refresh()
            
            if self.show_help:
                self._draw_help_overlay(stdscr)
                continue

            key = stdscr.getch()
            page_size = max(1, sh - 2)
            
            # Handle counts
            if ord('0') <= key <= ord('9'):
                if self.input_buffer == "" and key == ord('0'):
                    # 0 is normally move to start of line in vim, but here we ignore it as count
                    pass
                else:
                    self.input_buffer += chr(key)
                    continue

            count = int(self.input_buffer) if self.input_buffer and self.input_buffer.isdigit() else 1

            if key in [ord('q'), 27]:
                break
            elif key == ord('?'):
                self.show_help = True
            elif key == ord('/'):
                self.filter_query = self._get_search_query(stdscr)
                self.display_items = self._get_display_list()
                self.input_buffer = ""
            elif key == ord('y'):
                if self.videos and self.selected_index < len(self.videos):
                    video = self.videos[self.selected_index]
                    self._copy_to_clipboard(video.url)
                self.input_buffer = ""
            elif key == ord('s'):
                self.show_shorts = not self.show_shorts
                self.display_items = self._get_display_list()
                self.input_buffer = ""
            elif key == ord('b'):
                if self.filter_channel_id:
                    self.filter_channel_id = None
                else:
                    if self.videos and self.selected_index < len(self.videos):
                        self.filter_channel_id = self.videos[self.selected_index].channel_id
                self.display_items = self._get_display_list()
                self.input_buffer = ""
            elif key in [curses.KEY_UP, ord('k')]:
                current_display_idx = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        current_display_idx = idx
                        break
                
                # Move up count times
                moves_left = count
                target_idx = current_display_idx
                while moves_left > 0 and target_idx > 0:
                    target_idx -= 1
                    if self.display_items[target_idx]["type"] == "video":
                        self.selected_index = self.display_items[target_idx]["original_index"]
                        moves_left -= 1
                self.input_buffer = ""
            elif key in [curses.KEY_DOWN, ord('j')]:
                current_display_idx = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        current_display_idx = idx
                        break
                
                # Move down count times
                moves_left = count
                target_idx = current_display_idx
                while moves_left > 0 and target_idx < len(self.display_items) - 1:
                    target_idx += 1
                    if self.display_items[target_idx]["type"] == "video":
                        self.selected_index = self.display_items[target_idx]["original_index"]
                        moves_left -= 1
                self.input_buffer = ""
            elif key == ord('d'):
                # Jump down count days
                current_display_idx = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        current_display_idx = idx
                        break
                
                days_to_jump = count
                target_idx = current_display_idx
                while days_to_jump > 0 and target_idx < len(self.display_items) - 1:
                    target_idx += 1
                    if self.display_items[target_idx]["type"] == "header":
                        days_to_jump -= 1
                
                # Find first video after or at target header
                for idx in range(target_idx, len(self.display_items)):
                    if self.display_items[idx]["type"] == "video":
                        self.selected_index = self.display_items[idx]["original_index"]
                        break
                self.input_buffer = ""
            elif key == ord('D'):
                # Jump up count days
                current_display_idx = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        current_display_idx = idx
                        break
                
                days_to_jump = count
                target_idx = current_display_idx
                
                # If we are already at the first video of a day (header is just above),
                # we need to skip the current day's header to jump to the previous one.
                if target_idx > 0 and self.display_items[target_idx - 1]["type"] == "header":
                    target_idx -= 1 # Move to current header so the loop starts looking above it
                
                while days_to_jump > 0 and target_idx > 0:
                    target_idx -= 1
                    if self.display_items[target_idx]["type"] == "header":
                        days_to_jump -= 1
                
                # Find first video after or at target header
                for idx in range(target_idx, len(self.display_items)):
                    if self.display_items[idx]["type"] == "video":
                        self.selected_index = self.display_items[idx]["original_index"]
                        break
                self.input_buffer = ""
            elif key == ord('G'):
                if self.input_buffer:
                    # Jump to line (count)
                    line_no = min(count, len(self.display_items))
                    idx = line_no - 1
                    if idx < 0: idx = 0
                    # Find nearest video
                    if self.display_items[idx]["type"] == "video":
                        self.selected_index = self.display_items[idx]["original_index"]
                    else:
                        for sub_idx in range(idx, len(self.display_items)):
                            if self.display_items[sub_idx]["type"] == "video":
                                self.selected_index = self.display_items[sub_idx]["original_index"]
                                break
                else:
                    # Jump to bottom
                    for idx in range(len(self.display_items) - 1, -1, -1):
                        if self.display_items[idx]["type"] == "video":
                            self.selected_index = self.display_items[idx]["original_index"]
                            break
                self.input_buffer = ""
            elif key == ord('g'):
                if self.input_buffer == "g":
                    # gg: Jump to top
                    for idx in range(len(self.display_items)):
                        if self.display_items[idx]["type"] == "video":
                            self.selected_index = self.display_items[idx]["original_index"]
                            break
                    self.input_buffer = ""
                else:
                    self.input_buffer = "g"
            elif key == ord('z'):
                # zz: center
                if self.input_buffer == "z":
                    current_display_idx = -1
                    for idx, item in enumerate(self.display_items):
                        if item["type"] == "video" and item["original_index"] == self.selected_index:
                            current_display_idx = idx
                            break
                    if current_display_idx != -1:
                        self.top_line = max(0, current_display_idx - (sh - 1) // 2)
                    self.input_buffer = ""
                else:
                    self.input_buffer = "z"
            elif key in [curses.KEY_PPAGE, 2]:
                current_display_idx = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        current_display_idx = idx
                        break
                target_idx = max(0, current_display_idx - page_size)
                for idx in range(target_idx, len(self.display_items)):
                    if self.display_items[idx]["type"] == "video":
                        self.selected_index = self.display_items[idx]["original_index"]
                        break
                self.input_buffer = ""
            elif key in [curses.KEY_NPAGE, 6]:
                current_display_idx = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        current_display_idx = idx
                        break
                target_idx = min(len(self.display_items) - 1, current_display_idx + page_size)
                for idx in range(target_idx, -1, -1):
                    if self.display_items[idx]["type"] == "video":
                        self.selected_index = self.display_items[idx]["original_index"]
                        break
                self.input_buffer = ""
            elif key in [ord('\n'), curses.KEY_ENTER]:
                if self.videos and self.selected_index < len(self.videos):
                    self._play_video(self.videos[self.selected_index])
                self.input_buffer = ""
            elif key == curses.KEY_RESIZE:
                stdscr.clear()
            else:
                # Any other key clears the buffer
                self.input_buffer = ""

def start_tui(videos: List[Video]):
    if not videos:
        print("No videos in database. Try refreshing first.")
        return
    os.environ.setdefault('TERM', 'xterm-256color')
    curses.wrapper(YouTubeTUI(videos).run)
