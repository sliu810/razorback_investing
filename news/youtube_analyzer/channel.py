# channel.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Set, Union
from datetime import datetime, timezone
import pandas as pd
import os
import logging
from youtube_base import YouTubeBase
from video import Video
from utils import sanitize_filename, make_clickable
import pytz
from textwrap import dedent
from IPython.display import HTML
import re

class Channel(ABC):
    def __init__(self, name: str, api_key: Optional[str] = None, timezone: str = 'America/Chicago', transcript_language: str = 'en'):
        self.name = name
        self.description = ""
        self.videos: List[Video] = []
        self.channel_metadata: Optional[Dict] = None
        self.youtube_base = YouTubeBase(api_key, timezone)
        self.transcript_language = transcript_language
        self.timezone = pytz.timezone(timezone)
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def fetch_channel_metadata(self) -> Dict:
        pass

    @abstractmethod
    def fetch_videos(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Video]:
        pass

    def save_channel_videos_to_csv(self, root_dir: str) -> Optional[str]:
        if not self.videos:
            self.logger.warning("No videos to save.")
            return None

        os.makedirs(root_dir, exist_ok=True)
        
        sanitized_name = sanitize_filename(self.name)
        file_name = self._generate_file_name(sanitized_name)
        file_path = os.path.join(root_dir, file_name)

        df = pd.DataFrame([video.to_dict() for video in self.videos])
        df.to_csv(file_path, index=False)
        self.logger.info(f"Saved {len(self.videos)} videos to {file_path}")
        return file_path

    @abstractmethod
    def _generate_file_name(self, sanitized_name: str) -> str:
        pass

    def initialize(self, csv_path: Optional[str] = None) -> 'Channel':
        self.channel_metadata = self.fetch_channel_metadata()
        if csv_path:
            self.load_videos_from_csv(csv_path)
        return self

    def get_video_count(self) -> int:
        return len(self.videos)

    def load_videos_from_csv(self, csv_path: str):
        if not os.path.exists(csv_path):
            self.logger.warning(f"Specified CSV file does not exist: {csv_path}")
            return
        try:
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                video = Video(
                    video_id=row['Video ID'],
                    youtube_base=self.youtube_base,
                    transcript_language=self.transcript_language
                )
                video.title = row['Title']
                video.set_published_at(row['Published At'])
                video.description = row['Description']
                video.duration_minutes = row['Duration (minutes)']
                video.channel_id = row['Channel ID']
                video.channel_name = row['Channel Name']
                video.transcript = (row['Transcript'], row.get('Transcript Language', 'en'))
                video._info_fetched = True
                self.videos.append(video)
            self.logger.info(f"Loaded {len(self.videos)} videos from {csv_path}")
        except Exception as e:
            self.logger.error(f"Error loading videos from CSV: {str(e)}")

    def create_video_objects(self, video_ids: Set[str]) -> List[Video]:
        new_videos = []
        for video_id in video_ids:
            video = Video(video_id, youtube_base=self.youtube_base, transcript_language=self.transcript_language)
            if video.fetch_video_info():
                new_videos.append(video)
        return new_videos

    def _ensure_timezone_aware(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return self.timezone.localize(dt)
        return dt

    def get_channel_info_for_display(self, num_videos: Optional[int] = None) -> Union[str, HTML]:
        """
        Prepare a formatted display of channel information and videos.

        This method generates a string or HTML representation of the channel's metadata
        and a list of its videos. Video names are displayed as clickable links.

        Args:
            num_videos (Optional[int]): The number of videos to include in the display.
                                        If None, all videos will be included.

        Returns:
            Union[str, HTML]: A formatted string or HTML object containing the channel information
                              and video list. Returns HTML if in a notebook environment,
                              otherwise returns a string.

        Raises:
            ValueError: If channel metadata is not available (initialize() not called).
        """
        if not self.channel_metadata:
            raise ValueError("Channel metadata is not available. Ensure initialize() was called successfully.")

        if not self.videos:
            self.logger.warning("No videos available. Ensure fetch_videos() was called and returned videos.")

        channel_info = f"""
        <h2>Channel Information</h2>
        <p><strong>Name:</strong> {self.channel_metadata.get('channel_name', 'N/A')}</p>
        <p><strong>ID:</strong> {self.channel_metadata.get('channel_id', 'N/A')}</p>
        <p><strong>Published At:</strong> {self.channel_metadata.get('published_at', 'N/A')}</p>
        <p><strong>Description:</strong> {self.channel_metadata.get('description', 'N/A')}</p>
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
            plain_text = re.sub(r'<li><a.*?>(.*?)</a></li>', r'\1', plain_text)
            return plain_text

class YouTubeChannel(Channel):
    def __init__(self, channel_name: str, api_key: Optional[str] = None, timezone: str = 'America/Chicago', 
                 transcript_language: str = 'en'):
        super().__init__(channel_name, api_key, timezone, transcript_language)
        self.channel_id = self.get_channel_id_from_name(channel_name)
        if not self.channel_id:
            raise ValueError(f"Could not find channel ID for: {channel_name}")
        self.logger.info(f"Initialized YouTubeChannel with name: {channel_name}, ID: {self.channel_id}")

    def fetch_channel_metadata(self) -> Dict:
        try:
            channel_request = self.youtube_base.create_channels_request(
                part="snippet",
                id=self.channel_id
            )
            channel_response = self.youtube_base.execute_api_request(channel_request)
            channel_data = channel_response['items'][0]

            metadata = {
                'channel_name': self.name,
                'channel_id': self.channel_id,
                'description': channel_data['snippet']['description'],
                'published_at': channel_data['snippet']['publishedAt'],
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
            self.videos.sort(key=lambda v: v.published_at if v.published_at else datetime.min.replace(tzinfo=self.timezone), reverse=True)
            
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
            request = self.youtube_base.create_search_request(
                part="id",
                channelId=self.channel_id,
                type="video",
                publishedAfter=start_date.astimezone(pytz.UTC).isoformat(),
                publishedBefore=end_date.astimezone(pytz.UTC).isoformat(),
                maxResults=50,
                pageToken=page_token
            )
            response = self.youtube_base.execute_api_request(request)
            
            for item in response.get('items', []):
                video_ids.add(item['id']['videoId'])
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        
        return video_ids

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
    def __init__(self, channel_name: str, api_key: Optional[str] = None, 
                 timezone: str = 'America/Chicago', transcript_language: str = 'en'):
        super().__init__(channel_name, api_key, timezone, transcript_language)
        self.video_ids: List[str] = []

    def initialize(self, video_ids: Optional[List[str]] = None, csv_path: Optional[str] = None) -> 'VirtualChannel':
        if video_ids is None and csv_path is None:
            raise ValueError("Either video_ids or csv_path must be provided")

        self.video_ids = video_ids or []
        self.channel_metadata = self.fetch_channel_metadata()
        
        if csv_path:
            self.load_videos_from_csv(csv_path)
        
        return self

    def fetch_channel_metadata(self) -> Dict:
        return {
            'channel_name': self.name,
            'channel_id': 'virtual',
            'description': f"Virtual channel containing {len(self.video_ids)} videos",
            'published_at': datetime.now().isoformat(),
        }

    def fetch_videos(self) -> List[Video]:
        existing_video_ids = {video.video_id for video in self.videos}
        new_ids_to_fetch = set(self.video_ids) - existing_video_ids
        
        self.logger.info(f"Existing videos: {len(self.videos)}, New videos to fetch: {len(new_ids_to_fetch)}")

        new_videos = self.create_video_objects(new_ids_to_fetch)
        self.videos.extend(new_videos)
        self.videos.sort(key=lambda v: v.published_at if v.published_at else datetime.min.replace(tzinfo=self.timezone), reverse=True)

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