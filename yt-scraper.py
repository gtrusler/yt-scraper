#!/usr/bin/env python3

import os
import sys
import subprocess
import logging
from datetime import datetime

__version__ = "1.2"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def verify_virtualenv():
    logging.info(f"VIRTUAL_ENV before sourcing: {os.getenv('VIRTUAL_ENV')}")
    if not os.getenv('VIRTUAL_ENV'):
        logging.info("Virtual environment is not activated. Attempting to activate it...")
        activate_script = os.path.join(os.path.dirname(__file__), 'venv', 'bin', 'activate')
        if os.path.exists(activate_script):
            command = f"source {activate_script} && exec {sys.executable} {' '.join(sys.argv)}"
            subprocess.run(command, shell=True, executable='/bin/zsh')
            sys.exit(0)
        else:
            logging.error(f"Activate script not found at {activate_script}")
            sys.exit(1)
    logging.info("Verifying virtual environment...")

def install_missing_modules(required_modules):
    logging.info("Checking dependencies...")
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            logging.info(f"Installing missing module: {module}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", module])
                logging.info(f"Successfully installed {module}")
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to install {module}: {e}")
                sys.exit(1)

def get_youtube_api_key():
    api_key_file = '.yt_api_key'
    if os.path.exists(api_key_file):
        with open(api_key_file, 'r') as file:
            return file.read().strip()
    else:
        api_key = input("Enter your YouTube API key: ").strip()
        with open(api_key_file, 'w') as file:
            file.write(api_key)
        return api_key

def get_channel_id(youtube, channel_url):
    if '@' not in channel_url:
        raise ValueError("Invalid YouTube channel URL format.")
    channel_handle = channel_url.split('@')[1].split('/')[0]
    request = youtube.search().list(part="snippet", q=channel_handle, type="channel")
    response = request.execute()
    if not response['items']:
        raise ValueError("Could not find channel ID using the provided handle.")
    return response['items'][0]['snippet']['channelId']

def get_playlist_id(playlist_url):
    if 'list=' not in playlist_url:
        raise ValueError("Invalid YouTube playlist URL format.")
    return playlist_url.split('list=')[1]

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
    request = youtube.videos().list(part="snippet,contentDetails", id=video_id)
    response = request.execute()
    if not response['items']:
        return None
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
        from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([entry['text'] for entry in transcript_list])
    except (TranscriptsDisabled, NoTranscriptFound):
        logging.warning(f"Transcript not available for video {video_id}")
        return "Transcript not available."
    except Exception as e:
        logging.error(f"Error getting transcript for video {video_id}: {str(e)}")
        return f"Error getting transcript: {str(e)}"

def save_video_info(folder_name, video_info, transcript):
    title = video_info['title']
    published_at = video_info['published_at']
    video_url = video_info['url']
    description = video_info['description']
    
    date_str = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
    safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c == ' ']).rstrip()
    filename = f"{date_str} {safe_title}.txt"
    
    downloads_path = os.path.join(os.path.expanduser("~"), "Downloads", folder_name)
    if not os.path.exists(downloads_path):
        os.makedirs(downloads_path)
    
    with open(os.path.join(downloads_path, filename), 'w', encoding='utf-8') as file:
        file.write(f"Title: {title}\n")
        file.write(f"Published At: {published_at}\n")
        file.write(f"URL: {video_url}\n")
        file.write(f"Description: {description}\n")
        file.write(f"Transcript: {transcript}\n")

def main():
    logging.info("Starting script...")
    verify_virtualenv()
    logging.info("Virtual environment verified.")
    
    required_modules = ['requests', 'bs4', 'googleapiclient', 'youtube_transcript_api']
    install_missing_modules(required_modules)

    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        youtube_api_key = get_youtube_api_key()
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        
        url_input = input("Enter your YouTube channel or playlist URL: ").strip()
        
        if 'list=' in url_input:
            playlist_id = get_playlist_id(url_input)
            video_ids = get_playlist_video_ids(youtube, playlist_id)
            folder_name = input("Enter a folder name for the playlist: ").strip()
            logging.info(f"Found {len(video_ids)} videos in the playlist.")
        else:
            channel_id = get_channel_id(youtube, url_input)
            
            channel_request = youtube.channels().list(part="statistics", id=channel_id)
            channel_response = channel_request.execute()
            video_count = int(channel_response['items'][0]['statistics']['videoCount'])
            
            logging.info(f"The channel has {video_count} videos.")
            confirm = input("Do you want to proceed with processing these videos? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                logging.info("Operation cancelled by the user.")
                return
            
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
            
            folder_name = input("Enter a folder name for the channel: ").strip()
            logging.info(f"Found {len(video_ids)} videos in the channel.")
        
        confirm = input("Do you want to proceed with processing these videos? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            logging.info("Operation cancelled by the user.")
            return

        for idx, video_id in enumerate(video_ids, start=1):
            try:
                logging.info(f"Processing video {idx}/{len(video_ids)}...")
                video_info = get_video_details(youtube, video_id)
                if video_info:
                    transcript = get_video_transcript(video_id)
                    save_video_info(folder_name, video_info, transcript)
                else:
                    logging.warning(f"Could not get details for video {video_id}")
            except Exception as e:
                logging.error(f"Error processing video {video_id}: {str(e)}")
                continue  # Continue with the next video

    except HttpError as e:
        logging.error(f"An HTTP error occurred: {e}")
    except ValueError as e:
        logging.error(f"Value error: {e}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
