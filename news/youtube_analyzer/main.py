# main.py
import os
import argparse
from video_analyzer import VideoAnalyzer, LLMConfig
from llm_processor import LLMProcessor
from video import Video

def setup_processors(provider=None, model=None):
    """
    Initialize LLM processors based on configuration
    
    Args:
        provider: Optional provider for analysis (openai or anthropic)
        model: Optional model name for the specified provider
    """
    processors = []
    
    # Default configurations
    default_configs = {
        "anthropic": LLMConfig(
            provider="anthropic",
            model_name="claude-3-opus-20240229",
            temperature=0.7,
            max_tokens=4000
        ),
        "openai": LLMConfig(
            provider="openai",
            model_name="gpt-4-0125-preview",
            temperature=0.7,
            max_tokens=4000
        )
    }
    
    if provider:
        # Use specified provider and model
        if provider not in default_configs:
            raise ValueError(f"Unsupported provider: {provider}")
        
        config = default_configs[provider]
        if model:
            config.model_name = model
        processors.append(LLMProcessor(config))
    else:
        # Use both providers with default models
        processors = [LLMProcessor(config) for config in default_configs.values()]
    
    return processors

def process_video(video_id: str):
    """Process video and get transcript"""
    video = Video(video_id)
    if not video.fetch_video_info():
        print(f"Could not fetch video info for {video_id}")
        return None
    return video

def main():
    # Set up command line arguments
    parser = argparse.ArgumentParser(description='Analyze YouTube video and chat about it')
    parser.add_argument('--videoid', required=True, help='YouTube video ID')
    parser.add_argument('--provider', choices=['openai', 'anthropic'], help='Provider for analysis')
    parser.add_argument('--model', help='Model name for analysis')
    parser.add_argument('--chat_provider', choices=['openai', 'anthropic'], default='openai', 
                      help='Provider for chat (default: openai)')
    parser.add_argument('--chat_model', default='gpt-4-0125-preview',
                      help='Model name for chat (default: gpt-4-0125-preview)')
    
    args = parser.parse_args()
    
    try:
        # Setup processors based on arguments
        processors = setup_processors(args.provider, args.model)
        
        # Setup chat processor
        chat_config = LLMConfig(
            provider=args.chat_provider,
            model_name=args.chat_model,
            temperature=0.7,
            max_tokens=4000
        )
        chat_processor = LLMProcessor(chat_config)
        
        # Process video
        video = process_video(args.videoid)
        
        if video:
            # Run analysis with all processors
            for processor in processors:
                print(f"\nAnalyzing with {processor.config.provider} {processor.config.model_name}...")
                analysis = processor.process_text(
                    text=video.transcript,
                    role_name="content_summarizer",
                    task_name="summarize_transcript"
                )
                print(f"\nAnalysis:\n{analysis}\n")
            
            # Interactive chat loop
            print(f"\nStarting chat with {chat_processor.config.provider} {chat_processor.config.model_name}")
            while True:
                question = input("\nEnter your question (or 'quit' to exit): ")
                if question.lower() == 'quit':
                    break
                
                response = chat_processor.chat(
                    question=question,
                    context=video.transcript
                )
                print("\nResponse:", response)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()