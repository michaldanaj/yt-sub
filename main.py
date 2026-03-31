import argparse
import sys
from datetime import datetime, timezone
from typing import Optional

from youtube_client import YouTubeClient
from database import Database
from tui import start_tui

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
        # Use last update from DB
        sync_start_rfc3339 = db.get_last_update()
    
    # Always sync channels first to get current subscriptions and uploads playlist IDs
    channels = client.get_subscriptions()
    db.save_channels(channels)
    
    # Sync videos since sync_start_rfc3339
    new_videos = client.sync_data(channels, sync_start_rfc3339)
    if new_videos:
        print(f"Saving {len(new_videos)} new videos to database...")
        db.save_videos(new_videos)
    else:
        print("No new videos found since last update.")

    # Update metadata with current time in RFC3339
    now_rfc3339 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.set_last_update(now_rfc3339)

    if args.display_channels:
        print("\n--- Channels in Database ---")
        for ch in db.get_all_channels():
            print(f"{ch.title} (ID: {ch.id}, Videos: {ch.video_count or 'N/A'})")

    if not args.sync_only:
        all_videos = db.get_all_videos()
        if args.no_tui:
            # Fallback text mode
            current_date = None
            for v in all_videos[:50]: # Show last 50
                p_date = v.published_at.split('T')[0]
                if p_date != current_date:
                    print(f"\n--- {p_date} ---")
                    current_date = p_date
                print(f"[{v.duration}] {v.channel_title} - {v.title}")
        else:
            start_tui(all_videos)

    db.close()

if __name__ == "__main__":
    main()
