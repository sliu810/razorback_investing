import pytest
import os
from datetime import datetime
import pytz
from ..libs.video import Video
from ..libs.youtube_api_client import YouTubeAPIClient
import json

def test_video_creation():
    """Test video creation with real YouTube API"""
    # Skip test if no API key available
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        pytest.skip("No YouTube API key available")

    video_id = "eQZbi8HBRcQ"  # SpaceX Starship video    
    video = Video(video_id)
    video.get_video_metadata_and_transcript()
    
    # Assert video ID and title
    assert video.video_id == video_id
    assert video.title == "What's new with Flight 7's massively upgraded Starship?!?"
    assert video.url == "https://www.youtube.com/watch?v=eQZbi8HBRcQ"
    
    # Assert transcript content
    transcript_text, language_code = video.transcript  # Unpacking the tuple
    assert "Starship" in transcript_text
    assert "SpaceX" in transcript_text
    assert len(transcript_text) > 100  # Check length of the actual transcript text
    assert language_code == "en"  # Verify it's English
    
    # Print for debugging
    print(f"\nTranscript info:")
    print(f"Language: {language_code}")
    print(f"Text length: {len(transcript_text)}")
    print(f"Preview: {transcript_text[:200]}...")

def test_video_serialize_and_deserialize():
    """Test video serialization and deserialization"""
    video_id = "eQZbi8HBRcQ"  # SpaceX Starship video    
    video = Video(video_id)
    video.get_video_metadata_and_transcript()
    temp_dir = "test_data"
    serialized_json = video.serialize_video_to_json(temp_dir) # use default filename
    print(f"serialized_json: {serialized_json}")

    # Load and verify JSON content
    with open(serialized_json, 'r', encoding='utf-8') as f:
        json_content = json.load(f)
        assert "Starship" in json_content['Transcript'][0]
        assert "SpaceX" in json_content['Transcript'][0]
        assert json_content['Transcript'][1] == 'en'  # verify language code

    # Deserialize the video from the JSON file
    video2 = Video.create_from_json_file(serialized_json)
    assert video2.to_dict()['Transcript'][0] == video.to_dict()['Transcript'][0]
    assert video2.to_dict()['Title'] == video.to_dict()['Title']
    assert video2.to_dict()['Video ID'] == video.to_dict()['Video ID']
    assert video2.to_dict()['Channel Name'] == video.to_dict()['Channel Name']
    assert video2.to_dict()['Published At'] == video.to_dict()['Published At']

    # clean up
    os.remove(serialized_json)

def test_video_creation_without_assertions():
    """Test video creation without assertions"""
    video_id = "zMw8RuNpHhk"  # SpaceX Starship video    
    video = Video(video_id)
    video.get_video_metadata_and_transcript()

    video_dict = video.to_dict()
    print(f"\n ==={video.title}===")
    print(f"{video_dict['Transcript']}")