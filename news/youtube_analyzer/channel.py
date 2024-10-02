# channel.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import pandas as pd
import os
import logging
from youtube_base import YouTubeBase
from video import Video
from utils import sanitize_filename
from dateutil import parser  # Add this import at the top of the file
import pytz

class Channel(ABC):
    def __init__(self, name: str, api_key: Optional[str] = None, timezone: str = 'America/Chicago', transcript_language: str = 'en'):
        self.name = name
        self.description = ""
        self.videos: List[Video] = []  # Changed from YoutubeVideo to Video
        self.channel_info: Optional[Dict] = None
        self.channel_videos: Optional[pd.DataFrame] = None
        self.youtube_base = YouTubeBase(api_key, timezone)
        self.transcript_language = transcript_language
        self.logger = logging.getLogger(self.__class__.__name__)
        self._video_apis: Dict[str, Video] = {}  # Changed from YoutubeVideo to Video

    @abstractmethod
    def fetch_channel_info(self, start_date: datetime, end_date: datetime, force_refresh: bool = False) -> Tuple[Optional[Dict], Optional[pd.DataFrame]]:
        pass

    def get_video_count(self) -> int:
        return len(self.videos)

    def get_video_api(self, video_id: str) -> Video:  # Changed return type
        if video_id not in self._video_apis:
            self._video_apis[video_id] = Video(  # Changed from YoutubeVideo to Video
                video_id, 
                youtube_base=self.youtube_base,  # Pass youtube_base instead of api_key
                transcript_language=self.transcript_language
            )
        return self._video_apis[video_id]

    def update_video_transcripts(self):
        if self.channel_videos is None:
            raise ValueError("Channel videos have not been fetched yet. Call fetch_channel_info() first.")

        for index, video in self.channel_videos.iterrows():
            if pd.isna(video['Transcript']) or video['Transcript'] == "":
                transcript, language = self.get_video_api(video['Video ID']).get_transcript()
                self.channel_videos.at[index, 'Transcript'] = transcript if transcript else "No transcript available"
                self.channel_videos.at[index, 'Transcript_Language'] = language

        self.logger.info("Video transcripts have been updated.")
        return self.channel_videos

    def save_channel_videos_to_csv(self, root_dir: Optional[str] = None) -> Optional[str]:
        if self.channel_videos is None or self.channel_videos.empty:
            self.logger.warning(f"No channel videos available to save for channel: {self.name}")
            return None

        try:
            valid_channel_name = sanitize_filename(self.name, max_length=100)

            start_date = self.channel_videos['Published At'].min().strftime('%Y%m%d')
            end_date = self.channel_videos['Published At'].max().strftime('%Y%m%d')

            file_name = f"{valid_channel_name}_{start_date}_{end_date}.csv"

            if root_dir is None:
                root_dir = os.getcwd()

            file_path = os.path.join(root_dir, file_name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Select columns to save, excluding 'Description' and 'Channel ID'
            columns_to_save = [col for col in self.channel_videos.columns if col not in ['Description', 'Channel ID']]
            
            # Save to CSV with selected columns
            self.channel_videos[columns_to_save].to_csv(file_path, index=False, encoding='utf-8')

            self.logger.info(f"Successfully saved channel videos to {file_path}")
            return file_path

        except Exception as e:
            self.logger.error(f"An error occurred while saving channel videos: {str(e)}")
            return None

    def clear_video_apis(self):
        self._video_apis.clear()

class YouTubeChannel(Channel):
    def __init__(self, channel_name: str, api_key: Optional[str] = None, timezone: str = 'America/Chicago', transcript_language: str = 'en', existing_csv: Optional[str] = None):
        super().__init__(channel_name, api_key, timezone, transcript_language)
        self.channel_id = self.get_channel_id_from_name(channel_name)
        if not self.channel_id:
            raise ValueError(f"Could not find channel ID for: {channel_name}")
        
        if existing_csv:
            self.load_existing_data(existing_csv)

    def load_existing_data(self, csv_path: str):
        self.channel_videos = pd.read_csv(csv_path)
        self.channel_videos['Published At'] = pd.to_datetime(self.channel_videos['Published At'])
        self.set_channel_info_from_loaded_data()
        self.logger.info(f"Loaded {len(self.channel_videos)} videos from existing CSV.")

    def set_channel_info_from_loaded_data(self):
        if self.channel_videos is not None and not self.channel_videos.empty:
            self.channel_info = {
                'channel_name': self.name,
                'channel_id': self.channel_id,
                'video_count': len(self.channel_videos),
                'description': "Loaded from existing CSV",
            }
            self.logger.info(f"Set channel info from loaded data for {self.name}")

    def get_channel_id_from_name(self, name: str) -> Optional[str]:
        try:
            request = self.youtube_base.create_search_request(
                part="id",
                type="channel",
                q=name,
                maxResults=1
            )
            response = self.youtube_base.execute_api_request(request)

            if 'items' in response and len(response['items']) > 0:
                channel_id = response['items'][0]['id']['channelId']
                return channel_id
            else:
                self.logger.error(f"No channel found for name: {name}")
                return None
        except Exception as e:
            self.logger.error(f"An error occurred while fetching channel ID for {name}: {str(e)}")
            return None

    def fetch_channel_info(self, start_date: datetime, end_date: datetime, force_refresh: bool = False) -> Tuple[Optional[Dict], Optional[pd.DataFrame]]:
        if self.channel_info is not None and self.channel_videos is not None and not self.channel_videos.empty and not force_refresh:
            self.logger.info("Using existing channel info. Set force_refresh=True to fetch new data.")
            return self.channel_info, self.channel_videos

        channel_request = self.youtube_base.create_channels_request(
            part="snippet",
            id=self.channel_id
        )
        channel_response = self.youtube_base.execute_api_request(channel_request)
        channel_data = channel_response['items'][0]

        self.channel_info = {
            'channel_name': self.name,
            'channel_id': self.channel_id,
            'description': channel_data['snippet']['description'],
        }

        latest_video_date = self.get_latest_video_date()
        if latest_video_date:
            start_date = max(start_date, latest_video_date)

        new_videos_data = self.fetch_new_videos(start_date, end_date)
        self.merge_new_videos(new_videos_data)

        return self.channel_info, self.channel_videos

    def get_latest_video_date(self) -> Optional[datetime]:
        if self.channel_videos is not None and not self.channel_videos.empty:
            return self.channel_videos['Published At'].max()
        return None

    def fetch_new_videos(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        videos_data = []
        page_token = None

        while True:
            try:
                request = self.youtube_base.create_search_request(
                    part="snippet",
                    channelId=self.channel_id,
                    publishedAfter=start_date.isoformat() + "Z",
                    publishedBefore=end_date.isoformat() + "Z",
                    maxResults=50,
                    pageToken=page_token,
                    type="video"
                )
                response = self.youtube_base.execute_api_request(request)

                for item in response.get("items", []):
                    video_id = item['id']['videoId']
                    video_info = self.get_video_api(video_id).fetch_video_info()
                    if video_info:
                        videos_data.append(video_info)

                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            except Exception as e:
                self.logger.error(f"An error occurred while fetching videos: {str(e)}")
                break

        self.logger.info(f"Fetched {len(videos_data)} new videos.")
        return videos_data

    def merge_new_videos(self, new_videos_data: List[Dict]):
        if not new_videos_data:
            self.logger.info("No new videos to merge.")
            return

        new_videos_df = pd.DataFrame(new_videos_data)
        if self.channel_videos is None or self.channel_videos.empty:
            self.channel_videos = new_videos_df
        else:
            self.channel_videos = pd.concat([self.channel_videos, new_videos_df], ignore_index=True)
            self.channel_videos.drop_duplicates(subset=['Video ID'], keep='first', inplace=True)
        self.channel_videos.sort_values('Published At', ascending=False, inplace=True)
        self.logger.info(f"Merged new videos. Total videos: {len(self.channel_videos)}")

class VirtualChannel(Channel):
    def __init__(self, name: str, video_ids: List[str], api_key: Optional[str] = None, timezone: str = 'America/Chicago', transcript_language: str = 'en'):
        super().__init__(name, api_key, timezone, transcript_language)
        self.video_ids = video_ids

    def fetch_channel_info(self, start_date: datetime, end_date: datetime, force_refresh: bool = False) -> Tuple[Optional[Dict], Optional[pd.DataFrame]]:
        if self.channel_info is not None and self.channel_videos is not None and not self.channel_videos.empty and not force_refresh:
            self.logger.info("Using existing channel info. Set force_refresh=True to fetch new data.")
            return self.channel_info, self.channel_videos

        # Convert start_date and end_date to UTC
        start_date = start_date.replace(tzinfo=pytz.UTC)
        end_date = end_date.replace(tzinfo=pytz.UTC)

        video_info_list = []
        for video_id in self.video_ids:
            video_info = self.get_video_api(video_id).fetch_video_info()
            if video_info:
                try:
                    published_at = video_info['Published At']
                    if isinstance(published_at, str):
                        published_at = parser.isoparse(published_at)
                    
                    # Ensure published_at is UTC
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=pytz.UTC)
                    else:
                        published_at = published_at.astimezone(pytz.UTC)
                    
                    if start_date <= published_at <= end_date:
                        video_info_list.append(video_info)
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Error processing date for video {video_id}: {str(e)}")

        self.channel_videos = pd.DataFrame(video_info_list)
        
        self.channel_info = {
            'channel_name': self.name,
            'channel_id': 'virtual',
            'description': self.description,
            'video_count': len(video_info_list)
        }

        return self.channel_info, self.channel_videos

class ChannelFactory:
    @staticmethod
    def create_channel(channel_type: str, name: str, **kwargs) -> Channel:
        if channel_type == "youtube":
            return YouTubeChannel(name, **kwargs)
        elif channel_type == "virtual":
            return VirtualChannel(name, **kwargs)
        else:
            raise ValueError(f"Unsupported channel type: {channel_type}")