# youtube_analysis.py
import logging
import os
import sys
from datetime import datetime
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from typing import Dict, Any, List, Callable
import openai
from youtube_api import YouTubeAPI
from news.youtube_analyzer.llm_processor import LLMProcessor

class YouTubeAnalyzer:
    def __init__(self, config: Dict[str, Any], youtube_api: YouTubeAPI, llm_processor: LLMProcessor, base_dir: str = None):
        self.config = config
        self.base_dir = base_dir or os.path.join(os.getcwd(), 'youtube_analysis_data')
        self.youtube_api = youtube_api
        self.llm_processor = llm_processor
        self._setup_logging()
        self._videos_df = None
        self._html_content = None
        self._channel_name = self.config['channels']['default']
        self._timezone = self.config.get('timezone', 'America/Chicago')
        self._set_channel()
        self._setup_pipeline()

    def _setup_logging(self):
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

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
        self._channel_id = self.youtube_api.get_channel_id_from_name(self._channel_name)
        if not self._channel_id:
            raise ValueError(f"Invalid channel name: {self._channel_name}")
        self._channel_dir = os.path.join(self.base_dir, self._channel_name)
        os.makedirs(self._channel_dir, exist_ok=True)
        self._file_prefix = os.path.join(self._channel_dir, f"youtube_analysis_{self._channel_name}_{self._get_formated_date_today()}")
        logging.info(f"Channel set to {self._channel_name} (ID: {self._channel_id})")
        logging.info(f"Results will be saved in: {self._channel_dir}")

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
        start_date, end_date = YouTubeAPI.get_date_range(self.config['fetch']['period_type'], self.config['fetch']['number'], self._timezone)
        logging.info(f"Date range: {start_date} to {end_date}")

        try:
            existing_df = pd.read_csv(csv_file) if os.path.exists(csv_file) else pd.DataFrame()
            logging.info(f"Existing DataFrame shape: {existing_df.shape}")
            self._videos_df = self.youtube_api.fetch_channel_info(self._channel_id, start_date, end_date)
            logging.info(f"Fetched videos DataFrame shape: {self._videos_df.shape if self._videos_df is not None else 'None'}")

            if self._videos_df is not None and not self._videos_df.empty:
                self._videos_df['Published At'] = pd.to_datetime(self._videos_df['Published At'])
                self._videos_df = self._videos_df.sort_values('Published At', ascending=False).reset_index(drop=True)
                self._videos_df.to_csv(csv_file, index=False)
                new_videos_count = len(self._videos_df) - len(existing_df)
                logging.info(f"Added {new_videos_count} new videos. Total videos: {len(self._videos_df)}")
            else:
                logging.warning("No videos data available.")
        except Exception as e:
            logging.error(f"An error occurred while fetching videos: {str(e)}")
            logging.exception("Traceback:")
            self._videos_df = existing_df if 'existing_df' in locals() else pd.DataFrame()

    def _add_transcripts(self):
        if self._videos_df is None or self._videos_df.empty:
            logging.error("No videos data available. Make sure to fetch videos first.")
            return

        csv_file = f'{self._file_prefix}.csv'
        logging.info("Adding transcripts to videos")
        self._videos_df['Transcript'] = self._videos_df['Video ID'].apply(self.youtube_api.get_transcript_for_video)
        self._videos_df.to_csv(csv_file, index=False)
        logging.info(f"Saved videos with transcripts to {csv_file}")

    def apply_tasks_on_all_transcripts(self, df, task):
        if 'Summary' not in df.columns:
            df['Summary'] = pd.NA

        for index, row in df.iterrows():
            if pd.isna(row['Summary']):
                transcript = row['Transcript']
                if pd.isna(transcript) or transcript == "No transcript for video":
                    summary = "No summary"
                else:
                    summary = self.llm_processor.apply_task(transcript, task)
                    if not summary or summary == "Context length exceeded. Summary not available.":
                        summary = "No summary"
                df.at[index, 'Summary'] = summary

        return df

    def _generate_summaries(self):
        if self._videos_df is None or self._videos_df.empty:
            logging.error("No videos data available. Make sure to fetch videos and add transcripts first.")
            return

        if 'Transcript' not in self._videos_df.columns:
            logging.error("'Transcript' column not found in the DataFrame. Make sure to run add_transcripts() first.")
            return

        logging.info("Generating summaries for videos")
        self._videos_df = self.apply_tasks_on_all_transcripts(self._videos_df, self.config['summary']['task'])
        csv_file = f'{self._file_prefix}.csv'
        self._videos_df.to_csv(csv_file, index=False)
        logging.info(f"Saved summaries to {csv_file}")

    def _save_results(self):
        logging.info("Saving results to files")
        # Save DataFrame to CSV
        csv_file = self._file_prefix + '.csv'
        self._videos_df.to_csv(csv_file, index=False)
        logging.info(f"Data saved to {csv_file}")

        # Save formatted HTML content
        html_file = self._file_prefix + '.html'
        self.save_videos_to_text(self._videos_df, html_file, 'Title', 'Transcript', 'AI Tasks Results')

        # Store HTML content for emailing
        with open(html_file, 'r', encoding='utf-8') as file:
            self._html_content = file.read()

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
        message['Subject'] = f'analysis_{self._channel_name}_{self._get_formated_date_today()}'

        if self._videos_df is None or self._videos_df.empty:
            logging.error("No data available to send in email.")
            return

        html_content = self._generate_html_content(self._videos_df)
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
                logging.exception("Traceback:")
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

    def add_transcripts_to_df(self, df):
        if 'Transcript' not in df.columns:
            df['Transcript'] = pd.NA
    
        for index, row in df.iterrows():
            if pd.isna(row['Transcript']) or row['Transcript'] == "":
                transcript = self.youtube_api.get_transcript_for_video(row['Video ID'])
                if transcript is None:
                    transcript = "No transcript for video"
                df.at[index, 'Transcript'] = transcript
    
        return df

    def format_content(self, row, columns):
        content = ""
        for col in columns:
            if pd.isna(row[col]):
                row[col] = ""
            content += f"<strong>{col}:</strong> {str(row[col]).replace('\n', '<br>')}<br>\n"
        return content

    def save_videos_to_text(self, df, file_name, *columns):
        html_content = ""
        for _, row in df.iterrows():
            formatted_content = self.format_content(row, columns)
            html_content += f'<div>{formatted_content}</div>\n'

        with open(file_name, 'w', encoding='utf-8') as file:
            file.write(html_content)
        
        logging.info(f"Saved video content to {file_name}")

    def _generate_html_content(self, df):
        html_content = "<html><body>"
        for _, row in df.iterrows():
            html_content += f"<h2>{html.escape(row['Title'])}</h2>"
            html_content += f"<p><strong>Published At:</strong> {row['Published At']}</p>"
            html_content += f"<p><strong>Summary:</strong> {html.escape(row.get('Summary', ''))}</p>"
            html_content += "<hr>"
        html_content += "</body></html>"
        return html_content

    def _get_formated_date_today(self):
        return datetime.now().strftime("%Y-%m-%d")

# Usage example:
if __name__ == "__main__":
    config = {
        'channels': {'default': 'ExampleChannel'},
        'fetch': {'period_type': 'days', 'number': 7},
        'summary': {'task': 'Summarize the video content'},
        'email': {'recipients': ['example@email.com']},
        'timezone': 'America/New_York'
    }
    
    youtube_api = YouTubeAPI(api_key=os.getenv('YOUTUBE_API_KEY'), timezone=config['timezone'])
    llm_processor = LLMProcessor(openai.Client(api_key=os.getenv('OPENAI_API_KEY')))
    
    analysis = YouTubeAnalyzer(config, youtube_api, llm_processor)
    analysis.run()