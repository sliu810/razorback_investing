"""
YouTube Video Analysis Tool

This script provides the core functionality for analyzing YouTube videos using various LLM models.
It can be used as a command-line tool or imported by other modules.

Required Environment Variables:
    - YOUTUBE_API_KEY: API key for YouTube Data API (optional, will use default if not provided)
    - ANTHROPIC_API_KEY: API key for Claude models (optional)
    - OPENAI_API_KEY: API key for GPT models (optional)

Example Commands:
    # Basic analysis with default settings (will use all available models)
    python -m youtube_analyzer.apps.video --video "https://www.youtube.com/watch?v=WQ35G6XI8Uw"
    
    # Analysis with specific model
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --models claude_37_sonnet
    
    # Analysis with multiple models
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --models claude_37_sonnet gpt_4o
    
    # Custom analysis with specific prompt
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --task custom --prompt "List the main technical concepts discussed" --models claude_37_sonnet
    
    # Analysis with research assistant role
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --role research_assistant --models claude_37_sonnet
    
    # Analysis followed by chat mode with Claude
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --models claude_37_sonnet --chat
    
    # Direct to chat mode with specific model
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --chat-only --chat-model claude_37_sonnet
    
    # Financial analysis with GPT-4o
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --models gpt_4o --role financial_analyst
    
Note: 
    - When using URLs, wrap them in quotes to handle special characters
    - Video IDs can be used directly without quotes
    - The --models flag accepts multiple models separated by spaces
    - Chat mode can be combined with initial analysis
    - All commands require appropriate API keys set in environment variables
"""
import os
import logging
import sys
import argparse
from typing import List, Optional, Dict

from ..libs.video_client import YouTubeVideoClient
from ..libs.youtube_api_client import YouTubeAPIClient
from ..libs.llm_processor import LLMConfig, Role, Task
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def initialize_client(video_id: str,
                     youtube_api_key: Optional[str] = None,
                     anthropic_api_key: Optional[str] = None,
                     openai_api_key: Optional[str] = None) -> Optional[YouTubeVideoClient]:
    """Initialize YouTubeVideoClient with provided API keys
    
    Args:
        video_id: YouTube video ID to analyze
        youtube_api_key: Optional YouTube Data API key (defaults to env var)
        anthropic_api_key: Optional Anthropic API key for Claude models
        openai_api_key: Optional OpenAI API key for GPT models
    """
    try:
        client = YouTubeVideoClient(
            video_id=video_id,
        )
        
        # Add Claude processor if API key available
        if anthropic_api_key:
            try:
                claude_config = LLMConfig(
                    provider="anthropic",
                    model_name="claude-3-7-sonnet-20250219",
                    api_key=anthropic_api_key
                )
                client.add_processor("claude_37_sonnet", claude_config)
            except Exception as e:
                logger.warning(f"Could not add Claude processor: {e}")
        
        # Add GPT processor if API key available
        if openai_api_key:
            try:
                gpt_config = LLMConfig(
                    provider="openai",
                    model_name="gpt-4o",
                    api_key=openai_api_key
                )
                client.add_processor("gpt_4o", gpt_config)
            except Exception as e:
                logger.warning(f"Could not add GPT processor: {e}")
        
        return client
    except Exception as e:
        logger.error(f"Error initializing client: {e}")
        return None

def analyze_video(video: str,
                 models: List[str] = None,
                 task_type: str = "summarize",
                 custom_prompt: Optional[str] = None,
                 role_type: Optional[str] = None) -> List[Dict]:
    """Analyze a YouTube video using specified models and settings
    
    Args:
        video: YouTube video URL or video ID
        models: List of model names to use (e.g., ['claude_35_sonnet', 'gpt_4o'])
        task_type: Type of analysis ('summarize' or 'custom')
        custom_prompt: Custom analysis prompt (required if task_type is 'custom')
        role_type: Optional role for analysis ('research_assistant' or 'financial_analyst')
    """
    try:
        video_id = YouTubeAPIClient.parse_video_id(video)
        client = initialize_client(
            video_id=video_id,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        if not client:
            return []

        # Set models if not provided
        if not models:
            models = list(client.get_processors().keys())
            
        # Configure task
        if task_type == "custom" and custom_prompt:
            task = Task.custom(prompt=custom_prompt)
        else:
            task = Task.summarize()
            
        # Configure role
        role = None
        if role_type == "research_assistant":
            role = Role.research_assistant()
        elif role_type == "financial_analyst":
            role = Role.financial_analyst()
            
        # Run analysis
        results = client.analyze_video(
            processor_names=models,
            task=task,
            role=role
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Error analyzing video: {e}")
        return []

def chat_mode(video: str, model: str):
    """Interactive chat mode for discussing a video"""
    video_id = YouTubeAPIClient.parse_video_id(video)
    client = initialize_client(
        video_id=video_id,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    if not client:
        print("Failed to initialize client. Please check API keys.")
        return
        
    print(f"\nStarting chat mode with {model}...")
    print("Type 'exit' to quit, 'switch' to change models, or your question.")
    
    available_models = list(client.get_processors().keys())
    current_model = model
    
    while True:
        try:
            question = input(f"\n[{current_model}] Your question: ").strip()
            
            if question.lower() == 'exit':
                print("\nExiting chat mode...")
                break
                
            if question.lower() == 'switch':
                print("\nAvailable models:")
                for idx, m in enumerate(available_models, 1):
                    print(f"{idx}. {m}")
                try:
                    choice = int(input("\nSelect model number: ")) - 1
                    if 0 <= choice < len(available_models):
                        current_model = available_models[choice]
                        print(f"\nSwitched to {current_model}")
                    else:
                        print("\nInvalid choice. Keeping current model.")
                except ValueError:
                    print("\nInvalid input. Keeping current model.")
                continue
                
            if not question:
                continue
                
            print("\nThinking...")
            response = client.chat(
                processor_name=current_model,
                question=question
            )
            
            if response:
                print(f"\nResponse from {current_model}:\n{response}")
            else:
                print("\nNo response received. Please try again.")
                
        except KeyboardInterrupt:
            print("\n\nExiting chat mode...")
            break
        except Exception as e:
            print(f"\nError: {e}")

def parse_args():
    parser = argparse.ArgumentParser(
        description="YouTube Video Analysis Tool",
        epilog="""Examples:
    # Basic analysis with default settings
    python -m youtube_analyzer.apps.video --video "https://www.youtube.com/watch?v=WQ35G6XI8Uw"
    
    # Analysis with specific model
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --models claude_37_sonnet
    
    # Analysis with multiple models
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --models claude_37_sonnet gpt_4o
    
    # Custom analysis with specific prompt
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --task custom --prompt "List the main technical concepts discussed" --models claude_37_sonnet
    
    # Analysis with research assistant role
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --role research_assistant --models claude_37_sonnet
    
    # Analysis followed by chat mode with Claude
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --models claude_37_sonnet --chat
    
    # Direct to chat mode with specific model (skips analysis)
    python -m youtube_analyzer.apps.video --video WQ35G6XI8Uw --chat-only --chat-model claude_37_sonnet
    """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--video", required=True, help="YouTube video URL or video ID")
    parser.add_argument("--models", nargs="+", help="Models to use for analysis")
    parser.add_argument("--task", choices=["summarize", "custom"], default="summarize",
                      help="Type of analysis to perform")
    parser.add_argument("--prompt", help="Custom analysis prompt")
    parser.add_argument("--role", choices=["research_assistant", "financial_analyst"],
                      help="Optional role for analysis")
    parser.add_argument("--chat", action="store_true", 
                      help="Enter interactive chat mode after analysis")
    parser.add_argument("--chat-only", action="store_true",
                      help="Skip analysis and enter chat mode directly")
    parser.add_argument("--chat-model", 
                      help="Specify model to use in chat mode (defaults to first available)")
    
    args = parser.parse_args()
    
    # Validate chat arguments
    if args.chat and args.chat_only:
        parser.error("Please use either --chat OR --chat-only, not both")
        
    return args

def main():
    """Command-line interface for video analysis"""
    args = parse_args()
    
    # Run initial analysis unless chat-only mode
    if not args.chat_only:
        results = analyze_video(
            video=args.video,
            models=args.models,
            task_type=args.task,
            custom_prompt=args.prompt,
            role_type=args.role
        )
        
        # Print analysis results
        for result in results:
            print(f"\nAnalysis by {result.model}:")
            print(result.content)
    
    # Enter chat mode if requested
    if args.chat or args.chat_only:
        chat_model = args.chat_model
        if not chat_model:
            # Use first specified model or let chat_mode handle default
            chat_model = args.models[0] if args.models else None
        
        chat_mode(args.video, chat_model)

if __name__ == "__main__":
    main()