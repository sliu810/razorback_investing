import os
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class YouTubeQuotaExceededError(Exception):
    """Raised when YouTube API quota is exceeded"""
    pass

class YouTubeVideoNotFoundError(Exception):
    """Raised when video is not found or has been removed"""
    pass

class YouTubePrivateVideoError(Exception):
    """Raised when video is private or requires authentication"""
    pass

class YouTubeRateLimitError(Exception):
    """Raised when requests are being rate limited"""
    pass

class YouTubeAPIClient:
    """Client for handling all YouTube API interactions"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize YouTube API client
        
        Args:
            api_key: YouTube API key. If not provided, will try to get from YOUTUBE_API_KEY env var
        """
        self._api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        if not self._api_key:
            raise ValueError("No API key found. Provide an API key or set the YOUTUBE_API_KEY environment variable")
        
        self._youtube = build('youtube', 'v3', developerKey=self._api_key)

    def _handle_api_error(self, error: HttpError, operation: str) -> None:
        """Centralized API error handling with detailed logging"""
        error_details = error.error_details[0] if error.error_details else {}
        error_reason = error_details.get('reason', 'unknown')
        error_domain = error_details.get('domain', 'unknown')
        
        logger.error(
            f"YouTube API Error during {operation}:\n"
            f"Status: {error.status_code}\n"
            f"Reason: {error_reason}\n"
            f"Domain: {error_domain}\n"
            f"Message: {str(error)}"
        )
        
        # Handle specific error cases
        if error.status_code == 403:
            if error_reason == "quotaExceeded":
                raise YouTubeQuotaExceededError(
                    "YouTube API quota exceeded. Try again tomorrow or use a different API key."
                ) from error
            elif error_reason == "rateLimitExceeded":
                raise YouTubeRateLimitError(
                    "Too many requests. Please wait before trying again."
                ) from error
        
        elif error.status_code == 404:
            raise YouTubeVideoNotFoundError(
                f"Video not found or has been removed: {str(error)}"
            ) from error
            
        elif error.status_code == 401:
            raise ValueError(
                "Invalid API key or authentication required"
            ) from error
            
        elif error.status_code == 400:
            if "private" in str(error).lower():
                raise YouTubePrivateVideoError(
                    "This video is private or requires authentication"
                ) from error
            raise ValueError(f"Invalid request: {str(error)}") from error
            
        # Generic error for unhandled cases
        raise error

    def get_video_metadata(self, video_id: str) -> Dict[str, Any]:
        """Get video metadata from YouTube API"""
        try:
            request = self._youtube.videos().list(
                part="snippet,contentDetails",
                id=video_id
            )
            response = request.execute()
            
            if not response.get('items'):
                raise YouTubeVideoNotFoundError(f"No video found with ID: {video_id}")
                
            return response['items'][0]
            
        except HttpError as e:
            self._handle_api_error(e, f"getting metadata for video {video_id}")

    def get_channel_videos(self, channel_id: str, **kwargs) -> List[Dict[str, Any]]:
        """Get channel videos from YouTube API"""
        try:
            request = self._youtube.search().list(
                part="snippet",
                channelId=channel_id,
                type="video",
                **kwargs
            )
            return request.execute()
        except HttpError as e:
            self._handle_api_error(e, f"listing videos for channel {channel_id}")

    def execute_api_request(self, request) -> Dict[str, Any]:
        """Execute a YouTube API request with error handling"""
        try:
            return request.execute()
        except HttpError as e:
            self._handle_api_error(e, "executing API request")

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
        
        request = self._youtube.channels().list(
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

    def create_search_request(self, **kwargs):
        return self._youtube.search().list(**kwargs)

    def create_videos_request(self, **kwargs):
        return self._youtube.videos().list(**kwargs)

    def create_channels_request(self, **kwargs):
        return self._youtube.channels().list(**kwargs)