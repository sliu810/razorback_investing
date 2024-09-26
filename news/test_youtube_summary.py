import pytest
import os
import tempfile
import shutil
import pandas as pd
from YouTubeSummary import YouTubeSummary, CONFIG
import fetch_videos
from unittest.mock import patch, MagicMock
from googleapiclient.errors import HttpError

@pytest.fixture(scope="module")
def test_dir():
    test_dir = tempfile.mkdtemp()
    yield test_dir
    shutil.rmtree(test_dir)

@pytest.fixture
def yt_summary(test_dir):
    return YouTubeSummary(CONFIG, base_dir=test_dir)

def test_set_channel(yt_summary):
    yt_summary._set_channel()
    assert yt_summary._channel_name == CONFIG['channels']['default']
    assert yt_summary._channel_id is not None
    assert os.path.exists(yt_summary._channel_dir)
    assert yt_summary._channel_name in yt_summary._file_prefix

@patch('fetch_videos.fetch_videos')
def test_fetch_videos(mock_fetch_videos, yt_summary):
    mock_df = pd.DataFrame({'Video ID': ['1', '2'], 'Title': ['Video 1', 'Video 2'], 'Published At': ['2024-09-23', '2024-09-22']})
    mock_fetch_videos.return_value = mock_df
    yt_summary._fetch_videos()
    assert yt_summary._videos_df is not None
    assert len(yt_summary._videos_df) == 2

@patch('fetch_videos.fetch_videos')
@patch('os.path.exists')
@patch('pandas.read_csv')
def test_fetch_videos_quota_exceeded(mock_read_csv, mock_exists, mock_fetch_videos, yt_summary):
    mock_exists.return_value = True
    existing_df = pd.DataFrame({'Video ID': ['1'], 'Title': ['Existing Video'], 'Published At': ['2024-09-22']})
    mock_read_csv.return_value = existing_df
    mock_fetch_videos.side_effect = HttpError(resp=MagicMock(status=403), content=b'quotaExceeded')
    yt_summary._fetch_videos()
    assert yt_summary._videos_df is not None
    assert len(yt_summary._videos_df) == 1

# ... (other test functions)

if __name__ == "__main__":
    pytest.main()