"""
Streamlit interface for YouTube channel analysis
"""

import warnings
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

import os
import logging
import sys
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Use absolute imports
from ..libs.channel_client import ChannelClientFactory
from ..libs.llm_processor import Task, Role, LLMConfig
from ..libs.utils import DateFilter

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

def initialize_client(channel_id: str) -> ChannelClientFactory:
    """Initialize client with default processors"""
    client = ChannelClientFactory(
        channel_id=channel_id,
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
        st.session_state.current_results = None
        st.session_state.channel_id = None
        st.session_state.date_filter = DateFilter.all()

    # Sidebar
    with st.sidebar:
        st.title("YouTube Channel Analyzer")
        st.session_state.channel_id = st.text_input(
            "Enter YouTube Channel ID",
            value=st.session_state.channel_id if 'channel_id' in st.session_state else "",
            placeholder="UC...",
            key="channel_id_input"
        )
        
        # Date filter selection
        st.subheader("Date Filter")
        date_options = {
            "All Time": DateFilter.all(),
            "Last 30 Days": DateFilter.last_30_days(),
            "Today": DateFilter.today(),
            "Custom Range": None
        }
        selected_date_option = st.selectbox(
            "Select Date Range",
            options=list(date_options.keys()),
            index=0,
            key="date_filter_selector"
        )
        
        if selected_date_option == "Custom Range":
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date", datetime.now() - timedelta(days=30))
            with col2:
                end_date = st.date_input("End Date", datetime.now())
            st.session_state.date_filter = DateFilter.custom_range(start_date, end_date)
        else:
            st.session_state.date_filter = date_options[selected_date_option]
        
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
            "Role",
            options=list(roles.keys()),
            index=0,
            key="role_selector",
            label_visibility="collapsed"
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
            "Task",
            options=list(tasks.keys()),
            index=0,
            key="task_selector",
            label_visibility="collapsed"
        )
        
        if selected_task_name == "Custom Task":
            custom_task_prompt = st.text_area("Enter Custom Task", key="custom_task")
            if custom_task_prompt:
                st.session_state.selected_task = Task.custom(prompt=custom_task_prompt)
        else:
            st.session_state.selected_task = tasks[selected_task_name]

        # Analyze button
        analyze_button = st.button(
            "Analyze Channel", 
            type="primary",
            key="analyze_button"
        )
        
        # Debug info
        with st.expander("Debug Info", expanded=False):
            st.write("Selected Models:", st.session_state.selected_models)
            st.write("Selected Role:", st.session_state.selected_role)
            st.write("Selected Task:", st.session_state.selected_task)
            st.write("Date Filter:", st.session_state.date_filter)

    # Main panel
    if st.session_state.channel_id:
        logger.info(f"Processing channel ID: {st.session_state.channel_id}")
        
        try:
            # Initialize or reinitialize client if needed
            if (st.session_state.client is None or 
                st.session_state.client.channel_id != st.session_state.channel_id):
                logger.info("Initializing ChannelClientFactory")
                st.session_state.client = initialize_client(st.session_state.channel_id)
                logger.info("Client initialization complete")

            # Show channel title
            if st.session_state.client:
                st.header(st.session_state.client.channel_title)
                st.markdown(f"[View Channel](https://www.youtube.com/channel/{st.session_state.channel_id})")

            if analyze_button:
                logger.info("Analyze button clicked - starting analysis")
                with st.spinner("Analyzing channel..."):
                    results = st.session_state.client.analyze_channel(
                        processor_names=st.session_state.selected_models,
                        task=st.session_state.selected_task,
                        role=st.session_state.selected_role,
                        date_filter=st.session_state.date_filter
                    )
                    st.session_state.current_results = results
                logger.info("Analysis complete")

            if st.session_state.current_results is not None:
                for result in st.session_state.current_results:
                    with st.expander(f"Analysis by {result.model}", expanded=True):
                        st.markdown(result.html, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Error analyzing channel: {str(e)}")
            logger.error(f"Error analyzing channel: {e}", exc_info=True)
            return

if __name__ == "__main__":
    logger.info("Starting channel_analyzer_app.py")
    main() 