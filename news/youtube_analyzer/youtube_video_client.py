from typing import Dict, List, Optional, Union
import os
from datetime import datetime
from llm_processor import LLMProcessor, LLMConfig, Role, Task
from video import Video
import logging
from googleapiclient.discovery import build
import re

logger = logging.getLogger(__name__)

class YouTubeVideoClient:
    """Client for managing YouTube video analysis with multiple LLM processors
    
    Preloaded Processors (if API keys provided):
        1. "claude_35_sonnet":
           - Provider: Anthropic
           - Model: Claude 3.5 Sonnet (claude-3-5-sonnet-20241022)
           - Temperature: 0.7
           - Requires: anthropic_api_key
           
        2. "gpt_4o":
           - Provider: OpenAI
           - Model: GPT-4 (gpt-4o)
           - Temperature: 0.7
           - Requires: openai_api_key
    
    Example:
        >>> # Initialize with all processors
        >>> client = YouTubeVideoClient(
        ...     youtube_api_key="your_yt_key",
        ...     anthropic_api_key="your_anthropic_key",
        ...     openai_api_key="your_openai_key"
        ... )
        >>> 
        >>> # Check available processors
        >>> print(client.processors.keys())  # ['claude_35_sonnet', 'gpt_4o']
        >>> 
        >>> # Or initialize with just Claude
        >>> client = YouTubeVideoClient(
        ...     youtube_api_key="your_yt_key",
        ...     anthropic_api_key="your_anthropic_key"
        ... )
        >>> print(client.processors.keys())  # ['claude_35_sonnet']
        
    Custom Processors:
        Additional processors can be added using add_processor():
        >>> custom_config = LLMConfig(
        ...     provider="anthropic",
        ...     model_name="claude-3-opus-20240229",
        ...     api_key="your_key",
        ...     temperature=0.3
        ... )
        >>> client.add_processor("my_claude", custom_config)
    """
    
    def __init__(self, youtube_api_key: str, anthropic_api_key: Optional[str] = None, openai_api_key: Optional[str] = None):
        """Initialize YouTube video client with common processors
        
        Args:
            youtube_api_key: YouTube Data API key
            anthropic_api_key: Optional API key for Claude models
            openai_api_key: Optional API key for GPT models
            
        Note:
            Common processors (Claude and GPT-4) will be added automatically if their
            API keys are provided.
            
        Example:
            >>> # Initialize with all processors
            >>> client = YouTubeVideoClient(
            ...     youtube_api_key="your_yt_key",
            ...     anthropic_api_key="your_anthropic_key",
            ...     openai_api_key="your_openai_key"
            ... )
            >>> 
            >>> # Or initialize with just Claude
            >>> client = YouTubeVideoClient(
            ...     youtube_api_key="your_yt_key",
            ...     anthropic_api_key="your_anthropic_key"
            ... )
        """
        self.youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        self.processors: Dict[str, LLMProcessor] = {}
        self.analysis_results: List[Dict] = []
        
        self._initialize_common_processors(anthropic_api_key, openai_api_key)

    def _initialize_common_processors(self, anthropic_api_key: Optional[str], openai_api_key: Optional[str]) -> None:
        """Initialize common processors with provided API keys
        
        Args:
            anthropic_api_key: API key for Claude models
            openai_api_key: API key for GPT models
        """
        if anthropic_api_key:
            try:
                claude_config = LLMConfig(
                    provider="anthropic",
                    model_name="claude-3-5-sonnet-20241022",
                    api_key=anthropic_api_key,
                    temperature=0.7
                )
                self.add_processor("claude_35_sonnet", claude_config)
                logger.info("Added Claude 3.5 Sonnet processor")
            except Exception as e:
                logger.warning(f"Could not add Claude processor: {e}")
        
        if openai_api_key:
            try:
                gpt4_config = LLMConfig(
                    provider="openai",
                    model_name="gpt-4o",
                    api_key=openai_api_key,
                    temperature=0.7
                )
                self.add_processor("gpt_4o", gpt4_config)
                logger.info("Added GPT-4 processor")
            except Exception as e:
                logger.warning(f"Could not add GPT-4 processor: {e}")

    def add_processor(self, name: str, config: LLMConfig) -> None:
        """Add a custom processor with given configuration
        
        Args:
            name: Unique name for the processor
            config: LLM configuration
        """
        try:
            self.processors[name] = LLMProcessor(config)
            logger.info(f"Processor '{name}' initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize processor '{name}': {e}")
            raise

    def analyze_video(self, 
                     video_id: str, 
                     processor_names: List[str], 
                     task: Task,
                     role: Optional[Role] = None,
                     status_container=None) -> List[Dict]:
        """Analyze YouTube video using specified processors and role/task
        
        Args:
            video_id: YouTube video ID
            processor_names: List of processor names to use for analysis
            task: Analysis task to perform
            role: Optional role for the analysis
            status_container: Optional UI container for status updates
            
        Returns:
            List of dictionaries containing analysis results. Each dictionary has:
            {
                'video_info': {
                    'id': str,          # YouTube video ID
                    'url': str,         # Full YouTube URL
                    'title': str,       # Video title
                    'duration': float,  # Duration in minutes
                    'channel': str,     # Channel name
                    'transcript': str   # Full video transcript
                },
                'analysis': {
                    'content': str,     # Analysis text from LLM
                    'model': str,       # Format: "provider/model_name"
                    'timestamp': str,   # ISO format timestamp
                    'role': str,        # Name of role used
                    'task': str         # Name of task performed
                },
                'html': str            # Formatted HTML version of analysis
            }
        """
        if not self.processors:
            raise ValueError("No processors available. Please add processors before analyzing videos.")
        
        if not processor_names:
            raise ValueError("No processor names specified. Please select at least one processor.")

        try:
            # Get video data
            if status_container:
                status_container.info("📥 Fetching video metadata and transcript...")
            logger.info(f"Fetching video metadata and transcript for {video_id}")
            
            video = Video(video_id)
            video.get_video_metadata_and_transcript()
            
            if not video.transcript or not video.transcript[0]:
                logger.error("No transcript available")
                if status_container:
                    status_container.error("❌ No transcript available for this video")
                return []

            transcript_text = video.transcript[0]
            analyses = []

            for proc_name in processor_names:
                if proc_name not in self.processors:
                    logger.error(f"Processor '{proc_name}' not found")
                    continue

                try:
                    if status_container:
                        status_container.info(f"🤖 Analyzing with {proc_name}...")
                    logger.info(f"Starting analysis with {proc_name}")

                    processor = self.processors[proc_name]
                    analysis = processor.process_text(
                        text=transcript_text,
                        task=task,
                        role=role
                    )

                    if analysis:
                        result = {
                            'video_info': {
                                'id': video.video_id,
                                'url': video.url,
                                'title': video.title,
                                'duration': video.duration_minutes,
                                'channel': video.channel_name,
                                'transcript': transcript_text
                            },
                            'analysis': {
                                'content': analysis,
                                'model': f"{processor.config.provider}/{processor.config.model_name}",
                                'timestamp': datetime.now().isoformat(),
                                'role': role.name if role else None,
                                'task': task.name
                            },
                            'html': self._format_analysis_result(video, analysis, processor.config)
                        }
                        analyses.append(result)
                        self.analysis_results.append(result)
                        
                        if status_container:
                            status_container.success(f"✅ Analysis complete for {proc_name}")
                        logger.info(f"Analysis complete for {proc_name}")

                except Exception as e:
                    if status_container:
                        status_container.error(f"❌ Error with {proc_name}: {str(e)}")
                    logger.error(f"Error with {proc_name}: {e}")
                    continue

            return analyses

        except Exception as e:
            logger.error(f"Error analyzing video: {e}")
            if status_container:
                status_container.error(f"❌ Error analyzing video: {e}")
            return []

    def chat(self, processor_name: str, question: str, video_id: str) -> Optional[str]:
        """Chat about video content using specified processor
        
        Args:
            processor_name: Name of the processor to use
            question: Question to ask about the video
            video_id: YouTube video ID
            
        Returns:
            Model's response or None if error occurs
        """
        if processor_name not in self.processors:
            logger.error(f"Processor '{processor_name}' not found")
            return None

        try:
            # Get video if not already analyzed
            video = Video(video_id)
            video.get_video_metadata_and_transcript()
            
            if not video.transcript or not video.transcript[0]:
                logger.error("No transcript available for chat")
                return None

            processor = self.processors[processor_name]
            processor.init_chat_with_context(video.transcript[0])
            return processor.chat(question)

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return None

    def _format_analysis_result(self, video: Video, analysis: str, config: LLMConfig) -> str:
        """Format analysis with video context into HTML. Pure display, no coupling with chat."""
        formatted_analysis = self._format_text_to_html(analysis.strip())
        
        html = f"""<style>.section-header{{color:#0068C9!important;font-weight:bold;font-size:1.2em;margin-top:20px;margin-bottom:10px;padding:5px 0}}.video-info{{margin-bottom:20px}}.analysis-content{{margin-top:20px}}.video-link{{margin:10px 0}}</style><div class="video-info"><h2>{video.title}</h2><div class="video-link"><a href="{video.url}" target="_blank">Watch on YouTube</a></div></div><div class="analysis-content">{formatted_analysis}</div>"""
        
        return html

    def _format_text_to_html(self, text: str) -> str:
        """Convert text to HTML with basic formatting
        
        Formatting Rules:
        1. Headers:
           - Any text between square brackets [Header Text] becomes a section header
           - Special characters allowed inside brackets (e.g., [M&A Analysis], [Intel's Future])
        
        2. Lists:
           - Lines starting with • or - become list items
           - Consecutive list items are grouped in a <ul> element
           - List closes when a non-bullet line is encountered
        
        3. Paragraphs:
           - Any line that's not a header or bullet point becomes a paragraph
           - Empty lines are skipped
        
        Example Input:
            [Market Analysis]
            • Stock rose 10%
            • Trading volume increased
            This is a regular paragraph
            [Next Section]
        
        Example Output:
            <div class="section-header">Market Analysis</div>
            <ul>
                <li>Stock rose 10%</li>
                <li>Trading volume increased</li>
            </ul>
            <p>This is a regular paragraph</p>
            <div class="section-header">Next Section</div>
        """
        # First split into lines for easier processing
        lines = text.split('\n')
        formatted_lines = []
        
        # Track if we're currently building a list
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:  # Skip empty lines
                continue
            
            # Rule 1: Headers in brackets
            if line.startswith('['):
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                header_match = re.match(r'\[(.*?)\]', line)
                if header_match:
                    formatted_lines.append(f'<div class="section-header">{header_match.group(1).strip()}</div>')
                continue
            
            # Rule 2: Bullet points
            if line.startswith(('•', '-')):
                line = re.sub(r'^[•-]\s*', '', line)  # Remove bullet and spaces
                if not in_list:
                    formatted_lines.append('<ul>')
                    in_list = True
                formatted_lines.append(f'<li>{line}</li>')
            
            # Rule 3: Regular paragraphs
            else:
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                formatted_lines.append(f'<p>{line}</p>')
        
        # Close any open list at the end
        if in_list:
            formatted_lines.append('</ul>')
        
        # Join all lines and return
        return '\n'.join(formatted_lines)

    def add_common_processors(self, use_claude: bool = True, use_gpt4: bool = True) -> None:
        """Add commonly used processors with standard configurations
        
        This is a convenience method for adding the most commonly used processors
        with recommended settings. For custom configurations, use add_processor()
        directly.
        
        Args:
            use_claude: Whether to add Claude 3.5 Sonnet processor
            use_gpt4: Whether to add GPT-4 processor
            
        Raises:
            ValueError: If required API keys are not set in environment variables
        """
        if use_claude:
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise ValueError("ANTHROPIC_API_KEY environment variable is required for Claude")
                
            claude_config = LLMConfig(
                provider="anthropic",
                model_name="claude-3-5-sonnet-20241022",
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                temperature=0.7  # Standard temperature for balanced output
            )
            self.add_processor("claude_35_sonnet", claude_config)
            
        if use_gpt4:
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError("OPENAI_API_KEY environment variable is required for GPT-4")
                
            gpt4_config = LLMConfig(
                provider="openai",
                model_name="gpt-4o",
                api_key=os.getenv("OPENAI_API_KEY"),
                temperature=0.7  # Standard temperature for balanced output
            )
            self.add_processor("gpt_4o", gpt4_config)

    def get_available_processors(self) -> Dict[str, Dict]:
        """Get information about all available processors
        
        Returns:
            Dictionary mapping processor names to their configurations:
            {
                'processor_name': {
                    'provider': str,
                    'model': str,
                    'temperature': float
                }
            }
        """
        return {
            name: {
                'provider': processor.config.provider,
                'model': processor.config.model_name,
                'temperature': processor.config.temperature
            }
            for name, processor in self.processors.items()
        }