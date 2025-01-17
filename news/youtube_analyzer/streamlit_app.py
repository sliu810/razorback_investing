import streamlit as st
from typing import Optional
from video import Video
from youtube_client import YouTubeAnalysisClient
from llm_processor import RoleRegistry, TaskRegistry
from video_analyzer import TranscriptAnalysis, VideoAnalyzer, LLMConfig, AnalysisConfig
import logging
import sys

# Set up logging
logger = logging.getLogger(__name__)

# Custom CSS with even larger font sizes
st.markdown("""
    <style>
        /* Main content */
        .main .block-container {
            padding-top: 2rem;
        }
        
        /* Main Title */
        h1 {
            font-size: 3rem !important;
            font-weight: 600 !important;
            margin-bottom: 2rem !important;
        }
        
        /* Sidebar */
        section[data-testid="stSidebar"] .block-container {
            padding-top: 2rem;
        }
        
        section[data-testid="stSidebar"] h1 {
            font-size: 2rem !important;
        }
        
        section[data-testid="stSidebar"] h2 {
            font-size: 1.8rem !important;
            margin-top: 1rem !important;
        }
        
        /* Specifically target sidebar labels and inputs */
        section[data-testid="stSidebar"] label {
            font-size: 1.8rem !important;
            font-weight: 500 !important;
            margin-bottom: 0.5rem !important;
            color: rgb(49, 51, 63) !important;
        }
        
        section[data-testid="stSidebar"] input {
            font-size: 1.6rem !important;
            padding: 0.5rem !important;
        }
        
        section[data-testid="stSidebar"] .stCheckbox label span {
            font-size: 1.6rem !important;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab"] {
            font-size: 1.8rem !important;
            font-weight: 500 !important;
            padding: 1rem 2rem !important;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 2rem;
            margin-bottom: 2rem;
        }
        
        /* Expander headers */
        .streamlit-expanderHeader {
            font-size: 1.6rem !important;
            font-weight: 500 !important;
            padding: 1rem 0 !important;
        }
        
        /* Button text */
        .stButton button {
            font-size: 1.6rem !important;
            padding: 0.75rem 1.5rem !important;
        }
        
        /* Input fields and labels in main content */
        .stTextInput label, .stSelectbox label {
            font-size: 1.8rem !important;
            font-weight: 500 !important;
            margin-bottom: 0.5rem !important;
        }
        
        .stTextInput input, .stSelectbox select {
            font-size: 1.6rem !important;
            padding: 0.5rem !important;
        }
        
        /* Chat messages */
        .stMarkdown p {
            font-size: 1.6rem !important;
            line-height: 1.6 !important;
        }
        
        /* Headers */
        .stMarkdown h1 {
            font-size: 2.5rem !important;
        }
        
        .stMarkdown h2 {
            font-size: 2rem !important;
        }
        
        .stMarkdown h3 {
            font-size: 1.8rem !important;
        }
        
        /* Specifically target sidebar input labels */
        section[data-testid="stSidebar"] .stTextInput label,
        section[data-testid="stSidebar"] .stSelectbox label {
            font-size: 2rem !important;
            font-weight: 500 !important;
        }
        
        /* Dark mode support for sidebar labels */
        @media (prefers-color-scheme: dark) {
            section[data-testid="stSidebar"] .stTextInput label,
            section[data-testid="stSidebar"] .stSelectbox label {
                color: #ffffff !important;
            }
        }

        /* Make tabs larger */
        button[data-baseweb="tab"] {
            font-size: 2.5rem !important;
            font-weight: 500 !important;
            padding: 1rem 2rem !important;
        }
    </style>
""", unsafe_allow_html=True)

def init_session_state():
    """Initialize session state variables"""
    if 'client' not in st.session_state:
        st.session_state.client = YouTubeAnalysisClient()
    if 'video' not in st.session_state:
        st.session_state.video = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'processors' not in st.session_state:
        st.session_state.processors = {}

def show_processing_steps(video_id: str, use_claude: bool, use_gpt4: bool):
    """Show processing steps with status messages"""
    
    # Create status containers
    status_container = st.empty()
    debug_container = st.empty()
    
    try:
        # Step 1: Initialize processors
        status_container.info("Setting up processors...")
        claude, gpt4 = st.session_state.client.setup_processors()
        st.session_state.processors = {
            "Claude": claude if use_claude else None,
            "GPT-4": gpt4 if use_gpt4 else None
        }
        
        # Step 2: Process video
        status_container.info("Fetching video information...")
        
        # Debug: Check client initialization
        with st.expander("Debug Information"):
            st.text("=== Client Setup ===")
            st.text(f"Client type: {type(st.session_state.client)}")
            st.text(f"YouTube API initialized: {hasattr(st.session_state.client, 'youtube_client')}")
            
            st.text("\n=== Processing Video ===")
            st.text(f"Processing video ID: {video_id}")
            
            # Process video and capture intermediate results
            video = st.session_state.client.process_video(video_id)
            
            st.text("\n=== Video Object ===")
            st.text(f"Video object created: {video is not None}")
            if video:
                st.text(f"Video ID: {video.video_id}")
                st.text(f"Title: {video.title}")
                st.text(f"Transcript length: {len(video.transcript) if video.transcript else 0}")
                st.text(f"First 200 chars: {video.transcript[:200] if video.transcript else 'EMPTY'}")
            
            st.text("\n=== Available Processors ===")
            st.text(f"Processors: {list(st.session_state.processors.keys())}")
            
        if not video:
            status_container.error("Could not process video")
            return None
        
        if not video.transcript:
            status_container.error("Transcript is empty")
            return None
        
        status_container.success("Video processed successfully!")
        st.session_state.video = video
        
        # After video object creation
        logger.debug("Created video object, fetching transcript...")
        logger.debug(f"Initial video object: {video}")
        
        return video
        
    except Exception as e:
        status_container.error(f"Error during processing: {str(e)}")
        st.error(f"Detailed error: {str(e)}")
        return None

def init_analysis_settings():
    """Initialize analysis settings in sidebar"""
    st.sidebar.subheader("Analysis Settings")

    # Role selection with consistent styling
    st.sidebar.markdown("##### Role")
    role = st.sidebar.radio(
        label="",
        options=["research_assistant", "financial_analyst"],
        format_func=lambda x: "Research Assistant" if x == "research_assistant" else "Financial Analyst"
    )
    
    # Use class methods directly without instantiation
    role_info = RoleRegistry.get_research_assistant() if role == "research_assistant" else RoleRegistry.get_financial_analyst()
    
    with st.sidebar.expander("Role Description"):
        st.markdown(f"**Description:** {role_info.description}")
    
    # Task selection with consistent styling
    st.sidebar.markdown("##### Task")
    task = st.sidebar.radio(
        label="",
        options=["summarize_transcript"],
        format_func=lambda x: "Summarize Transcript"
    )
    
    # Use class method directly
    task_info = TaskRegistry.get_summarize_transcript()
    with st.sidebar.expander("Task Description"):
        st.markdown(f"**Description:** {task_info.description}")
    
    return role

def display_analysis_results(video, analysis_results):
    """Display video analysis results"""
    logger.debug(f"Raw video object: {video}")
    if video and analysis_results:
        logger.debug(f"Displaying video with title: {video.title}")
        st.header("Analysis Results")
        
        # Video information section
        st.subheader("Video Information")
        col1, col2 = st.columns([1, 2])
        with col2:
            st.write(f"**Title:** {video.title}")
            st.write(f"**URL:** {video.url}")
            st.write(f"**Channel:** {video.channel_name}")
            st.write(f"**Published:** {video.published_at}")
            st.write(f"**Duration:** {video.duration_minutes} minutes")
            
        # Analysis results section
        st.subheader("Content Analysis")
        for model, result in analysis_results.items():
            with st.expander(f"{model} Analysis"):
                st.markdown(result)

def main():
    st.title("YouTube Video Analyzer")
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        video_id = st.text_input("YouTube Video ID")
        
        # Model selection
        st.subheader("Models")
        use_claude = st.checkbox("Use Claude", value=True)
        use_gpt4 = st.checkbox("Use GPT-4", value=True)
        
        # Role and Task configuration
        st.subheader("Analysis Settings")
        role = init_analysis_settings()
        task = st.text_input("Task", value="summarize_transcript")
        
        if st.button("Analyze Video"):
            if video_id:
                status_container = st.empty()
                video = show_processing_steps(video_id, use_claude, use_gpt4)
                
                if video:
                    st.session_state.analysis_results = {}
                    # Process with selected models
                    for name, processor in st.session_state.processors.items():
                        if processor:
                            status_container.info(f"Analyzing with {name}...")
                            # Create TranscriptAnalysis object and populate it
                            analysis_obj = TranscriptAnalysis(video)
                            analysis_obj.model_provider = processor.config.provider
                            analysis_obj.model_name = processor.config.model_name
                            analysis_obj.summary = st.session_state.client.analyze_text(
                                processor=processor,
                                text=video.transcript,
                                role_name=role,
                                task_name=task
                            )
                            # Store the HTML version
                            st.session_state.analysis_results[name] = analysis_obj.get_html()
                    
                    # Show completion after all analyses are done
                    status_container.success("Analysis completed successfully!")
            else:
                st.error("Please enter a YouTube Video ID")
    
    # Main content - Tabs
    tab1, tab2 = st.tabs(["Analysis", "Chat"])
    
    # Analysis Tab
    with tab1:
        if st.session_state.video and hasattr(st.session_state, 'analysis_results'):
            # Create placeholders for analysis results
            analysis_placeholders = {}
            for name in st.session_state.analysis_results:
                with st.expander(f"{name} Analysis"):
                    analysis_placeholders[name] = st.empty()
                    # Use unsafe_allow_html=True to render HTML
                    analysis_placeholders[name].markdown(
                        st.session_state.analysis_results[name],
                        unsafe_allow_html=True
                    )
            
            with st.expander("Full Transcript"):
                st.text(st.session_state.video.transcript)
    
    # Chat Tab
    with tab2:
        if st.session_state.video:
            # Add model selector in the chat tab
            available_models = {
                name: processor 
                for name, processor in st.session_state.processors.items() 
                if processor is not None
            }
            
            if available_models:
                chat_model = st.selectbox(
                    "Select model for chat:",
                    options=list(available_models.keys()),
                    key="chat_model"
                )
                selected_processor = available_models[chat_model]
                
                # Accept user input at the top
                if prompt := st.chat_input("Ask about the video"):
                    # Display user message
                    with st.chat_message("user"):
                        st.write(prompt)
                    st.session_state.chat_history.append({"role": "user", "content": prompt})

                    # Generate and display assistant response
                    with st.chat_message("assistant"):
                        with st.spinner(f"Thinking with {chat_model}..."):
                            response = st.session_state.client.chat(
                                processor=selected_processor,
                                question=prompt,
                                context=st.session_state.video.transcript
                            )
                        st.write(response)
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                
                # Add a divider before history
                if st.session_state.chat_history:
                    st.markdown("---")
                    st.markdown("#### Chat History")
                
                # Display chat history in reverse order (newest first)
                for message in reversed(st.session_state.chat_history):
                    with st.chat_message(message["role"]):
                        st.write(message["content"])
            else:
                st.warning("Please select at least one model in the sidebar to enable chat.")
        else:
            st.info("Please analyze a video first to start chatting.")

if __name__ == "__main__":
    main() 