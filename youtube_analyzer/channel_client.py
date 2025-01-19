from typing import Dict, List, Optional, Set
from datetime import datetime
import pytz
import logging
from youtube_api_client import YouTubeAPIClient
from video_client import YouTubeVideoClient
from llm_processor import LLMProcessor, LLMConfig, Role, Task

logger = logging.getLogger(__name__)

class YouTubeChannelClient:
    """Client for managing YouTube channel analysis with multiple LLM processors
    
    Example:
        >>> # Initialize client
        >>> client = YouTubeChannelClient(
        ...     channel_id="UCxxx",
        ...     youtube_api_key="your_api_key"
        ... )
        >>> 
        >>> # Fetch videos with criteria
        >>> client.fetch_videos(
        ...     start_date=datetime(2024, 1, 1),
        ...     title_contains="AI"
        ... )
        >>> 
        >>> # Add processor and analyze
        >>> client.add_processor("claude", claude_config)
        >>> results = client.analyze_videos(task=Task.summarize())
    """
    
    def __init__(self, channel_id: str, youtube_api_key: str):
        """Initialize YouTube channel client
        
        Args:
            channel_id: YouTube channel ID
            youtube_api_key: YouTube Data API key
        """
        self.channel_id = channel_id
        self.youtube_api_client = YouTubeAPIClient(youtube_api_key)
        self.video_ids: List[str] = []
        self.video_metadata: Dict[str, Dict] = {}
        self._video_clients: Dict[str, YouTubeVideoClient] = {}
        self._processors: Dict[str, LLMConfig] = {}
        
    def fetch_videos(self, 
                    start_date: Optional[datetime] = None,
                    end_date: Optional[datetime] = None,
                    title_contains: Optional[str] = None,
                    max_results: Optional[int] = None) -> List[str]:
        """Fetch videos matching criteria and store their metadata
        
        Args:
            start_date: Filter videos published after this date
            end_date: Filter videos published before this date
            title_contains: Filter videos with titles containing this string
            max_results: Maximum number of videos to fetch
            
        Returns:
            List of video IDs matching criteria
        """
        self.video_ids = []
        self.video_metadata = {}
        page_token = None
        
        while True:
            request = self.youtube_api_client.create_search_request(
                part="id,snippet",
                channelId=self.channel_id,
                type="video",
                publishedAfter=start_date.astimezone(pytz.UTC).isoformat() if start_date else None,
                publishedBefore=end_date.astimezone(pytz.UTC).isoformat() if end_date else None,
                q=title_contains,
                maxResults=min(50, max_results) if max_results else 50,
                pageToken=page_token
            )
            
            response = self.youtube_api_client.execute_api_request(request)
            
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                self.video_ids.append(video_id)
                self.video_metadata[video_id] = {
                    'title': item['snippet']['title'],
                    'published_at': item['snippet']['publishedAt'],
                    'description': item['snippet']['description'],
                    'channel_title': item['snippet']['channelTitle']
                }
                
                if max_results and len(self.video_ids) >= max_results:
                    return self.video_ids
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
                
        return self.video_ids

    def add_processor(self, name: str, config: LLMConfig) -> None:
        """Add an LLM processor configuration
        
        Args:
            name: Identifier for the processor
            config: LLM configuration
        """
        self._processors[name] = config
        # Add to existing video clients
        for client in self._video_clients.values():
            client.add_processor(name, config)

    def get_video_client(self, video_id: str) -> YouTubeVideoClient:
        """Get or create a video client with channel-level processors
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            YouTubeVideoClient configured with channel-level processors
        """
        if video_id not in self._video_clients:
            client = YouTubeVideoClient(video_id)
            # Add channel-level processors
            for name, config in self._processors.items():
                client.add_processor(name, config)
            self._video_clients[video_id] = client
        return self._video_clients[video_id] 