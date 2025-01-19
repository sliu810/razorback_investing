"""
Streamlit interface for YouTube video analysis
"""

import warnings
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

import os
import logging
import sys

# Debug info just before the problematic import
print("Current directory:", os.getcwd())
print("Files in directory:", os.listdir())

import streamlit as st
from youtube_video_client import YouTubeVideoClient
from llm_processor import Task, Role, LLMConfig
from utils import extract_video_id

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
            st.session_state.selected_models = list(st.session_state.client.get_processors().keys())
            st.session_state.current_video_id = video_id
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
            # Run analysis when button is clicked
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

            # Create tabs
            logger.info("Creating tabs")
            tab1, tab2 = st.tabs(["Analysis", "Chat"])
            
            with tab1:  # Analysis tab
                logger.info("Rendering Analysis tab")
                if st.session_state.current_results is not None:
                    # Display video information using client properties
                    st.header(st.session_state.client.title)
                    st.markdown(f"[Watch Video]({st.session_state.client.url})")
                    
                    # Display analysis results using new AnalysisResult structure
                    for result in st.session_state.current_results:
                        with st.expander(
                            f"Analysis by {result.model}", 
                            expanded=True
                        ):
                            st.markdown(result.html, unsafe_allow_html=True)
                    
                    # Display transcript using client property
                    with st.expander("Original Transcript", expanded=False):
                        st.markdown(st.session_state.client.transcript)
            
            with tab2:  # Chat tab
                logger.info("Rendering Chat tab")
                if st.session_state.current_video_id:
                    # Set active tab to Chat when user starts chatting
                    if "messages" in st.session_state and len(st.session_state.messages) > 0:
                        st.session_state.active_tab = "Chat"
                    chat_interface(
                        st.session_state.client,
                        st.session_state.current_video_id,
                        st.session_state.client.get_processors()
                    )

        except Exception as e:
            st.error(f"Error loading video: {str(e)}")
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
                st.session_state.selected_models = list(st.session_state.client.get_processors().keys())
                st.session_state.current_video_id = video_id
            
            with st.spinner("Analyzing video..."):
                results = st.session_state.client.analyze_video(
                    processor_names=st.session_state.selected_models,
                    task=st.session_state.selected_task,
                    role=st.session_state.selected_role
                )
                st.session_state.current_results = results

if __name__ == "__main__":
    logger.info("Starting streamlit_app.py")
    main() 