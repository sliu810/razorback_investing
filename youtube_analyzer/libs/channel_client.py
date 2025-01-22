from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pytz
from googleapiclient.discovery import build
import logging
from .utils import DateFilter
from .llm_processor import LLMConfig, Task
from .video_client import YouTubeVideoClient
from .youtube_api_client import YouTubeAPIClient

logger = logging.getLogger(__name__)

class BaseChannelClient:
    """Base client for managing video collections and analysis
    
    This is the base class for both YouTube channels and virtual collections.
    """
    
    def __init__(self, name: str, youtube_api_key: str = None, timezone: str = 'America/Chicago'):
        self.name = name
        self.timezone = pytz.timezone(timezone)
        
        # Core state
        self.channel_metadata: Dict = {}
        self.video_ids: List[str] = []
        self.video_metadata: Dict[str, Dict] = {}
        
        # Video clients cache
        self._video_clients: Dict[str, YouTubeVideoClient] = {}
        
        # Shared processor configurations
        self._processors: Dict[str, LLMConfig] = {}
        
        # Last update tracking
        self.last_update: Optional[datetime] = None
        
        # Initialize YouTube API client with optional key
        self.youtube_api_client = YouTubeAPIClient(api_key=youtube_api_key)

    def update_video_ids(
        self, 
        published_after: Optional[str] = None,
        published_before: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[str]:
        """Fetch and update video IDs with optional date filters and search query
        
        Args:
            published_after: Optional RFC 3339 formatted date (e.g., '2024-01-01T00:00:00Z')
            published_before: Optional RFC 3339 formatted date (e.g., '2024-01-01T00:00:00Z')
            query: Optional search query string to filter videos
            
        Examples:
            # Get all videos
            channel.update_video_ids()
            
            # Get videos since a week ago using DateFilter
            df = DateFilter(timezone='America/Chicago')
            params = df.from_days_ago(7)
            channel.update_video_ids(
                published_after=params['publishedAfter'],
                published_before=params.get('publishedBefore')
            )
        """
        search_params = {}
        
        if published_after:
            search_params['publishedAfter'] = published_after
        if published_before:
            search_params['publishedBefore'] = published_before
        if query:
            search_params['q'] = query

        new_video_ids = []
        page_token = None
        
        while True:
            try:
                request = self.youtube_api_client.create_search_request(
                    part="id",
                    channelId=self.channel_id,
                    type="video",
                    order="date",
                    maxResults=50,
                    pageToken=page_token,
                    **search_params
                )
                
                response = self.youtube_api_client.execute_api_request(request)
                
                for item in response.get('items', []):
                    video_id = item['id']['videoId']
                    if video_id not in self.video_ids:
                        new_video_ids.append(video_id)
                        self.video_ids.append(video_id)
                    
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching videos: {e}")
                break

        self.last_update = datetime.now(pytz.UTC)
        return new_video_ids

    def create_or_get_video_client(self, video_id: str) -> YouTubeVideoClient:
        """Get existing or create new video client for specific video
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            YouTubeVideoClient: Configured video client with channel's API key and processors
        """
        if video_id not in self._video_clients:
            client = YouTubeVideoClient(
                video_id=video_id,
                youtube_api_key=self.youtube_api_key
            )
            
            # Add any channel-level processors
            for name, config in self._processors.items():
                client.add_processor(name, config)
                
            self._video_clients[video_id] = client
            
        return self._video_clients[video_id]

    def analyze_videos(self, 
                      video_ids: Optional[List[str]] = None,
                      processor_names: Optional[List[str]] = None,
                      task: Optional[Task] = None) -> Dict[str, List]:
        """Analyze multiple videos"""
        if video_ids is None:
            video_ids = self.video_ids
            
        if not task:
            task = Task.summarize()
            
        results = {}
        for video_id in video_ids:
            try:
                client = self.create_or_get_video_client(video_id)
                analysis = client.analyze_video(
                    processor_names=processor_names,
                    task=task
                )
                results[video_id] = analysis
            except Exception as e:
                logger.error(f"Error analyzing video {video_id}: {e}")
                results[video_id] = []
                
        return results

    def add_processor(self, name: str, config: LLMConfig) -> None:
        """Add processor configuration"""
        self._processors[name] = config
        
        # Add to existing video clients
        for client in self._video_clients.values():
            client.add_processor(name, config)

    def get_processors(self) -> Dict[str, LLMConfig]:
        """Get all processor configurations"""
        return self._processors.copy()

    def to_dict(self) -> Dict:
        """Serialize channel state"""
        return {
            'name': self.name,
            'channel_metadata': self.channel_metadata,
            'video_ids': self.video_ids,
            'video_metadata': self.video_metadata,
            'processors': self._processors,
            'last_update': self.last_update.isoformat() if self.last_update else None
        }

    def update_from_dict(self, data: Dict) -> None:
        """Update channel state from serialized data"""
        self.name = data['name']
        self.channel_metadata = data.get('channel_metadata', {})
        self.video_ids = data.get('video_ids', [])
        self.video_metadata = data.get('video_metadata', {})
        self._processors = data.get('processors', {})
        if data.get('last_update'):
            self.last_update = datetime.fromisoformat(data['last_update'])


class YouTubeChannelClient(BaseChannelClient):
    """Client for managing YouTube channel analysis"""
    
    def __init__(self, channel_id: str, youtube_api_key: str, timezone: str = 'America/Chicago'):
        super().__init__(name=channel_id, timezone=timezone)
        self.channel_id = channel_id
        self.youtube_api_key = youtube_api_key
        self._fetch_channel_metadata()

    def _fetch_channel_metadata(self) -> None:
        """Fetch basic channel information"""
        try:
            request = self.youtube_api_client.create_channels_request(
                part="snippet,statistics",
                id=self.channel_id
            )
            response = self.youtube_api_client.execute_api_request(request)
            
            if not response.get('items'):
                logger.error(f"No channel found for ID: {self.channel_id}")
                self.channel_metadata = {
                    'title': 'Unknown Channel',
                    'description': '',
                    'subscriber_count': 0,
                    'video_count': 0,
                    'view_count': 0
                }
                return
                
            channel_data = response['items'][0]
            self.channel_metadata = {
                'title': channel_data['snippet']['title'],
                'description': channel_data['snippet']['description'],
                'subscriber_count': channel_data['statistics'].get('subscriberCount', '0'),
                'video_count': channel_data['statistics'].get('videoCount', '0'),
                'view_count': channel_data['statistics'].get('viewCount', '0')
            }
                
        except Exception as e:
            logger.error(f"Failed to fetch channel metadata: {str(e)}")
            # Set default metadata instead of raising
            self.channel_metadata = {
                'title': 'Unknown Channel',
                'description': '',
                'subscriber_count': 0,
                'video_count': 0,
                'view_count': 0
            }

    def create_or_get_video_client(self, video_id: str) -> YouTubeVideoClient:
        """Get existing or create new video client for specific video"""
        if video_id not in self._video_clients:
            client = YouTubeVideoClient(
                video_id=video_id,
                youtube_api_key=self.youtube_api_key
            )
            
            # Add any channel-level processors
            for name, config in self._processors.items():
                client.add_processor(name, config)
                
            self._video_clients[video_id] = client
            
        return self._video_clients[video_id]


class VirtualChannelClient(BaseChannelClient):
    """Client for custom video collections"""
    
    def __init__(self, name: str, video_ids: List[str], youtube_api_key: str, timezone: str = 'America/Chicago'):
        super().__init__(name=name, timezone=timezone)
        self.youtube_api_key = youtube_api_key
        self.video_ids = video_ids.copy()

    def create_or_get_video_client(self, video_id: str) -> YouTubeVideoClient:
        """Get existing or create new video client for specific video"""
        if video_id not in self._video_clients:
            client = YouTubeVideoClient(
                video_id=video_id,
                youtube_api_key=self.youtube_api_key
            )
            
            # Add any channel-level processors
            for name, config in self._processors.items():
                client.add_processor(name, config)
                
            self._video_clients[video_id] = client
            
        return self._video_clients[video_id]


class ChannelClientFactory:
    """Factory for creating channel clients"""
    
    @staticmethod
    def create_channel(channel_type: str, **kwargs) -> BaseChannelClient:
        """Create appropriate channel client
        
        Args:
            channel_type: "youtube" or "virtual"
            **kwargs: Arguments for specific channel type
        
        Returns:
            BaseChannelClient instance
        """
        if channel_type == "youtube":
            return YouTubeChannelClient(
                channel_id=kwargs['channel_id'],
                youtube_api_key=kwargs['youtube_api_key'],
                timezone=kwargs.get('timezone', 'America/Chicago')
            )
        elif channel_type == "virtual":
            return VirtualChannelClient(
                name=kwargs['name'],
                video_ids=kwargs['video_ids'],
                youtube_api_key=kwargs['youtube_api_key'],
                timezone=kwargs.get('timezone', 'America/Chicago')
            )
        else:
            raise ValueError(f"Unsupported channel type: {channel_type}") 