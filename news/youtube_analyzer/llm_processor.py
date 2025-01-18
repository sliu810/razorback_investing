from typing import Optional, List
from pydantic import BaseModel
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
import logging
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from operator import itemgetter

logger = logging.getLogger(__name__)

class LLMConfig(BaseModel):
    """Configuration for Language Models"""
    model_config = {
        'protected_namespaces': ()
    }
    
    provider: str
    model_name: str
    api_key: str
    temperature: float = 0.7
    max_tokens: int = 2000

class Role(BaseModel):
    """Role configuration with optional system prompt"""
    name: str
    description: str
    system_prompt: Optional[str] = None
    
    @classmethod
    def research_assistant(cls) -> 'Role':
        return cls(
            name="research_assistant",
            description="General research assistance for various topics",
            system_prompt="""You are a skilled research assistant with expertise in analyzing and synthesizing information.

Your responses should be:
- Well-structured and organized
- Focused on key findings and insights
- Supported by evidence from the source material
- Clear and concise
- Objective and unbiased"""
        )
    
    @classmethod
    def financial_analyst(cls) -> 'Role':
        return cls(
            name="financial_analyst",
            description="Investment research and market analysis specialist",
            system_prompt="""You are an experienced financial analyst working at a top hedge fund.

            Your responses should be:
            - Well-structured and organized
            - Focused on key findings and insights
            - Supported by evidence from the source material
            - Clear and concise
            - Objective and unbiased

            When analyzing content, consider:
            1. Financial metrics and performance
            2. Market positioning and competitive advantages
            3. Industry trends and market conditions
            4. Management strategy and execution
            5. Potential risks and opportunities"""
        )
    
    @classmethod
    def custom(cls, system_prompt: str, name: str = "custom", description: str = "Custom role") -> 'Role':
        return cls(
            name=name,
            description=description,
            system_prompt=system_prompt
        )

class Task(BaseModel):
    """Task configuration"""
    name: str
    description: str
    prompt_template: str
    
    @classmethod
    def summarize(cls) -> 'Task':
        return cls(
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

            Content:
            {text}"""
        )
    
    @classmethod
    def market_analysis(cls) -> 'Task':
        return cls(
            name="market_analysis",
            description="Analyze market trends and insights",
            prompt_template="""Analyze this content for key market insights.

            Guidelines:
            1. Focus on actionable insights and specific data points
            2. Identify both short-term and long-term implications
            3. Consider market context and broader industry trends
            4. Highlight potential risks and opportunities
            5. Note any significant metrics or valuation factors            
            
            Format:
            [Key Topic]
            • Specific point with exact details
            • Precise data or example
            • Concrete fact or finding

            [Next Topic]
            • Continue with specific points...

            Content:
            {text}"""
        )
    
    @classmethod
    def custom(cls, prompt: str, name: str = "custom", description: str = "Custom task") -> 'Task':
        return cls(
            name=name,
            description=description,
            prompt_template=f"{prompt}\n\n{{text}}"
        )

class LLMProcessor:
    """Processes text using language models with configurable roles and tasks"""
    
    def __init__(self, config: LLMConfig):
        """Initialize processor with config"""
        self.config = config
        self._init_client()
    
    def _init_client(self):
        """Initialize LangChain client based on provider"""
        try:
            if self.config.provider == "anthropic":
                self.client = ChatAnthropic(
                    model=self.config.model_name,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    anthropic_api_key=self.config.api_key
                )
            elif self.config.provider == "openai":
                self.client = ChatOpenAI(
                    model=self.config.model_name,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    openai_api_key=self.config.api_key
                )
            else:
                raise ValueError(f"Unsupported provider: {self.config.provider}")
        except Exception as e:
            logger.error(f"Error initializing client: {str(e)}")
            raise
    
    def process_text(self, text: str, task: Task, role: Optional[Role] = None) -> Optional[str]:
        """Process text using specified task and optional role
        
        Args:
            text: Input text to process
            task: Task to perform
            role: Optional role to use (defaults to None)
            
        Returns:
            Processed text or None if processing fails
        """
        try:
            messages = []
            
            # Add system message if role is provided
            if role and role.system_prompt:
                messages.append(SystemMessage(content=role.system_prompt))
            
            # Format task prompt with input text
            formatted_prompt = task.prompt_template.format(text=text)
            messages.append(HumanMessage(content=formatted_prompt))
            
            # Log the prompts being used
            logger.info(f"Role: {role.name if role else 'None'}")
            logger.info(f"Task: {task.name}")
            logger.info(f"System prompt: {role.system_prompt if role and role.system_prompt else 'None'}")
            logger.info(f"Task prompt: {formatted_prompt}")
            
            response = self.client.invoke(messages)
            return response.content
                
        except Exception as e:
            logger.error(f"Error processing text: {str(e)}")
            return None

    def init_chat_with_context(self, context: str):
        """Initialize chat with specific content to analyze
        
        Args:
            context: The content to analyze and discuss
        """
        self.memory = ConversationBufferMemory(
            return_messages=True
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You must only reference and discuss the content provided below. 
            Do not make assumptions or add information not present in this content.
            If the information is not in the content, say so directly.
            
            Content:
            {context}"""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}")
        ])
        
        def get_memory(_):
            return self.memory.load_memory_variables({})["history"]
        
        self.chat_chain = (
            {
                "context": lambda x: self.chat_context,
                "history": RunnableLambda(get_memory),
                "question": lambda x: x
            }
            | prompt 
            | self.client
        )
        
        self.chat_context = context
        logger.info("Chat initialized with context")

    def chat(self, prompt: str) -> Optional[str]:
        """Chat about the initialized context"""
        if not hasattr(self, 'chat_chain'):
            raise ValueError("Chat not initialized. Call init_chat first.")
            
        try:
            response = self.chat_chain.invoke(prompt)
            
            # Update memory
            self.memory.save_context(
                {"input": prompt},
                {"output": response.content}
            )
            
            logger.info(f"Chat prompt: {prompt}")
            return response.content
                
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return None

    def reset_chat(self):
        """Reset chat history"""
        if hasattr(self, 'memory'):
            self.memory.clear()
            logger.info("Chat history reset")