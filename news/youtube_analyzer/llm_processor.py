import logging
from langchain.chat_models import ChatOpenAI, ChatAnthropic
from langchain.llms import HuggingFaceHub
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.chains import LLMChain
from langchain.callbacks import get_openai_callback

# Create a logger for this module
logger = logging.getLogger(__name__)

class LLMProcessor:
    def __init__(self, llm_choice="openai", model_name="gpt-3.5-turbo", temperature=0):
        self.llm_choice = llm_choice
        self.llm = self._initialize_llm(llm_choice, model_name, temperature)
        logger.info(f"Initialized LLMProcessor with {llm_choice} model: {model_name}")

    def _initialize_llm(self, llm_choice, model_name, temperature):
        if llm_choice == "openai":
            return ChatOpenAI(model_name=model_name, temperature=temperature)
        elif llm_choice == "anthropic":
            return ChatAnthropic(model=model_name, temperature=temperature)
        elif llm_choice == "huggingface":
            return HuggingFaceHub(repo_id=model_name, model_kwargs={"temperature": temperature})
        else:
            raise ValueError(f"Unsupported LLM choice: {llm_choice}")

    def _get_prompt(self):
        system_message = "You are a financial analyst assistant. Your task is to analyze and process financial information."
        if self.llm_choice == "anthropic":
            return ChatPromptTemplate.from_messages([
                HumanMessagePromptTemplate.from_template(f"{system_message}\n\nPlease {{task}} for the following text:\n\n{{input_text}}")
            ])
        else:
            return ChatPromptTemplate.from_messages([
                ("system", system_message),
                ("human", "Please {task} for the following text:\n\n{input_text}")
            ])

    def apply_task(self, input_text, task):
        prompt = self._get_prompt()
        chain = LLMChain(llm=self.llm, prompt=prompt)

        try:
            with get_openai_callback() as cb:
                response = chain.run(task=task, input_text=input_text)
                logger.info(f"Task completed. Tokens used: {cb.total_tokens} (Prompt: {cb.prompt_tokens}, Completion: {cb.completion_tokens})")
                logger.info(f"Total Cost (USD): ${cb.total_cost:.4f}")
            
            return response.strip()
        except Exception as e:
            logger.error(f"An error occurred while processing the task: {str(e)}", exc_info=True)
            return "Error: Unable to process the task."

# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # OpenAI example
    openai_processor = LLMProcessor(llm_choice="openai", model_name="gpt-3.5-turbo")
    
    # Anthropic example
    anthropic_processor = LLMProcessor(llm_choice="anthropic", model_name="claude-2")
    
    # HuggingFace example
    huggingface_processor = LLMProcessor(llm_choice="huggingface", model_name="google/flan-t5-xxl")

    task = "summarize the main points"
    input_text = "The stock market showed significant volatility today due to concerns about inflation and potential interest rate hikes. The S&P 500 closed down 1.5%, while tech stocks were hit particularly hard, with the Nasdaq falling 2.3%. Analysts are closely watching upcoming economic data releases for clues about the Federal Reserve's next moves."

    for processor in [openai_processor, anthropic_processor, huggingface_processor]:
        result = processor.apply_task(input_text, task)
        logger.info(f"Result from {processor.llm.__class__.__name__}: {result}")