import os
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def check_dependencies():
    required_modules = ['requests', 'bs4', 'googleapiclient', 'youtube_transcript_api']
    for module in required_modules:
        if module not in sys.modules:
            print(f"Error: {module} is not installed.")
            sys.exit(1)

# Constants
YOUTUBE_CHANNEL_URL = os.getenv('YOUTUBE_CHANNEL_URL', 'YOUR_YOUTUBE_CHANNEL_URL')
API_KEY_FILE = '.yt_api_key'

def get_youtube_api_key():
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, 'r') as file:
            return file.read().strip()
    else:
        api_key = input("Enter your YouTube API key: ").strip()
        with open(API_KEY_FILE, 'w') as file:
            file.write(api_key)
        return api_key

def get_channel_id(youtube, channel_url):
    # Extract the channel handle from the URL
    if '@' not in channel_url:
        raise ValueError("Invalid YouTube channel URL format.")
    channel_handle = channel_url.split('@')[1].split('/')[0]
    
    # Use the YouTube API to retrieve the channel ID
    request = youtube.search().list(
        part="snippet",
        q=channel_handle,
        type="channel"
    )
    response = request.execute()
    if not response['items']:
        raise ValueError("Could not find channel ID using the provided handle.")
    channel_id = response['items'][0]['snippet']['channelId']
    return channel_id
    request = youtube.playlists().list(
        part="snippet",
        id=playlist_id
    )
    response = request.execute()
    if not response['items']:
        raise ValueError("Could not find playlist using the provided ID.")
    playlist_info = response['items'][0]['snippet']
    return {
        'title': playlist_info['title'],
        'description': playlist_info['description']
    }

def get_playlist_video_ids(youtube, playlist_id):
    video_ids = []
    next_page_token = None
    while True:
        request = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        response = request.execute()
        video_ids.extend([item['contentDetails']['videoId'] for item in response['items']])
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    return video_ids

def get_video_details(youtube, video_id):
    request = youtube.videos().list(
        part="snippet,contentDetails",
        id=video_id
    )
    response = request.execute()
    if not response['items']:
        return None
    video_info = response['items'][0]['snippet']
    video_info = response['items'][0]['snippet']
    return {
        'author': video_info['channelTitle'],
        'title': video_info['title'],
        'published_at': video_info['publishedAt'],
        'description': video_info['description'],
        'url': f"https://www.youtube.com/watch?v={video_id}"
    }

def get_video_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = ' '.join([entry['text'] for entry in transcript_list])
        return transcript
    except (TranscriptsDisabled, NoTranscriptFound):
        return "Transcript not available."

def save_video_info(channel_name, video_info, transcript):
    title = video_info['title']
    published_at = video_info['published_at']
    video_url = video_info['url']
    description = video_info['description']
    
    date_str = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
    safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    filename = f"{date_str} {safe_title}.txt"
    
    downloads_path = os.path.join(os.path.expanduser("~"), "Downloads", channel_name)
    if not os.path.exists(downloads_path):
        os.makedirs(downloads_path)
    
    with open(os.path.join(downloads_path, filename), 'w', encoding='utf-8') as file:
        file.write(f"Title: {title}\n")
        file.write(f"Published At: {published_at}\n")
        file.write(f"URL: {video_url}\n")
        file.write(f"Description: {description}\n")
        file.write(f"Transcript: {transcript}\n")

def main():
    try:
        check_dependencies()
        global YOUTUBE_CHANNEL_URL
        if YOUTUBE_CHANNEL_URL == 'YOUR_YOUTUBE_CHANNEL_URL':
            YOUTUBE_CHANNEL_URL = input("Enter your YouTube channel URL: ").strip()
        
        YOUTUBE_API_KEY = get_youtube_api_key()
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        if 'list=' in YOUTUBE_CHANNEL_URL:
            playlist_id = YOUTUBE_CHANNEL_URL.split('list=')[1]
            playlist_details = get_playlist_details(youtube, playlist_id)
            video_ids = get_playlist_video_ids(youtube, playlist_id)
            folder_name = playlist_details['title']
            print(f"Found {len(video_ids)} videos in the playlist '{folder_name}'.")
        else:
            channel_id = get_channel_id(youtube, YOUTUBE_CHANNEL_URL)
            
            # Get the total number of videos in the channel
            channel_request = youtube.channels().list(
                part="statistics",
                id=channel_id
            )
            channel_response = channel_request.execute()
            video_count = int(channel_response['items'][0]['statistics']['videoCount'])
            
            print(f"The channel has {video_count} videos.")
            confirm = input("Do you want to proceed with processing these videos? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                print("Operation cancelled by the user.")
                return
            
            # Fetch video IDs
            video_ids = []
            next_page_token = None
            while True:
                request = youtube.search().list(
                    part="id",
                    channelId=channel_id,
                    maxResults=50,
                    pageToken=next_page_token
                )
                response = request.execute()
                video_ids.extend([item['id']['videoId'] for item in response['items'] if item['id']['kind'] == 'youtube#video'])
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            folder_name = YOUTUBE_CHANNEL_URL.split('/')[-1]
            
            print(f"Found {len(video_ids)} videos in the channel.")
        confirm = input("Do you want to proceed with processing these videos? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Operation cancelled by the user.")
            return

        for idx, video_id in enumerate(video_ids, start=1):
            print(f"Processing video {idx}/{len(video_ids)}...")
            video_info = get_video_details(youtube, video_id)
            if video_info:
                transcript = get_video_transcript(video_id)
                save_video_info(folder_name, video_info, transcript)
    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
    except ValueError as e:
        print(f"Value error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
