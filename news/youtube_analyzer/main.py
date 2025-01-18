"""
YouTube Video Analysis Tool

This script provides the core functionality for analyzing YouTube videos using various LLM models.
It can be used as a command-line tool or imported by other modules (like streamlit_app.py).

Required Environment Variables:
    - YOUTUBE_API_KEY: API key for YouTube Data API
    - ANTHROPIC_API_KEY: API key for Claude models (optional)
    - OPENAI_API_KEY: API key for GPT models (optional)

Example Commands:
    # Basic analysis with default settings
    python main.py --video "https://www.youtube.com/watch?v=WQ35G6XI8Uw"
    
    # Analysis with specific model
    python main.py --video WQ35G6XI8Uw --models claude_35_sonnet
    
    # Custom analysis
    python main.py --video WQ35G6XI8Uw --task custom --prompt "List main topics" --models claude_35_sonnet
    
    # Chat mode with Claude
    python main.py --video WQ35G6XI8Uw --chat claude_35_sonnet
    
    # Chat mode with GPT-4
    python main.py --video WQ35G6XI8Uw --chat gpt_4o
    
Note: 
    - When using URLs, wrap them in quotes to handle special characters
    - Video IDs can be used directly without quotes
"""

from youtube_video_client import YouTubeVideoClient
from llm_processor import Task, Role
from utils import extract_video_id
import os
import logging
import sys
import argparse
from typing import List, Optional, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def initialize_client(youtube_api_key: str,
                     anthropic_api_key: Optional[str] = None,
                     openai_api_key: Optional[str] = None) -> Optional[YouTubeVideoClient]:
    """Initialize YouTubeVideoClient with provided API keys"""
    try:
        client = YouTubeVideoClient(
            youtube_api_key=youtube_api_key,
            anthropic_api_key=anthropic_api_key,
            openai_api_key=openai_api_key
        )
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
        client = initialize_client(
            youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        if not client:
            return []

        video_id = extract_video_id(video)
        
        # Set models if not provided
        if not models:
            models = list(client.get_available_processors().keys())
            
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
            video_id=video_id,
            processor_names=models,
            task=task,
            role=role
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Error analyzing video: {e}")
        return []

def chat_mode(client: YouTubeVideoClient, video: str, model: str):
    """Interactive chat mode for discussing a video
    
    Args:
        client: Initialized YouTubeVideoClient
        video: YouTube video URL or ID
        model: Model to use for chat (e.g., 'claude_35_sonnet')
    """
    video_id = extract_video_id(video)
    print(f"\nStarting chat mode with {model}...")
    print("Type 'exit' to quit, 'switch' to change models, or your question.")
    
    available_models = list(client.get_available_processors().keys())
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
                question=question,
                video_id=video_id
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

def main():
    """Command-line interface for video analysis"""
    parser = argparse.ArgumentParser(description="Analyze YouTube videos using LLM models")
    parser.add_argument("--video", required=True, help="YouTube video URL or video ID")
    parser.add_argument("--models", nargs="+", help="Models to use for analysis")
    parser.add_argument("--task", choices=["summarize", "custom"], default="summarize",
                      help="Type of analysis to perform")
    parser.add_argument("--prompt", help="Custom analysis prompt")
    parser.add_argument("--role", choices=["research_assistant", "financial_analyst"],
                      help="Optional role for analysis")
    parser.add_argument("--chat", action="store_true", 
                      help="Enter interactive chat mode after analysis")
    parser.add_argument("--chat-model", 
                      help="Specify model to use in chat mode (defaults to first available)")
    
    args = parser.parse_args()
    
    # Initialize client first
    client = initialize_client(
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    if not client:
        print("Failed to initialize client. Please check API keys.")
        return
    
    # Run initial analysis
    results = analyze_video(
        video=args.video,
        models=args.models,
        task_type=args.task,
        custom_prompt=args.prompt,
        role_type=args.role
    )
    
    # Print analysis results
    for result in results:
        print(f"\nAnalysis by {result['analysis']['model']}:")
        print("-" * 80)
        print(result['analysis']['content'])
        print("-" * 80)
    
    # Enter chat mode if requested
    if args.chat:
        available_models = list(client.get_available_processors().keys())
        
        # Determine which model to use for chat
        chat_model = None
        if args.chat_model:
            if args.chat_model in available_models:
                chat_model = args.chat_model
            else:
                print(f"\nRequested chat model '{args.chat_model}' not available.")
                print(f"Available models: {', '.join(available_models)}")
                return
        else:
            # Use the first specified model or first available
            chat_model = args.models[0] if args.models else available_models[0]
        
        chat_mode(client, args.video, chat_model)

if __name__ == "__main__":
    main()