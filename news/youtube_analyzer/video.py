import logging
from datetime import datetime
import pytz
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from utils import iso_duration_to_minutes, sanitize_filename
from youtube_api_client import YouTubeAPIClient
import os
import json
from typing import Optional, Tuple, Union, Dict, List

logger = logging.getLogger(__name__)

class Video:
    def __init__(self, video_id: str, transcript_language: str = 'en', timezone: str = 'America/Chicago'):
        self.video_id: str = video_id
        self.url: str = f"https://www.youtube.com/watch?v={video_id}"
        self.youtube_api_client: YouTubeAPIClient = YouTubeAPIClient()
        self.transcript_language: str = transcript_language
        self.timezone = pytz.timezone(timezone)
        self.title: Optional[str] = None
        self.published_at: Optional[datetime] = None
        self.duration_minutes: Optional[float] = None
        self.channel_id: Optional[str] = None
        self.channel_name: Optional[str] = None
        self.transcript: Optional[Tuple[str, str]] = None
        self._metadata_fetched: bool = False
        self._transcript_fetched: bool = False

    # Core data fetching methods
    def get_video_metadata(self) -> None:
        """Fetch basic video information from YouTube API"""
        try:
            video_request = self.youtube_api_client.create_videos_request(
                part="snippet,contentDetails",
                id=self.video_id
            )
            video_response = self.youtube_api_client.execute_api_request(video_request)

            if not video_response['items']:
                raise ValueError(f"No video found for ID: {self.video_id}")

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
            
            self._metadata_fetched = True

        except Exception as e:
            self._metadata_fetched = False
            logger.error(f"Failed to fetch video metadata for {self.video_id}: {str(e)}")
            raise

    def get_transcript(self) -> Tuple[Optional[str], Optional[str]]:
        """Fetch and process video transcript"""
        if self.transcript is not None and self._transcript_fetched:
            logger.debug(f"Returning cached transcript for video {self.video_id}")
            return self.transcript

        logger.debug(f"Fetching transcript from YouTube API for video {self.video_id}")
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(self.video_id)
            
            try:
                transcript = transcript_list.find_transcript([self.transcript_language])
            except NoTranscriptFound:
                if self.transcript_language != 'en':
                    logger.warning(f"{self.transcript_language.upper()} transcript not found for video ID: {self.video_id}. Falling back to English.")
                    transcript = transcript_list.find_transcript(['en'])
                else:
                    raise

            full_transcript = ' '.join([entry['text'] for entry in transcript.fetch()])
            transformed_transcript = self._transform_transcript_for_readability(full_transcript, transcript.language_code)
            
            self.transcript = (transformed_transcript, transcript.language_code)
            self._transcript_fetched = True
            logger.debug(f"Successfully fetched and cached transcript for video {self.video_id}")
            return self.transcript

        except (TranscriptsDisabled, NoTranscriptFound):
            logger.warning(f"No transcript available for video ID: {self.video_id}")
            self.transcript = (None, None)
            self._transcript_fetched = False
            return None, None
        except Exception as e:
            logger.error(f"An error occurred while fetching transcript for {self.video_id}: {str(e)}")
            self.transcript = (None, None)
            self._transcript_fetched = False
            return None, None

    def get_video_metadata_and_transcript(self) -> None:
        """Fetch both video metadata and transcript"""
        try:
            self.get_video_metadata()
            self.get_transcript()
        except Exception as e:
            logger.error(f"Failed to fetch video info and transcript for {self.video_id}: {str(e)}")
            raise

    # Helper methods
    def _transform_transcript_for_readability(self, transcript: str, language: str) -> str:
        """Transform transcript text for better readability"""
        if not transcript or language != 'en':
            return transcript

        def is_all_caps(text):
            return text.isupper() and any(c.isalpha() for c in text)

        if is_all_caps(transcript):
            sentences = transcript.capitalize().split('. ')
            transformed_transcript = '. '.join(sentence.capitalize() for sentence in sentences)
            return transformed_transcript

        return transcript

    # Serialization methods
    def to_dict(self) -> dict:
        """Convert video object to dictionary"""
        if not self._metadata_fetched:
            self.get_video_metadata_and_transcript()
        
        return {
            'Video ID': self.video_id,
            'URL': self.url,
            'Title': self.title,
            'Published At': self.published_at.isoformat() if self.published_at else None,
            'Duration (minutes)': self.duration_minutes,
            'Channel ID': self.channel_id,
            'Channel Name': self.channel_name,
            'Transcript': self.transcript
        }

    def serialize_video_to_file(self, root_dir: str) -> Optional[str]:
        """Save video information to a JSON file"""
        if not self._metadata_fetched:
            self.get_video_metadata_and_transcript()

        if not self.title:
            logger.warning(f"No video info available to save for video ID: {self.video_id}")
            return None

        transcript_language = self.transcript[1] if self.transcript else 'en'
        valid_title = sanitize_filename(self.title, max_length=100)

        file_name = f"{valid_title}_{transcript_language}.json"
        file_path = os.path.join(root_dir, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        
        return file_path

    @classmethod
    def from_json_file(cls, file_path: str) -> 'Video':
        """Create a Video object from a JSON file"""
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
        
        video._metadata_fetched = True
        video._transcript_fetched = bool(video.transcript and video.transcript[0])
        return video

    def set_published_at(self, value: Union[str, datetime]):
        """Set the published_at datetime from string or datetime object"""
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        self.published_at = value

    def __str__(self):
        """String representation of Video object"""
        return f"Video(id='{self.video_id}', title='{self.title}', url='{self.url}')"