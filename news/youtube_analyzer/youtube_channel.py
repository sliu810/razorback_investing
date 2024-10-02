import logging
from datetime import datetime
import pytz
import pandas as pd
import os
from typing import Dict, Optional, List
from youtube_base import YouTubeBase
from youtube_video import YoutubeVideo
from utils import sanitize_filename

class YoutubeChannel(YouTubeBase):
    def __init__(self, channel_name, api_key=None, timezone='America/Chicago', transcript_language='en', existing_csv=None):
        super().__init__(api_key, timezone)
        self.channel_name = channel_name
        self.channel_id = self.get_channel_id_from_name(channel_name)
        if not self.channel_id:
            raise ValueError(f"Could not find channel ID for: {channel_name}")
        self.transcript_language = transcript_language
        self.channel_info: Optional[Dict] = None
        self.channel_videos: Optional[pd.DataFrame] = None
        self._video_apis: Dict[str, YoutubeVideo] = {} 
        
        if existing_csv:
            self.load_existing_data(existing_csv)

    def load_existing_data(self, csv_path):
        """Load existing data from a CSV file."""
        self.channel_videos = pd.read_csv(csv_path)
        self.channel_videos['Published At'] = pd.to_datetime(self.channel_videos['Published At'])
        self.set_channel_info_from_loaded_data()
        self.logger.info(f"Loaded {len(self.channel_videos)} videos from existing CSV.")

    def set_channel_info_from_loaded_data(self):
        """Set channel_info based on loaded data."""
        if self.channel_videos is not None and not self.channel_videos.empty:
            self.channel_info = {
                'channel_name': self.channel_name,
                'channel_id': self.channel_id,
                'video_count': len(self.channel_videos),
                'description': "Loaded from existing CSV",
            }
            self.logger.info(f"Set channel info from loaded data for {self.channel_name}")

    def get_channel_id_from_name(self, name):
        try:
            request = self.youtube.search().list(
                part="id",
                type="channel",
                q=name,
                maxResults=1
            )
            response = self._execute_api_request(request)

            if 'items' in response and len(response['items']) > 0:
                channel_id = response['items'][0]['id']['channelId']
                return channel_id
            else:
                self.logger.error(f"No channel found for name: {name}")
                return None
        except Exception as e:
            self.logger.error(f"An error occurred while fetching channel ID for {name}: {str(e)}")
            return None

    def fetch_channel_info(self, start_date, end_date, force_refresh=False):
        if self.channel_info is not None and self.channel_videos is not None and not force_refresh:
            self.logger.info("Using existing channel info. Set force_refresh=True to fetch new data.")
            return self.channel_info, self.channel_videos

        # Fetch channel metadata
        channel_request = self.youtube.channels().list(
            part="snippet",
            id=self.channel_id
        )
        channel_response = self._execute_api_request(channel_request)
        channel_data = channel_response['items'][0]

        self.channel_info = {
            'channel_name': self.channel_name,
            'channel_id': self.channel_id,
            'description': channel_data['snippet']['description'],
        }

        # Determine the latest video date from existing data
        latest_video_date = self.get_latest_video_date()
        if latest_video_date:
            start_date = max(start_date, latest_video_date)

        # Fetch only new videos
        new_videos_data = self.fetch_new_videos(start_date, end_date)

        # Merge new videos with existing ones
        self.merge_new_videos(new_videos_data)

        return self.channel_info, self.channel_videos

    def get_latest_video_date(self):
        """Get the latest video date from existing data."""
        if self.channel_videos is not None and not self.channel_videos.empty:
            return self.channel_videos['Published At'].max()
        return None

    def fetch_new_videos(self, start_date, end_date) -> List[Dict]:
        """Fetch only new videos from YouTube API."""
        videos_data = []
        page_token = None

        while True:
            try:
                request = self.youtube.search().list(
                    part="snippet",
                    channelId=self.channel_id,
                    publishedAfter=start_date.isoformat() + "Z",
                    publishedBefore=end_date.isoformat() + "Z",
                    maxResults=50,
                    pageToken=page_token,
                    type="video"
                )
                response = self._execute_api_request(request)

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

    def merge_new_videos(self, new_videos_data):
        """Merge new videos with existing ones."""
        new_videos_df = pd.DataFrame(new_videos_data)
        if self.channel_videos is None:
            self.channel_videos = new_videos_df
        else:
            self.channel_videos = pd.concat([self.channel_videos, new_videos_df], ignore_index=True)
            self.channel_videos.drop_duplicates(subset=['Video ID'], keep='first', inplace=True)
        self.channel_videos.sort_values('Published At', ascending=False, inplace=True)
        self.logger.info(f"Merged new videos. Total videos: {len(self.channel_videos)}")

    def get_video_api(self, video_id: str) -> YoutubeVideo:
        """
        Get or create a YoutubeVideo instance for the given video ID.
        """
        if video_id not in self._video_apis:
            self._video_apis[video_id] = YoutubeVideo(
                video_id, 
                api_key=self.api_key, 
                timezone=self.timezone, 
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

    def save_channel_videos_to_csv(self, root_dir=None):
        if self.channel_videos is None or self.channel_videos.empty:
            self.logger.warning(f"No channel videos available to save for channel: {self.channel_name}")
            return None

        try:
            valid_channel_name = sanitize_filename(self.channel_name, max_length=100)

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
        """
        Clear stored VideoAPI objects to free up memory.
        """
        self._video_apis.clear()