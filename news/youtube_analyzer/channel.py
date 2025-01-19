# channel.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Set, Union
from datetime import datetime, timezone
import pandas as pd
import os
import logging
from youtube_api_client import YouTubeAPIClient
from video import Video
from utils import sanitize_filename, make_clickable
import pytz
from textwrap import dedent
from IPython.display import HTML
import re
import io
import gzip
import shutil
import json

class Channel(ABC):
    def __init__(self, name: str, timezone: str = 'America/Chicago', transcript_language: str = 'en'):
        self.name = name
        self.videos: List[Video] = []
        self.channel_metadata: Optional[Dict] = None
        self.youtube_api_client = YouTubeAPIClient()
        self.transcript_language = transcript_language
        self.timezone = timezone
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def fetch_channel_metadata(self) -> Dict:
        pass

    @abstractmethod
    def fetch_videos(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Video]:
        pass

    def serialize_channel_to_json(self, root_dir: str) -> Optional[str]:
        if not self.videos:
            self.logger.warning("No videos to serialize.")
            return None

        os.makedirs(root_dir, exist_ok=True)
        
        sanitized_name = sanitize_filename(self.name)
        file_name = self._generate_file_name(sanitized_name).replace('.csv', '.json')
        file_path = os.path.join(root_dir, file_name)

        channel_data = {
            'channel_metadata': self.channel_metadata,
            'videos': [video.to_dict() for video in self.videos]  # Videos are already sorted
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(channel_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Serialized channel data with {len(self.videos)} videos to JSON: {file_path}")
        return file_path

    @abstractmethod
    def _generate_file_name(self, sanitized_name: str) -> str:
        pass

    def initialize(self, json_path: Optional[str] = None) -> 'Channel':
        if json_path:
            self.load_from_json(json_path)
        else:
            self.channel_metadata = self.fetch_channel_metadata()
        return self

    def load_from_json(self, json_path: str):
        if not os.path.exists(json_path):
            self.logger.warning(f"Specified JSON file does not exist: {json_path}")
            return

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.channel_metadata = data.get('channel_metadata', {})
            
            for video_data in data.get('videos', []):
                video = Video(
                    video_id=video_data['Video ID'],
                    transcript_language=self.transcript_language
                )
                video.title = video_data['Title']
                video.set_published_at(video_data['Published At'])
                video.duration_minutes = video_data['Duration (minutes)']
                video.channel_id = video_data['Channel ID']
                video.channel_name = video_data['Channel Name']
                if 'Transcript' in video_data:
                    video.transcript = (video_data['Transcript'], video_data.get('Transcript Language', 'en'))
                video._info_fetched = True
                self.videos.append(video)

            self.logger.info(f"Loaded channel metadata and {len(self.videos)} videos from {json_path}")
        except Exception as e:
            self.logger.error(f"Error loading data from JSON: {str(e)}")

    def get_video_count(self) -> int:
        return len(self.videos)

    def create_video_objects(self, video_ids: Set[str]) -> List[Video]:
        new_videos = []
        for video_id in video_ids:
            try:
                video = Video(video_id, transcript_language=self.transcript_language, timezone=self.timezone)
                video.get_video_metadata_and_transcript()
                new_videos.append(video)
            except Exception as e:
                logger.error(f"Failed to create video object for ID {video_id}: {str(e)}")
                continue
        return new_videos

    def _ensure_timezone_aware(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return self.timezone.localize(dt)
        return dt

    def _convert_to_local_time(self, utc_time: datetime) -> datetime:
        return utc_time.replace(tzinfo=pytz.UTC).astimezone(self.timezone)

    def get_channel_info_for_display(self, num_videos: Optional[int] = None) -> Union[str, HTML]:
        if not self.channel_metadata:
            raise ValueError("Channel metadata is not available. Ensure initialize() was called successfully.")

        if not self.videos:
            self.logger.warning("No videos available. Ensure fetch_videos() was called and returned videos.")

        channel_info = f"""
        <h2>Channel Information</h2>
        <p><strong>Name:</strong> {self.channel_metadata.get('channel_name', 'N/A')}</p>
        <p><strong>ID:</strong> {self.channel_metadata.get('channel_id', 'N/A')}</p>
        <p><strong>Videos:</strong> {len(self.videos)} total</p>
        """

        videos_to_show = self.videos[:num_videos] if num_videos is not None else self.videos
        video_list = "<h3>Videos:</h3><ol>"
        for video in videos_to_show:
            video_url = f"https://www.youtube.com/watch?v={video.video_id}"
            video_link = make_clickable(video.title, video_url)
            video_list += f"<li>{video_link}</li>"
        video_list += "</ol>"

        full_info = channel_info + video_list

        try:
            return HTML(full_info)
        except NameError:
            # If HTML display is not available, return a plain text version
            plain_text = full_info.replace('<h2>', '').replace('</h2>', '\n')
            plain_text = plain_text.replace('<h3>', '').replace('</h3>', '\n')
            plain_text = plain_text.replace('<p>', '').replace('</p>', '\n')
            plain_text = plain_text.replace('<strong>', '').replace('</strong>', '')
            plain_text = plain_text.replace('<ol>', '').replace('</ol>', '')
            plain_text = plain_text.replace('<li><a.*?>(.*?)</a></li>', r'\1', plain_text)
            return plain_text

    def sort_videos(self):
        self.videos.sort(key=lambda v: v.published_at or datetime.min, reverse=True)

class YouTubeChannel(Channel):
    def __init__(self, channel_name: str, timezone: str = 'America/Chicago', 
                 transcript_language: str = 'en'):
        super().__init__(channel_name, timezone, transcript_language)
        self.channel_id = None  # We'll set this during initialization

    def initialize(self, json_path: Optional[str] = None) -> 'YouTubeChannel':
        if not self.channel_id:
            self.channel_id = self.get_channel_id_from_name(self.name)
        if not self.channel_id:
            raise ValueError(f"Could not find channel ID for: {self.name}")
        super().initialize(json_path)
        self.logger.info(f"Initialized YouTubeChannel with name: {self.name}, ID: {self.channel_id}")
        return self

    def fetch_channel_metadata(self) -> Dict:
        try:
            channel_request = self.youtube_api_client.create_channels_request(
                part="snippet",
                id=self.channel_id
            )
            channel_response = self.youtube_api_client.execute_api_request(channel_request)
            channel_data = channel_response['items'][0]

            metadata = {
                'channel_name': self.name,
                'channel_id': self.channel_id,
            }
            self.logger.info(f"Fetched channel metadata: {metadata}")
            return metadata
        except Exception as e:
            self.logger.error(f"Error fetching channel metadata: {str(e)}")
            raise

    def fetch_videos(self, start_date: datetime, end_date: datetime) -> List[Video]:
        try:
            start_date = self._ensure_timezone_aware(start_date)
            end_date = self._ensure_timezone_aware(end_date)

            existing_video_count = len(self.videos)
            new_video_ids = self.fetch_video_ids(start_date, end_date)
            existing_video_ids = {video.video_id for video in self.videos}
            new_ids_to_fetch = new_video_ids - existing_video_ids
            
            self.logger.info(f"Existing videos: {existing_video_count}, New videos to fetch: {len(new_ids_to_fetch)}")

            new_videos = self.create_video_objects(new_ids_to_fetch)
            self.videos.extend(new_videos)
            
            self.sort_videos()  # Sort videos after adding new ones
            
            filtered_videos = [v for v in self.videos if v.published_at and start_date <= self._ensure_timezone_aware(v.published_at) <= end_date]
            self.logger.info(f"Fetched {len(filtered_videos)} videos within the date range")
            return filtered_videos
        except Exception as e:
            self.logger.error(f"Error fetching videos: {str(e)}")
            raise

    def fetch_video_ids(self, start_date: datetime, end_date: datetime) -> Set[str]:
        video_ids = set()
        page_token = None

        while True:
            request = self.youtube_api_client.create_search_request(
                part="id",
                channelId=self.channel_id,
                type="video",
                publishedAfter=start_date.astimezone(pytz.UTC).isoformat(),
                publishedBefore=end_date.astimezone(pytz.UTC).isoformat(),
                maxResults=50,
                pageToken=page_token
            )
            response = self.youtube_api_client.execute_api_request(request)
            
            for item in response.get('items', []):
                video_ids.add(item['id']['videoId'])
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        
        return video_ids

    def get_channel_id_from_name(self, name: str) -> Optional[str]:
        try:
            request = self.youtube_api_client.create_search_request(
                part="id",
                type="channel",
                q=name,
                maxResults=1
            )
            response = self.youtube_api_client.execute_api_request(request)

            if 'items' in response and len(response['items']) > 0:
                channel_id = response['items'][0]['id']['channelId']
                return channel_id
            else:
                logging.error(f"No channel found for name: {name}")
                return None
        except Exception as e:
            logging.error(f"An error occurred while fetching channel ID for {name}: {str(e)}")
            return None

    def _generate_file_name(self, sanitized_name: str) -> str:
        start_date = min(v.published_at for v in self.videos if v.published_at)
        end_date = max(v.published_at for v in self.videos if v.published_at)
        return f"{sanitized_name}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"

class VirtualChannel(Channel):
    def __init__(self, channel_name: str, timezone: str = 'America/Chicago', transcript_language: str = 'en'):
        super().__init__(channel_name, timezone, transcript_language)
        self.video_ids: List[str] = []

    def initialize(self, video_ids: Optional[List[str]] = None, json_path: Optional[str] = None) -> 'VirtualChannel':
        if video_ids is None and json_path is None:
            raise ValueError("Either video_ids or json_path must be provided")

        self.video_ids = video_ids or []
        super().initialize(json_path)
        
        if not self.channel_metadata:
            self.channel_metadata = self.fetch_channel_metadata()
        
        return self

    def fetch_channel_metadata(self) -> Dict:
        return {
            'channel_name': self.name,
            'channel_id': 'virtual',
        }

    def fetch_videos(self) -> List[Video]:
        existing_video_ids = {video.video_id for video in self.videos}
        new_ids_to_fetch = set(self.video_ids) - existing_video_ids
        
        self.logger.info(f"Existing videos: {len(self.videos)}, New videos to fetch: {len(new_ids_to_fetch)}")

        new_videos = self.create_video_objects(new_ids_to_fetch)
        self.videos.extend(new_videos)
        
        self.sort_videos()  # Sort videos after adding new ones

        return self.videos

    def _generate_file_name(self, sanitized_name: str) -> str:
        return f"{sanitized_name}.csv"

class ChannelFactory:
    @staticmethod
    def create_channel(channel_type: str, name: str, **kwargs) -> Channel:
        if channel_type == "youtube":
            return YouTubeChannel(name, **kwargs)
        elif channel_type == "virtual":
            return VirtualChannel(name, **kwargs)
        else:
            raise ValueError(f"Unsupported channel type: {channel_type}")