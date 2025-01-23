import pytest
from ..libs.video_client import YouTubeVideoClient
from ..libs.llm_processor import LLMConfig, Role, Task
import os
from pathlib import Path
import logging
import sys
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

@pytest.fixture
def claude_config():
    """Fixture providing Claude configuration"""
    return LLMConfig(
        provider="anthropic",
        model_name="claude-3-5-sonnet-20241022",
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

@pytest.fixture
def gpt_config():
    """Fixture providing GPT configuration"""
    return LLMConfig(
        provider="openai",
        model_name="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY")
    )

@pytest.fixture
def youtube_client(test_video_id, claude_config, gpt_config):
    """Fixture providing YouTubeVideoClient instance with all API keys"""
    client = YouTubeVideoClient(
        video_id=test_video_id,
    )
    
    # Add Claude processor
    try:
        client.add_processor("claude_35_sonnet", claude_config)
    except Exception as e:
        logger.warning(f"Could not add Claude processor: {e}")
    
    # Add GPT processor
    try:
        client.add_processor("gpt_4o", gpt_config)
    except Exception as e:
        logger.warning(f"Could not add GPT-4 processor: {e}")
    
    return client

@pytest.fixture
def claude_only_client(test_video_id, claude_config):
    """Fixture providing YouTubeVideoClient instance with only Claude"""
    client = YouTubeVideoClient(
        video_id=test_video_id,
    )
    
    try:
        client.add_processor("claude_35_sonnet", claude_config)
    except Exception as e:
        logger.warning(f"Could not add Claude processor: {e}")
    
    return client

@pytest.fixture
def gpt4_only_client(test_video_id, gpt_config):
    """Fixture providing YouTubeVideoClient instance with only GPT-4"""
    client = YouTubeVideoClient(
        video_id=test_video_id,
    )
    
    try:
        client.add_processor("gpt_4o", gpt_config)
    except Exception as e:
        logger.warning(f"Could not add GPT-4 processor: {e}")
    
    return client

@pytest.fixture
def test_video_id():
    """Fixture providing a test video ID"""
    return "eQZbi8HBRcQ"

def _test_video_analysis(client: YouTubeVideoClient, 
                        processor_names: List[str],
                        task: Task = Task.summarize(),
                        role: Optional[Role] = Role.research_assistant()) -> None:
    """Helper function to test video analysis with different processors"""
    if not os.getenv("YOUTUBE_API_KEY"):
        pytest.skip("No YouTube API key available")
        
    results = client.analyze_video(
        processor_names=processor_names,
        task=task,
        role=role
    )
    
    assert len(results) == len(processor_names)
    
    for result in results:
        model = result.model
        content = result.content
        print(f"\nResult from {model}:")
        print(content)
        
        # Verify result structure using AnalysisResult
        assert result.content
        assert result.model
        assert result.role == (role.name if role else None)
        assert result.task == task.name
        assert result.html
        assert result.timestamp
        
        # Check video info using client properties
        assert client.title
        assert client.transcript
        assert client.url == f"https://www.youtube.com/watch?v={client._video.video_id}"

def test_client_initialization(test_video_id):
    """Test client initialization with different API key combinations"""
    # Initialize client
    client = YouTubeVideoClient(
        video_id=test_video_id,
    )
    
    # Test with all API keys
    try:
        claude_config = LLMConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        client.add_processor("claude_35_sonnet", claude_config)
    except Exception as e:
        logger.warning(f"Could not add Claude processor: {e}")
        
    try:
        gpt_config = LLMConfig(
            provider="openai",
            model_name="gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        client.add_processor("gpt_4o", gpt_config)
    except Exception as e:
        logger.warning(f"Could not add GPT-4 processor: {e}")
    
    processors = client.get_processors()
    assert "claude_35_sonnet" in processors or "gpt_4o" in processors
    
    # Test with only Claude
    client = YouTubeVideoClient(
        video_id=test_video_id,
    )
    try:
        claude_config = LLMConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        client.add_processor("claude_35_sonnet", claude_config)
        assert "claude_35_sonnet" in client.get_processors()
        assert "gpt_4o" not in client.get_processors()
    except Exception as e:
        logger.warning(f"Could not add Claude processor: {e}")
    
    # Test with only GPT-4
    client = YouTubeVideoClient(
        video_id=test_video_id,
    )
    try:
        gpt_config = LLMConfig(
            provider="openai",
            model_name="gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        client.add_processor("gpt_4o", gpt_config)
        assert "claude_35_sonnet" not in client.get_processors()
        assert "gpt_4o" in client.get_processors()
    except Exception as e:
        logger.warning(f"Could not add GPT-4 processor: {e}")
    
    # Test with no LLM API keys
    client = YouTubeVideoClient(
        video_id=test_video_id,
    )
    assert len(client.get_processors()) == 0

def test_analyze_video_with_all_processors(youtube_client, test_video_id):
    """Test video analysis with all preloaded processors"""
    _test_video_analysis(
        client=youtube_client,
        processor_names=["claude_35_sonnet", "gpt_4o"]
    )

def test_analyze_video_with_claude_only(claude_only_client, test_video_id):
    """Test video analysis with only Claude"""
    _test_video_analysis(
        client=claude_only_client,
        processor_names=["claude_35_sonnet"],
        task=Task.summarize(),
        role=Role.financial_analyst()
    )

def test_analyze_video_with_custom_task(youtube_client, test_video_id):
    """Test video analysis with custom task"""
    custom_task = Task.custom(prompt="who is the speaker?")
    _test_video_analysis(
        client=youtube_client,
        processor_names=["claude_35_sonnet"],
        task=custom_task
    )

def test_chat_functionality(claude_only_client, test_video_id):
    """Test chat functionality with Claude"""
    if not os.getenv("YOUTUBE_API_KEY"):
        pytest.skip("No YouTube API key available")
        
    response = claude_only_client.chat(
        processor_name="claude_35_sonnet",
        question="Is this video about SpaceX?"
    )

    assert response is not None
    assert len(response) > 0
    print(response)

def test_error_handling(youtube_client):
    """Test error handling"""
    # Test with invalid processor name
    with pytest.raises(ValueError) as exc_info:
        results = youtube_client.analyze_video(
            processor_names=["invalid_processor"],
            task=Task.summarize()
        )
    
    # Verify the error message
    assert "Processors not found: invalid_processor" in str(exc_info.value)

def test_processor_initialization(test_video_id):
    """Test adding processors to YouTubeVideoClient"""
    client = YouTubeVideoClient(
        video_id=test_video_id,
    )
    
    # Test adding Claude processor
    try:
        claude_config = LLMConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        client.add_processor("claude_35_sonnet", claude_config)
    except Exception as e:
        logger.warning(f"Could not add Claude processor: {e}")

    # Test adding GPT processor
    try:
        gpt_config = LLMConfig(
            provider="openai",
            model_name="gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        client.add_processor("gpt_4o", gpt_config)
    except Exception as e:
        logger.warning(f"Could not add GPT-4 processor: {e}")

    # Verify processors
    processors = client.get_processors()
    assert "claude_35_sonnet" in processors or "gpt_4o" in processors, "No processors were added successfully"
    
    # Test processor validation
    with pytest.raises(ValueError):
        client.analyze_video(["nonexistent_processor"], task=Task.summarize())

# def test_html_formatting():
#     """Test HTML formatting of analysis results"""
#     content = '[Test Header]\n• Test bullet point\nTest paragraph'
#     config = LLMConfig(
#         provider="test",
#         model_name="test_model",
#         api_key="dummy_key",
#         temperature=0.5
#     )
    
#     client = YouTubeVideoClient("dummy_key")
#     html = client._format_analysis_result(content, content, config)
    
#     # Update expected elements to match current implementation
#     assert '.section-header{color:#0068C9' in html  # Check for blue header styling
#     assert '<div class="section-header">' in html  # Check for header div
#     assert '<ul>' in html  # Check for bullet point list
#     assert '<p>' in html  # Check for paragraph