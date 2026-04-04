import os
import pickle
import json
import logging
import threading
import re
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

from models import Channel, Video

# Constants
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CREDENTIALS_PICKLE = "credentials.pickle"
CLIENT_SECRET_FILE = "client_secret_475291016858-5pnovc0dlqgsgv8m933qfk4u8uvs779r.apps.googleusercontent.com.json"

class YouTubeClient:
    """Handles all interactions with the YouTube Data API."""
    
    def __init__(self):
        self._thread_local = threading.local()
        self.youtube = self._get_authenticated_service()

    def _get_authenticated_service(self):
        """Authenticates and returns the YouTube service."""
        if os.path.exists(CREDENTIALS_PICKLE):
            with open(CREDENTIALS_PICKLE, "rb") as f:
                credentials = pickle.load(f)
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            credentials = flow.run_local_server(port=0)
            with open(CREDENTIALS_PICKLE, "wb") as f:
                pickle.dump(credentials, f)

        return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

    def _get_service_for_thread(self):
        """Returns a thread-safe YouTube service instance."""
        if not hasattr(self._thread_local, "youtube"):
            with open(CREDENTIALS_PICKLE, "rb") as f:
                credentials = pickle.load(f)
            self._thread_local.youtube = googleapiclient.discovery.build(
                "youtube", "v3", credentials=credentials
            )
        return self._thread_local.youtube

    def get_subscriptions(self, progress_callback=None) -> List[Channel]:
        """Fetches detailed information for all subscribed channels."""
        all_channel_ids = []
        next_page_token = None
        
        if progress_callback: progress_callback("Fetching subscription IDs...")
        while True:
            response = self.youtube.subscriptions().list(
                part="snippet", mine=True, maxResults=50, pageToken=next_page_token
            ).execute()
            
            for item in response["items"]:
                all_channel_ids.append(item["snippet"]["resourceId"]["channelId"])
                
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
        
        if progress_callback: progress_callback(f"Fetching details for {len(all_channel_ids)} channels...")
        channels = []
        for i in range(0, len(all_channel_ids), 50):
            batch_ids = all_channel_ids[i:i+50]
            response = self.youtube.channels().list(
                part="snippet,contentDetails,statistics",
                id=",".join(batch_ids)
            ).execute()
            
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                content = item.get("contentDetails", {})
                
                channels.append(Channel(
                    id=item["id"],
                    title=snippet.get("title", ""),
                    description=snippet.get("description"),
                    custom_url=snippet.get("customUrl"),
                    published_at=snippet.get("publishedAt"),
                    thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
                    view_count=int(stats.get("viewCount", 0)) if stats.get("viewCount") else None,
                    subscriber_count=int(stats.get("subscriberCount", 0)) if stats.get("subscriberCount") else None,
                    video_count=int(stats.get("videoCount", 0)) if stats.get("videoCount") else None,
                    uploads_playlist_id=content.get("relatedPlaylists", {}).get("uploads"),
                    raw_json=json.dumps(item)
                ))
        return channels

    def _parse_duration(self, duration: str) -> str:
        """Parses ISO 8601 duration to a fixed-width format."""
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return "   0:00"
        h, m, s = [int(x) if x else 0 for x in match.groups()]
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}".rjust(7)
        return f"{m}:{s:02d}".rjust(7)

    def fetch_videos_from_playlist(self, channel: Channel, published_after: Optional[str], channel_stats: Dict[str, float] = None) -> Tuple[List[Dict], str, Optional[str]]:
        """Fetches videos from a channel's uploads playlist since a given date using adaptive batching."""
        youtube = self._get_service_for_thread()
        playlist_id = channel.uploads_playlist_id
        if not playlist_id:
            return [], channel.id, None
            
        videos = []
        latest_video_date = None
        next_page_token = None

        # Calculate adaptive maxResults
        max_results = 50 # Default
        if channel_stats:
            avg_per_day = channel_stats.get(channel.id)
            days_passed = 1 # Minimum 1 day
            if published_after:
                try:
                    last_refresh = datetime.strptime(published_after, "%Y-%m-%dT%H:%M:%SZ")
                    delta = datetime.now() - last_refresh
                    days_passed = max(1, (delta.days + (1 if delta.seconds > 0 else 0)))
                except ValueError:
                    pass
            
            if avg_per_day is not None:
                # Algorithm: max(avg_per_day * days_passed, 2)
                max_results = max(int(avg_per_day * days_passed + 0.5), 2)
            else:
                # If channel has no videos in DB yet, use 10
                max_results = 10
            
            # Cap at 50 as it's the API limit for maxResults
            max_results = min(max_results, 50)
        
        try:
            while True:
                response = youtube.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=max_results,
                    pageToken=next_page_token
                ).execute()
                
                items = response.get("items", [])
                if not items:
                    break
                    
                batch_finished = False
                for item in items:
                    video_pub_at = item["contentDetails"].get("videoPublishedAt") or item["snippet"]["publishedAt"]
                    # ISO 8601 strings in YYYY-MM-DDTHH:MM:SSZ format compare correctly as plain strings
                    if published_after and video_pub_at < published_after:
                        batch_finished = True
                        break
                    
                    item["channelId"] = channel.id
                    videos.append(item)
                    if latest_video_date is None or video_pub_at > latest_video_date:
                        latest_video_date = video_pub_at
                
                if batch_finished:
                    break
                    
                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break
                    
        except googleapiclient.errors.HttpError as e:
            logger.warning("HttpError fetching playlist %s (channel %s): %s", playlist_id, channel.id, e)
            
        return videos, channel.id, latest_video_date

    def get_detailed_videos(self, raw_items: List[Dict]) -> List[Video]:
        """Fetches detailed statistics and descriptions for a list of video items."""
        if not raw_items:
            return []
            
        video_ids = [item["contentDetails"]["videoId"] for item in raw_items]
        detailed_videos = []
        
        for i in range(0, len(video_ids), 50):
            batch_ids = video_ids[i:i+50]
            response = self.youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(batch_ids)
            ).execute()

            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                content = item.get("contentDetails", {})
                vid_id = item["id"]
                
                detailed_videos.append(Video(
                    id=vid_id,
                    channel_id=snippet.get("channelId", ""),
                    title=snippet.get("title", ""),
                    description=snippet.get("description"),
                    published_at=snippet.get("publishedAt", ""),
                    duration=self._parse_duration(content.get("duration", "")),
                    thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
                    view_count=int(stats.get("viewCount", 0)) if stats.get("viewCount") else None,
                    like_count=int(stats.get("likeCount", 0)) if stats.get("likeCount") else None,
                    comment_count=int(stats.get("commentCount", 0)) if stats.get("commentCount") else None,
                    channel_title=snippet.get("channelTitle", ""),
                    raw_json=json.dumps(item)
                ))
        return detailed_videos

    def sync_data(self, channels: List[Channel], published_after: Optional[str], channel_stats: Dict[str, float] = None, progress_callback=None) -> List[Video]:
        """Synchronizes new videos from subscriptions in parallel using adaptive batching."""
        if progress_callback: progress_callback(f"Syncing videos since {published_after or 'forever'}...")
        all_raw_videos = []
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(self.fetch_videos_from_playlist, c, published_after, channel_stats) for c in channels]
            completed = 0
            for future in as_completed(futures):
                videos, cid, latest_date = future.result()
                all_raw_videos.extend(videos)
                # Update latest_video_date in channel object
                for c in channels:
                    if c.id == cid:
                        c.latest_video_date = latest_date
                        break
                
                completed += 1
                if completed % 20 == 0 or completed == len(channels):
                    if progress_callback: progress_callback(f"Progress: {completed}/{len(channels)} channels synced.")

        if not all_raw_videos:
            return []
            
        if progress_callback: progress_callback(f"Fetching details for {len(all_raw_videos)} new videos...")
        return self.get_detailed_videos(all_raw_videos)
