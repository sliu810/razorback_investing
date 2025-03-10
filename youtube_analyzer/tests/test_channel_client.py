import pytest
from datetime import datetime, timedelta
import pytz

import os
from ..libs.channel_client import ChannelClientFactory
from ..libs.utils import DateFilter

@pytest.fixture
def youtube_channel():
    """Fixture providing configured YouTube channel client"""
    channel = ChannelClientFactory.create_channel(
        channel_type="youtube",
        channel_id="UCSHZKyawb77ixDdsGog4iWA",  # lex
    )
    return channel

@pytest.fixture
def date_filter():
    """Fixture providing DateFilter with Chicago timezone"""
    return DateFilter(timezone='America/Chicago')

@pytest.mark.parametrize("days", [1, 7, 30, 90])  # Test with different day ranges
def test_youtube_channel_last_n_days(youtube_channel, date_filter, days):
    """Test fetching videos from last N days
    
    Args:
        youtube_channel: YouTube channel fixture
        date_filter: Date filter fixture
        days: Number of days to look back
    """
    params = date_filter.from_days_ago(days)
    new_videos = youtube_channel.update_video_ids(
        published_after=params['publishedAfter']
    )
    
    print(f"\nFound {len(new_videos)} videos in last {days} days")
    _print_video_details(youtube_channel, new_videos)

def test_youtube_channel_today(youtube_channel, date_filter):
    """Test fetching today's videos"""
    params = date_filter.today()
    new_videos = youtube_channel.update_video_ids(
        published_after=params['publishedAfter'],
        published_before=params['publishedBefore']
    )
    
    print(f"\nFound {len(new_videos)} videos today")
    _print_video_details(youtube_channel, new_videos)

def test_youtube_channel_all(youtube_channel):
    """Test fetching all videos (no date filter)"""
    new_videos = youtube_channel.update_video_ids()
    
    print(f"\nFound {len(new_videos)} total videos")
    _print_video_details(youtube_channel, new_videos[:5])  # Show first 5 only

def test_youtube_channel_date_range(youtube_channel, date_filter):
    """Test fetching videos for specific date range"""
    # Get videos from Jan 2024
    params = date_filter.from_dates(
        after=datetime(2024, 1, 1),
        before=datetime(2024, 2, 1)
    )
    new_videos = youtube_channel.update_video_ids(
        published_after=params['publishedAfter'],
        published_before=params['publishedBefore']
    )
    
    print(f"\nFound {len(new_videos)} videos in January 2024")
    _print_video_details(youtube_channel, new_videos)

def _print_video_details(channel, video_ids):
    """Helper to print video details"""
    if not video_ids:
        print("No videos found")
        return
        
    print("\nVideo Details:")
    print("-" * 50)
    for video_id in video_ids[:5]:  # Show first 5 videos
        video = channel.create_or_get_video_client(video_id)
        print(f"Title: {video.title}")
        print(f"Published: {video.published_at}")
        print(f"URL: {video.url}")
        print("-" * 50)
