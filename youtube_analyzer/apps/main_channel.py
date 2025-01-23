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
    "CNBC": "@CNBCtelevision"
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

def list_channel_videos(channel_name: str, last_n_days: Optional[int] = None):
    """List videos from a channel with optional date filtering"""
    try:
        client = initialize_channel_client(channel_name)
        date_filter = DateFilter()
        
        # Get date parameters based on filter type
        if last_n_days == 1:  # today
            date_params = date_filter.today()
        elif last_n_days:
            date_params = date_filter.from_days_ago(last_n_days)
        else:
            date_params = {}
            
        # Update videos with date filtering (already sorted by date, newest first)
        new_videos = client.update_video_ids(
            published_after=date_params.get('publishedAfter'),
            published_before=date_params.get('publishedBefore')
        )
        
        print(f"\nVideos from channel: {client.channel_metadata.get('title', channel_name)}")
        print("=" * 50)
        
        # Print videos in order returned by API (already newest first)
        for video_id in new_videos:
            vclient = client.create_or_get_video_client(video_id)
            print(f"{vclient.published_at.strftime('%Y-%m-%d')} - {vclient.title}")
            print(f"https://youtube.com/watch?v={video_id}")
            print()
            
    except Exception as e:
        logger.error(f"Error listing channel videos: {str(e)}")
        raise

def main():
    """Main entry point with command line argument parsing"""
    import argparse

    parser = argparse.ArgumentParser(description="List YouTube channel videos")
    parser.add_argument(
        "-c", "--channel",
        help="YouTube channel name (e.g., @lexfridman) or preset name (Lex Fridman, Joe Rogan, CNBC)"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days to look back (default: list all videos)",
        default=None
    )
    parser.add_argument(
        "--today",
        action="store_true",
        help="List only today's videos"
    )

    args = parser.parse_args()

    # Handle preset channels
    channel_name = args.channel
    if channel_name in PRESET_CHANNELS:
        channel_name = PRESET_CHANNELS[channel_name]

    # Handle date filtering
    last_n_days = None
    if args.today:
        last_n_days = 1
    elif args.days:
        last_n_days = args.days

    list_channel_videos(
        channel_name=channel_name,
        last_n_days=last_n_days
    )

if __name__ == "__main__":
    main() 