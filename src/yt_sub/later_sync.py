import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any

import googleapiclient.errors

from .database import Database
from .youtube_client import YouTubeClient
from . import paths

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Holds the outcome of a single Later two-way synchronisation run.

    Attributes:
        added_locally: Number of videos added to the local watch-later list
            because they were found on the YouTube playlist.
        removed_locally: Number of videos removed from the local watch-later
            list because they were deleted from the YouTube playlist.
        added_to_yt: Number of videos pushed to the YouTube playlist from
            the local watch-later list.
        removed_from_yt: Number of videos deleted from the YouTube playlist
            because they were removed locally.
        errors: Human-readable error messages for individual operations that
            failed; the sync continues for remaining items when one fails.
    """

    added_locally: int = 0
    removed_locally: int = 0
    added_to_yt: int = 0
    removed_from_yt: int = 0
    errors: list = field(default_factory=list)


def _save_playlist_id_to_config(playlist_id: str) -> None:
    """Persists *playlist_id* to the ``youtube.later_playlist_id`` config key.

    Reads the current config file, updates the value, and writes it back.
    Silently does nothing on I/O errors so a missing config never crashes sync.

    Args:
        playlist_id: YouTube playlist ID to store.
    """
    config_path = str(paths.config_file())
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}

    if "youtube" not in config:
        config["youtube"] = {}
    config["youtube"]["later_playlist_id"] = playlist_id

    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        logger.warning("Could not save later_playlist_id to config: %s", e)


def sync_later(db: Database, yt: YouTubeClient, config: Dict[str, Any]) -> SyncResult:
    """Performs a full two-way synchronisation of the local Later list with YouTube.

    Algorithm overview:

    1. Load snapshot ``S`` (``{video_id: playlist_item_id}``) from the database.
    2. Fetch current YouTube playlist items ``Y`` (``{video_id: playlist_item_id}``);
       filter to IDs present in the local database.
    3. Load local watch-later IDs ``L`` from the database.
    4. Compute changes:
       - ``yt_added``     = Y - S  → mark locally as watch-later
       - ``yt_removed``   = S - Y  → unmark locally
       - ``local_added``  = L - S  → push to YouTube
       - ``local_removed``= S - L  → delete from YouTube
    5. Apply changes (errors are collected; processing continues).
    6. Build new snapshot and persist it.

    Videos present in the YouTube playlist but absent from the local database
    are silently ignored — they stay on YouTube and are not imported.

    Args:
        db: Open database connection.
        yt: Authenticated YouTube API client.
        config: Parsed application config dict; must contain at minimum
            ``{"youtube": {"later_playlist_name": "...", "later_playlist_id": ""}}``.

    Returns:
        :class:`SyncResult` describing what changed during this sync.
    """
    result = SyncResult()
    youtube_cfg = config.get("youtube", {})
    playlist_name = youtube_cfg.get("later_playlist_name", "Later")
    playlist_id = youtube_cfg.get("later_playlist_id", "")

    # Resolve playlist ID
    if not playlist_id:
        try:
            playlist_id = yt.find_or_create_playlist(playlist_name)
            _save_playlist_id_to_config(playlist_id)
        except Exception as e:
            result.errors.append(
                f"Could not find/create playlist '{playlist_name}': {e}"
            )
            return result

    # Step 1: Load snapshot S
    S: Dict[str, str] = db.get_later_snapshot()

    # Step 2: Fetch Y from YouTube, filter to locally known IDs
    try:
        Y_raw: Dict[str, str] = yt.get_playlist_items(playlist_id)
    except Exception as e:
        result.errors.append(f"Failed to fetch playlist items: {e}")
        return result

    local_video_ids: set = {v.id for v in db.get_all_videos()}
    Y: Dict[str, str] = {
        vid: iid for vid, iid in Y_raw.items() if vid in local_video_ids
    }

    # Step 3: Load L from database
    L: set = db.get_watch_later_ids()

    S_keys = set(S.keys())
    Y_keys = set(Y.keys())

    # Step 4: Compute deltas
    yt_added = Y_keys - S_keys
    yt_removed = S_keys - Y_keys
    local_added = L - S_keys
    local_removed = S_keys - L

    # Step 5: Apply changes
    for vid_id in yt_added:
        try:
            db.update_watch_later(vid_id, True)
            result.added_locally += 1
        except Exception as e:
            result.errors.append(f"DB update watch_later True for {vid_id}: {e}")

    for vid_id in yt_removed:
        try:
            db.update_watch_later(vid_id, False)
            result.removed_locally += 1
        except Exception as e:
            result.errors.append(f"DB update watch_later False for {vid_id}: {e}")

    new_item_ids: Dict[str, str] = {}
    for vid_id in local_added:
        try:
            item_id = yt.add_to_playlist(playlist_id, vid_id)
            new_item_ids[vid_id] = item_id
            result.added_to_yt += 1
        except Exception as e:
            result.errors.append(f"Failed to add {vid_id} to playlist: {e}")
            logger.warning("later_sync add_to_playlist failed for %s: %s", vid_id, e)

    for vid_id in local_removed:
        try:
            yt.remove_from_playlist(S[vid_id])
            result.removed_from_yt += 1
        except Exception as e:
            result.errors.append(f"Failed to remove {vid_id} from playlist: {e}")
            logger.warning(
                "later_sync remove_from_playlist failed for %s: %s", vid_id, e
            )

    # Step 6: Build and persist new snapshot
    new_S: Dict[str, str] = {vid: iid for vid, iid in Y.items()}
    new_S.update(new_item_ids)
    # Items in local_removed are absent from new_S (not in Y, not in new_item_ids)

    db.save_later_snapshot(new_S)

    return result
