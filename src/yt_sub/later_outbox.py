"""Background worker that drains the ``later_sync_queue`` outbox table.

The worker runs as a daemon thread and propagates local watch-later changes
(add / remove) to the YouTube playlist as soon as possible.  Failed operations
are retried with exponential backoff up to :data:`MAX_ATTEMPTS` times before
being marked as permanently ``failed`` — at which point the TUI shows an
``[E]rrors`` indicator so the user can review and retry manually.
"""

import json
import logging
import threading
import time
from typing import Any, Dict, Optional

import googleapiclient.errors

from .database import Database
from .youtube_client import YouTubeClient
from . import paths

logger = logging.getLogger(__name__)

# Seconds to wait between retries: 1s, 5s, 30s, 5min, 30min.
BACKOFF_SECONDS = [1, 5, 30, 300, 1800]

# Stop retrying after this many attempts; entry is then marked 'failed'.
MAX_ATTEMPTS = 5


def _save_playlist_id(playlist_id: str) -> None:
    """Persists *playlist_id* to ``config.json`` under ``youtube.later_playlist_id``.

    Args:
        playlist_id: YouTube playlist ID to store.
    """
    config_path = str(paths.config_file())
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}
    config.setdefault("youtube", {})["later_playlist_id"] = playlist_id
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except IOError as exc:
        logger.warning("Could not save later_playlist_id to config: %s", exc)


class LaterOutboxWorker:
    """Daemon worker that drains the ``later_sync_queue`` outbox.

    Attributes:
        db: Shared database connection.
        yt: Authenticated YouTube API client.
        config: Parsed application config dict (shared reference; may be
            updated with the resolved ``later_playlist_id``).
        outbox_event: ``threading.Event`` that the TUI sets after enqueuing a
            new operation so the worker wakes up immediately.
        drained_event: ``threading.Event`` set once after the initial drain on
            startup completes.  ``main.py`` waits on this before starting the
            two-way Later sync so both operations see a consistent state.
    """

    def __init__(
        self,
        db: Database,
        yt: YouTubeClient,
        config: Dict[str, Any],
        outbox_event: threading.Event,
    ) -> None:
        """Initialises the worker without starting the background thread.

        Args:
            db: Open database connection shared with the TUI.
            yt: Authenticated YouTube API client.
            config: Parsed application config dict.
            outbox_event: Event to signal the worker when new ops are queued.
        """
        self.db = db
        self.yt = yt
        self.config = config
        self.outbox_event = outbox_event
        self.drained_event = threading.Event()
        self._stop = False
        self._playlist_id: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Starts the background daemon thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="later-outbox")
        self._thread.start()

    def _resolve_playlist_id(self) -> Optional[str]:
        """Returns the YouTube Later playlist ID, resolving it from API if needed.

        Reads ``youtube.later_playlist_id`` from :attr:`config`.  If missing or
        empty, calls :meth:`YouTubeClient.find_or_create_playlist` and persists
        the result back to ``config.json``.

        Returns:
            Playlist ID string, or ``None`` if resolution failed.
        """
        if self._playlist_id:
            return self._playlist_id
        yt_cfg = self.config.get("youtube", {})
        pid = yt_cfg.get("later_playlist_id", "")
        if not pid:
            name = yt_cfg.get("later_playlist_name", "Later")
            try:
                pid = self.yt.find_or_create_playlist(name)
                self.config.setdefault("youtube", {})["later_playlist_id"] = pid
                _save_playlist_id(pid)
            except Exception as exc:
                logger.error("LaterOutboxWorker: could not resolve playlist: %s", exc)
                return None
        self._playlist_id = pid
        return pid

    def _process_op(self, op_id: int, video_id: str, action: str) -> None:
        """Attempts a single add-or-remove API call and updates the outbox accordingly.

        On success the outbox entry is deleted and the snapshot is updated.
        On failure the attempt counter is incremented; once :data:`MAX_ATTEMPTS`
        is reached the entry is marked ``'failed'``.  Intermediate failures sleep
        for the next backoff interval **before returning** so the caller's loop
        naturally implements the delay.

        Args:
            op_id: Outbox row ID.
            video_id: YouTube video ID to add or remove.
            action: ``'add'`` or ``'remove'``.
        """
        playlist_id = self._resolve_playlist_id()
        if playlist_id is None:
            new_attempts = self.db.increment_op_attempts(op_id, "Could not resolve playlist ID")
            if new_attempts >= MAX_ATTEMPTS:
                self.db.mark_op_failed(op_id)
            else:
                time.sleep(BACKOFF_SECONDS[min(new_attempts - 1, len(BACKOFF_SECONDS) - 1)])
            return

        try:
            if action == "add":
                item_id = self.yt.add_to_playlist(playlist_id, video_id)
                self.db.delete_op(op_id)
                self.db.update_snapshot_add(video_id, item_id)
            else:  # remove
                item_id = self.db.get_snapshot_item_id(video_id)
                if item_id:
                    self.yt.remove_from_playlist(item_id)
                    self.db.update_snapshot_remove(video_id)
                # If item_id is None the video was never tracked in our snapshot,
                # meaning it isn't in the YouTube playlist — treat as success.
                self.db.delete_op(op_id)
        except Exception as exc:
            error_msg = str(exc)[:200]
            logger.warning("LaterOutboxWorker %s %s failed: %s", action, video_id, error_msg)
            with open(str(paths.log_file()), "a") as lf:
                lf.write(f"LaterOutboxWorker {action} {video_id}: {error_msg}\n")
            new_attempts = self.db.increment_op_attempts(op_id, error_msg)
            if new_attempts >= MAX_ATTEMPTS:
                self.db.mark_op_failed(op_id)
            else:
                time.sleep(BACKOFF_SECONDS[min(new_attempts - 1, len(BACKOFF_SECONDS) - 1)])

    def _run(self) -> None:
        """Main loop: drain pending ops, then wait for new ones via *outbox_event*.

        Sets :attr:`drained_event` once the initial queue is empty (even if it
        was already empty on startup) so that the two-way sync can start safely.
        """
        first_pass = True
        while not self._stop:
            op = self.db.get_next_pending_op()
            if op is None:
                if first_pass:
                    self.drained_event.set()
                    first_pass = False
                self.outbox_event.wait()
                self.outbox_event.clear()
                continue
            first_pass = False
            self._process_op(op.id, op.video_id, op.action)
