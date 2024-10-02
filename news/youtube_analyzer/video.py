import logging
from datetime import datetime
import pytz
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from utils import iso_duration_to_minutes, sanitize_filename
from youtube_base import YouTubeBase
import os
import json
from typing import Optional, Dict, Tuple

class Video:
    def __init__(self, video_id: str, youtube_base: Optional[YouTubeBase] = None, transcript_language: str = 'en'):
        self.video_id = video_id
        self.youtube_base = youtube_base or YouTubeBase()
        self.transcript_language = transcript_language
        self.video_info: Optional[Dict] = None

    def fetch_video_info(self, transcript_language: Optional[str] = None) -> Optional[Dict]:
        if self.video_info is not None:
            return self.video_info

        try:
            video_request = self.youtube_base.create_videos_request(
                part="snippet,contentDetails",
                id=self.video_id
            )
            video_response = self.youtube_base.execute_api_request(video_request)

            if not video_response['items']:
                self.youtube_base.logger.warning(f"No video found for ID: {self.video_id}")
                return None

            video_data = video_response['items'][0]
            snippet = video_data['snippet']
            content_details = video_data['contentDetails']

            local_timezone = pytz.timezone(self.youtube_base.timezone)
            published_at = datetime.strptime(
                snippet['publishedAt'], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=pytz.UTC).astimezone(local_timezone)

            self.video_info = {
                'Video ID': self.video_id,
                'Title': snippet['title'],
                'Description': snippet['description'],
                'Published At': published_at,
                'Duration (minutes)': iso_duration_to_minutes(content_details['duration']),
                'Channel ID': snippet['channelId'],
                'Channel Name': snippet['channelTitle'],
                'Transcript': self.get_transcript(transcript_language)
            }
            return self.video_info
        except Exception as e:
            self.youtube_base.logger.error(f"An error occurred while fetching video info for {self.video_id}: {str(e)}")
            return None

    def get_video_title(self) -> Optional[str]:
        info = self.fetch_video_info()
        return info['Title'] if info else None

    def to_dict(self) -> Dict:
        if not self.video_info:
            self.fetch_video_info()
        
        serializable_info = self.video_info.copy() if self.video_info else {}
        
        if 'Published At' in serializable_info:
            serializable_info['Published At'] = serializable_info['Published At'].isoformat()
        
        return serializable_info

    def transform_transcript_for_readability(self, transcript: str, language: str) -> str:
        if not transcript or language != 'en':
            return transcript

        def is_all_caps(text):
            return text.isupper() and any(c.isalpha() for c in text)

        if is_all_caps(transcript):
            sentences = transcript.capitalize().split('. ')
            transformed_transcript = '. '.join(sentence.capitalize() for sentence in sentences)
            return transformed_transcript

        return transcript

    def get_transcript(self, transcript_language: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        transcript_language = transcript_language or self.transcript_language
        
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(self.video_id)
            
            try:
                transcript = transcript_list.find_transcript([transcript_language])
            except NoTranscriptFound:
                if transcript_language != 'en':
                    self.youtube_base.logger.warning(f"{transcript_language.upper()} transcript not found for video ID: {self.video_id}. Falling back to English.")
                    transcript = transcript_list.find_transcript(['en'])
                else:
                    raise

            full_transcript = ' '.join([entry['text'] for entry in transcript.fetch()])
            transformed_transcript = self.transform_transcript_for_readability(full_transcript, transcript.language_code)
            
            if self.video_info is not None:
                self.video_info['Transcript'] = (transformed_transcript, transcript.language_code)
            
            return transformed_transcript, transcript.language_code
        except (TranscriptsDisabled, NoTranscriptFound):
            self.youtube_base.logger.warning(f"No transcript available for video ID: {self.video_id}")
            
            if self.video_info is not None:
                self.video_info['Transcript'] = (None, None)
            
            return None, None
        except Exception as e:
            self.youtube_base.logger.error(f"An error occurred while fetching transcript for {self.video_id}: {str(e)}")
            
            if self.video_info is not None:
                self.video_info['Transcript'] = (None, None)
            
            return None, None

    def save_video_info_to_file(self, root_dir: str) -> Optional[str]:
        if not self.video_info:
            self.youtube_base.logger.warning(f"No video info available to save for video ID: {self.video_id}")
            return None

        title = self.video_info['Title']
        transcript_language = self.video_info.get('Transcript', [None, None])[1] or 'en'

        valid_title = sanitize_filename(title, max_length=100)

        file_name = f"{valid_title}_{transcript_language}.json"
        file_path = os.path.join(root_dir, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        serializable_info = self.to_dict()

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_info, f, ensure_ascii=False, indent=2)
        
        return file_path