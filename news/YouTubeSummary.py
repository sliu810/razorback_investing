import logging
import os
import sys
from datetime import datetime
import fetch_videos
import openai
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from typing import Dict, Any, List, Callable
from googleapiclient.errors import HttpError

CONFIG = {
    'channels': {
        'default': 'CNBC_TV'
    },
    'fetch': {
        'period_type': 'today',
        'number': 1
    },
    'summary': {
        'task': """I would like you to summarize the transcript with the following instructions: 
First categorize the video content. The category should be one of the following: Crypto, Macro, Politics, Technology, Small Caps or Other. 
Then summarize the stocks that are mentioned in this video.
Then provide key takeaways in a bullet point format. Please make sure don't miss anything about small cap, Nvidia, Tesla, Meta and Macro is mentioned in the transcript.
Please print the summary in a human-readable format like the following: 
Category: Technology
Stock mentioned: STOCK1, STOCK2, STOCK3
Key takeaways:
* takeaway 1
* takeaway 2
* takeaway 3
"""
    },
    'file_operations': {
        'file_prefix': 'youtube_summary',
        'output_types': ['csv', 'html', 'txt']
    },
    'email': {
        'send': True,
        'recipients': ['recipient1@example.com', 'recipient2@example.com']
    },
    'stop_on_error': False
}

class YouTubeSummary:
    def __init__(self, config: Dict[str, Any], base_dir: str = None):
        self.config = config
        self.base_dir = base_dir or os.path.join(os.getcwd(), 'youtube_summary_data')
        self._setup_logging()
        self._initialize_clients()
        self._videos_df = None
        self._html_content = None
        self._channel_name = self.config['channels']['default']
        self._set_channel()
        self._setup_pipeline()

    def _setup_logging(self):
        # Set up console logging
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        # Remove any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Create formatter and add it to the handler
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)

        # Add the handler to the logger
        logger.addHandler(console_handler)

    def _initialize_clients(self):
        self._client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def _setup_pipeline(self):
        self.pipeline_stages: List[Callable] = [
            self._set_channel,
            self._load_existing_data,
            self._fetch_videos,
            self._add_transcripts,
            self._generate_summaries,
            self._save_results,
            self._send_email
        ]

    def _set_channel(self):
        logging.info(f"Setting channel to {self._channel_name}")
        self._channel_id = fetch_videos.channels.get(self._channel_name)
        if not self._channel_id:
            raise ValueError(f"Invalid channel name: {self._channel_name}")
        
        self._channel_dir = os.path.join(self.base_dir, self._channel_name)
        os.makedirs(self._channel_dir, exist_ok=True)
        
        self._file_prefix = os.path.join(self._channel_dir, f"youtube_summary_{self._channel_name}_{fetch_videos.get_formated_date_today()}")
        logging.info(f"Channel set to {self._channel_name} (ID: {self._channel_id})")
        logging.info(f"Summaries will be saved in: {self._channel_dir}")

    def _load_existing_data(self):
        csv_file = f'{self._file_prefix}.csv'
        if os.path.exists(csv_file):
            logging.info(f"Loading existing data from {csv_file}")
            self._videos_df = pd.read_csv(csv_file)
            self._videos_df['Published At'] = pd.to_datetime(self._videos_df['Published At'])
            logging.info(f"Loaded {len(self._videos_df)} existing videos")
        else:
            logging.info("No existing data found. Will start with an empty DataFrame.")
            self._videos_df = pd.DataFrame()

    def _fetch_videos(self):
        logging.info(f"Fetching videos for channel ID: {self._channel_id}")
        csv_file = f'{self._file_prefix}.csv'
        
        start_date, end_date = fetch_videos.get_date_range(self.config['fetch']['period_type'], self.config['fetch']['number'])
        logging.info(f"Date range: {start_date} to {end_date}")

        try:
            # Load existing data if available
            if os.path.exists(csv_file):
                existing_df = pd.read_csv(csv_file)
                logging.info(f"Loaded {len(existing_df)} existing videos from {csv_file}")
            else:
                existing_df = pd.DataFrame()
                logging.info("No existing data found. Starting fresh.")

            initial_count = len(existing_df)
            logging.info(f"Fetching videos with args: start_date={start_date}, end_date={end_date}, channel_id={self._channel_id}")
            logging.info(f"Existing DataFrame shape: {existing_df.shape}")
            self._videos_df = fetch_videos.fetch_videos(start_date, end_date, self._channel_id, existing_df)
            
            logging.info(f"Fetched videos DataFrame shape: {self._videos_df.shape if self._videos_df is not None else 'None'}")

            if self._videos_df is not None and not self._videos_df.empty:
                self._videos_df['Published At'] = pd.to_datetime(self._videos_df['Published At'])
                self._videos_df = self._videos_df.sort_values('Published At', ascending=False).reset_index(drop=True)
                self._videos_df.to_csv(csv_file, index=False)
                new_videos_count = len(self._videos_df) - initial_count
                logging.info(f"Added {new_videos_count} new videos. Total videos: {len(self._videos_df)}")
            else:
                logging.warning("No videos data available.")
        except Exception as e:
            logging.error(f"An error occurred while fetching videos: {str(e)}")
            logging.exception("Traceback:")
            self._videos_df = existing_df if 'existing_df' in locals() else pd.DataFrame()

        if self._videos_df is None or self._videos_df.empty:
            logging.warning("No videos fetched. Check if the date range is correct or if there are any API issues.")
            self._videos_df = pd.DataFrame(columns=['Video ID', 'Title', 'Published At', 'Duration (Min)', 'URL'])
        else:
            logging.info(f"Working with {len(self._videos_df)} videos.")

    def _add_transcripts(self):
        if self._videos_df is None or self._videos_df.empty:
            logging.warning("No videos available to add transcripts.")
            return

        csv_file = f'{self._file_prefix}.csv'
        
        logging.info("Adding transcripts to videos")
        self._videos_df = fetch_videos.add_transcripts_to_df(self._videos_df)
        
        self._videos_df.to_csv(csv_file, index=False)
        logging.info(f"Saved videos with transcripts to {csv_file}")

    def _generate_summaries(self):
        if self._videos_df is None or self._videos_df.empty:
            logging.error("No videos data available. Make sure to fetch videos and add transcripts first.")
            return

        if 'Transcript' not in self._videos_df.columns:
            logging.error("'Transcript' column not found in the DataFrame. Make sure to run add_transcripts() first.")
            return

        summary_task = self.config['summary']['task']
        logging.info("Generating summaries for videos")
        summaries = fetch_videos.apply_tasks_on_all_transcripts(self._videos_df, self._client, summary_task)
        
        self._videos_df['Summary'] = summaries['Summary']
        
        csv_file = f'{self._file_prefix}.csv'
        self._videos_df.to_csv(csv_file, index=False)
        logging.info(f"Saved summaries to {csv_file}")

    def _save_results(self):
        logging.info("Starting _save_results method")
        if self._videos_df is None or self._videos_df.empty:
            logging.error("No data to save. Make sure to fetch videos first.")
            return

        logging.info(f"DataFrame columns: {self._videos_df.columns.tolist()}")
        logging.info(f"Number of rows in DataFrame: {len(self._videos_df)}")

        for file_type in self.config['file_operations']['output_types']:
            file_name = f'{self._file_prefix}.{file_type}'
            logging.info(f"Attempting to save {file_type} file: {file_name}")

            try:
                if file_type == 'csv':
                    self._videos_df.to_csv(file_name, index=False)
                    logging.info(f"Saved CSV to {file_name}")
                elif file_type == 'html':
                    if 'Summary' in self._videos_df.columns:
                        self._html_content = fetch_videos.get_html_content_summary_only(self._videos_df)
                        with open(file_name, 'w', encoding='utf-8') as file:
                            file.write(self._html_content)
                        logging.info(f"Saved HTML to {file_name}")
                    else:
                        logging.warning("Skipped saving HTML: 'Summary' column not found in the DataFrame.")
                elif file_type == 'txt':
                    columns_to_save = ['Title', 'Transcript']
                    columns_present = [col for col in columns_to_save if col in self._videos_df.columns]
                    if len(columns_present) == 2:
                        fetch_videos.save_videos_to_text(self._videos_df, file_name, *columns_present)
                        logging.info(f"Saved TXT to {file_name}")
                    else:
                        logging.warning(f"Skipped saving TXT: Missing columns {set(columns_to_save) - set(columns_present)}")
            except Exception as e:
                logging.error(f"Error saving {file_type} file: {str(e)}")

        logging.info(f"Finished saving results in {self._channel_dir}")

    def _send_email(self):
        email_user = os.getenv('EMAIL_USER')
        email_password = os.getenv('EMAIL_PASSWORD')
        
        if not email_user or not email_password:
            logging.error("Email credentials not set in environment variables.")
            return

        recipients = self.config['email']['recipients']

        message = MIMEMultipart()
        message['From'] = email_user
        message['To'] = ', '.join(recipients)
        message['Subject'] = f'summaries_{self._channel_name}_{fetch_videos.get_formated_date_today()}'

        if self._videos_df is None or self._videos_df.empty:
            logging.error("No data available to send in email.")
            return

        html_content = fetch_videos.get_html_content_summary_only(self._videos_df)
        message.attach(MIMEText(html_content, 'html'))

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(email_user, email_password)
                server.sendmail(email_user, recipients, message.as_string())
            logging.info("Email sent successfully!")
        except Exception as e:
            logging.error(f"Failed to send email: {e}")

    def run_pipeline(self):
        for stage in self.pipeline_stages:
            try:
                logging.info(f"Starting stage: {stage.__name__}")
                stage()
                logging.info(f"Completed stage: {stage.__name__}")
            except Exception as e:
                logging.error(f"Error in {stage.__name__}: {str(e)}")
                logging.exception("Traceback:")  # This will log the full traceback
                if self.config.get('stop_on_error', False):
                    logging.info("Stopping pipeline due to error")
                    break
        logging.info("Pipeline execution completed")

    def run(self, channel_name: str = None):
        if channel_name:
            self._channel_name = channel_name
            self._set_channel()
        try:
            self.run_pipeline()
            logging.info("Pipeline completed successfully")
        except Exception as e:
            logging.error(f"An error occurred during pipeline execution: {str(e)}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate YouTube summaries")
    parser.add_argument("--channel", help="The name of the YouTube channel to summarize")
    args = parser.parse_args()

    yt_summary = YouTubeSummary(CONFIG)
    yt_summary.run(args.channel)

if __name__ == "__main__":
    main()
else:
    print("Module loaded. Use YouTubeSummary(CONFIG).run(channel_name) to run the script or call individual functions.")

