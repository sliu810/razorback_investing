import os
from typing import Optional, Tuple
from video_analyzer import VideoAnalyzer, LLMConfig, AnalysisConfig, LLMProcessor
from video import Video
from youtube_api_client import YouTubeAPIClient
import logging

logger = logging.getLogger(__name__)

class YouTubeAnalysisClient:
    """Client class that uses VideoAnalyzer for YouTube videos"""
    
    def __init__(self):
        self.analyzer = VideoAnalyzer(
            config=AnalysisConfig(output_dir="outputs")
        )
        
        # Initialize with API key from environment or Streamlit secrets
        try:
            import streamlit as st
            api_key = os.getenv("YOUTUBE_API_KEY") or st.secrets["YOUTUBE_API_KEY"]
            if not api_key:
                raise ValueError("YouTube API key not found")
            
            # Initialize YouTube API client
            print(f"Attempting to initialize YouTube API client...")  # Debug print
            self.youtube_client = YouTubeAPIClient(api_key)
            print("YouTube API client initialized successfully")  # Debug print
        except Exception as e:
            print(f"Failed to initialize YouTube API client: {str(e)}")
            raise
    
    def setup_processors(self) -> Tuple[LLMProcessor, LLMProcessor]:
        """Initialize and add processors to analyzer"""
        claude = LLMProcessor(LLMConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            temperature=0.7,
            max_tokens=4000
        ))
        
        gpt4 = LLMProcessor(LLMConfig(
            provider="openai",
            model_name="gpt-4o",
            temperature=0.7,
            max_tokens=4000
        ))
        
        # Add to analyzer
        self.analyzer.add_processor(claude)
        self.analyzer.add_processor(gpt4)
        
        return claude, gpt4
    
    def process_video(self, video_id: str) -> Optional[Video]:
        """Process a video and return Video object"""
        try:
            # Create Video object
            video = Video(video_id)
            
            # Get video info and transcript
            video.get_video_metadata_and_transcript()
            
            logger.debug(f"Video info fetched - ID: {video.video_id}, "
                        f"Title: {video.title}, "
                        f"URL: {video.url}")
            
            return video
            
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            return None
    
    def analyze_text(self, 
                    processor: LLMProcessor, 
                    text: str,
                    role_name: str = "research_assistant",
                    task_name: str = "summarize_transcript") -> str:
        """Analyze text using specified processor"""
        return processor.process_text(
            text=text,
            role_name=role_name,
            task_name=task_name
        )
    
    def chat(self, 
            processor: LLMProcessor,
            question: str,
            context: str) -> str:
        """Chat about video content"""
        return processor.chat(
            question=question,
            context=context
        )