"""
Combined Streamlit interface for YouTube channel and video analysis,
preserving old st_channel_app and st_video_app UI/flow, with drag/drop 
for custom tasks and roles.
"""

import os
import sys
import logging
import warnings
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st

warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

# Ensure parent directory is in Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Absolute imports
from libs.utils import DateFilter
from libs.youtube_api_client import YouTubeAPIClient
from libs.channel_client import ChannelClientFactory
from libs.video_client import YouTubeVideoClient
from libs.llm_processor import LLMConfig, Role, Task

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Define available models
AVAILABLE_MODELS = {
    "claude_37_sonnet": {
        "provider": "anthropic",
        "model_name": "claude-3-7-sonnet-20250219",
        "display_name": "Claude 3.7 Sonnet"
    },
    "gpt_4o": {
        "provider": "openai",
        "model_name": "gpt-4o",
        "display_name": "GPT-4o"
    }
}

# Some preset channels
PRESET_CHANNELS = {
    "Lex Fridman": "@lexfridman",
    "Joe Rogan": "@joerogan",
    "CNBC": "@CNBCtelevision",
    "AI Explained": "@aiexplained-official"
}


# ------------------------------------------------------------------------------
# Initialization Helpers
# ------------------------------------------------------------------------------
def initialize_channel_client(channel_name: str):
    """Initialize channel client just like old st_channel_app."""
    api_client = YouTubeAPIClient(api_key=os.getenv("YOUTUBE_API_KEY"))
    channel_id = api_client.get_channel_id(channel_name)
    
    channel_client = ChannelClientFactory.create_channel(
        channel_type="youtube",
        channel_id=channel_id,
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        timezone='America/Chicago'
    )

    # Optionally add channel-level LLM processors
    try:
        claude_config = LLMConfig(
            provider="anthropic",
            model_name="claude-3-7-sonnet-20250219",
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        channel_client.add_processor("claude_37_sonnet", claude_config)
    except Exception as e:
        logger.warning(f"Unable to add Claude to channel: {e}")

    try:
        gpt_config = LLMConfig(
            provider="openai",
            model_name="gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        channel_client.add_processor("gpt_4o", gpt_config)
    except Exception as e:
        logger.warning(f"Unable to add GPT-4 to channel: {e}")

    return channel_client


def initialize_video_client(video_id_or_url: str) -> YouTubeVideoClient:
    """Initialize a YouTubeVideoClient exactly like old st_video_app."""
    api_client = YouTubeAPIClient(api_key=os.getenv("YOUTUBE_API_KEY"))
    video_id = api_client.parse_video_id(video_id_or_url)

    client = YouTubeVideoClient(
        video_id=video_id,
    )

    # Add LLM processors
    try:
        claude_config = LLMConfig(
            provider="anthropic",
            model_name="claude-3-7-sonnet-20250219",
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        client.add_processor("claude_37_sonnet", claude_config)
    except Exception as e:
        logger.warning(f"Could not add Claude: {e}")
    
    try:
        gpt_config = LLMConfig(
            provider="openai",
            model_name="gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        client.add_processor("gpt_4o", gpt_config)
    except Exception as e:
        logger.warning(f"Could not add GPT-4: {e}")

    return client


# ------------------------------------------------------------------------------
# Channel View (Main Panel)
# ------------------------------------------------------------------------------
def render_channel_tab():
    """Render channel view with inline video analysis."""
    if st.session_state.get("show_channel", False) and st.session_state.channel_handle:
        try:
            client = initialize_channel_client(st.session_state.channel_handle)
            
            # Use DateFilter to properly format dates for YouTube API
            date_filter = DateFilter()
            
            logger.info(f"Date option selected: {st.session_state.date_option}")
            
            if st.session_state.date_option == "Today":
                date_params = date_filter.today()
                logger.info(f"Today's date parameters: {date_params}")
            else:  # "Last N Days"
                days = st.session_state.get("days", 30)
                logger.info(f"Last {days} days selected")
                date_params = date_filter.from_days_ago(days)
                logger.info(f"Date range parameters: {date_params}")

            st.session_state.date_range_start = date_params.get('publishedAfter')
            st.session_state.date_range_end = date_params.get('publishedBefore')
            
            logger.info(f"Fetching videos between {st.session_state.date_range_start} and {st.session_state.date_range_end}")

            video_ids = client.update_video_ids(
                published_after=date_params.get('publishedAfter'),
                published_before=date_params.get('publishedBefore')
            )
            
            logger.info(f"Found {len(video_ids)} videos")
            
            videos = [client.create_or_get_video_client(v_id) for v_id in video_ids]
            for vid in videos:
                logger.info(f"Video {vid.video_id} published at: {vid.published_at}")
                video_key = f"video_state_{vid.video_id}"
                analyze_button_key = f"analyze_button_{vid.video_id}"
                analysis_state_key = f"analysis_state_{vid.video_id}"

                # Video header with title and analyze button
                col1, col2 = st.columns([6, 1])
                with col1:
                    published_date = (vid.published_at.strftime('%Y-%m-%d') 
                                    if vid.published_at else "N/A")
                    st.markdown(
                        f"[**{vid.title}**](https://youtube.com/watch?v={vid.video_id}) "
                        f"({published_date})"
                    )
                
                with col2:
                    if st.button("Analyze", key=analyze_button_key):
                        st.session_state[analysis_state_key] = {
                            'vclient': None,
                            'results': None
                        }
                        try:
                            vclient = initialize_video_client(f"https://youtube.com/watch?v={vid.video_id}")
                            with st.spinner("Analyzing..."):
                                results = vclient.analyze_video(
                                    processor_names=st.session_state.selected_models,
                                    task=st.session_state.selected_task,
                                    role=st.session_state.selected_role
                                )
                            st.session_state[analysis_state_key]['vclient'] = vclient
                            st.session_state[analysis_state_key]['results'] = results
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Error analyzing video: {str(e)}")
                            logger.error(e, exc_info=True)

                # Show analysis results and chat if available
                if (analysis_state_key in st.session_state and 
                    isinstance(st.session_state[analysis_state_key], dict) and 
                    st.session_state[analysis_state_key].get('results')):
                    
                    # Wrap tabs in an expander
                    with st.expander("Analysis & Chat", expanded=False):
                        # Tabs for Analysis and Chat
                        analysis_tab, chat_tab = st.tabs(["Analysis", "Chat"])
                        
                        with analysis_tab:
                            for result in st.session_state[analysis_state_key]['results']:
                                st.markdown(f"**Analysis by {result.model}**")
                                st.markdown(result.html, unsafe_allow_html=True)
                                st.markdown("---")
                        
                        with chat_tab:
                            vclient = st.session_state[analysis_state_key]['vclient']
                            if prompt := st.chat_input(f"Ask about {vid.title}..."):
                                with st.chat_message("user"):
                                    st.markdown(prompt)
                                
                                with st.chat_message("assistant"):
                                    with st.spinner("Thinking..."):
                                        try:
                                            response = vclient.chat(
                                                processor_name=st.session_state.selected_models[0],
                                                question=prompt
                                            )
                                            if response:
                                                st.markdown(response)
                                            else:
                                                st.error("No response from the model.")
                                        except Exception as e:
                                            st.error(f"Error in chat: {str(e)}")
                                            logger.error(e, exc_info=True)
                
                # Visual separator between videos
                st.markdown("---")

        except Exception as e:
            st.error(f"Error loading channel: {e}")
            logger.error(f"Error loading channel: {e}", exc_info=True)


# ------------------------------------------------------------------------------
# Video View (Main Panel)
# ------------------------------------------------------------------------------
def render_video_tab():
    """Replicate st_video_app's main flow for video analysis & chat."""
    if st.session_state.get("show_video", False) and st.session_state.get("selected_video_url"):
        try:
            # Initialize or get video client
            if not hasattr(st.session_state, 'vclient') or (
                st.session_state.vclient.video_id != st.session_state.get("selected_video_id")
            ):
                vclient = initialize_video_client(st.session_state.selected_video_url)
                st.session_state.vclient = vclient
                st.session_state.selected_video_id = vclient.video_id
            else:
                vclient = st.session_state.vclient

            st.subheader(f"{vclient.title}")
            st.markdown(f"[Watch on YouTube](https://youtube.com/watch?v={vclient.video_id})")

            # Two tabs: Analysis, Chat
            analysis_tab, chat_tab = st.tabs(["Analysis", "Chat"])

            with analysis_tab:
                # If URL changed or analyze clicked from sidebar, run analysis
                if (st.session_state.get("selected_video_url") != st.session_state.get("last_analyzed_url")):
                    with st.spinner("Analyzing video..."):
                        try:
                            results = vclient.analyze_video(
                                processor_names=st.session_state.selected_models,
                                task=st.session_state.selected_task,
                                role=st.session_state.selected_role
                            )
                            st.session_state.current_results = results
                            st.session_state.last_analyzed_url = st.session_state.selected_video_url
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error analyzing video: {str(e)}")
                            logger.error(e, exc_info=True)

                # Show results if available
                if hasattr(st.session_state, 'current_results') and st.session_state.current_results:
                    for result in st.session_state.current_results:
                        with st.expander(f"Analysis by {result.model}", expanded=True):
                            st.markdown(result.html, unsafe_allow_html=True)

                # Show transcript if available
                if vclient.transcript:
                    with st.expander("Video Transcript", expanded=False):
                        st.text(vclient.transcript)

            with chat_tab:
                # Show the model selector for Chat
                available_processors = vclient.get_processors()
                if not available_processors:
                    st.error("No language models available for chat. Check your API keys.")
                    return

                selected_model = st.selectbox(
                    "Select Model for Chat",
                    list(available_processors.keys()),
                    key="chat_model"
                )

                # Initialize chat history if needed
                if "messages" not in st.session_state:
                    st.session_state.messages = []

                # Chat input box
                if prompt := st.chat_input("Ask a question about the video..."):
                    # Add user message
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    # Model response
                    with st.chat_message("assistant"):
                        with st.spinner(f"Thinking... ({selected_model})"):
                            try:
                                response = vclient.chat(
                                    processor_name=selected_model,
                                    question=prompt
                                )
                                if response:
                                    st.session_state.messages.append({"role": "assistant", "content": response})
                                    st.markdown(response)
                                else:
                                    st.error("No response from the model.")
                            except Exception as e:
                                st.error(f"Error in chat: {str(e)}")
                                logger.error(e, exc_info=True)

                # Show messages in reverse order so newest appear at top
                for message in reversed(st.session_state.messages):
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

        except Exception as e:
            st.error(f"Error initializing video: {e}")
            logger.error(e, exc_info=True)


# ------------------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------------------
def render_sidebar_analysis_settings():
    """Render the shared analysis settings (models, roles, tasks) in sidebar."""
    # Only show analyze button if we're in video tab AND not channel view
    if st.session_state.active_tab == "Video" and not st.session_state.get("show_channel", False):
        if st.sidebar.button(
            "Analyze Video", 
            use_container_width=True,
            key="analyze_video_sidebar"
        ):
            if st.session_state.get("selected_video_url"):
                try:
                    vclient = initialize_video_client(st.session_state.selected_video_url)
                    with st.spinner("Analyzing video..."):
                        results = vclient.analyze_video(
                            processor_names=st.session_state.selected_models,
                            task=st.session_state.selected_task,
                            role=st.session_state.selected_role
                        )
                    st.session_state.vclient = vclient
                    st.session_state.current_results = results
                    st.session_state.show_video = True
                    st.session_state.last_analyzed_url = st.session_state.selected_video_url
                    st.rerun()
                except Exception as e:
                    st.error(f"Error analyzing video: {str(e)}")
                    logger.error(e, exc_info=True)
    
    # 1. Models (just checkbox, Claude default)
    st.sidebar.subheader("Models")
    st.session_state.selected_models = []
    
    for model_key, model_info in AVAILABLE_MODELS.items():
        if st.sidebar.checkbox(model_info["display_name"], 
                             value=(model_key == "claude_37_sonnet")):  # Default to Claude 3.7
            st.session_state.selected_models.append(model_key)

    # 2. Roles (dropdown like tasks, no custom)
    st.sidebar.subheader("Roles")
    role_options = ["Research Assistant", "Financial Analyst"]
    chosen_role = st.sidebar.selectbox(
        "Choose Role",
        role_options,
        index=0
    )
    if chosen_role == "Research Assistant":
        st.session_state.selected_role = Role.research_assistant()
    else:
        st.session_state.selected_role = Role.financial_analyst()

    # 3. Tasks (show only existing tasks)
    st.sidebar.subheader("Task")
    task_options = ["Summarize", "Market Analysis", "Reformat", "Custom"]
    chosen_task = st.sidebar.selectbox(
        "Choose Task",
        task_options,
        index=0  # Default to Summarize
    )

    if chosen_task == "Summarize":
        st.session_state.selected_task = Task.summarize()
    elif chosen_task == "Market Analysis":
        st.session_state.selected_task = Task.market_analysis()
    elif chosen_task == "Reformat":
        st.session_state.selected_task = Task.reformat()
    else:  # Custom
        custom_task_prompt = st.sidebar.text_area("Enter custom task instructions:")
        if custom_task_prompt.strip():
            st.session_state.selected_task = Task.custom(
                prompt=custom_task_prompt,
                name="custom",
                description="Custom analysis task"
            )
        else:
            st.session_state.selected_task = Task.summarize()

def render_sidebar():
    """Render sidebar with shared analysis settings."""
    st.sidebar.title("Settings")

    # Navigation
    st.sidebar.subheader("Navigation")
    current_tab = st.sidebar.radio(
        "Select View",
        ["Channel", "Video"],
        index=0 if "active_tab" not in st.session_state
              else ["Channel", "Video"].index(st.session_state.active_tab)
    )
    if current_tab != st.session_state.get("active_tab"):
        st.session_state.active_tab = current_tab

    # Channel-specific settings
    if current_tab == "Channel":
        st.sidebar.subheader("Select a Channel")
        channel_options = list(PRESET_CHANNELS.keys()) + ["Custom"]
        channel_choice = st.sidebar.selectbox(
            "Choose channel:",
            options=channel_options,
            index=2  # Default to CNBC
        )
        
        if channel_choice == "Custom":
            st.session_state.channel_handle = st.sidebar.text_input(
                "Enter channel handle (e.g., @lexfridman):",
                placeholder="@channel"
            )
        else:
            st.session_state.channel_handle = PRESET_CHANNELS[channel_choice]

        st.sidebar.subheader("Date Range")
        st.session_state.date_option = st.sidebar.radio(
            "Choose date range:",
            ["Today", "Last N Days"]
        )
        if st.session_state.date_option == "Last N Days":
            st.session_state.days = st.sidebar.number_input(
                "Number of days to look back:",
                min_value=1,
                max_value=365,
                value=30
            )

        if st.sidebar.button("Show Channel Videos", use_container_width=True):
            st.session_state.show_channel = True
            st.session_state.show_video = False
            st.rerun()

    else:  # Video tab
        st.sidebar.subheader("Video Input")
        video_url = st.sidebar.text_input(
            "Enter YouTube video URL or ID:",
            value=st.session_state.get("selected_video_url", "")
        )
        if video_url:
            st.session_state.selected_video_url = video_url

    # Shared analysis settings for both tabs
    render_sidebar_analysis_settings()

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
def main():
    # Session state defaults
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Channel"
    if "show_channel" not in st.session_state:
        st.session_state.show_channel = False
    if "show_video" not in st.session_state:
        st.session_state.show_video = False
    if "channel_handle" not in st.session_state:
        st.session_state.channel_handle = ""

    if "selected_models" not in st.session_state:
        st.session_state.selected_models = list(AVAILABLE_MODELS.keys())
    if "selected_role" not in st.session_state:
        st.session_state.selected_role = Role.research_assistant()
    if "selected_task" not in st.session_state:
        st.session_state.selected_task = Task.summarize()
    if "days" not in st.session_state:
        st.session_state.days = 30
    if "date_option" not in st.session_state:
        st.session_state.date_option = "Today"

    # Draw side controls
    render_sidebar()

    # Main content area
    if st.session_state.active_tab == "Channel":
        render_channel_tab()
    else:
        render_video_tab()


if __name__ == "__main__":
    main()