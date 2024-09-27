import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime
import pytz
from youtube_analysis import YouTubeAnalysis

class TestYouTubeAnalysis(unittest.TestCase):

    def setUp(self):
        self.config = {
            'channels': {'default': 'TestChannel'},
            'fetch': {'period_type': 'days', 'number': 7},
            'summary': {'task': 'Summarize the video'},
            'email': {'recipients': ['test@example.com']},
            'timezone': 'America/Chicago'
        }
        self.youtube_api_mock = MagicMock()
        self.openai_client_mock = MagicMock()
        self.analysis = YouTubeAnalysis(self.config, self.youtube_api_mock, self.openai_client_mock)

    def test_set_channel(self):
        self.youtube_api_mock.get_channel_id_from_name.return_value = 'UC123456789'
        self.analysis._set_channel()
        self.assertEqual(self.analysis._channel_id, 'UC123456789')
        self.assertTrue(self.analysis._channel_dir.endswith('TestChannel'))

    @patch('pandas.read_csv')
    def test_load_existing_data(self, mock_read_csv):
        mock_df = pd.DataFrame({'Video ID': ['1', '2'], 'Title': ['Video 1', 'Video 2']})
        mock_read_csv.return_value = mock_df
        self.analysis._load_existing_data()
        pd.testing.assert_frame_equal(self.analysis._videos_df, mock_df)

    def test_fetch_videos(self):
        mock_df = pd.DataFrame({
            'Video ID': ['1', '2'], 
            'Title': ['Video 1', 'Video 2'], 
            'Published At': ['2023-01-01', '2023-01-02']
        })
        self.youtube_api_mock.fetch_videos.return_value = mock_df
        self.analysis._fetch_videos()
        self.assertIsNotNone(self.analysis._videos_df)
        self.assertEqual(len(self.analysis._videos_df), 2)

    def test_add_transcripts(self):
        self.analysis._videos_df = pd.DataFrame({'Video ID': ['1', '2'], 'Title': ['Video 1', 'Video 2']})
        self.youtube_api_mock.get_transcript.side_effect = ['Transcript 1', 'Transcript 2']
        self.analysis._add_transcripts()
        self.assertTrue('Transcript' in self.analysis._videos_df.columns)
        self.assertEqual(self.analysis._videos_df['Transcript'].tolist(), ['Transcript 1', 'Transcript 2'])

    @patch('youtube_analysis.apply_tasks_on_all_transcripts')
    def test_generate_summaries(self, mock_apply_tasks):
        self.analysis._videos_df = pd.DataFrame({
            'Video ID': ['1', '2'], 
            'Title': ['Video 1', 'Video 2'], 
            'Transcript': ['Transcript 1', 'Transcript 2']
        })
        mock_result_df = self.analysis._videos_df.copy()
        mock_result_df['AI Tasks Results'] = ['Summary 1', 'Summary 2']
        mock_apply_tasks.return_value = mock_result_df
        self.analysis._generate_summaries()
        self.assertTrue('AI Tasks Results' in self.analysis._videos_df.columns)

    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('pandas.DataFrame.to_csv')
    def test_save_results(self, mock_to_csv, mock_open):
        self.analysis._videos_df = pd.DataFrame({'Video ID': ['1', '2'], 'Title': ['Video 1', 'Video 2']})
        self.analysis._save_results()
        mock_to_csv.assert_called()
        mock_open.assert_called()

    @patch('smtplib.SMTP_SSL')
    @patch.dict('os.environ', {'EMAIL_USER': 'test@example.com', 'EMAIL_PASSWORD': 'password'})
    def test_send_email(self, mock_smtp):
        self.analysis._videos_df = pd.DataFrame({
            'Video ID': ['1'], 
            'Title': ['Video 1'], 
            'Published At': ['2023-01-01'], 
            'Summary': ['Test summary']
        })
        self.analysis._send_email()
        mock_smtp.return_value.__enter__.return_value.sendmail.assert_called()

    def test_format_content(self):
        row = pd.Series({'Title': 'Test Video', 'Transcript': 'Test transcript'})
        formatted = self.analysis.format_content(row, ['Title', 'Transcript'])
        self.assertIn('<strong>Title:</strong>', formatted)
        self.assertIn('<strong>Transcript:</strong>', formatted)

    def test_generate_html_content(self):
        df = pd.DataFrame({
            'Title': ['Video 1'], 
            'Published At': ['2023-01-01'], 
            'Summary': ['Test summary']
        })
        html_content = self.analysis._generate_html_content(df)
        self.assertIn('<h2>Video 1</h2>', html_content)
        self.assertIn('<strong>Published At:</strong> 2023-01-01', html_content)
        self.assertIn('<strong>Summary:</strong> Test summary', html_content)

    @patch('youtube_analysis.YouTubeAnalysis._set_channel')
    @patch('youtube_analysis.YouTubeAnalysis.run_pipeline')
    def test_run(self, mock_run_pipeline, mock_set_channel):
        self.analysis.run('NewChannel')
        mock_set_channel.assert_called()
        mock_run_pipeline.assert_called()

if __name__ == '__main__':
    unittest.main()
