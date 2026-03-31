import sqlite3
import json
from typing import List, Optional, Tuple, Dict
from datetime import datetime
from models import Channel, Video

DB_PATH = "youtube_monitor.db"

class Database:
    """Manages SQLite storage for channels and videos."""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._create_tables()

    def _create_tables(self):
        """Initializes the database schema."""
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
                raw_json TEXT,
                FOREIGN KEY (channel_id) REFERENCES channels(id)
            )
        ''')
        
        # Check if watch_later column exists (for existing databases)
        cursor.execute("PRAGMA table_info(videos)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'watch_later' not in columns:
            cursor.execute("ALTER TABLE videos ADD COLUMN watch_later INTEGER DEFAULT 0")

        # Metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        self.conn.commit()

    def save_channels(self, channels: List[Channel]):
        """Persists a list of channels to the database."""
        cursor = self.conn.cursor()
        for c in channels:
            cursor.execute('''
                INSERT OR REPLACE INTO channels 
                (id, title, description, custom_url, published_at, thumbnail_url, view_count, subscriber_count, video_count, uploads_playlist_id, latest_video_date, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (c.id, c.title, c.description, c.custom_url, c.published_at, c.thumbnail_url, c.view_count, c.subscriber_count, c.video_count, c.uploads_playlist_id, c.latest_video_date, c.raw_json))
        self.conn.commit()

    def save_videos(self, videos: List[Video]):
        """Persists a list of videos to the database, preserving watch_later status."""
        cursor = self.conn.cursor()
        for v in videos:
            cursor.execute('''
                INSERT INTO videos 
                (id, channel_id, title, description, published_at, duration, thumbnail_url, view_count, like_count, comment_count, channel_title, watch_later, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    view_count=excluded.view_count,
                    like_count=excluded.like_count,
                    comment_count=excluded.comment_count,
                    raw_json=excluded.raw_json
            ''', (v.id, v.channel_id, v.title, v.description, v.published_at, v.duration, v.thumbnail_url, v.view_count, v.like_count, v.comment_count, v.channel_title, 1 if v.watch_later else 0, v.raw_json))
        self.conn.commit()

    def update_watch_later(self, video_id: str, status: bool):
        """Updates the watch later status for a video."""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE videos SET watch_later = ? WHERE id = ?', (1 if status else 0, video_id))
        self.conn.commit()

    def reset_watch_later(self):
        """Clears the watch later status for all videos."""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE videos SET watch_later = 0')
        self.conn.commit()

    def get_all_videos(self) -> List[Video]:
        """Retrieves all videos from the database, sorted by publication date."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, channel_id, title, description, published_at, duration, thumbnail_url, view_count, like_count, comment_count, channel_title, watch_later, raw_json 
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
                channel_title=row[10], watch_later=bool(row[11]), raw_json=row[12]
            ))
        return videos

    def get_all_channels(self) -> List[Channel]:
        """Retrieves all channels from the database."""
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

    def set_last_update(self, date_str: str):
        """Updates the last refresh timestamp."""
        cursor = self.conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)', ("last_update", date_str))
        self.conn.commit()

    def get_last_update(self) -> Optional[str]:
        """Retrieves the last refresh timestamp."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM metadata WHERE key = ?', ("last_update",))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_channel_stats(self) -> Dict[str, float]:
        """Calculates average daily videos for each channel over the last 3 months."""
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

    def close(self):
        """Closes the database connection."""
        self.conn.close()
