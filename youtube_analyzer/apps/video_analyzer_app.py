"""
Streamlit interface for YouTube video analysis
"""

import warnings
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

import os
import logging
import sys
import streamlit as st
from pathlib import Path

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Use absolute imports
from youtube_analyzer.video_client import YouTubeVideoClient
from youtube_analyzer.llm_processor import Task, Role, LLMConfig
from youtube_analyzer.utils import extract_video_id
from tenacity import retry, stop_after_attempt, wait_exponential
from youtube_transcript_api import YouTubeTranscriptApi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Define available models at app level
AVAILABLE_MODELS = {
    "claude_35_sonnet": {
        "provider": "anthropic",
        "model_name": "claude-3-5-sonnet-20241022",
        "display_name": "Claude 3.5 Sonnet"
    },
    "gpt_4o": {
        "provider": "openai",
        "model_name": "gpt-4o",
        "display_name": "GPT-4 Turbo"
    }
}

def initialize_client(video_id: str) -> YouTubeVideoClient:
    """Initialize client with default processors"""
    client = YouTubeVideoClient(
        video_id=video_id,
        youtube_api_key=os.getenv("YOUTUBE_API_KEY")
    )
    
    # Add Claude processor
    try:
        claude_config = LLMConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        client.add_processor("claude_35_sonnet", claude_config)
    except Exception as e:
        logger.warning(f"Could not add Claude processor: {e}")
    
    # Add GPT processor
    try:
        gpt_config = LLMConfig(
            provider="openai",
            model_name="gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        client.add_processor("gpt_4o", gpt_config)
    except Exception as e:
        logger.warning(f"Could not add GPT-4 processor: {e}")
    
    return client

def chat_interface(client, video_id: str, processors: dict):
    """Chat interface using Streamlit's chat components.
    Only depends on video_id and available processors."""
    
    # Model selector above chat input (always visible)
    selected_model = st.selectbox(
        "Select Model for Chat",
        list(processors.keys()),
        key="chat_model"
    )
    
    # Initialize chat history in session state if not exists
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Accept user input (always at top)
    if prompt := st.chat_input("Ask a question about the video..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Get AI response
        with st.spinner(f"Thinking... ({selected_model})"):
            response = client.chat(
                processor_name=selected_model,
                question=prompt
            )
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Display chat messages in reverse chronological order (newest at top)
    for message in reversed(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

def main():
    logger.info("Starting main()")
    st.set_page_config(layout="wide")
    
    # Initialize session state variables
    if 'client' not in st.session_state:
        logger.info("Initializing session state")
        st.session_state.client = None
        st.session_state.selected_models = list(AVAILABLE_MODELS.keys())  # Default all selected
        st.session_state.selected_role = Role.research_assistant()
        st.session_state.selected_task = Task.summarize()
        st.session_state.messages = []
        st.session_state.current_video_id = None
        st.session_state.current_results = None
        st.session_state.video_url = None

    # Initialize client if we have a video URL
    if st.session_state.video_url:
        video_id = extract_video_id(st.session_state.video_url)
        if video_id and (st.session_state.client is None or 
                        st.session_state.current_video_id != video_id):
            logger.info("Initializing YouTubeVideoClient")
            st.session_state.client = initialize_client(video_id)
            st.session_state.current_video_id = video_id  # Set this right after client initialization
            logger.info("Client initialization complete")

    # Sidebar
    with st.sidebar:
        st.title("YouTube Video Analyzer")
        st.session_state.video_url = st.text_input(
            "Enter YouTube Video URL/ID",
            value=st.session_state.video_url if 'video_url' in st.session_state else "",
            placeholder="https://www.youtube.com/watch?v=...",
            key="video_url_input"
        )
        
        # Model selection
        st.subheader("Models")
        st.session_state.selected_models = [
            model_id for model_id, model_info in AVAILABLE_MODELS.items()
            if st.checkbox(
                model_info["display_name"], 
                value=model_id in st.session_state.selected_models,
                key=f"model_{model_id}"
            )
        ]
        
        # Role selection
        st.subheader("Select Role")
        roles = {
            "Research Assistant": Role.research_assistant(),
            "Financial Analyst": Role.financial_analyst(),
        }
        selected_role_name = st.selectbox(
            "Role",  # Add label instead of empty string
            options=list(roles.keys()),
            index=0,
            key="role_selector",
            label_visibility="collapsed"  # Hide the label but keep it for accessibility
        )
        st.session_state.selected_role = roles[selected_role_name]
        
        # Task selection
        st.subheader("Select Task")
        tasks = {
            "Summarize": Task.summarize(),
            "Market Analysis": Task.market_analysis(),
            "Custom Task": None
        }
        selected_task_name = st.selectbox(
            "Task",  # Add label instead of empty string
            options=list(tasks.keys()),
            index=0,
            key="task_selector",
            label_visibility="collapsed"  # Hide the label but keep it for accessibility
        )
        
        if selected_task_name == "Custom Task":
            custom_task_prompt = st.text_area("Enter Custom Task", key="custom_task")
            if custom_task_prompt:
                st.session_state.selected_task = Task.custom(prompt=custom_task_prompt)
        else:
            st.session_state.selected_task = tasks[selected_task_name]

        # Analyze button
        analyze_button = st.button(
            "Analyze Video", 
            type="primary",
            key="analyze_button"
        )
        
        # Debug info
        with st.expander("Debug Info", expanded=False):
            st.write("Selected Models:", st.session_state.selected_models)
            st.write("Selected Role:", st.session_state.selected_role)
            st.write("Selected Task:", st.session_state.selected_task)

    # Main panel
    if st.session_state.video_url:
        logger.info(f"Processing video URL: {st.session_state.video_url}")
        video_id = extract_video_id(st.session_state.video_url)
        logger.info(f"Extracted video ID: {video_id}")
        
        if not video_id:
            st.error("""
                ❌ Invalid YouTube URL. Please enter:
                • A video URL (youtube.com/watch?v=...)
                • A shortened URL (youtu.be/...)
                • A video ID
                
                Channel URLs (@ChannelName) are not supported.
            """)
            return
            
        try:
            # Create tabs first
            logger.info("Creating tabs")
            tab1, tab2 = st.tabs(["Analysis", "Chat"])
            
            with tab1:  # Analysis tab
                logger.info("Rendering Analysis tab")
                # Show video title first
                if st.session_state.client:
                    st.header(st.session_state.client.title)
                    st.markdown(f"[Watch Video]({st.session_state.client.url})")

                if analyze_button:
                    logger.info("Analyze button clicked - starting analysis")
                    with st.spinner("Analyzing video..."):
                        results = st.session_state.client.analyze_video(
                            processor_names=st.session_state.selected_models,
                            task=st.session_state.selected_task,
                            role=st.session_state.selected_role
                        )
                        st.session_state.current_results = results
                    logger.info("Analysis complete")

                if st.session_state.current_results is not None:
                    for result in st.session_state.current_results:
                        with st.expander(f"Analysis by {result.model}", expanded=True):
                            st.markdown(result.html, unsafe_allow_html=True)
                
                # Show transcript expander last
                if st.session_state.client:
                    with st.expander("Full Transcript", expanded=False):
                        st.markdown(st.session_state.client.transcript)
            
            with tab2:  # Chat tab
                logger.info("Rendering Chat tab")
                if st.session_state.current_video_id:
                    chat_interface(
                        st.session_state.client,
                        st.session_state.current_video_id,
                        st.session_state.client.get_processors()
                    )

        except Exception as e:
            st.error("Unable to analyze this video - subtitles/closed captions are not available. Please try a different video or contact the video owner to enable captions.")
            logger.error(f"Error initializing client: {e}", exc_info=True)
            return

def analyze_video():
    """Helper function to analyze video with selected parameters"""
    if st.session_state.video_url:
        video_id = extract_video_id(st.session_state.video_url)
        if video_id:
            # Initialize or reinitialize client if needed
            if (st.session_state.client is None or 
                st.session_state.current_video_id != video_id):
                st.session_state.client = initialize_client(video_id)
                st.session_state.current_video_id = video_id
            
            with st.spinner("Analyzing video..."):
                results = st.session_state.client.analyze_video(
                    processor_names=st.session_state.selected_models,
                    task=st.session_state.selected_task,
                    role=st.session_state.selected_role
                )
                st.session_state.current_results = results

@retry(
    stop=stop_after_attempt(3),  # Try 3 times
    wait=wait_exponential(multiplier=1, min=4, max=10),  # Wait 4-10 seconds between attempts
    reraise=True
)
def fetch_transcript_with_retry(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        logger.warning(f"Attempt to fetch transcript failed: {str(e)}")
        raise  # This will trigger a retry unless max attempts reached

if __name__ == "__main__":
    logger.info("Starting streamlit_app.py")
    main() 