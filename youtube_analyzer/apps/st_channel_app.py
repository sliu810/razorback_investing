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
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Use absolute imports
from libs.channel_client import ChannelClientFactory
from libs.utils import DateFilter
from libs.llm_processor import Task, Role, LLMConfig
from libs.youtube_api_client import YouTubeAPIClient

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

# Preset channels with handles
PRESET_CHANNELS = {
    "Lex Fridman": "@lexfridman",
    "Joe Rogan": "@joerogan",
    "CNBC": "@CNBCtelevision"
}

def initialize_client(channel_name: str) -> ChannelClientFactory:
    """Initialize client with channel name
    
    Args:
        channel_name: Channel handle (e.g., @lexfridman)
    """
    # First get the channel ID using YouTubeAPIClient
    api_client = YouTubeAPIClient(api_key=os.getenv("YOUTUBE_API_KEY"))
    channel_id = api_client.get_channel_id(channel_name)
    
    # Then create channel client with the ID
    return ChannelClientFactory.create_channel(
        channel_type="youtube",
        channel_id=channel_id,
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        timezone='America/Chicago'
    )

def main():
    logger.info("Starting main()")
    st.set_page_config(layout="wide")
    
    # Initialize session state variables
    if 'client' not in st.session_state:
        logger.info("Initializing session state")
        st.session_state.client = None
        st.session_state.channel_handle = None
        st.session_state.videos = None
        st.session_state.selected_models = list(AVAILABLE_MODELS.keys())  # Default all selected
        st.session_state.selected_role = Role.research_assistant()
        st.session_state.selected_task = Task.summarize()
        st.session_state.current_results = None
        st.session_state.channel_id = None
        st.session_state.date_filter = DateFilter()  # Initialize with default constructor

    # Sidebar
    with st.sidebar:
        st.title("YouTube Channel Videos")
        
        # Channel selection
        st.subheader("Select Channel")
        channel_option = st.radio(
            "Choose channel source:",
            ["Preset Channels", "Custom Channel"],
            label_visibility="collapsed"
        )
        
        if channel_option == "Preset Channels":
            channel_name = st.selectbox(
                "Select a channel:",
                options=list(PRESET_CHANNELS.keys())
            )
            channel_handle = PRESET_CHANNELS[channel_name]
        else:
            channel_handle = st.text_input(
                "Enter channel handle (e.g., @lexfridman):",
                placeholder="@channel"
            )
        
        # Date range selection
        st.subheader("Select Date Range")
        date_option = st.radio(
            "Choose date range:",
            ["Today", "Last N Days"]
        )
        
        if date_option == "Last N Days":
            days = st.number_input(
                "Number of days to look back:",
                min_value=1,
                max_value=365,
                value=30
            )
        
        # Show channel button
        show_channel = st.button("Show Channel Videos", type="primary")
        
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
    if show_channel and channel_handle:
        try:
            # Initialize client
            client = initialize_client(channel_handle)
            st.header(f"Videos from {client.channel_metadata['title']}")
            
            # Set up date filter
            date_filter = DateFilter()
            if date_option == "Today":
                params = date_filter.today()
            else:
                params = date_filter.from_days_ago(days)
            
            # Get videos
            video_ids = client.update_video_ids(
                published_after=params.get('publishedAfter'),
                published_before=params.get('publishedBefore')
            )
            
            # Get video clients for each ID
            videos = [client.create_or_get_video_client(video_id) for video_id in video_ids]
            
            # Display video information in a cleaner format
            for video in videos:
                with st.container():
                    # Format date to show only YYYY-MM-DD
                    published_date = video.published_at.strftime('%Y-%m-%d')
                    
                    # Create columns for link and button
                    col1, col2 = st.columns([6, 1])
                    
                    # Display clickable title and date in first column
                    with col1:
                        st.markdown(f"[**{video.title}**](https://youtube.com/watch?v={video.video_id}) ({published_date})")
                    
                    # Add analyze link in second column
                    with col2:
                        video_url = f"https://youtube.com/watch?v={video.video_id}"
                        
                        # Get current selected models, role, and task from session state
                        models_param = ",".join(st.session_state.selected_models)
                        role_param = st.session_state.selected_role.name
                        task_param = st.session_state.selected_task.name
                        
                        # Create URL with all parameters
                        analyze_url = (
                            f"http://localhost:8502/?"
                            f"video_url={video_url}&"
                            f"models={models_param}&"
                            f"role={role_param}&"
                            f"task={task_param}&"
                            f"auto_analyze=true"
                        )
                        
                        st.markdown(f"[Analyze]({analyze_url})")
                    
                    st.divider()  # Add a visual separator between videos
        
        except Exception as e:
            st.error(f"Error loading channel: {str(e)}")
            logger.error(f"Error loading channel: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("Starting channel_analyzer_app.py")
    main() 