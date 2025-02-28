import pytest
from ..libs.llm_processor import LLMProcessor, LLMConfig, Role, Task
import os
from pathlib import Path
import logging
import sys
from typing import Optional

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create logger for this module
logger = logging.getLogger(__name__)

# Ensure all loggers are set to INFO level
logging.getLogger('llm_processor').setLevel(logging.INFO)

@pytest.fixture
def test_text():
    """Fixture providing sample text for testing"""
    test_data_path = Path(__file__).parent / "test_data" / "test_input_text.txt"
    
    with open(test_data_path, 'r', encoding='utf-8') as file:
        return file.read()

@pytest.fixture
def anthropic_config():
    """Fixture providing Anthropic config"""
    return LLMConfig(
        provider="anthropic",
        model_name="claude-3-7-sonnet-20250219",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        temperature=0.7
    )

@pytest.fixture
def openai_config():
    """Fixture providing OpenAI config"""
    return LLMConfig(
        provider="openai",
        model_name="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.7
    )

@pytest.fixture
def anthropic_chat_processor(anthropic_config):
    """Fixture providing Anthropic LLMProcessor with cleanup"""
    processor = LLMProcessor(anthropic_config)
    yield processor
    if hasattr(processor, 'memory'):
        processor.reset_chat()

@pytest.fixture
def openai_chat_processor(openai_config):
    """Fixture providing OpenAI LLMProcessor with cleanup"""
    processor = LLMProcessor(openai_config)
    yield processor
    if hasattr(processor, 'memory'):
        processor.reset_chat()

### Text processing tests
def process_text_with_config(config: LLMConfig, test_text: str, task: Task, role: Optional[Role] = None) -> Optional[str]:
    """Helper function to process text with given config, task, and role
    
    Args:
        config: LLM configuration
        test_text: Input text to process
        task: Task to perform
        role: Optional role (defaults to None)
        
    Returns:
        Processed text or None if skipped/failed
    """
    print(f"\nTesting with {config.provider}...")
    
    # Skip if no API key
    if not config.api_key:
        print(f"Skipping test - no {config.provider} API key")
        pytest.skip(f"No {config.provider} API key available")
        return None
    
    processor = LLMProcessor(config)
    
    print(f"Running {task.name} task with {role.name if role else 'no'} role...")
    result = processor.process_text(
        text=test_text,
        task=task,
        role=role
    )
    
    assert result is not None
    print(f"Result: {result}")
    logger.info(f"Result from {task.name}: {result}")
    return result

def test_process_text_anthropic(anthropic_config, test_text):
    """Test text processing with Anthropic"""
    process_text_with_config(
        config=anthropic_config,
        test_text=test_text,
        role=Role.research_assistant(),
        task=Task.summarize()
    )    
    process_text_with_config(
        config=anthropic_config,
        test_text=test_text,
        task=Task.market_analysis(),
        role=Role.financial_analyst()
    )

def test_process_text_openai(openai_config, test_text):
   process_text_with_config(
        config=openai_config,
        test_text=test_text,
        role=Role.research_assistant(),
        task=Task.summarize()
    )    
   
   process_text_with_config(
        config=openai_config,
        test_text=test_text,
        task=Task.market_analysis(),
        role=Role.financial_analyst()
    )
def test_custom_roles_and_tasks(anthropic_config, test_text):

    if not anthropic_config.api_key:
        pytest.skip("No Anthropic API key available")
    
    processor = LLMProcessor(anthropic_config)
    
    custom_role = Role.custom(
        system_prompt="You are a stock market technical analyst.",
        name="technical_analyst",
        description="Analyzes stock market patterns"
    )
    assert custom_role.system_prompt is not None
    
    # Test custom task
    custom_task = Task.custom(
        prompt="Analyze the technical trading patterns in this text.",
        name="technical_analysis",
        description="Technical trading pattern analysis"
    )
    assert "technical trading patterns" in custom_task.prompt_template
    
    # Test processing with custom role and task
    result = processor.process_text(
        text=test_text,
        role=custom_role,
        task=custom_task
    )
    assert result is not None
    print(f"Custom role/task result: {result}")

def test_error_handling():
    """Test error handling"""
    config = LLMConfig(
        provider="invalid",
        model_name="invalid",
        api_key="invalid"
    )
    
    with pytest.raises(ValueError, match="Unsupported provider"):
        LLMProcessor(config) 

### Chat functionality tests

def _test_chat_functionality(config: LLMConfig, test_text: str, provider: str):
    """Generic chat functionality test"""
    print(f"\nTesting chat functionality with {provider}...")
    
    # Skip if no API key
    if not config.api_key:
        pytest.skip(f"No {provider} API key available")
    
    processor = LLMProcessor(config)
    
    # Initialize chat with test context
    processor.init_chat_with_context(context=test_text)
    
    # Test basic chat interaction
    response1 = processor.chat("What is the main topic of this content?")
    assert response1 is not None
    print(f"First response: {response1}")
    
    # Test follow-up question
    response2 = processor.chat("What is the percentage mentioned?")
    assert response2 is not None
    print(f"Second response: {response2}")
    
    # Test error handling
    new_processor = LLMProcessor(config)
    with pytest.raises(ValueError, match="Chat not initialized"):
        new_processor.chat("This should fail")

def test_chat_functionality_anthropic(anthropic_config, test_text):
    """Test chat functionality with Anthropic"""
    _test_chat_functionality(anthropic_config, test_text, "Anthropic")

def test_chat_functionality_openai(openai_config, test_text):
    """Test chat functionality with OpenAI"""
    _test_chat_functionality(openai_config, test_text, "OpenAI")

def test_chat_memory(anthropic_config, test_text):
    """Test chat memory retention"""
    print("\nTesting chat memory...")
    
    # Skip if no API key
    if not anthropic_config.api_key:
        pytest.skip("No Anthropic API key available")
    
    processor = LLMProcessor(anthropic_config)
    processor.init_chat_with_context(context=test_text)
    
    # Test memory retention
    response1 = processor.chat("What company is discussed?")
    response2 = processor.chat("What happened to their stock price?")
    
    assert response1 is not None
    assert response2 is not None
    print(f"Memory test responses:\n1: {response1}\n2: {response2}")
    logger.info(f"Memory test responses:\n1: {response1}\n2: {response2}")