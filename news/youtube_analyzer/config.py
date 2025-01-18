from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

@dataclass
class AppConfig:
    """Application configuration"""
    # API Keys
    youtube_api_key: str
    openai_api_key: str 
    anthropic_api_key: str
    
    # Output settings
    output_dir: str = "output"
    max_summary_length: int = 4000
    save_format: str = "html"
    
    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        load_dotenv()  # This will load .env file if it exists
        
        return cls(
            youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
    
    @classmethod
    def from_streamlit_secrets(cls):
        """Load configuration from Streamlit secrets"""
        import streamlit as st
        
        return cls(
            youtube_api_key=st.secrets["YOUTUBE_API_KEY"],
            openai_api_key=st.secrets["OPENAI_API_KEY"],
            anthropic_api_key=st.secrets["ANTHROPIC_API_KEY"],
        )

    def validate(self):
        """Validate the configuration"""
        if not self.youtube_api_key:
            raise ValueError("YouTube API key is required")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required")
        if not self.anthropic_api_key:
            raise ValueError("Anthropic API key is required") 