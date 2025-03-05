"""
Main script for listing YouTube channel videos with date filtering
"""

import os
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from ..libs.channel_client import ChannelClientFactory
from ..libs.utils import DateFilter
from ..libs.youtube_api_client import YouTubeAPIClient
from ..libs.channel_client import YouTubeChannelClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add after imports
PRESET_CHANNELS = {
    "Lex Fridman": "@lexfridman",
    "Joe Rogan": "@joerogan",
    "CNBC": "@CNBCtelevision",
    "AI Explained": "@aiexplained-official",
    "Bloomberg Podcasts": "@BloombergPodcasts"
}

def initialize_channel_client(channel_name: str):
    """Initialize YouTube channel client"""
    try:
        api_client = YouTubeAPIClient()
        channel_id = api_client.get_channel_id(channel_name)
        
        return YouTubeChannelClient(channel_id=channel_id)
        
    except Exception as e:
        logger.error(f"Error initializing channel client: {str(e)}")
        raise

def list_channel_videos(channel_handle: str, days: Optional[int] = None, today: bool = False):
    """List videos from specified channel with optional date filtering"""
    try:
        # Suppress googleapiclient.discovery_cache logs
        logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.WARNING)
        # Suppress youtube_analyzer.libs logs
        logging.getLogger('youtube_analyzer.libs').setLevel(logging.WARNING)
        
        client = initialize_channel_client(channel_handle)
        
        # Configure date filter
        date_filter = DateFilter()
        if today:
            date_params = date_filter.today()
        elif days:
            date_params = date_filter.from_days_ago(days)
        else:
            date_params = {}
            
        # Get videos
        video_ids = client.update_video_ids(
            published_after=date_params.get('publishedAfter'),
            published_before=date_params.get('publishedBefore')
        )
        
        # Clean display format
        print(f"\nVideos from channel: {channel_handle}")
        print("=" * 50)
        
        for vid_id in video_ids:
            video = client.create_or_get_video_client(vid_id)
            print(f"{video.published_at.strftime('%Y-%m-%d')} | {video.title}")
            print(f"https://youtube.com/watch?v={vid_id}")
            print()  # Empty line between videos
            
    except Exception as e:
        logger.error(f"Error listing videos: {e}")
        return None

def main():
    """Main entry point with command line argument parsing"""
    import argparse

    parser = argparse.ArgumentParser(
        description="List YouTube channel videos",
        epilog="""
Examples:
  python -m youtube_analyzer.apps.channel -c "@CNBCtelevision" --today
  python -m youtube_analyzer.apps.channel -c "BloombergPodcasts" --days 7
  python -m youtube_analyzer.apps.channel -c "@lexfridman"  # lists all videos
        """
    )
    parser.add_argument(
        "-c", "--channel",
        help="YouTube channel name (e.g., @lexfridman) or preset name (Lex Fridman, Joe Rogan, CNBC)",
        required=True
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days to look back (note: cannot be used with --today)",
        default=None
    )
    parser.add_argument(
        "--today",
        action="store_true",
        help="List only today's videos (note: cannot be used with --days)"
    )

    args = parser.parse_args()
    
    if not args.channel:
        parser.error("Channel name or handle is required")
        
    # Convert preset names to handles if needed
    channel_handle = PRESET_CHANNELS.get(args.channel, args.channel)
    
    list_channel_videos(
        channel_handle=channel_handle,
        days=args.days,
        today=args.today
    )

if __name__ == "__main__":
    main() 