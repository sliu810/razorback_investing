import os
import logging
from googleapiclient.discovery import build
from typing import Optional

class YouTubeAPIClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("No API key found. Provide an API key or set the YOUTUBE_API_KEY environment variable.")
        
        # Build the YouTube service
        self.youtube = build('youtube', 'v3', developerKey=self.api_key, cache_discovery=False)
        
        # Create a logger for this class
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_channel_id(self, username: str) -> str:
        """
        Retrieve the YouTube channel ID for a given username/handle.
        
        Args:
            username: Channel username/handle (with or without @)
        
        Returns:
            str: YouTube channel ID
            
        Raises:
            ValueError: If channel not found or API error occurs
        """
        # Remove @ if present
        username = username.strip('@')
        
        request = self.youtube.channels().list(
            part="id",
            forHandle=username
        )
        
        try:
            response = self.execute_api_request(request)
            if "items" in response and len(response["items"]) > 0:
                return response["items"][0]["id"]
            else:
                raise ValueError(f"No channel found for @{username}")
        except Exception as e:
            raise ValueError(f"Error fetching channel ID: {str(e)}")

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