import sqlite3
import statistics
import threading
from collections import defaultdict
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .models import Channel, Video, ChannelStatRow
from . import paths


def _parse_duration_seconds(duration: str) -> int:
    """Parse a formatted duration string (``H:MM:SS`` or ``M:SS``) to seconds.

    Args:
        duration: Right-justified duration string as stored in the database.

    Returns:
        Total seconds, or ``0`` for unrecognised formats.
    """
    parts = duration.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        pass
    return 0

DB_PATH = str(paths.database_file())


class Database:
    """SQLite-backed persistence layer for channels and videos.

    All write operations are serialised with an internal ``threading.Lock``
    so that the background sync thread and the TUI main thread can share a
    single connection safely.
    """

    def __init__(self) -> None:
        """Opens (or creates) the database and initialises the schema."""
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self) -> None:
        """Creates tables and migrates missing columns on existing databases."""
        cursor = self.conn.cursor()

        # Channels table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                custom_url TEXT,
                published_at TEXT,
                thumbnail_url TEXT,
                view_count INTEGER,
                subscriber_count INTEGER,
                video_count INTEGER,
                uploads_playlist_id TEXT,
                latest_video_date TEXT,
                raw_json TEXT
            )
        ''')

        # Videos table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                channel_id TEXT,
                title TEXT,
                description TEXT,
                published_at TEXT,
                duration TEXT,
                thumbnail_url TEXT,
                view_count INTEGER,
                like_count INTEGER,
                comment_count INTEGER,
                channel_title TEXT,
                watch_later INTEGER DEFAULT 0,
                last_synced TEXT,
                raw_json TEXT,
                FOREIGN KEY (channel_id) REFERENCES channels(id)
            )
        ''')

        # Check if columns exist (for existing databases)
        cursor.execute("PRAGMA table_info(videos)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'watch_later' not in columns:
            cursor.execute("ALTER TABLE videos ADD COLUMN watch_later INTEGER DEFAULT 0")
        if 'last_synced' not in columns:
            cursor.execute("ALTER TABLE videos ADD COLUMN last_synced TEXT")

        # Metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Later sync snapshot table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS later_sync_snapshot (
                video_id TEXT PRIMARY KEY,
                playlist_item_id TEXT NOT NULL
            )
        ''')

        self.conn.commit()

    def save_channels(self, channels: List[Channel]) -> None:
        """Upserts a list of channels into the database.

        Args:
            channels: Channel objects to persist.  Existing rows are replaced
                in full (``INSERT OR REPLACE``).
        """
        with self._lock:
            cursor = self.conn.cursor()
            for c in channels:
                cursor.execute('''
                    INSERT OR REPLACE INTO channels
                    (id, title, description, custom_url, published_at, thumbnail_url, view_count, subscriber_count, video_count, uploads_playlist_id, latest_video_date, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (c.id, c.title, c.description, c.custom_url, c.published_at, c.thumbnail_url, c.view_count, c.subscriber_count, c.video_count, c.uploads_playlist_id, c.latest_video_date, c.raw_json))
            self.conn.commit()

    def save_videos(self, videos: List[Video]) -> None:
        """Upserts a list of videos into the database.

        Metadata fields (title, duration, counts, etc.) are always updated on
        conflict.  The ``watch_later`` flag is intentionally excluded from the
        ``ON CONFLICT`` update so that user-set flags are never overwritten by
        a sync.

        Args:
            videos: Video objects to persist.
        """
        with self._lock:
            cursor = self.conn.cursor()
            for v in videos:
                cursor.execute('''
                    INSERT INTO videos
                    (id, channel_id, title, description, published_at, duration, thumbnail_url, view_count, like_count, comment_count, channel_title, watch_later, last_synced, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title,
                        description=excluded.description,
                        published_at=excluded.published_at,
                        duration=excluded.duration,
                        thumbnail_url=excluded.thumbnail_url,
                        view_count=excluded.view_count,
                        like_count=excluded.like_count,
                        comment_count=excluded.comment_count,
                        last_synced=excluded.last_synced,
                        raw_json=excluded.raw_json
                ''', (v.id, v.channel_id, v.title, v.description, v.published_at, v.duration, v.thumbnail_url, v.view_count, v.like_count, v.comment_count, v.channel_title, 1 if v.watch_later else 0, v.last_synced, v.raw_json))
            self.conn.commit()

    def update_watch_later(self, video_id: str, status: bool) -> None:
        """Sets the watch-later flag for a single video.

        Args:
            video_id: YouTube video ID to update.
            status: ``True`` to mark for later viewing, ``False`` to clear.
        """
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('UPDATE videos SET watch_later = ? WHERE id = ?', (1 if status else 0, video_id))
            self.conn.commit()

    def reset_watch_later(self) -> None:
        """Clears the watch-later flag for every video in the database."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('UPDATE videos SET watch_later = 0')
            self.conn.commit()

    def get_all_videos(self) -> List[Video]:
        """Returns all videos ordered by publication date descending.

        Returns:
            List of :class:`Video` objects, newest first.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, channel_id, title, description, published_at, duration, thumbnail_url, view_count, like_count, comment_count, channel_title, watch_later, last_synced, raw_json
            FROM videos
            ORDER BY published_at DESC
        ''')
        rows = cursor.fetchall()

        videos = []
        for row in rows:
            videos.append(Video(
                id=row[0], channel_id=row[1], title=row[2], description=row[3],
                published_at=row[4], duration=row[5], thumbnail_url=row[6],
                view_count=row[7], like_count=row[8], comment_count=row[9],
                channel_title=row[10], watch_later=bool(row[11]), last_synced=row[12], raw_json=row[13]
            ))
        return videos

    def get_all_channels(self) -> List[Channel]:
        """Returns all channels ordered alphabetically by title.

        Returns:
            List of :class:`Channel` objects.
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM channels ORDER BY title ASC')
        rows = cursor.fetchall()

        channels = []
        for row in rows:
            channels.append(Channel(
                id=row[0], title=row[1], description=row[2], custom_url=row[3],
                published_at=row[4], thumbnail_url=row[5], view_count=row[6],
                subscriber_count=row[7], video_count=row[8], uploads_playlist_id=row[9],
                latest_video_date=row[10], raw_json=row[11]
            ))
        return channels

    def set_last_update(self, date_str: str) -> None:
        """Persists the last-sync timestamp in the metadata table.

        Args:
            date_str: ISO 8601 timestamp string (``YYYY-MM-DDTHH:MM:SSZ``).
        """
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)', ("last_update", date_str))
            self.conn.commit()

    def get_last_update(self) -> Optional[str]:
        """Retrieves the last-sync timestamp from the metadata table.

        Returns:
            ISO 8601 timestamp string, or ``None`` if no sync has run yet.
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM metadata WHERE key = ?', ("last_update",))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_channel_stats(self) -> Dict[str, float]:
        """Calculates the average number of videos published per day per channel.

        Uses only the last 90 days of data to keep the estimate relevant for
        adaptive batch sizing during sync.

        Returns:
            Mapping of ``channel_id`` to average daily video count.  Channels
            with no videos in the window are absent from the dict.
        """
        cursor = self.conn.cursor()
        three_months_ago = (datetime.now().timestamp() - (90 * 24 * 3600))
        three_months_ago_str = datetime.fromtimestamp(three_months_ago).strftime("%Y-%m-%dT%H:%M:%SZ")

        cursor.execute('''
            SELECT channel_id, COUNT(*)
            FROM videos
            WHERE published_at > ?
            GROUP BY channel_id
        ''', (three_months_ago_str,))

        counts = {row[0]: row[1] / 90.0 for row in cursor.fetchall()}
        return counts

    def get_later_snapshot(self) -> Dict[str, str]:
        """Returns the stored snapshot of the YouTube Later playlist.

        Returns:
            Mapping of ``video_id`` to ``playlist_item_id`` from the last sync.
            Empty dict if no sync has occurred yet.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT video_id, playlist_item_id FROM later_sync_snapshot")
        return {row[0]: row[1] for row in cursor.fetchall()}

    def save_later_snapshot(self, snapshot: Dict[str, str]) -> None:
        """Atomically replaces the Later sync snapshot.

        Clears the entire table and inserts the new snapshot in a single
        transaction to avoid partial state on failure.

        Args:
            snapshot: Mapping of ``video_id`` to ``playlist_item_id``
                representing the current state of the YouTube playlist.
        """
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM later_sync_snapshot")
            cursor.executemany(
                "INSERT INTO later_sync_snapshot (video_id, playlist_item_id) VALUES (?, ?)",
                snapshot.items()
            )
            self.conn.commit()

    def get_watch_later_ids(self) -> set:
        """Returns the set of video IDs currently marked as watch-later.

        Returns:
            Set of ``video_id`` strings where ``watch_later = 1``.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM videos WHERE watch_later = 1")
        return {row[0] for row in cursor.fetchall()}

    def get_channels_stats_table(
        self,
        months: int,
        threshold_seconds: int,
    ) -> List[ChannelStatRow]:
        """Returns per-channel statistics aggregated over the given period.

        Computes average video counts per month and the median duration of
        non-short videos for every channel in the database.  Channels with no
        videos in the period still appear in the result with zero averages and
        ``None`` median.

        Args:
            months: Number of months to look back (each month approximated as
                30 days).
            threshold_seconds: Videos shorter than this value are considered
                Shorts and excluded from non-short counts and the median.

        Returns:
            List of :class:`ChannelStatRow`, one per channel, unsorted.
        """
        cutoff = (datetime.now() - timedelta(days=months * 30)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        cursor = self.conn.cursor()
        cursor.execute("SELECT id, title FROM channels ORDER BY title ASC")
        channels = [(row[0], row[1]) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT channel_id, duration FROM videos WHERE published_at > ?",
            (cutoff,),
        )

        # channel_id -> list of all duration_seconds in period
        all_durations: Dict[str, List[int]] = defaultdict(list)
        for channel_id, duration_str in cursor.fetchall():
            all_durations[channel_id].append(_parse_duration_seconds(duration_str))

        rows = []
        for channel_id, channel_title in channels:
            durations = all_durations.get(channel_id, [])
            non_short = [d for d in durations if d >= threshold_seconds]

            rows.append(ChannelStatRow(
                channel_id=channel_id,
                channel_title=channel_title,
                avg_per_month=len(durations) / months,
                avg_non_short_per_month=len(non_short) / months,
                median_duration_seconds=statistics.median(non_short) if non_short else None,
            ))

        return rows

    def close(self) -> None:
        """Closes the underlying SQLite connection."""
        self.conn.close()
