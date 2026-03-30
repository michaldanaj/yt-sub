import os
import pickle
import google_auth_oauthlib.flow
import googleapiclient.discovery
from collections import defaultdict
from datetime import datetime
import json


scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def get_authenticated_service():
    credentials_path = "credentials.pickle"
    if os.path.exists(credentials_path):
        with open(credentials_path, "rb") as f:
            credentials = pickle.load(f)
    else:
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            "client_secret_475291016858-5pnovc0dlqgsgv8m933qfk4u8uvs779r.apps.googleusercontent.com.json",
            scopes,
        )
        credentials = flow.run_local_server(port=0)
        with open(credentials_path, "wb") as f:
            pickle.dump(credentials, f)

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    return youtube


def get_subscriptions(youtube):
    subscriptions = []
    next_page_token = None
    topic_count = defaultdict(int)

    while True:
        response = (
            youtube.subscriptions()
            .list(part="snippet", mine=True, maxResults=50, pageToken=next_page_token)
            .execute()
        )

        subscriptions += response["items"]
        next_page_token = response.get("nextPageToken")

        if next_page_token is None:
            break

    for subscription in subscriptions:
        snippet = subscription["snippet"]
        channelId = snippet["resourceId"]["channelId"]
        response = youtube.channels().list(part="topicDetails", id=channelId).execute()

        items = response.get("items", [])
        if items:
            topicDetails = items[0].get("topicDetails", {})
            topicCategories = topicDetails.get("topicCategories", [])
        else:
            topicCategories = []

        for topic in topicCategories:
            topic_count[topic] += 1

    return topic_count


def get_latest_videos_from_subscriptions(youtube, max_results=10, published_after=None):
    all_channel_ids = []
    next_page_token = None

    while True:
        response = (
            youtube.subscriptions()
            .list(part="snippet", mine=True, maxResults=50, pageToken=next_page_token)
            .execute()
        )
        for item in response["items"]:
            all_channel_ids.append(item["snippet"]["resourceId"]["channelId"])
        next_page_token = response.get("nextPageToken")
        if next_page_token is None:
            break
    
    print(f"Found {len(all_channel_ids)} subscribed channels.")

    all_upload_playlist_info = []
    # Fetch uploads playlist for each channel
    for i in range(0, len(all_channel_ids), 50): # Batch channels to avoid too many API calls
        channel_ids_batch = all_channel_ids[i:i+50]
        response = youtube.channels().list(
            part="contentDetails,snippet",
            id=",".join(channel_ids_batch)
        ).execute()
        for item in response["items"]:
            all_upload_playlist_info.append({
                "playlist_id": item["contentDetails"]["relatedPlaylists"]["uploads"],
                "channel_title": item["snippet"]["title"]
            })
    
    print(f"Found {len(all_upload_playlist_info)} upload playlist IDs.")

    all_videos = []
    # Fetch videos from each uploads playlist
    for info in all_upload_playlist_info:
        playlist_id = info["playlist_id"]
        channel_title = info["channel_title"]
        try:
            request_params = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 10,
            }

            response = youtube.playlistItems().list(**request_params).execute()
            items = response.get("items", [])
            if published_after:
                items = [item for item in items if item["snippet"]["publishedAt"] >= published_after]
            all_videos.extend(items)
        except googleapiclient.errors.HttpError as e:
            if e.resp.status == 404:
                print(f"Warning: Uploads playlist not found for channel: {channel_title} (ID: {playlist_id}). The channel might be deleted, private, or has no uploads.")
            else:
                print(f"Warning: Could not fetch videos for channel {channel_title}. Error: {e}")

    
    
    # Sort and return top N videos
    all_videos.sort(key=lambda x: x["snippet"]["publishedAt"], reverse=True)

    top_videos = []
    for video in all_videos[:max_results]:
        top_videos.append(
            {
                "publishedAt": video["snippet"]["publishedAt"],
                "title": video["snippet"]["title"],
                "channelTitle": video["snippet"]["channelTitle"],
            }
        )
    return top_videos

def main():
    print("Hello from script!")
    youtube = get_authenticated_service()

    published_after_date_str = input("Enter a date (YYYY-MM-DD) to filter videos published after (leave blank for no filter): ")
    published_after_rfc3339 = None
    if published_after_date_str:
        try:
            # Parse the input date string and format it to RFC3339
            published_after_date = datetime.strptime(published_after_date_str, "%Y-%m-%d")
            published_after_rfc3339 = published_after_date.isoformat("T") + "Z"
            print(f"Filtering videos published after: {published_after_rfc3339}")
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD. No date filter will be applied.")
            published_after_rfc3339 = None

    latest_videos = get_latest_videos_from_subscriptions(youtube, published_after=published_after_rfc3339)
    
    for video in latest_videos:
        published_date = datetime.strptime(video["publishedAt"], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
        print(f"{published_date} - {video['channelTitle']} - {video['title']}")


if __name__ == "__main__":
    main()
