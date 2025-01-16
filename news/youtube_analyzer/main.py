# main.py
import argparse
from youtube_client import YouTubeAnalysisClient
import time

def show_cli_progress(message: str):
    """Show progress message with timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def main():
    """CLI interface"""
    parser = argparse.ArgumentParser(description='Analyze YouTube video and chat about it')
    parser.add_argument('--videoid', required=True, help='YouTube video ID')
    parser.add_argument('--provider', choices=['openai', 'anthropic'], help='Provider for analysis')
    parser.add_argument('--chat_provider', choices=['openai', 'anthropic'], default='openai',
                      help='Provider for chat (default: openai)')
    parser.add_argument('--chat_model', default='gpt-4o',
                      help='Model name for chat (default: gpt-4o)')
    
    args = parser.parse_args()
    
    show_cli_progress("Initializing YouTube Analyzer...")
    client = YouTubeAnalysisClient()
    
    show_cli_progress("Setting up processors...")
    claude, gpt4 = client.setup_processors()
    
    show_cli_progress(f"Processing video {args.videoid}...")
    video = client.process_video(args.videoid)
    
    if video:
        show_cli_progress("Video processed successfully!")
        
        # Use specified provider or both for analysis
        processors = []
        if args.provider == 'openai':
            processors = [gpt4]
        elif args.provider == 'anthropic':
            processors = [claude]
        else:
            processors = [claude, gpt4]
        
        # Run analysis
        for processor in processors:
            provider_name = processor.config.provider
            show_cli_progress(f"Analyzing with {provider_name}...")
            analysis = client.analyze_text(
                processor=processor,
                text=video.transcript
            )
            print(f"\nAnalysis from {provider_name}:\n{analysis}\n")
            show_cli_progress(f"Analysis complete for {provider_name}")
        
        # Select chat processor based on chat_provider
        chat_processor = gpt4 if args.chat_provider == 'openai' else claude
        show_cli_progress(f"Chat ready using {args.chat_provider}")
        
        # Interactive chat loop
        while True:
            question = input("\nEnter your question (or 'quit' to exit): ")
            if question.lower() == 'quit':
                break
            
            show_cli_progress("Processing your question...")
            response = client.chat(
                processor=chat_processor,
                question=question,
                context=video.transcript
            )
            print("\nResponse:", response)
            show_cli_progress("Response complete")
    else:
        show_cli_progress("Error: Could not process video")

if __name__ == "__main__":
    main()