"""
Main script for listing YouTube channel videos with date filtering
"""

import os
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from .channel_client import ChannelClientFactory
from .utils import DateFilter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def list_channel_videos(channel_name: str, last_n_days: Optional[int] = None) -> None:
    """
    List videos from a YouTube channel with optional date filtering

    Args:
        channel_name: Name of the YouTube channel (e.g., @lexfridman)
        last_n_days: Number of days to look back (None for all videos)
    """
    try:
        # Initialize date filter if last_n_days is specified
        date_filter = None
        if last_n_days is not None:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=last_n_days)
            date_filter = DateFilter(start_date=start_date, end_date=end_date)
            logger.info(f"Listing videos from {start_date.date()} to {end_date.date()}")
        
        # Create channel URL from name
        channel_url = f"https://youtube.com/{channel_name}"
        
        # Create channel client
        client = ChannelClientFactory.create_client(
            channel_url=channel_url,
            youtube_api_key=os.getenv("YOUTUBE_API_KEY")
        )

        # Get videos
        videos = client.get_videos(date_filter=date_filter)

        # Print results
        print(f"\nVideos from channel: {client.channel_name}")
        print("=" * 50)
        for video in videos:
            print(f"\nTitle: {video.title}")
            print(f"URL: https://youtube.com/watch?v={video.video_id}")
            print(f"Published: {video.published_at.strftime('%Y-%m-%d')}")
            print("-" * 50)

    except Exception as e:
        logger.error(f"Error listing channel videos: {e}", exc_info=True)
        raise

def main():
    """Main entry point with command line argument parsing"""
    import argparse

    parser = argparse.ArgumentParser(description="List YouTube channel videos")
    parser.add_argument(
        "-c", "--channel",
        required=True,
        help="YouTube channel name (e.g., @lexfridman)"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days to look back (default: list all videos)",
        default=None
    )

    args = parser.parse_args()

    list_channel_videos(
        channel_name=args.channel,
        last_n_days=args.days
    )

if __name__ == "__main__":
    main() 