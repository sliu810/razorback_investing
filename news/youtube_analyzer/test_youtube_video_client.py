import pytest
from youtube_video_client import YouTubeVideoClient
from llm_processor import LLMConfig, Role, Task
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
def youtube_client():
    """Fixture providing YouTubeVideoClient instance with all API keys"""
    client = YouTubeVideoClient(
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    return client

@pytest.fixture
def claude_only_client():
    """Fixture providing YouTubeVideoClient instance with only Claude"""
    client = YouTubeVideoClient(
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    return client

@pytest.fixture
def gpt4_only_client():
    """Fixture providing YouTubeVideoClient instance with only GPT-4"""
    client = YouTubeVideoClient(
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    return client

@pytest.fixture
def test_video_id():
    """Fixture providing a test video ID"""
    return "eQZbi8HBRcQ"

def _test_video_analysis(client: YouTubeVideoClient, 
                        video_id: str,
                        processor_names: List[str],
                        task: Task = Task.summarize(),
                        role: Optional[Role] = Role.research_assistant(),
                        custom_prompt: Optional[str] = None) -> None:
    """Helper function to test video analysis with different processors"""
    if not os.getenv("YOUTUBE_API_KEY"):
        pytest.skip("No YouTube API key available")
        
    results = client.analyze_video(
        video_id=video_id,
        processor_names=processor_names,
        task=task,
        role=role
    )
    
    assert len(results) == len(processor_names), f"Expected {len(processor_names)} results, got {len(results)}"
    
    for result in results:
        model = result['analysis']['model']
        content = result['analysis']['content']
        print(f"\nResult from {model}:")
        print(content)
        
        # Verify result structure
        assert "video_info" in result
        assert "analysis" in result
        assert "html" in result
        
        # Check video info
        video_info = result["video_info"]
        assert video_info["id"] == video_id
        assert video_info["url"] == f"https://www.youtube.com/watch?v={video_id}"
        assert video_info["title"]
        assert video_info["transcript"]
        
        # Check analysis content
        analysis = result["analysis"]
        assert analysis["content"]
        assert analysis["model"]
        assert analysis["role"] == (role.name if role else None)
        assert analysis["task"] == task.name
        print(f"Analysis content for {model}:")
        print(analysis["content"])

def test_client_initialization():
    """Test client initialization with different API key combinations"""
    # Test with all API keys
    client = YouTubeVideoClient(
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    assert "claude_35_sonnet" in client.processors
    assert "gpt_4o" in client.processors
    
    # Test with only Claude
    client = YouTubeVideoClient(
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    assert "claude_35_sonnet" in client.processors
    assert "gpt_4o" not in client.processors
    
    # Test with only GPT-4
    client = YouTubeVideoClient(
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    assert "claude_35_sonnet" not in client.processors
    assert "gpt_4o" in client.processors
    
    # Test with no LLM API keys
    client = YouTubeVideoClient(youtube_api_key=os.getenv("YOUTUBE_API_KEY"))
    assert len(client.processors) == 0

def test_add_custom_processor(youtube_client):
    """Test adding a custom processor"""
    custom_config = LLMConfig(
        provider="anthropic",
        model_name="claude-3-opus-20240229",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        temperature=0.3
    )
    
    youtube_client.add_processor("custom_claude", custom_config)
    assert "custom_claude" in youtube_client.processors
    assert youtube_client.processors["custom_claude"].config == custom_config

def test_analyze_video_with_all_processors(youtube_client, test_video_id):
    """Test video analysis with all preloaded processors"""
    _test_video_analysis(
        client=youtube_client,
        video_id=test_video_id,
        processor_names=["claude_35_sonnet", "gpt_4o"]
    )

def test_analyze_video_with_claude_only(claude_only_client, test_video_id):
    """Test video analysis with only Claude"""
    _test_video_analysis(
        client=claude_only_client,
        video_id=test_video_id,
        processor_names=["claude_35_sonnet"],
        task=Task.summarize(),
        role=Role.financial_analyst()
    )

def test_analyze_video_with_custom_task(youtube_client, test_video_id):
    """Test video analysis with custom task"""
    custom_task = Task.custom(prompt="who is the speaker?")
    _test_video_analysis(
        client=youtube_client,
        video_id=test_video_id,
        processor_names=["claude_35_sonnet"],
        task=custom_task
    )

def test_chat_functionality(claude_only_client, test_video_id):
    """Test chat functionality with Claude"""
    if not os.getenv("YOUTUBE_API_KEY"):
        pytest.skip("No YouTube API key available")
        
    response = claude_only_client.chat(
        processor_name="claude_35_sonnet",
        question="Is this video about SpaceX?",
        video_id=test_video_id
    )
    
    assert response is not None
    assert len(response) > 0
    print(response)

def test_error_handling(youtube_client):
    """Test error handling"""
    # Test with invalid video ID
    results = youtube_client.analyze_video(
        video_id="invalid_id",
        processor_names=["claude_35_sonnet"],
        task=Task.summarize()
    )
    assert len(results) == 0
    
    # Test with invalid processor name
    results = youtube_client.analyze_video(
        video_id="dQw4w9WgXcQ",
        processor_names=["invalid_processor"],
        task=Task.summarize()
    )
    assert len(results) == 0
    
    # Test chat with invalid processor
    response = youtube_client.chat(
        processor_name="invalid_processor",
        question="test",
        video_id="dQw4w9WgXcQ"
    )
    assert response is None

def test_html_formatting():
    """Test HTML formatting of analysis results"""
    content = '[Test Header]\n• Test bullet point\nTest paragraph'
    config = LLMConfig(
        provider="test",
        model_name="test_model",
        api_key="dummy_key",
        temperature=0.5
    )
    
    client = YouTubeVideoClient("dummy_key")
    html = client._format_analysis_result(content, content, config)
    
    # Update expected elements to match current implementation
    assert '.section-header{color:#0068C9' in html  # Check for blue header styling
    assert '<div class="section-header">' in html  # Check for header div
    assert '<ul>' in html  # Check for bullet point list
    assert '<p>' in html  # Check for paragraph