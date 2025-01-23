import os
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Optional, List, Dict, Any
import re

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
    _working_key = None  # Class level variable
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize YouTube API client with multiple API keys"""
        # If we already have a working key, use it directly
        if YouTubeAPIClient._working_key:
            self._youtube = build('youtube', 'v3', developerKey=YouTubeAPIClient._working_key)
            self._current_key = YouTubeAPIClient._working_key
            return
            
        # Otherwise proceed with normal initialization
        self._primary_key = api_key or os.getenv('YOUTUBE_API_KEY')
        self._secondary_key = os.getenv('YOUTUBE_API_KEY_2')
        self._tertiary_key = os.getenv('YOUTUBE_API_KEY_3')  # Add tertiary key
        logger.info(f"Primary key available: {bool(self._primary_key)}")
        logger.info(f"Secondary key available: {bool(self._secondary_key)}")
        logger.info(f"Tertiary key available: {bool(self._tertiary_key)}")  # Add log
        self._current_key = None
        self._tried_keys = set()
        
        if not self._primary_key:
            raise ValueError("No primary API key found. Provide an API key or set the YOUTUBE_API_KEY environment variable")
        
        # Try primary key first
        logger.info("Trying primary key...")
        if self._try_key(self._primary_key):
            logger.info("Using primary key")
            return
            
        # If primary key fails and we have a secondary key, try that
        logger.info(f"Primary key failed, have secondary key: {bool(self._secondary_key)}")
        if self._secondary_key and self._try_key(self._secondary_key):
            logger.info("Using secondary key")
            return
            
        # If secondary key fails and we have a tertiary key, try that
        logger.info(f"Secondary key failed, have tertiary key: {bool(self._tertiary_key)}")
        if self._tertiary_key and self._try_key(self._tertiary_key):
            logger.info("Using tertiary key")
            return
            
        # If we get here, no keys worked
        raise YouTubeQuotaExceededError(
            "YouTube API quota exceeded. Try again tomorrow or use a different API key."
        )

    def _try_key(self, key: str) -> bool:
        """Try using an API key and return True if successful"""
        if key in self._tried_keys:
            return False
        
        self._tried_keys.add(key)
        try:
            # Only show first 4 and last 4 characters of the key
            masked_key = f"{key[:4]}...{key[-4:]}" if key else "None"
            logger.info(f"Testing API key: {masked_key}")
            self._youtube = build('youtube', 'v3', developerKey=key)
            test_request = self._youtube.search().list(
                part="id",  # Minimum required field
                maxResults=1,  # Just need one result
                q="test"  # Simple search term
            )
            test_request.execute()
            self._current_key = key
            YouTubeAPIClient._working_key = key
            return True
        
        except HttpError as e:
            if e.status_code == 403 and "quota" in str(e).lower():
                logger.info("API key out of quota")
                return False
            raise

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

    def execute_api_request(self, request):
        """Execute a YouTube API request with automatic key rotation on quota errors"""
        try:
            return request.execute()
        except HttpError as e:
            self._handle_api_error(e, "executing API request")

    def _rebuild_request(self, old_request):
        """Rebuild a request with the current API key"""
        # Get the same API endpoint
        api_name = old_request._methodId.split('.')[0]
        method = getattr(self._youtube, api_name)()
        # Copy the original request parameters
        return method.list(**old_request._developerKey_params)

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

    @staticmethod
    def parse_video_id(video_input: Optional[str]) -> str:
        """Extract YouTube video ID from various URL formats or return the ID if already in correct format.
        
        Args:
            video_input: YouTube video URL or ID
                Supported formats:
                - Full URL: https://www.youtube.com/watch?v=VIDEO_ID
                - Short URL: https://youtu.be/VIDEO_ID
                - Embed URL: https://www.youtube.com/embed/VIDEO_ID
                - Just the ID: VIDEO_ID (11 chars, alphanumeric with _ and -)
        
        Returns:
            str: YouTube video ID
        
        Raises:
            ValueError: If video ID cannot be extracted or doesn't match YouTube format
        """
        if not video_input:
            raise ValueError("No video ID or URL provided")

        # YouTube-specific ID validation (11 chars, alphanumeric with _ and -)
        youtube_id_pattern = r'^[0-9A-Za-z_-]{11}$'
        
        # If it's already just the ID
        if len(video_input) == 11 and re.match(youtube_id_pattern, video_input):
            return video_input
        
        # YouTube-specific URL patterns
        youtube_patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11}).*',  # Standard and embed URLs
            r'youtu\.be/([0-9A-Za-z_-]{11})',   # Short URLs
        ]
        
        for pattern in youtube_patterns:
            match = re.search(pattern, video_input)
            if match:
                video_id = match.group(1)
                # Double check the extracted ID matches YouTube format
                if re.match(youtube_id_pattern, video_id):
                    return video_id
        
        raise ValueError(
            f"Could not extract valid YouTube video ID from: {video_input}. "
            "YouTube IDs must be 11 characters long and contain only alphanumeric characters, underscores, and hyphens."
        )