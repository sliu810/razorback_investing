from typing import Dict, List, Optional, Literal
from pydantic import BaseModel
import logging
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import os

logger = logging.getLogger(__name__)

class Role(BaseModel):
    """Defines a role for the AI system"""
    name: str
    description: str
    system_prompt: str

class Task(BaseModel):
    """Defines a task for the AI system"""
    name: str
    description: str
    prompt_template: str

class LLMConfig(BaseModel):
    """Configuration for Language Models"""
    provider: Literal["openai", "anthropic"]
    model_name: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None

class RoleRegistry:
    """Registry of predefined AI roles"""
    
    @classmethod
    def get_content_summarizer(cls) -> Role:
        return Role(
            name="content_summarizer",
            description="Expert in creating concise summaries",
            system_prompt="You are an expert content summarizer. Create clear, structured summaries while retaining key information."
        )
    
    @classmethod
    def get_financial_analyst(cls) -> Role:
        return Role(
            name="financial_analyst",
            description="Expert in analyzing financial content",
            system_prompt="You are an expert financial analyst. Analyze content for key financial insights, trends, and implications."
        )
    
    # Add more predefined roles as class methods

class TaskRegistry:
    """Registry of predefined AI tasks"""
    
    @classmethod
    def get_summarize_transcript(cls) -> Task:
        return Task(
            name="summarize_transcript",
            description="Create a structured summary with topics and takeaways",
            prompt_template="""Analyze and summarize this transcript into clear sections with bullet points.
            Focus on key topics discussed and main takeaways.
            Use clear headings and bullet points for each section.
            Here's the transcript:
            {text}"""
        )
    
    @classmethod
    def get_market_analysis(cls) -> Task:
        return Task(
            name="market_analysis",
            description="Analyze market trends and insights",
            prompt_template="""Analyze this content for key market insights.
            Focus on:
            - Market trends
            - Key developments
            - Future implications
            
            Content:
            {text}"""
        )
    
    # Add more predefined tasks as class methods

class LLMProcessor:
    """Core text processing using LLM"""
    
    # Supported models by provider
    SUPPORTED_MODELS = {
        "openai": ["gpt-4-0125-preview", "gpt-4-turbo-preview", "gpt-4", "gpt-3.5-turbo"],
        "anthropic": ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240229"]
    }

    def __init__(self, config: LLMConfig):
        self.config = config
        self.roles = {}  # Initialize roles dictionary
        self.tasks = {}  # Initialize tasks dictionary
        self._init_client()
        self._register_roles_and_tasks()

    def _init_client(self):
        """Initialize the appropriate client based on provider"""
        if self.config.provider == "anthropic":
            import anthropic
            self.client = anthropic.Client(api_key=os.getenv("ANTHROPIC_API_KEY"))
        elif self.config.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")

    def _register_roles_and_tasks(self):
        """Register default roles and tasks"""
        # Register default roles
        self.register_role("content_summarizer")
        self.register_role("financial_analyst")
        
        # Register default tasks
        self.register_task("summarize_transcript")
        self.register_task("market_analysis")

    def register_role(self, role: str) -> None:
        """Register a new role"""
        self.roles[role] = role
        logger.info(f"Registered role: {role}")

    def register_task(self, task: str) -> None:
        """Register a new task"""
        self.tasks[task] = task
        logger.info(f"Registered task: {task}")

    def process_text(self, text: str, role_name: str, task_name: str) -> Optional[str]:
        try:
            prompt = self._create_prompt(text, role_name, task_name)
            response = self._get_response(prompt)
            logger.info("Text processed successfully")
            return response
        except Exception as e:
            logger.error(f"Error processing text: {str(e)}")
            return None

    def _create_prompt(self, text: str, role_name: str, task_name: str) -> str:
        """Create a standardized prompt for all models"""
        format_instructions = """
Analyze the transcript and create a clear summary with the following format:

[Section Title 1]
- Key point or finding
- Another key point
- Additional detail or insight

[Section Title 2]
- Key point or finding
- Another key point
- Additional detail or insight

Important formatting rules:
1. Use clear, concise section titles in square brackets
2. Use bullet points (-)
3. Don't use markdown formatting
4. Don't include introductory text
5. Keep sections focused and organized
6. Use 4-6 main sections
"""

        role_prompts = {
            "content_summarizer": f"""As a content summarizer, analyze this video transcript and provide a structured summary.

{format_instructions}

Transcript:
{text}""",
            
            "financial_analyst": f"""As a financial analyst, analyze this video transcript and provide key financial insights.

{format_instructions}

Transcript:
{text}"""
        }

        return role_prompts.get(role_name, role_prompts["content_summarizer"])

    def _get_response(self, prompt: str) -> Optional[str]:
        """Get response from the appropriate model"""
        try:
            if self.config.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.config.model_name,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text

            elif self.config.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.config.model_name,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error getting response from {self.config.provider}: {str(e)}")
            return None

    @classmethod
    def list_available_models(cls, provider: Optional[str] = None) -> Dict[str, List[str]]:
        """List available models, optionally filtered by provider"""
        if provider:
            return {provider: cls.SUPPORTED_MODELS.get(provider, [])}
        return cls.SUPPORTED_MODELS

    def chat(self, question: str, context: str) -> str:
        """
        Chat about any context using this processor's model
        
        Args:
            question: Question to ask
            context: The text content to analyze
        """
        prompt = f"""Please answer the following question based on this content only, don't use any other information:

Content:
{context}

Question: {question}

Please answer based only on information provided in the content."""

        return self.process_text(
            text=prompt,
            role_name="content_analyst",
            task_name="answer_question"
        )