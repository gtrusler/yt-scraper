import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Constants
YOUTUBE_API_KEY = 'YOUR_YOUTUBE_API_KEY'
YOUTUBE_CHANNEL_URL = 'YOUR_YOUTUBE_CHANNEL_URL'

def get_channel_id(channel_url):
    response = requests.get(channel_url)
    if response.status_code != 200:
        raise ValueError("Invalid YouTube channel URL or network issue.")
    soup = BeautifulSoup(response.text, 'html.parser')
    channel_id = soup.find('meta', itemprop='channelId')['content']
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
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        channel_id = get_channel_id(YOUTUBE_CHANNEL_URL)
        
        request = youtube.search().list(
            part="id",
            channelId=channel_id,
            maxResults=50
        )
        response = request.execute()
        
        video_ids = [item['id']['videoId'] for item in response['items'] if item['id']['kind'] == 'youtube#video']
        
        channel_name = YOUTUBE_CHANNEL_URL.split('/')[-1]
        
        for video_id in video_ids:
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
