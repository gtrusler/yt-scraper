import os
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def check_dependencies():
    required_modules = ['requests', 'bs4', 'googleapiclient']
    for module in required_modules:
        if module not in sys.modules:
            print(f"Error: {module} is not installed.")
            sys.exit(1)

# Constants
YOUTUBE_CHANNEL_URL = os.getenv('YOUTUBE_CHANNEL_URL', 'YOUR_YOUTUBE_CHANNEL_URL')
API_KEY_FILE = 'youtube_api_key.txt'

def get_youtube_api_key():
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, 'r') as file:
            return file.read().strip()
    else:
        api_key = input("Enter your YouTube API key: ").strip()
        with open(API_KEY_FILE, 'w') as file:
            file.write(api_key)
        return api_key

def get_channel_id(channel_url):
    response = requests.get(channel_url)
    if response.status_code != 200:
        raise ValueError("Invalid YouTube channel URL or network issue.")
    soup = BeautifulSoup(response.text, 'html.parser')
    channel_meta = soup.find('meta', itemprop='channelId')
    if not channel_meta:
        raise ValueError("Could not find channel ID in the provided URL.")
    channel_id = channel_meta['content']
    return channel_id

def get_video_details(youtube, video_id):
    request = youtube.videos().list(
        part="snippet,contentDetails",
        id=video_id
    )
    response = request.execute()
    if not response['items']:
        return None
    video_info = response['items'][0]['snippet']
    return {
        'title': video_info['title'],
        'published_at': video_info['publishedAt'],
        'description': video_info['description'],
        'url': f"https://www.youtube.com/watch?v={video_id}"
    }

def get_video_transcript(video_id):
    try:
        transcript_url = f"https://www.youtube.com/api/timedtext?lang=en&v={video_id}"
        response = requests.get(transcript_url)
        if response.status_code != 200 or 'transcript' not in response.text:
            return "Transcript not available."
        soup = BeautifulSoup(response.text, 'html.parser')
        transcript = ' '.join([text.text for text in soup.find_all('text')])
        return transcript
    except Exception as e:
        return "Transcript not available."

def save_video_info(channel_name, video_info, transcript):
    title = video_info['title']
    published_at = video_info['published_at']
    video_url = video_info['url']
    description = video_info['description']
    
    date_str = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
    safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    filename = f"{date_str} {safe_title}.txt"
    
    if not os.path.exists(channel_name):
        os.makedirs(channel_name)
    
    with open(os.path.join(channel_name, filename), 'w', encoding='utf-8') as file:
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
        channel_id = get_channel_id(YOUTUBE_CHANNEL_URL)
        
        # Get the total number of videos in the channel
        channel_request = youtube.channels().list(
            part="statistics",
            id=channel_id
        )
        channel_response = channel_request.execute()
        video_count = int(channel_response['items'][0]['statistics']['videoCount'])
        
        print(f"The channel has {video_count} videos.")
        confirm = input("Do you want to proceed with processing these videos? (yes/no): ").strip().lower()
        if confirm != 'yes':
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
        
        channel_name = YOUTUBE_CHANNEL_URL.split('/')[-1]
        
        print(f"Found {len(video_ids)} videos in the channel.")
        for idx, video_id in enumerate(video_ids, start=1):
            print(f"Processing video {idx}/{len(video_ids)}...")
            video_info = get_video_details(youtube, video_id)
            if video_info:
                transcript = get_video_transcript(video_id)
                save_video_info(channel_name, video_info, transcript)
                
    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
    except ValueError as e:
        print(f"Value error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
