"""External actions triggered from the TUI: playback, clipboard, browser.

These are thin wrappers around external CLI tools (``mpv``, ``xclip`` /
``wl-copy``, ``xdg-open``). They do not touch curses state, so they live
in their own module rather than as methods of ``YouTubeTUI``.

The single curses-aware concern is :func:`play_video`, which has to
hand the terminal back to ``mpv`` and then reclaim it; that is handled
explicitly by the caller saving/restoring shell mode.
"""

from __future__ import annotations

import curses
import subprocess

from .models import Video


def play_video(video: Video) -> None:
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
        stderr=subprocess.DEVNULL,
    )
    curses.reset_shell_mode()


def copy_to_clipboard(text: str) -> None:
    """Copies text to the system clipboard using xclip or wl-copy.

    Tries ``xclip`` first (X11), then ``wl-copy`` (Wayland). Silently does
    nothing if neither tool is installed.

    Args:
        text: String to place on the clipboard.
    """
    for cmd in (["xclip", "-selection", "clipboard"], ["wl-copy"]):
        try:
            process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            process.communicate(input=text.encode("utf-8"))
            if process.returncode == 0:
                return
        except FileNotFoundError:
            continue


def open_in_browser(video: Video) -> None:
    """Opens the video URL in the system default browser via ``xdg-open``.

    Args:
        video: Video whose URL should be opened.
    """
    try:
        subprocess.run(
            ["xdg-open", video.url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
