import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Channel:
    """YouTube channel with subscriber and upload metadata.

    Attributes:
        id: YouTube channel ID (e.g. ``UCxxxxxx``).
        title: Display name of the channel.
        description: Channel description text.
        custom_url: Vanity URL handle (e.g. ``@channelname``).
        published_at: ISO 8601 creation date of the channel.
        thumbnail_url: URL of the high-resolution channel thumbnail.
        view_count: Total view count across all uploads.
        subscriber_count: Number of subscribers; ``None`` if hidden.
        video_count: Number of public videos.
        uploads_playlist_id: ID of the special uploads playlist used for
            fetching new videos.
        latest_video_date: ISO 8601 date of the most recently synced video.
        raw_json: Full JSON response from the YouTube Data API as a string.
    """

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
    """YouTube video with playback and engagement metadata.

    Attributes:
        id: YouTube video ID (e.g. ``dQw4w9WgXcQ``).
        channel_id: ID of the channel that uploaded this video.
        title: Video title.
        published_at: ISO 8601 publication date (``YYYY-MM-DDTHH:MM:SSZ``).
        duration: Human-readable, right-justified duration string produced by
            :meth:`YouTubeClient._parse_duration` (e.g. ``  3:45`` or
            ``1:02:33``).
        description: Full video description text.
        thumbnail_url: URL of the high-resolution thumbnail.
        view_count: Total view count; ``None`` if unavailable.
        like_count: Total like count; ``None`` if unavailable.
        comment_count: Total comment count; ``None`` if unavailable.
        channel_title: Display name of the uploading channel.
        watch_later: Whether the user marked this video for later viewing.
        last_synced: ISO 8601 timestamp of when this record was last written
            to the database.
        raw_json: Full JSON response from the YouTube Data API as a string.
    """

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
        """Total duration in seconds parsed from the formatted duration string.

        Supports ``H:MM:SS`` and ``M:SS`` formats produced by
        :meth:`YouTubeClient._parse_duration`.

        Returns:
            Duration in seconds, or ``0`` if the format is unrecognised.
        """
        parts = self.duration.strip().split(':')
        try:
            if len(parts) == 3:  # H:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:  # M:SS
                return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            pass
        logger.warning("Unrecognised duration format for video %s: %r", self.id, self.duration)
        return 0

    @property
    def url(self) -> str:
        """Full YouTube watch URL for this video.

        Returns:
            URL string in the form ``https://www.youtube.com/watch?v=<id>``.
        """
        return f"https://www.youtube.com/watch?v={self.id}"
