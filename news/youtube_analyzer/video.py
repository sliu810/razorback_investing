import logging
from datetime import datetime
import pytz
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from utils import iso_duration_to_minutes, sanitize_filename
from youtube_api_client import YouTubeAPIClient
import os
import json
from typing import Optional, Tuple, Union, Dict
import time

class Video:
    def __init__(self, video_id: str, transcript_language: str = 'en', timezone: str = 'America/Chicago'):
        self.video_id: str = video_id
        self.youtube_api_client: YouTubeAPIClient = YouTubeAPIClient()
        self.transcript_language: str = transcript_language
        self.timezone = pytz.timezone(timezone)
        self.title: Optional[str] = None
        self.published_at: Optional[datetime] = None
        self.duration_minutes: Optional[float] = None
        self.channel_id: Optional[str] = None
        self.channel_name: Optional[str] = None
        self.transcript: Optional[Tuple[str, str]] = None
        self._info_fetched: bool = False
        self.metadata: Dict = {}

    def fetch_video_info(self) -> bool:
        if self._info_fetched:
            return True

        try:
            video_request = self.youtube_api_client.create_videos_request(
                part="snippet,contentDetails",
                id=self.video_id
            )
            video_response = self.youtube_api_client.execute_api_request(video_request)

            if not video_response['items']:
                self.youtube_api_client.logger.warning(f"No video found for ID: {self.video_id}")
                return False

            video_data = video_response['items'][0]
            snippet = video_data['snippet']
            content_details = video_data['contentDetails']

            self.published_at = datetime.strptime(
                snippet['publishedAt'], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=pytz.UTC).astimezone(self.timezone)

            self.title = snippet['title']
            self.duration_minutes = iso_duration_to_minutes(content_details['duration'])
            self.channel_id = snippet['channelId']
            self.channel_name = snippet['channelTitle']
            self.transcript = self.get_transcript()

            self._info_fetched = True
            return True
        except Exception as e:
            self.youtube_api_client.logger.error(f"An error occurred while fetching video info for {self.video_id}: {str(e)}")
            return False

    def get_video_title(self) -> Optional[str]:
        if not self._info_fetched:
            self.fetch_video_info()
        return self.title

    def to_dict(self) -> dict:
        if not self._info_fetched:
            self.fetch_video_info()
        
        return {
            'Video ID': self.video_id,
            'Title': self.title,
            'Published At': self.published_at.isoformat() if self.published_at else None,
            'Duration (minutes)': self.duration_minutes,
            'Channel ID': self.channel_id,
            'Channel Name': self.channel_name,
            'Transcript': self.transcript
        }

    def _transform_transcript_for_readability(self, transcript: str, language: str) -> str:
        if not transcript or language != 'en':
            return transcript

        def is_all_caps(text):
            return text.isupper() and any(c.isalpha() for c in text)

        if is_all_caps(transcript):
            sentences = transcript.capitalize().split('. ')
            transformed_transcript = '. '.join(sentence.capitalize() for sentence in sentences)
            return transformed_transcript

        return transcript

    def get_transcript(self) -> Tuple[Optional[str], Optional[str]]:
        # First check if we already have the transcript
        if self.transcript is not None:
            logging.debug(f"Returning cached transcript for video {self.video_id}")
            return self.transcript

        logging.debug(f"Fetching transcript from YouTube API for video {self.video_id}")
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(self.video_id)
            
            try:
                transcript = transcript_list.find_transcript([self.transcript_language])
            except NoTranscriptFound:
                if self.transcript_language != 'en':
                    self.youtube_api_client.logger.warning(f"{self.transcript_language.upper()} transcript not found for video ID: {self.video_id}. Falling back to English.")
                    transcript = transcript_list.find_transcript(['en'])
                else:
                    raise

            full_transcript = ' '.join([entry['text'] for entry in transcript.fetch()])
            transformed_transcript = self._transform_transcript_for_readability(full_transcript, transcript.language_code)
            
            self.transcript = (transformed_transcript, transcript.language_code)  # Cache the result
            logging.debug(f"Successfully fetched and cached transcript for video {self.video_id}")
            return self.transcript
        except (TranscriptsDisabled, NoTranscriptFound):
            self.youtube_api_client.logger.warning(f"No transcript available for video ID: {self.video_id}")
            self.transcript = (None, None)  # Cache the negative result
            return None, None
        except Exception as e:
            self.youtube_api_client.logger.error(f"An error occurred while fetching transcript for {self.video_id}: {str(e)}")
            self.transcript = (None, None)  # Cache the negative result
            return None, None

    def serialize_video_to_file(self, root_dir: str) -> Optional[str]:
        if not self._info_fetched:
            self.fetch_video_info()

        if not self.title:
            self.youtube_api_client.logger.warning(f"No video info available to save for video ID: {self.video_id}")
            return None

        transcript_language = self.transcript[1] if self.transcript else 'en'
        valid_title = sanitize_filename(self.title, max_length=100)

        file_name = f"{valid_title}_{transcript_language}.json"
        file_path = os.path.join(root_dir, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        
        return file_path

    def set_published_at(self, value: Union[str, datetime]):
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        self.published_at = value

    @classmethod
    def from_json_file(cls, file_path: str) -> 'Video':
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        video = cls(video_id=data['Video ID'])
        video.title = data['Title']
        video.duration_minutes = data['Duration (minutes)']
        video.channel_id = data['Channel ID']
        video.channel_name = data['Channel Name']
        video.transcript = data['Transcript']
        
        if data['Published At']:
            video.set_published_at(data['Published At'])
        
        video._info_fetched = True  # Mark as fetched since we have the data
        return video

    def fetch_transcript(self, max_retries: int = 3, retry_delay: float = 1.0) -> bool:
        """Fetch transcript with retries"""
        for attempt in range(max_retries):
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(self.video_id)
                
                # Verify transcript is not empty
                if not transcript_list:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return False
                
                # Combine transcript pieces
                full_transcript = ""
                for entry in transcript_list:
                    if 'text' in entry:
                        full_transcript += entry['text'] + " "
                
                # Verify final transcript is not empty
                if not full_transcript.strip():
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return False
                
                self.transcript = full_transcript.strip()
                return True
                
            except (TranscriptsDisabled, NoTranscriptFound) as e:
                print(f"No transcript available: {str(e)}")
                return False
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return False
        
        return False

    def update_metadata(self, metadata: Dict):
        """Update video metadata"""
        self.metadata = metadata
        self.title = metadata.get('title', '')
        self.description = metadata.get('description', '')
        duration = metadata.get('duration', 'PT0M')
        self.duration_minutes = iso_duration_to_minutes(duration)