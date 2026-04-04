from dataclasses import dataclass
from typing import Optional

@dataclass
class Channel:
    """Represents a YouTube channel with detailed information."""
    id: str
    title: str
    description: Optional[str] = None
    custom_url: Optional[str] = None
    published_at: Optional[str] = None
    thumbnail_url: Optional[str] = None
    view_count: Optional[int] = None
    subscriber_count: Optional[int] = None
    video_count: Optional[int] = None
    uploads_playlist_id: Optional[str] = None
    latest_video_date: Optional[str] = None
    raw_json: str = "{}"

@dataclass
class Video:
    """Represents a YouTube video with detailed information."""
    id: str
    channel_id: str
    title: str
    published_at: str
    duration: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    channel_title: str = ""
    watch_later: bool = False
    last_synced: Optional[str] = None
    raw_json: str = "{}"

    @property
    def duration_seconds(self) -> int:
        """Converts the formatted duration string (H:MM:SS or M:SS) to total seconds."""
        parts = self.duration.strip().split(':')
        try:
            if len(parts) == 3: # H:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2: # M:SS
                return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            pass
        return 0

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.id}"

