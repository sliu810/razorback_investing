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
from llm_processor import Task, Role
from utils import extract_video_id

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Initialize client and processors globally
client = YouTubeVideoClient(
    youtube_api_key=os.getenv('YOUTUBE_API_KEY'),
    anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
    openai_api_key=os.getenv('OPENAI_API_KEY')
)  # This will automatically initialize common processors

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
                question=prompt,
                video_id=video_id
            )
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Display chat messages in reverse chronological order (newest at top)
    for message in reversed(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

def main():
    st.set_page_config(layout="wide")
    
    # Initialize all session state variables
    if 'client' not in st.session_state:
        st.session_state.client = client
        st.session_state.processors = client.processors
        st.session_state.selected_models = list(client.processors.keys())
        st.session_state.selected_role = Role.research_assistant()
        st.session_state.selected_task = Task.summarize()
        st.session_state.messages = []
        st.session_state.current_video_id = None
        st.session_state.current_results = None
        st.session_state.video_url = None

    # Sidebar
    with st.sidebar:
        st.title("YouTube Video Analyzer")
        st.session_state.video_url = st.text_input(
            "Enter YouTube Video URL/ID",
            value=st.session_state.video_url if 'video_url' in st.session_state else "",
            key="video_url_input"
        )
        
        # Model selection
        st.subheader("Models")
        available_models = list(st.session_state.processors.keys())
        st.session_state.selected_models = [
            model for model in available_models 
            if st.checkbox(model, value=True, key=f"model_{model}")
        ]
        
        # Role selection
        st.subheader("Select Role")
        roles = {
            "Research Assistant": Role.research_assistant(),
            "Financial Analyst": Role.financial_analyst(),
        }
        selected_role_name = st.selectbox(
            "",  # Empty label since we have the subheader
            options=list(roles.keys()),
            index=0,
            key="role_selector"
        )
        st.session_state.selected_role = roles[selected_role_name]
        
        # Task selection (simplified)
        st.subheader("Select Task")
        tasks = {
            "Summarize": Task.summarize(),
            "Market Analysis": Task.market_analysis(),
            "Custom Task": None  # Placeholder for custom task
        }
        selected_task_name = st.selectbox(
            "",  # Empty label
            options=list(tasks.keys()),
            index=0,
            key="task_selector"
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
        video_id = extract_video_id(st.session_state.video_url)
        if video_id:
            if analyze_button or st.session_state.current_results is not None:
                if analyze_button:
                    analyze_video()
                    st.session_state.active_tab = "Analysis"  # Set initial tab after analysis
            
            # Initialize active_tab if not exists
            if 'active_tab' not in st.session_state:
                st.session_state.active_tab = "Analysis"
            
            # Create tabs
            tab1, tab2 = st.tabs(["Analysis", "Chat"])
            
            with tab1:  # Analysis tab
                if st.session_state.current_results is not None:
                    # Display video information from the first result
                    video_info = st.session_state.current_results[0]['video_info']
                    st.header(video_info['title'])
                    st.markdown(f"[Watch Video](https://youtube.com/watch?v={video_info['id']})")
                    
                    # Display analysis results first
                    for result in st.session_state.current_results:
                        with st.expander(
                            f"Analysis by {result['analysis']['model']}", 
                            expanded=True
                        ):
                            st.markdown(result['html'], unsafe_allow_html=True)
                    
                    # Display transcript at the bottom
                    with st.expander("Original Transcript", expanded=False):
                        st.markdown(video_info['transcript'])
            
            with tab2:  # Chat tab
                if st.session_state.current_video_id:
                    # Set active tab to Chat when user starts chatting
                    if "messages" in st.session_state and len(st.session_state.messages) > 0:
                        st.session_state.active_tab = "Chat"
                    chat_interface(
                        st.session_state.client, 
                        st.session_state.current_video_id,
                        st.session_state.processors
                    )

def analyze_video():
    """Helper function to analyze video with selected parameters"""
    if st.session_state.video_url:
        video_id = extract_video_id(st.session_state.video_url)
        if video_id:
            with st.spinner("Analyzing video..."):
                results = st.session_state.client.analyze_video(
                    video_id=video_id,
                    processor_names=st.session_state.selected_models,
                    task=st.session_state.selected_task,
                    role=st.session_state.selected_role
                )
                st.session_state.current_results = results
                st.session_state.current_video_id = video_id

if __name__ == "__main__":
    main() 