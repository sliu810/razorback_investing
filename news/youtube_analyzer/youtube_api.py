import os
import logging
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime, timedelta
import pytz
from youtube_transcript_api import YouTubeTranscriptApi
from utils import iso_duration_to_minutes, make_clickable
from IPython.display import display, HTML
import textwrap

class YouTubeAPI:
    def __init__(self, api_key=None, timezone='America/Chicago'):
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("No API key found. Make sure the YOUTUBE_API_KEY environment variable is set.")
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self.timezone = timezone

    def get_channel_id_from_name(self, name):
        try:
            request = self.youtube.search().list(
                part="id",
                type="channel",
                q=name,
                maxResults=1
            )
            response = request.execute()

            if 'items' in response and len(response['items']) > 0:
                channel_id = response['items'][0]['id']['channelId']
                return channel_id
            else:
                logging.error(f"No channel found for name: {name}")
                return None
        except Exception as e:
            logging.error(f"An error occurred while fetching channel ID for {name}: {str(e)}")
            return None

    def get_date_range(self, period_type, number=1):
        local_timezone = pytz.timezone(self.timezone)
        now = datetime.now(pytz.utc).astimezone(local_timezone)

        if period_type == 'today':
            start_date = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=local_timezone)
            end_date = datetime(now.year, now.month, now.day, 23, 59, 59, 999999, tzinfo=local_timezone)
        elif period_type == 'days':
            start_date = (datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=local_timezone)
                          - timedelta(days=number-1))
            end_date = datetime(now.year, now.month, now.day, 23, 59, 59, 999999, tzinfo=local_timezone)
        elif period_type == 'weeks':
            start_date = (datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=local_timezone)
                          - timedelta(weeks=number))
            end_date = datetime(now.year, now.month, now.day, 23, 59, 59, 999999, tzinfo=local_timezone)
        elif period_type == 'months':
            start_date = (datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=local_timezone)
                          - timedelta(days=30*number))
            end_date = datetime(now.year, now.month, now.day, 23, 59, 59, 999999, tzinfo=local_timezone)
        else:
            raise ValueError("Unsupported period type specified.")
        
        logging.debug(f"Calculated date range - Start Date: {start_date.isoformat()}, End Date: {end_date.isoformat()}")
        return start_date, end_date
    
    def fetch_channel_video_info(self, channel_name_or_id, start_date, end_date):
        """
        Fetches video information from a YouTube channel within a date range.

        Parameters:
        - channel_name_or_id (str): The YouTube channel name or ID.
        - start_date (datetime): The start date for fetching videos.
        - end_date (datetime): The end date for fetching videos.

        Returns:
        - pd.DataFrame: A DataFrame containing video information.
        """
        if not channel_name_or_id.startswith('UC'):
            channel_id = self.get_channel_id_from_name(channel_name_or_id)
            if not channel_id:
                raise ValueError(f"Could not find channel ID for: {channel_name_or_id}")
        else:
            channel_id = channel_name_or_id

        video_data = []
        page_token = None
        local_timezone = pytz.timezone(self.timezone)

        while True:
            try:
                request = self.youtube.search().list(
                    part="snippet",
                    channelId=channel_id,
                    publishedAfter=start_date.isoformat(),
                    publishedBefore=end_date.isoformat(),
                    maxResults=50,
                    pageToken=page_token,
                    type="video"
                )
                response = request.execute()

                video_ids = [
                    item['id']['videoId']
                    for item in response.get("items", [])
                    if 'videoId' in item['id']
                ]

                if video_ids:
                    video_request = self.youtube.videos().list(
                        part='contentDetails,snippet',
                        id=','.join(video_ids)
                    )
                    video_response = video_request.execute()

                    for item in video_response.get("items", []):
                        video_id = item['id']
                        snippet = item['snippet']
                        content_details = item['contentDetails']

                        published_at = datetime.strptime(
                            snippet['publishedAt'], "%Y-%m-%dT%H:%M:%SZ"
                        ).replace(tzinfo=pytz.UTC).astimezone(local_timezone)

                        duration = iso_duration_to_minutes(content_details['duration'])  # Use the imported function

                        video_data.append({
                            'Video ID': video_id,
                            'Title': snippet['title'],
                            'Description': snippet['description'],
                            'Published At': published_at,
                            'Duration (minutes)': duration,
                            'Channel ID': channel_id,
                        })
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            except Exception as e:
                logging.error(f"An error occurred while fetching videos: {str(e)}")
                break

        df = pd.DataFrame(video_data)
        if not df.empty and 'Published At' in df.columns:
            df = df.sort_values('Published At', ascending=False)
        return df

    def fetch_video_info(self, video_id):
        """
        Fetches information for a single video.

        Parameters:
        - video_id (str): The YouTube video ID.

        Returns:
        - dict: A dictionary containing video information.
        """
        try:
            video_request = self.youtube.videos().list(
                part='snippet,contentDetails',
                id=video_id
            )
            video_response = video_request.execute()

            if 'items' in video_response and len(video_response['items']) > 0:
                item = video_response['items'][0]
                snippet = item['snippet']
                content_details = item['contentDetails']

                local_timezone = pytz.timezone(self.timezone)
                published_at = datetime.strptime(
                    snippet['publishedAt'], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=pytz.UTC).astimezone(local_timezone)

                duration = iso_duration_to_minutes(content_details['duration'])

                return {
                    'Video ID': video_id,
                    'Title': snippet['title'],
                    'Description': snippet['description'],
                    'Published At': published_at,
                    'Duration (minutes)': duration,
                    'Channel ID': snippet['channelId'],
                    'Channel Name': snippet['channelTitle']
                }
            else:
                logging.warning(f"No video found for ID: {video_id}")
                return None
        except Exception as e:
            logging.error(f"An error occurred while fetching video info for ID {video_id}: {str(e)}")
            return None

    def get_transcript_for_video(self, video_id):
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_transcript(['en'])
            transcript_data = transcript.fetch()
            transcript_text = " ".join([entry['text'] for entry in transcript_data]).lower()
            return transcript_text
        except Exception as e:
            logging.error(f"An error occurred for video ID {video_id}: {e}")
            return None

    def display_df(self, df, include_transcript=False, include_duration=False, include_video_id=False):
        """
        Displays the DataFrame in a Jupyter Notebook with clickable titles and optional columns.

        Parameters:
        - df (DataFrame): DataFrame to display.
        - include_transcript (bool): Whether to include the Transcript column in the display.
        - include_duration (bool): Whether to include the Duration (Min) column in the display.
        - include_video_id (bool): Whether to include the VideoID column in the display.
        """
        # Create a copy for display to avoid altering the original DataFrame
        df_display = df.copy()
        
        # Make titles clickable
        df_display['Title'] = df_display.apply(lambda x: make_clickable(x['Title'], f"https://www.youtube.com/watch?v={x['Video ID']}"), axis=1)

        # Format the 'Published At' column to show only the date
        df_display['Published At'] = pd.to_datetime(df_display['Published At']).dt.date

        # Drop optional columns based on parameters and existence
        if not include_transcript and 'Transcript' in df_display.columns:
            df_display.drop('Transcript', axis=1, inplace=True)
        if not include_duration and 'Duration (minutes)' in df_display.columns:
            df_display.drop('Duration (minutes)', axis=1, inplace=True)
        if not include_video_id:
            df_display.drop('Video ID', axis=1, inplace=True)

        # Generate HTML content and display the DataFrame
        html_content = df_display.to_html(escape=False, index=False)
        display(HTML(html_content))

def display_df_info(self, df, max_titles=20, columns=2, width=40):
    """
    Displays basic information about the DataFrame in a formatted manner.

    Parameters:
    - df (DataFrame): DataFrame to display information about.
    - max_titles (int): Maximum number of video titles to display.
    - columns (int): Number of columns to use for displaying titles.
    - width (int): Maximum width of each title before wrapping.
    """
    print("\n" + "="*50)
    print("DataFrame Summary".center(50))
    print("="*50)

    print(f"\nTotal number of videos: {len(df)}")
    
    if 'Published At' in df.columns:
        print(f"\nDate range of videos:")
        print(f"  Earliest: {df['Published At'].min().date()}")
        print(f"  Latest: {df['Published At'].max().date()}")

    print("\nColumns in the DataFrame:")
    for col in df.columns:
        print(f"  - {col}")

    print(f"\nFirst {max_titles} video titles:")
    titles = df['Title'].head(max_titles).tolist()
    wrapped_titles = [textwrap.fill(title, width=width) for title in titles]
    max_lines = max(len(title.split('\n')) for title in wrapped_titles)

    for i in range(0, len(wrapped_titles), columns):
        column_titles = wrapped_titles[i:i+columns]
        for line in range(max_lines):
            for title in column_titles:
                title_lines = title.split('\n')
                if line < len(title_lines):
                    print(f"{title_lines[line]:<{width}}", end="  ")
                else:
                    print(" " * width, end="  ")
            print()
        print()

    print("\n" + "="*50)