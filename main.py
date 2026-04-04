import argparse
import logging
import sys
import threading
import queue
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

logging.basicConfig(
    filename="sync_error.log",
    level=logging.WARNING,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)

from youtube_client import YouTubeClient
from database import Database
from tui import start_tui, THUMB_CACHE_DIR


def download_thumbnails(videos, progress_callback=None):
    """Pre-downloads maxresdefault thumbnails for videos that lack a cached file."""
    os.makedirs(THUMB_CACHE_DIR, exist_ok=True)
    to_fetch = [v for v in videos
                if not os.path.exists(os.path.join(THUMB_CACHE_DIR, f"{v.id}_max.jpg"))]
    if not to_fetch:
        return

    if progress_callback:
        progress_callback(f"Downloading {len(to_fetch)} thumbnails...")

    def fetch(video):
        path = os.path.join(THUMB_CACHE_DIR, f"{video.id}_max.jpg")
        for url in [f"https://i.ytimg.com/vi/{video.id}/maxresdefault.jpg",
                    video.thumbnail_url]:
            if not url:
                continue
            try:
                urllib.request.urlretrieve(url, path)
                return
            except Exception:
                continue

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(fetch, to_fetch))

def background_sync(db: Database, client: YouTubeClient, sync_queue: queue.Queue, sync_start_rfc3339: Optional[str]):
    """Runs the sync process in the background and pushes new videos to the TUI."""
    def progress(msg):
        sync_queue.put({"type": "progress", "message": msg})

    try:
        # Sync channels first
        channels = client.get_subscriptions(progress_callback=progress)
        db.save_channels(channels)
        
        # Get stats for adaptive batching
        channel_stats = db.get_channel_stats()
        
        # Sync videos since sync_start_rfc3339
        new_videos = client.sync_data(channels, sync_start_rfc3339, channel_stats, progress_callback=progress)
        
        if new_videos:
            progress(f"Saving {len(new_videos)} videos to DB...")
            # Set last_synced timestamp
            now_rfc3339 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for v in new_videos:
                v.last_synced = now_rfc3339
                
            try:
                db.save_videos(new_videos)
                # Push new videos to TUI
                sync_queue.put({"type": "videos", "data": new_videos})
                # Pre-download thumbnails for new videos
                download_thumbnails(new_videos, progress_callback=progress)
            except Exception as e:
                progress(f"DB Error: {str(e)}")
                raise e
            
        # Update metadata with current time
        now_rfc3339 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.set_last_update(now_rfc3339)
        
    except Exception as e:
        import traceback
        error_msg = f"Sync error: {str(e)}"
        progress(error_msg)
        # Log to file for debugging
        with open("sync_error.log", "a") as f:
            f.write(f"{datetime.now()}: {error_msg}\n")
            f.write(traceback.format_exc() + "\n")
    finally:
        sync_queue.put({"type": "done"})

def main():
    parser = argparse.ArgumentParser(description="YouTube Subscription Monitor with Database & TUI")
    parser.add_argument("--date-limit", type=str, help="Update from this date (YYYY-MM-DD). If not provided, updates from last refresh.")
    parser.add_argument("--display-channels", action="store_true", help="Display channels from database.")
    parser.add_argument("--no-tui", action="store_true", help="Don't start TUI after sync.")
    parser.add_argument("--sync-only", action="store_true", help="Only sync data, don't show TUI.")
    args = parser.parse_args()

    db = Database()
    client = YouTubeClient()

    # Determine sync start date
    sync_start_rfc3339 = None
    if args.date_limit:
        try:
            sync_start_date = datetime.strptime(args.date_limit, "%Y-%m-%d")
            sync_start_rfc3339 = sync_start_date.isoformat("T") + "Z"
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        last_update = db.get_last_update()
        if last_update:
            # Overlap sync by 24 hours to catch metadata updates (like duration for finished live streams)
            try:
                dt = datetime.strptime(last_update, "%Y-%m-%dT%H:%M:%SZ")
                overlap_dt = dt.replace(tzinfo=timezone.utc).timestamp() - (24 * 3600)
                sync_start_rfc3339 = datetime.fromtimestamp(overlap_dt, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                sync_start_rfc3339 = last_update
        else:
            sync_start_rfc3339 = None

    if args.display_channels:
        print("\n--- Channels in Database ---")
        for ch in db.get_all_channels():
            print(f"{ch.title} (ID: {ch.id}, Videos: {ch.video_count or 'N/A'})")
        db.close()
        return

    if args.sync_only:
        # In sync-only mode, we still run in foreground for simplicity
        sync_queue = queue.Queue()
        background_sync(db, client, sync_queue, sync_start_rfc3339)
        db.close()
        return

    # Load existing videos immediately
    all_videos = db.get_all_videos()

    if args.no_tui:
        # Text mode (we don't do background sync here for simplicity)
        current_date = None
        for v in all_videos[:50]:
            p_date = v.published_at.split('T')[0]
            if p_date != current_date:
                print(f"\n--- {p_date} ---")
                current_date = p_date
            print(f"[{v.duration}] {v.channel_title} - {v.title}")
        db.close()
    else:
        # Start TUI and background sync
        sync_queue = queue.Queue()
        sync_thread = threading.Thread(
            target=background_sync, 
            args=(db, client, sync_queue, sync_start_rfc3339),
            daemon=True
        )
        sync_thread.start()
        
        start_tui(all_videos, db, sync_queue)
        db.close()

if __name__ == "__main__":
    main()
