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
            description="Create a concise, specific summary with key data",
            prompt_template="""Provide a direct, specific summary of this transcript. Be concise and get straight to the point.

            Guidelines:
            1. Start each point with specific information (avoid vague statements)
            2. Include exact numbers and data points when mentioned
            3. Use precise terms instead of general ones
            4. State specific timeframes and dates when given
            5. Keep sections focused and brief

            Format:
            [Key Topic]
            • Specific point with exact details
            • Precise data or example
            • Concrete fact or finding

            [Next Topic]
            • Continue with specific points...

            Transcript:
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
        "openai": ["gpt-4o","gpt-4-0125-preview", "gpt-4-turbo-preview", "gpt-4", "gpt-3.5-turbo"],
        "anthropic": ["claude-3-5-sonnet-20241022","claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240229"]
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
        # Create a focused prompt that combines the question and context
        combined_text = f"""Question: {question}\n\nRelevant Context: {context}"""
        
        try:
            if self.config.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.config.model_name,
                    max_tokens=100,  # Limit response length
                    temperature=0.7,
                    messages=[{
                        "role": "user",
                        "content": f"Answer this question briefly: {question}\n\nContext: {context}"
                    }]
                )
                return response.content[0].text

            elif self.config.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.config.model_name,
                    temperature=0.7,
                    max_tokens=100,  # Limit response length
                    messages=[{
                        "role": "system",
                        "content": "You are a helpful assistant. Give brief answers."
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\n\nContext: {context}"
                    }]
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return "Sorry, I encountered an error processing your question."