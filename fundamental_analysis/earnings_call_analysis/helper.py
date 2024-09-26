import os
from dotenv import load_dotenv, find_dotenv

# these expect to find a .env file at the directory above the lesson.                                                                                                                     # the format for that file is (without the comment)                                                                                                                                       #API_KEYNAME=AStringThatIsTheLongAPIKeyFromSomeService                                                                                                                                     
def load_env():
    _ = load_dotenv(find_dotenv())

def get_openai_api_key():
    load_env()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    return openai_api_key

# helper function to display text 
def display_text(text):
    """
    Display text in a formatted HTML paragraph.
    
    Args:
    text (str): The text to be displayed.
    """
    from IPython.display import display, HTML
    display(HTML(f'<p style="font-size: 12px;">{text}</p>'))