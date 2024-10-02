import os
import logging
from googleapiclient.discovery import build
from typing import Optional

class YouTubeBase:
    def __init__(self, api_key: Optional[str] = None, timezone: str = 'America/Chicago'):
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("No API key found. Provide an API key or set the YOUTUBE_API_KEY environment variable.")
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self.timezone = timezone
        
        # Create a logger for this class
        self.logger = logging.getLogger(self.__class__.__name__)

    def execute_api_request(self, request):
        try:
            return request.execute()
        except Exception as e:
            self.logger.error(f"Error executing API request: {str(e)}")
            raise

    def create_search_request(self, **kwargs):
        return self.youtube.search().list(**kwargs)

    def create_videos_request(self, **kwargs):
        return self.youtube.videos().list(**kwargs)

    def create_channels_request(self, **kwargs):
        return self.youtube.channels().list(**kwargs)