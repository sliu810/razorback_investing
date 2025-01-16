from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging
from pathlib import Path
import os
from video import Video
from llm_processor import LLMProcessor, LLMConfig
from utils import sanitize_filename
from dataclasses import dataclass
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

@dataclass
class AnalysisConfig:
    output_dir: str
    max_summary_length: int = 4000
    save_format: str = "html"

class TranscriptAnalysis:
    """Represents the analysis result of a video's transcript"""
    def __init__(self, video: Video):
        self.video = video
        self.summary: Optional[str] = None
        self.analyzed_at: Optional[datetime] = None
        self.model_provider: Optional[str] = None
        self.model_name: Optional[str] = None
        self.role_used: Optional[str] = None
        self.task_used: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert analysis to dictionary format"""
        return {
            "video_id": self.video.video_id,
            "title": self.video.title,
            "language": getattr(self.video, 'language', 'en'),
            "summary": self.summary,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "model": f"{self.model_provider}/{self.model_name}",
            "role": self.role_used,
            "task": self.task_used
        }

    def get_html(self) -> str:
        """Generate HTML representation of the analysis"""
        video_url = f"https://www.youtube.com/watch?v={self.video.video_id}"
        
        html = f"""
        <div class="analysis-container">
            <div class="analysis-header">
                <h2 style="color: #f8f9fa;">{self.video.title}</h2>
                <small><a href="{video_url}" target="_blank" style="color: #63b3ed;">Watch Video</a></small>
                <p style="color: #e9ecef;">Analyzed by {self.model_provider}/{self.model_name}</p>
            </div>
            <div class="analysis-content" style="color: #e9ecef;">
                {self._format_summary_as_html()}
            </div>
        </div>
        <style>
            .analysis-container {{
                max-width: 800px;
                margin: 20px auto;
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #e9ecef;
            }}
            
            h3.section-title {{
                color: #63b3ed !important;
                font-size: 1.5rem !important;
                font-weight: 600 !important;
                margin-top: 1.5rem !important;
                margin-bottom: 1rem !important;
            }}
            
            .analysis-content ul {{
                color: #e9ecef !important;
            }}
            
            .analysis-content li {{
                color: #e9ecef !important;
                margin-bottom: 0.5rem;
            }}
        </style>
        """
        return html

    def _format_summary_as_html(self) -> str:
        """Format summary text as HTML with sections and bullet points"""
        if not self.summary:
            return "<p class='error' style='color: #ff6b6b;'>No analysis available</p>"

        html = ""
        current_section = None
        current_bullets = []

        # Process content lines
        lines = self.summary.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if it's a section header
            if line.startswith('[') and ']' in line:
                # If we have a previous section, close it
                if current_bullets:
                    html += "<ul style='color: #e9ecef;'>" + "".join(current_bullets) + "</ul>"
                    current_bullets = []

                # Extract section title and create new section
                title = line[1:line.index(']')].strip()
                html += f'<h3 class="section-title" style="color: #63b3ed;">{title}</h3>'
                current_section = title

            # Handle bullet points and content
            else:
                content = line.lstrip('-• ').strip()
                if content:
                    if line.startswith(('-', '•')):
                        current_bullets.append(f'<li style="color: #e9ecef;">{content}</li>')
                    elif current_section:
                        current_bullets.append(f'<li style="color: #e9ecef;">{content}</li>')

        # Close any open bullets
        if current_bullets:
            html += "<ul style='color: #e9ecef;'>" + "".join(current_bullets) + "</ul>"

        return html

    """
    Future Enhancement: AI-based HTML Formatter
    
    The code below represents a potential future enhancement to use AI for HTML formatting.
    Benefits of using AI formatting:
    1. More adaptable to different input formats
    2. Better handling of edge cases
    3. Easier to maintain (changes via prompt vs. code)
    4. More flexible for future format changes
    
    Current challenges to solve:
    1. Ensuring consistent formatting across different runs
    2. Maintaining exact content preservation
    3. Optimizing prompt for reliable structure
    4. Balancing cost/performance with benefits
    
    TODO:
    - Improve prompt engineering for consistent results
    - Add validation for AI-generated HTML
    - Consider hybrid approach combining rules and AI
    - Add caching to reduce API calls
    """
    def _format_summary_as_html_with_ai(self) -> str:
        """Future implementation of AI-based HTML formatting"""
        try:
            formatting_prompt = '''
            You are an HTML formatter. Your task is to convert the analysis into clean, structured HTML.

            Input Format:
            The text contains sections with titles in square brackets followed by bullet points.
            Example: [Section Title] - Point 1 - Point 2

            Required Output Format:
            <h3 class="section-title">Section Title</h3>
            <ul>
                <li>Point 1</li>
                <li>Point 2</li>
            </ul>

            Specific Requirements:
            1. Convert each [Title] into an <h3> tag
            2. Split content after each dash (-) into separate list items
            3. Group all points under their respective sections
            4. Remove the square brackets from titles
            5. Maintain the exact content but in a clean HTML structure

            Now format this content:
            {content}
            '''
            
            formatter = LLMProcessor(LLMConfig(
                provider="openai",
                model_name="gpt-3.5-turbo",
                temperature=0,
                max_tokens=4000
            ))
            
            formatted_html = formatter.process_text(
                self.summary,
                role_name="html_formatter",
                task_name="format_content"
            )
            
            return formatted_html or "<p class='error'>Formatting failed</p>"
            
        except Exception as e:
            logger.error(f"AI formatting failed: {str(e)}")
            return "<p class='error'>AI formatting failed</p>"

    def serialize_to_file(self, root_dir: str) -> Optional[str]:
        """Save analysis as HTML file"""
        try:
            # Create output directory
            os.makedirs(root_dir, exist_ok=True)

            # Create filename using video title, language, and model provider only
            valid_title = sanitize_filename(self.video.title, max_length=100)
            language = getattr(self.video, 'language', 'en')  # Default to 'en' if not set
            file_name = f"{valid_title}_{language}_{self.model_provider}_analysis.html"
            file_path = os.path.join(root_dir, file_name)

            # Generate full HTML document
            full_html = f"""<!DOCTYPE html>
<html lang="{language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analysis: {self.video.title}</title>
</head>
<body>
{self.get_html()}
</body>
</html>"""

            # Save to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_html)

            logger.info(f"Analysis saved to: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error saving analysis: {str(e)}")
            return None

class VideoAnalyzer:
    """Core analyzer that manages video analysis pipeline"""
    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.llm_processors: Dict[str, LLMProcessor] = {}

    def add_processor(self, processor: LLMProcessor):
        """Add a LLM processor"""
        key = f"{processor.config.provider}/{processor.config.model_name}"
        self.llm_processors[key] = processor

    def analyze_video(self, video: Video) -> List[TranscriptAnalysis]:
        """Main analysis pipeline"""
        if not self._validate_video(video):
            return []
        
        analyses = self._run_analyses(video)
        
        # Print summary of analyses
        if analyses:
            print(f"\nCreated {len(analyses)} analyses:")
            for analysis in analyses:
                provider = f"{analysis.model_provider}/{analysis.model_name}"
                print(f"- Using {provider}")
        
        return analyses

    def _validate_video(self, video: Video) -> bool:
        """Validate video has required data"""
        if not video.transcript:
            logger.warning(f"No transcript for video: {video.video_id}")
            return False
        return True

    def _run_analyses(self, video: Video) -> List[TranscriptAnalysis]:
        """Run all configured analyses"""
        analyses = []
        for processor_key, processor in self.llm_processors.items():
            provider, model = processor_key.split('/')
            
            try:
                analysis = self._create_analysis(video, processor, provider, model)
                if analysis:
                    self._save_analysis(analysis)
                    analyses.append(analysis)
            except Exception as e:
                logger.error(f"Analysis failed for {processor_key}: {str(e)}")
        
        return analyses

    def _create_analysis(
        self, 
        video: Video,
        processor: LLMProcessor,
        provider: str,
        model: str
    ) -> Optional[TranscriptAnalysis]:
        """Create single analysis with error handling"""
        try:
            analysis = TranscriptAnalysis(video)
            analysis.model_provider = provider
            analysis.model_name = model
            
            # Get summary from processor
            summary = processor.process_text(
                video.transcript,
                role_name="research_assistant",
                task_name="summarize_transcript"
            )
            
            if not summary:
                logger.error("Received empty summary from processor")
                return None
                
            analysis.summary = summary
            analysis.role_used = "research_assistant"
            analysis.task_used = "summarize_transcript"
            analysis.analyzed_at = datetime.now()
            
            logger.info(f"Created analysis using {provider}/{model}")
            return analysis
            
        except Exception as e:
            logger.error(f"Analysis creation failed: {str(e)}")
            return None

    def _save_analysis(self, analysis: TranscriptAnalysis) -> bool:
        """Save analysis to configured output"""
        try:
            file_path = analysis.serialize_to_file(self.config.output_dir)
            if file_path:
                print(f"Analysis saved to: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to save analysis: {str(e)}")
            return False 

    def list_processors(self) -> List[str]:
        """List available processor keys"""
        return list(self.llm_processors.keys())

    def get_processor(self, model: str = None) -> LLMProcessor:
        """Get specified processor or default to first available"""
        if not model:
            model = self.list_processors()[0]
        
        if model not in self.llm_processors:
            available = ", ".join(self.list_processors())
            raise ValueError(f"Model {model} not found. Available models: {available}")
            
        return self.llm_processors[model] 

class LLMConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    provider: str
    model_name: str
    temperature: float
    max_tokens: int
    api_key: str = None 