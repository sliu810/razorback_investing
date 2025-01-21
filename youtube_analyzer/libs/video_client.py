from typing import Dict, List, Optional, Union
import os
from datetime import datetime
from .llm_processor import LLMProcessor, LLMConfig, Role, Task
from .video import Video
import logging
from .youtube_api_client import YouTubeAPIClient
from dataclasses import dataclass
import re


logger = logging.getLogger(__name__)

@dataclass
class AnalysisResult:
    """Represents a single analysis result from an LLM processor
    
    Attributes:
        content: Raw analysis text from the LLM
        model: Model identifier (e.g., "anthropic/claude-3-sonnet")
        timestamp: When the analysis was performed
        role: Role used for analysis (e.g., "research_assistant")
        task: Task performed (e.g., "summarize")
        html: Formatted HTML version of the analysis
    """
    content: str
    model: str
    timestamp: datetime
    role: Optional[str]
    task: str
    html: str

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
        ...     video_id="your_video_id",
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
        ...     video_id="your_video_id",
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
    
    def __init__(self, 
                 video_id: str,
                 youtube_api_key: str):
        """Initialize YouTube video client
        
        Args:
            video_id: YouTube video ID to analyze
            youtube_api_key: YouTube Data API key
        """
        self._api_client = YouTubeAPIClient(youtube_api_key)
        self._processors: Dict[str, LLMProcessor] = {}
        self.analysis_results: List[AnalysisResult] = []
        self._video: Optional[Video] = None
        
        self._initialize_video(video_id)

    def _initialize_video(self, video_id: str) -> None:
        """Initialize video object and fetch its data
        
        Args:
            video_id: YouTube video ID
        """
        try:
            self._video = Video(video_id, self._api_client)
            self._video.get_video_metadata_and_transcript()
            logger.info(f"Initialized video: {video_id}")
        except Exception as e:
            logger.error(f"Failed to initialize video: {e}")
            raise

    def add_processor(self, name: str, config: LLMConfig) -> None:
        """Add a custom processor with given configuration"""
        try:
            self._processors[name] = LLMProcessor(config)
            logger.info(f"Processor '{name}' initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize processor '{name}': {e}")
            raise

    def analyze_video(self, 
                     processor_names: List[str], 
                     task: Task,
                     role: Optional[Role] = None,
                     status_container=None) -> List[AnalysisResult]:
        """Analyze video using specified processors and role/task
        
        Args:
            processor_names: List of processor names to use
            task: Task configuration defining what analysis to perform
            role: Optional role configuration defining the analyzer's perspective
            status_container: Optional UI container for showing progress (e.g., streamlit)
            
        Returns:
            List[AnalysisResult]: List of analysis results from each processor
            
        Raises:
            ValueError: If processor doesn't exist. Use add_processor() to add new processors.
        """
        missing_processors = [name for name in processor_names if name not in self._processors]
        if missing_processors:
            raise ValueError(
                f"Processors not found: {', '.join(missing_processors)}. "
                "Use add_processor() to add new processors before analysis."
            )

        try:
            # Show analysis start in UI if container provided
            if status_container:
                status_container.info("🤖 Starting analysis...")
            
            # Verify transcript availability
            if not self._video.transcript or not self._video.transcript[0]:
                logger.error("No transcript available")
                if status_container:
                    status_container.error("❌ No transcript available for this video")
                return []

            analyses = []
            # Process with each requested LLM
            for proc_name in processor_names:
                if proc_name not in self._processors:
                    logger.error(f"Processor '{proc_name}' not found")
                    continue

                try:
                    # Update UI with current processor
                    if status_container:
                        status_container.info(f"🤖 Analyzing with {proc_name}...")
                    logger.info(f"Starting analysis with {proc_name}")

                    # Get processor and analyze transcript
                    processor = self._processors[proc_name]
                    analysis = processor.process_text(
                        text=self._video.transcript[0],
                        task=task,
                        role=role
                    )

                    if analysis:
                        # Structure the analysis result
                        result = AnalysisResult(
                            content=analysis,
                            model=f"{processor.config.provider}/{processor.config.model_name}",
                            timestamp=datetime.now(),
                            role=role.name if role else None,
                            task=task.name,
                            html=self._format_analysis_result(self._video, analysis, processor.config)
                        )
                        analyses.append(result)
                        self.analysis_results.append(result)
                        
                        # Update UI with success
                        if status_container:
                            status_container.success(f"✅ Analysis complete for {proc_name}")
                        logger.info(f"Analysis complete for {proc_name}")

                except Exception as e:
                    # Handle processor-specific errors
                    if status_container:
                        status_container.error(f"❌ Error with {proc_name}: {str(e)}")
                    logger.error(f"Error with {proc_name}: {e}")
                    continue

            return analyses

        except Exception as e:
            # Handle general analysis errors
            logger.error(f"Error analyzing video: {e}")
            if status_container:
                status_container.error(f"❌ Error analyzing video: {e}")
            return []

    def chat(self, processor_name: str, question: str) -> Optional[str]:
        """Chat about video content using specified processor
        
        Args:
            processor_name: Name of the processor to use
            question: Question to ask about the video
            
        Raises:
            ValueError: If processor doesn't exist. Use add_processor() to add new processors.
        """
        missing_processors = [processor_name] if processor_name not in self._processors else []
        if missing_processors:
            raise ValueError(
                f"Processors not found: {', '.join(missing_processors)}. "
                "Use add_processor() to add new processors before chatting."
            )

        try:
            if not self._video.transcript or not self._video.transcript[0]:
                logger.error("No transcript available for chat")
                return None

            processor = self._processors[processor_name]
            processor.init_chat_with_context(self._video.transcript[0])
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

    def get_processors(self) -> Dict[str, Dict]:
        """Get information about all processors
        
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
            for name, processor in self._processors.items()
        }

    @property
    def title(self) -> str:
        """Get video title"""
        return self._video.title

    @property
    def url(self) -> str:
        """Get video URL"""
        return self._video.url

    @property
    def transcript(self) -> Optional[str]:
        """Get video transcript text"""
        return self._video.transcript[0] if self._video.transcript else None

    @property
    def duration_minutes(self) -> float:
        """Get video duration in minutes"""
        return self._video.duration_minutes

    @property
    def channel_name(self) -> str:
        """Get channel name"""
        return self._video.channel_name

    @property
    def published_at(self) -> datetime:
        """Get video publication date"""
        return self._video.published_at