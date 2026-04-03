import curses
import subprocess
import textwrap
import json
import os
import queue
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from models import Video
from database import Database

CONFIG_PATH = "config.json"

class YouTubeTUI:
    """A dual-pane terminal interface with customizable pastel colors and navigation."""
    def __init__(self, videos: List[Video], db: Database, sync_queue: queue.Queue = None):
        self.db = db
        self.videos = videos
        self.selected_index = 0
        self.top_line = 0
        self.show_shorts = True
        self.show_watch_later = False
        self.filter_channel_id = None
        self.filter_query = ""
        self.config = self._load_config()
        self.display_items = self._get_display_list()
        self.input_buffer = ""
        self.show_help = False
        self.sync_queue = sync_queue
        self.is_syncing = False if sync_queue is None else True
        self.sync_progress = ""

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
        
        # Status bar separator color: define as (Default, Red)
        # so that A_REVERSE results in (Red, Default) to match the rest of the bar
        curses.init_pair(9, -1, 210) 
        
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
            # If we are in "Watch Later" mode, ONLY show watch later videos.
            if self.show_watch_later:
                if video.watch_later:
                    filtered_videos.append((i, video))
                continue
            
            # Apply normal filters
            if not self.show_shorts and video.duration_seconds < threshold:
                continue
            if self.filter_channel_id and video.channel_id != self.filter_channel_id:
                continue
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

    def _open_in_browser(self, video: Video):
        """Opens the selected video in the default browser."""
        try:
            subprocess.run(["xdg-open", video.url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

    def _set_shorts_threshold(self, stdscr):
        """Prompt to set a new threshold for Shorts in seconds."""
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

    def _show_message(self, stdscr, message, seconds=1):
        """Displays a message in the center of the screen for a given duration."""
        sh, sw = stdscr.getmaxyx()
        h, w = 3, len(message) + 4
        y, x = (sh - h) // 2, (sw - w) // 2
        
        msg_win = curses.newwin(h, w, y, x)
        msg_win.box()
        self._safe_addstr(msg_win, 1, 2, message, curses.A_BOLD)
        msg_win.noutrefresh()
        curses.doupdate()
        curses.napms(int(seconds * 1000))

    def _draw_left_pane(self, win, width, height):
        """Renders the video list pane."""
        win.erase()
        if not self.display_items:
            self._safe_addstr(win, 0, 0, "No videos match filters.", curses.A_DIM)
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
                
    def _draw_right_pane(self, win, width, height):
        """Renders the video details pane."""
        win.erase()
        if not self.videos or self.selected_index >= len(self.videos) or width < 5:
            return
            
        video = self.videos[self.selected_index]
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
        add_detail("Published", video.published_at.replace('T', ' ').replace('Z', ''))
        if video.last_synced:
            add_detail("Synced", video.last_synced.replace('T', ' ').replace('Z', ''))
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

    def _get_search_query(self, stdscr):
        """Opens a search prompt and returns the user input."""
        sh, sw = stdscr.getmaxyx()
        prompt = "Search: "
        
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
        
        force_redraw = True
        left_win = None
        right_win = None
        
        while True:
            sh, sw = stdscr.getmaxyx()
            if sh < 5 or sw < 10:
                stdscr.erase()
                self._safe_addstr(stdscr, 0, 0, "Terminal too small")
                stdscr.refresh()
                if stdscr.getch() == ord('q'): break
                continue

            # Poll sync queue
            needs_redraw = force_redraw
            force_redraw = False
            if self.sync_queue:
                try:
                    while True:
                        msg = self.sync_queue.get_nowait()
                        if isinstance(msg, dict):
                            mtype = msg.get("type")
                            if mtype == "done":
                                self.is_syncing = False
                                self.sync_progress = "Complete"
                                needs_redraw = True
                            elif mtype == "progress":
                                self.sync_progress = msg.get("message", "")
                                needs_redraw = True
                            elif mtype == "videos":
                                new_batch = msg.get("data", [])
                                if new_batch:
                                    # Remember current selected video ID if possible
                                    sel_vid_id = None
                                    if self.videos and self.selected_index < len(self.videos):
                                        sel_vid_id = self.videos[self.selected_index].id

                                    # Merge and deduplicate by ID, preserving watch_later status
                                    video_dict = {v.id: v for v in self.videos}
                                    for v in new_batch:
                                        if v.id in video_dict:
                                            # Preserve user-controlled flags
                                            v.watch_later = video_dict[v.id].watch_later
                                        video_dict[v.id] = v # Update with new data (metadata, duration, etc)
                                    
                                    # Convert back to list and sort by date DESC
                                    self.videos = sorted(video_dict.values(), key=lambda x: x.published_at, reverse=True)
                                    
                                    # Restore selection by ID or adjust index
                                    if sel_vid_id:
                                        for i, v in enumerate(self.videos):
                                            if v.id == sel_vid_id:
                                                self.selected_index = i
                                                break
                                    
                                    self.display_items = self._get_display_list()
                                    self._show_message(stdscr, f"Sync complete: {len(new_batch)} items updated/added", 2)
                                    needs_redraw = True
                except queue.Empty:
                    pass

            if needs_redraw or left_win is None:
                split_ratio = self.config["ui"].get("pane_split_ratio", 0.5)
                left_width = int(sw * split_ratio)
                right_width = sw - left_width - 1
                
                if left_win is None:
                    left_win = curses.newwin(sh - 1, left_width, 0, 0)
                    right_win = curses.newwin(sh - 1, right_width, 0, left_width + 1)
                
                self._draw_left_pane(left_win, left_width, sh - 1)
                self._draw_right_pane(right_win, right_width, sh - 1)
                
                stdscr.erase()
                for y in range(sh - 1):
                    try: stdscr.addch(y, left_width, curses.ACS_VLINE, curses.A_DIM)
                    except: pass
                
                wl_count = sum(1 for v in self.videos if v.watch_later)
                threshold = self.config['ui'].get('shorts_threshold_seconds', 90)
                wl_label = "IST" if self.show_watch_later else "ist"
                wl_part = f"[l]ater [L]{wl_label} ({wl_count})"
                shorts_label = "HORTS" if not self.show_shorts else "horts"
                shorts_part = f"[s]{shorts_label} thre[S]hold ({threshold}s)"
                
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
                
                def add_footer_seg(text, attr=curses.A_REVERSE):
                    nonlocal x_footer
                    if x_footer >= sw: return
                    self._safe_addstr(stdscr, sh - 1, x_footer, text, attr)
                    x_footer += len(text)

                def add_footer_sep():
                    add_footer_seg("|", curses.color_pair(9) | curses.A_REVERSE)

                stdscr.move(sh - 1, 0)
                stdscr.clrtoeol()
                x_footer = 1
                add_footer_seg(f"[q]uit ")
                add_footer_sep()
                add_footer_seg(f" [?] help ")
                add_footer_sep()
                add_footer_seg(f" [/] find ")
                add_footer_sep()
                add_footer_seg(f" [y]ank ")
                add_footer_sep()
                add_footer_seg(f" [o]pen ")
                add_footer_sep()
                add_footer_seg(f" {wl_part} ")
                add_footer_sep()
                add_footer_seg(f" [d]el ")
                add_footer_sep()
                add_footer_seg(f" {shorts_part} ")
                add_footer_sep()
                add_footer_seg(f" [b]y channel ")
                add_footer_sep()
                add_footer_seg(f" {chan_filter}{search_status}")
                if self.is_syncing:
                    add_footer_sep()
                    add_footer_seg(f" [SYNC: {self.sync_progress}]")
                
                if self.input_buffer:
                    add_footer_sep()
                    add_footer_seg(f" :{self.input_buffer}")

                stdscr.noutrefresh()
                left_win.noutrefresh()
                right_win.noutrefresh()
                curses.doupdate()
                
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
            
            # Handle counts and other keys...
            if ord('0') <= key <= ord('9'):
                if self.input_buffer == "" and key == ord('0'): pass
                else:
                    self.input_buffer += chr(key)
                    continue

            count = int(self.input_buffer) if self.input_buffer and self.input_buffer.isdigit() else 1

            if key == ord('q'): break
            elif key == 27:
                self.show_watch_later = False
                self.filter_channel_id = None
                self.filter_query = ""
                self.input_buffer = ""
                self.display_items = self._get_display_list()
            elif key == ord('?'): self.show_help = True
            elif key == ord('/'):
                self.filter_query = self._get_search_query(stdscr)
                self.display_items = self._get_display_list()
                self.input_buffer = ""
            elif key == ord('y'):
                if self.videos and self.selected_index < len(self.videos):
                    self._copy_to_clipboard(self.videos[self.selected_index].url)
                self.input_buffer = ""
            elif key == ord('o'):
                if self.videos and self.selected_index < len(self.videos):
                    self._open_in_browser(self.videos[self.selected_index])
                self.input_buffer = ""
            elif key == ord('l'):
                if self.videos and self.selected_index < len(self.videos):
                    v = self.videos[self.selected_index]
                    v.watch_later = True
                    self.db.update_watch_later(v.id, True)
                    self._show_message(stdscr, f"Added to Watch Later: {v.title[:30]}...")
                    self.display_items = self._get_display_list()
                self.input_buffer = ""
            elif key == ord('L'):
                self.show_watch_later = not self.show_watch_later
                self.display_items = self._get_display_list()
                if self.show_watch_later:
                    video_count = sum(1 for v in self.videos if v.watch_later)
                    if not any(item["type"] == "video" for item in self.display_items):
                        self._show_message(stdscr, f"Watch Later list is empty (Total: {video_count})")
                if self.display_items:
                    found = False
                    for item in self.display_items:
                        if item["type"] == "video" and item["original_index"] == self.selected_index:
                            found = True; break
                    if not found:
                        for item in self.display_items:
                            if item["type"] == "video":
                                self.selected_index = item["original_index"]; break
                self.input_buffer = ""
            elif key == ord('d'):
                if self.videos and self.selected_index < len(self.videos):
                    v = self.videos[self.selected_index]
                    if v.watch_later:
                        v.watch_later = False
                        self.db.update_watch_later(v.id, False)
                        self._show_message(stdscr, "Removed from Watch Later")
                        self.display_items = self._get_display_list()
                self.input_buffer = ""
            elif key == ord('s'):
                self.show_shorts = not self.show_shorts
                self.display_items = self._get_display_list()
                self.input_buffer = ""
            elif key == ord('S'):
                self._set_shorts_threshold(stdscr)
                self.display_items = self._get_display_list()
                self.input_buffer = ""
            elif key == ord('b'):
                if self.filter_channel_id: self.filter_channel_id = None
                else:
                    if self.videos and self.selected_index < len(self.videos):
                        self.filter_channel_id = self.videos[self.selected_index].channel_id
                self.display_items = self._get_display_list()
                self.input_buffer = ""
            elif key in [curses.KEY_UP, ord('k')]:
                curr = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        curr = idx; break
                moves = count
                target = curr
                while moves > 0 and target > 0:
                    target -= 1
                    if self.display_items[target]["type"] == "video":
                        self.selected_index = self.display_items[target]["original_index"]
                        moves -= 1
                self.input_buffer = ""
            elif key in [curses.KEY_DOWN, ord('j')]:
                curr = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        curr = idx; break
                moves = count
                target = curr
                while moves > 0 and target < len(self.display_items) - 1:
                    target += 1
                    if self.display_items[target]["type"] == "video":
                        self.selected_index = self.display_items[target]["original_index"]
                        moves -= 1
                self.input_buffer = ""
            elif key == ord('J'):
                curr = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        curr = idx; break
                days = count
                target = curr
                while days > 0 and target < len(self.display_items) - 1:
                    target += 1
                    if self.display_items[target]["type"] == "header": days -= 1
                for idx in range(target, len(self.display_items)):
                    if self.display_items[idx]["type"] == "video":
                        self.selected_index = self.display_items[idx]["original_index"]; break
                self.input_buffer = ""
            elif key == ord('K'):
                curr = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        curr = idx; break
                days = count
                target = curr
                if target > 0 and self.display_items[target - 1]["type"] == "header": target -= 1
                while days > 0 and target > 0:
                    target -= 1
                    if self.display_items[target]["type"] == "header": days -= 1
                for idx in range(target, len(self.display_items)):
                    if self.display_items[idx]["type"] == "video":
                        self.selected_index = self.display_items[idx]["original_index"]; break
                self.input_buffer = ""
            elif key == ord('G'):
                if self.input_buffer:
                    line = min(count, len(self.display_items))
                    idx = max(0, line - 1)
                    if self.display_items[idx]["type"] == "video":
                        self.selected_index = self.display_items[idx]["original_index"]
                    else:
                        for sub in range(idx, len(self.display_items)):
                            if self.display_items[sub]["type"] == "video":
                                self.selected_index = self.display_items[sub]["original_index"]; break
                else:
                    for idx in range(len(self.display_items) - 1, -1, -1):
                        if self.display_items[idx]["type"] == "video":
                            self.selected_index = self.display_items[idx]["original_index"]; break
                self.input_buffer = ""
            elif key == ord('g'):
                if self.input_buffer == "g":
                    for idx in range(len(self.display_items)):
                        if self.display_items[idx]["type"] == "video":
                            self.selected_index = self.display_items[idx]["original_index"]; break
                    self.input_buffer = ""
                else: self.input_buffer = "g"
            elif key == ord('z'):
                if self.input_buffer == "z":
                    curr = -1
                    for idx, item in enumerate(self.display_items):
                        if item["type"] == "video" and item["original_index"] == self.selected_index:
                            curr = idx; break
                    if curr != -1: self.top_line = max(0, curr - (sh - 1) // 2)
                    self.input_buffer = ""
                else: self.input_buffer = "z"
            elif key in [curses.KEY_PPAGE, 2]:
                curr = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        curr = idx; break
                target = max(0, curr - max(1, sh - 2))
                for idx in range(target, len(self.display_items)):
                    if self.display_items[idx]["type"] == "video":
                        self.selected_index = self.display_items[idx]["original_index"]; break
                self.input_buffer = ""
            elif key in [curses.KEY_NPAGE, 6]:
                curr = -1
                for idx, item in enumerate(self.display_items):
                    if item["type"] == "video" and item["original_index"] == self.selected_index:
                        curr = idx; break
                target = min(len(self.display_items) - 1, curr + max(1, sh - 2))
                for idx in range(target, -1, -1):
                    if self.display_items[idx]["type"] == "video":
                        self.selected_index = self.display_items[idx]["original_index"]; break
                self.input_buffer = ""
            elif key in [ord('\n'), curses.KEY_ENTER]:
                if self.videos and self.selected_index < len(self.videos):
                    self._play_video(self.videos[self.selected_index])
                self.input_buffer = ""
            else: self.input_buffer = ""

def start_tui(videos: List[Video], db: Database, sync_queue: queue.Queue = None):
    if not videos: videos = []
    os.environ.setdefault('TERM', 'xterm-256color')
    os.environ.setdefault('ESCDELAY', '25')
    curses.wrapper(lambda stdscr: YouTubeTUI(videos, db, sync_queue).run(stdscr))
