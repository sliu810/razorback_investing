import os
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime, timedelta
import pytz
from IPython.display import HTML
import html
import re
from youtube_transcript_api import YouTubeTranscriptApi

MY_TIMEZONE = 'America/Chicago'

# Youtube Data API v3
api_key = os.getenv('YOUTUBE_API_KEY')
if not api_key:
    raise ValueError("No API key found. Make sure the YOUTUBE_API_KEY environment variable is set.")

youtube = build('youtube', 'v3', developerKey=api_key)

# Dictionary of channel IDs and their corresponding names
channels = {
    "CNBC_TV": "UCrp_UI8XtuYfpiqluWLD7Lw",
    "BloombergTechnology": 'UCrM7B7SL_g1edFOnmj-SDKg',
    "YahooFinance": 'UCEAZeUIeJs0IjQiqTCdVSIg',
    "DeepWater": 'UCQCNLsdpDV1XSHH4V8WQuPA',
    "BobUnlimited": 'UClkYGk572o1kZp9juGxSSHg',
    "LukeGromenFFTTLLC": 'UC3dgTGurzmoefBchduxs4Gg',
    "TheDavidLinReport": 'UCaD8nSFXtoX7pDeoK6v6pKw',
    "TheLeadLagReport": 'UCInl2wu4m5EjpgZP7kosVUg',
}

# Function to get channel name from ID
def get_channel_name_by_id(channel_id, channels):
    for name, id in channels.items():
        if id == channel_id:
            return name
    return None

def get_date_from_string(date_str):
    local_timezone = pytz.timezone(MY_TIMEZONE)
    try:
        specified_date = datetime.strptime(date_str, "%m-%d-%Y")
    except ValueError:
        raise ValueError("Incorrect date format, should be MM-DD-YYYY")
    
    localized_date = local_timezone.localize(specified_date)
    
    return localized_date

def get_date_range(period_type, number=1):
    local_timezone = pytz.timezone(MY_TIMEZONE)
    now = datetime.now(pytz.utc).astimezone(local_timezone)    
    
    if period_type == 'today':
        start_date = datetime(now.year, now.month, now.day, 0, 0, 0)
        end_date = datetime(now.year, now.month, now.day, 23, 59, 59, 999999)
    elif period_type == 'days':
        start_date = datetime(now.year, now.month, now.day, 0, 0, 0) - timedelta(days=number-1)
        end_date = datetime(now.year, now.month, now.day, 23, 59, 59, 999999)
    elif period_type == 'weeks':
        start_date = datetime(now.year, now.month, now.day, 0, 0, 0) - timedelta(weeks=number)
        end_date = datetime(now.year, now.month, now.day, 23, 59, 59, 999999)
    elif period_type == 'months':
        start_date = datetime(now.year, now.month, now.day, 0, 0, 0) - timedelta(days=30*number)
        end_date = datetime(now.year, now.month, now.day, 23, 59, 59, 999999)
    else:
        raise ValueError("Unsupported period type specified.")
    
    # Localize the datetime objects
    start_date = local_timezone.localize(start_date)
    end_date = local_timezone.localize(end_date)
    
    return start_date, end_date

# # Test get_date_range
# start_date, end_date = get_date_range('days',3)
# print(start_date, end_date)

def iso_duration_to_minutes(iso_duration):
    # Parse ISO 8601 duration format to total minutes
    pattern = re.compile(r'PT((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+)S)?')
    matches = pattern.match(iso_duration)
    if not matches:
        return 0  # Return 0 if the pattern does not match

    hours = int(matches.group('hours') or 0)
    minutes = int(matches.group('minutes') or 0)
    seconds = int(matches.group('seconds') or 0)

    # Calculate total minutes, rounding up if there are any seconds
    total_minutes = hours * 60 + minutes
    if seconds > 0:
        total_minutes += 1  # Round up if there are any remaining seconds

    return total_minutes

# Get formated date
def get_formated_date_today():
    timezone = pytz.timezone(MY_TIMEZONE)
    now = datetime.now(timezone)
    formatted_date = now.strftime('%Y-%m-%d')
    return formatted_date

def fetch_videos(start_date, end_date, channel_id, existing_df=None):
    # Convert 'Published At' to datetime to ensure proper comparison
    if existing_df is not None and not existing_df.empty and 'Published At' in existing_df.columns:
        existing_df['Published At'] = pd.to_datetime(existing_df['Published At'])

    video_data = []
    page_token = None
    local_timezone = pytz.timezone(MY_TIMEZONE)

    while True:
        request = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            publishedAfter=start_date.isoformat(),
            publishedBefore=end_date.isoformat(),
            maxResults=50,
            pageToken=page_token,
            type="video"
        )
        response = request.execute()

        video_ids = [item['id']['videoId'] for item in response.get("items", []) if 'videoId' in item['id']]
        if video_ids:
            video_request = youtube.videos().list(
                part='contentDetails,snippet',
                id=','.join(video_ids)
            )
            video_details_response = video_request.execute()

            for video in video_details_response.get("items", []):
                video_id = video['id']
                content_details = video['contentDetails']
                snippet = video['snippet']
                published_at = datetime.strptime(snippet['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC)

                # Check if video already exists in the existing DataFrame
                if not existing_df[existing_df['Video ID'] == video_id].empty:
                    continue

                video_data.append({
                    "Title": html.unescape(snippet['title']),
                    "Published At": published_at,
                    "Duration (Min)": iso_duration_to_minutes(content_details.get('duration', 'PT0S')),
                    "Video ID": video_id,
                    "URL": f"https://www.youtube.com/watch?v={video_id}"
                })

        page_token = response.get('nextPageToken')
        if not page_token:
            break

    if video_data:
        new_videos_df = pd.DataFrame(video_data)
        combined_df = pd.concat([existing_df, new_videos_df], ignore_index=True).sort_values(by=['Published At'], ascending=False)
        combined_df.to_csv(csv_file, index=False)
        print(f"Appended {len(new_videos_df)} new videos to {csv_file}.")
        return combined_df
    else:
        print("No new videos found.")
        return existing_df  # Return the existing DataFrame if no new videos were found
    
def filter_videos_by_date_and_time(df_videos, period_type='today', number=1, hour_range=None):
    """
    Filters videos based on the 'Published At' column within the specified date and optional time range.

    Parameters:
    - df_videos (DataFrame): DataFrame containing video data with 'Published At' as datetime.
    - period_type (str): 'today', 'days', 'weeks', or 'months'.
    - number (int): Number of days, weeks, or months to look back from today.
    - hour_range (str, optional): Hour range in the format 'HH-HH'. Only applicable if period_type is 'today'.

    Returns:
    - DataFrame: Filtered DataFrame based on the date and optional time range.
    """
    if df_videos.empty:
        print("The DataFrame is empty. No videos to filter.")
        return df_videos

    start_date, end_date = get_date_range(period_type, number)

    local_timezone = pytz.timezone(MY_TIMEZONE)
    start_date = start_date.astimezone(pytz.utc)
    end_date = end_date.astimezone(pytz.utc)
    df_videos['Published At'] = pd.to_datetime(df_videos['Published At'], utc=True)

    filtered_df = df_videos[(df_videos['Published At'] >= start_date) & (df_videos['Published At'] <= end_date)]

    if period_type == 'today' and hour_range:
        start_hour, end_hour = map(int, hour_range.split('-'))
        filtered_df = filtered_df[filtered_df['Published At'].dt.hour >= start_hour]
        filtered_df = filtered_df[filtered_df['Published At'].dt.hour < end_hour]

    return filtered_df

from IPython.display import HTML

def make_clickable(title, url):
    return f'<a href="{url}" target="_blank">{title}</a>'

def display_df(df, include_transcript=False, include_duration=False, include_video_id=False):
    """
    Displays the DataFrame in a Jupyter Notebook with clickable titles and optional columns.

    Parameters:
    - df (DataFrame): DataFrame to display.
    - include_transcript (bool): Whether to include the Transcript column in the display.
    - include_duration (bool): Whether to include the Duration (Min) column in the display.
    - include_video_id (bool): Whether to include the VideoID column in the display.
    """
    # Create a copy for display to avoid altering the original DataFrame
    df_display = df.copy()
    
    # Make titles clickable
    df_display['Title'] = df_display.apply(lambda x: make_clickable(x['Title'], x['URL']), axis=1)

    # Format the 'Published At' column to show only the date
    df_display['Published At'] = pd.to_datetime(df_display['Published At']).dt.date

    # Drop the URL column for display
    df_display.drop('URL', axis=1, inplace=True)

    # Drop optional columns based on parameters and existence
    if not include_transcript and 'Transcript' in df_display.columns:
        df_display.drop('Transcript', axis=1, inplace=True)
    if not include_duration and 'Duration (Min)' in df_display.columns:
        df_display.drop('Duration (Min)', axis=1, inplace=True)
    if not include_video_id and 'Video ID' in df_display.columns:
        df_display.drop('Video ID', axis=1, inplace=True)

    # Generate HTML content and display the DataFrame
    html_content = df_display.to_html(escape=False, index=False)
    display(HTML(html_content))

def save_df_to_html(df, file_name):
    """
    Saves the DataFrame to an HTML file with clickable titles and without the URL column.

    Parameters:
    - df (DataFrame): DataFrame to save.
    - file_name (str): Name of the HTML file to save the DataFrame.
    """
    html_content = get_html_content(df)
    with open(file_name, 'w') as file:
        file.write(html_content)
    print(f"DataFrame has been saved to {file_name}.")

def get_html_content(df):
    """
    Generates and returns the HTML content of the DataFrame with clickable titles and without the URL column.

    Parameters:
    - df (DataFrame): DataFrame to generate HTML content from.

    Returns:
    - str: HTML representation of the DataFrame.
    """
    # Create a copy for display to avoid altering the original DataFrame
    df_display = df.copy()
    
    # Make titles clickable
    df_display['Title'] = df_display.apply(lambda x: make_clickable(x['Title'], x['URL']), axis=1)

    # Generate HTML content without the URL column
    html_content = df_display.drop('URL', axis=1).to_html(escape=False, index=False)
    
    return html_content

def format_summary(summary):
    """Formats the summary with correct HTML structure and bullet points."""

    # Initialize empty lists for different sections
    categories = []
    stocks_mentioned = []
    key_takeaways = []

    # Split summary into lines
    lines = summary.split("\n")

    # Categorize lines based on their content
    current_section = None
    for line in lines:
        if line.startswith("Category:"):
            current_section = "categories"
            categories.append(line[len("Category:"):].strip())  # Extract category name
        elif line.startswith("Stocks mentioned:"):
            current_section = "stocks_mentioned"
            stocks_mentioned.append(line[len("Stocks mentioned:"):].strip())  # Extract stock name
        elif line.startswith("Key takeaways:"):
            current_section = "key_takeaways"
        elif current_section == "key_takeaways":
            key_takeaways.append(line.strip())

    # Format HTML output
    formatted_summary = ""

    # Add category
    if categories:
        formatted_summary += f"<p><b>Category:</b> {', '.join(categories)}</p>"

    # Add stocks mentioned
    if stocks_mentioned:
        formatted_summary += f"<p><b>Key Stocks mentioned:</b> {', '.join(stocks_mentioned)}</p>"

    # Add key takeaways
    if key_takeaways:
        formatted_summary += "<p><b>Key takeaways:</b></p><ul>"
        for takeaway in key_takeaways:
            formatted_summary += f"<li>{re.sub(r'^\\s*-\\s*', '', takeaway)}</li>"  # Remove leading hyphen and spaces
        formatted_summary += "</ul>"

    return formatted_summary

def get_html_content_summary_only(df):
    """
    Generates and returns the HTML content of the DataFrame with clickable titles and the video summary.
    
    Args:
    - df (pandas.DataFrame): DataFrame containing video information.
    
    Returns:
    - str: HTML representation of the DataFrame.
    """
    df['Summary'] = df['Summary'].fillna('')  # Fill NaN values with an empty string
    html_content = ""
    for _, row in df.iterrows():
        html_content += f"<h2><a href='https://www.youtube.com/watch?v={row['Video ID']}' target='_blank'>{row['Title']}</a></h2>"
        html_content += f"<p>{row['Summary']}</p>"
        html_content += "<hr>"
    return html_content

def get_transcript(video_id):
    """
    Fetches the transcript for a given YouTube video ID and converts it to lowercase.

    Parameters:
    - video_id (str): The YouTube video ID.

    Returns:
    - str: The lowercase transcript text or None if an error occurs.
    """
    try:
        # Fetch the transcript
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Find the English transcript
        transcript = transcript_list.find_transcript(['en'])
        
        # Fetch the actual transcript
        transcript_data = transcript.fetch()
        
        # Extract the text, combine into sentences, and convert to lowercase
        transcript_text = " ".join([entry['text'] for entry in transcript_data]).lower()
        
        return transcript_text
    
    except Exception as e:
        print(f"An error occurred for video ID {video_id}: {e}")
        return None

def add_transcripts_to_df(df):
    """
    Iterates through the DataFrame, retrieves the transcript for each Video ID,
    and saves the transcript in a new column in the DataFrame only if it doesn't exist or is NaN.

    Parameters:
    - df (pd.DataFrame): The DataFrame containing the video data.

    Returns:
    - pd.DataFrame: The DataFrame with an updated 'Transcript' column.
    """
    if 'Transcript' not in df.columns:
        df['Transcript'] = pd.NA  # Initialize the 'Transcript' column if it doesn't exist

    for index, row in df.iterrows():
        if pd.isna(row['Transcript']) or row['Transcript'] == "":
            transcript = get_transcript(row['Video ID'])
            if transcript is None:
                transcript = "No transcript for video"
            df.at[index, 'Transcript'] = transcript

    return df

def format_content(row, columns):
    content = ""
    for col in columns:
        if pd.isna(row[col]):
            row[col] = ""  # or some other placeholder text
        content += f"<strong>{col}:</strong> {str(row[col]).replace('\n', '<br>')}<br>\n"
    return content

def save_videos_to_text(df, file_name, *columns):
    html_content = ""
    for _, row in df.iterrows():
        formatted_content = format_content(row, columns)
        html_content += f'<div>{formatted_content}</div>\n'

    # Save the HTML content to an HTML file
    with open(file_name, 'w') as file:
        file.write(html_content)
        
def apply_task(text, client, task):
    try:
        response = client.chat.completions.create(
            model= "gpt-3.5-turbo", # "gpt-4o-2024-08-06", #"gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial analyst."},
                {"role": "user", "content": f"Please {task} for the following text:\n\n{text}"}
            ],
            max_tokens=3000
        )
        summary = response.choices[0].message.content.strip()
        return summary
    except openai.OpenAIError as e:  # Catch the general OpenAIError
        if "maximum context length" in str(e):
            print(f"Warning: Context length exceeded for transcript. Returning an empty summary.")
            return "Context length exceeded. Summary not available."
        else:
            raise e  # Re-raise other types of OpenAI errors

def apply_task_in_chunks(text, client, task, chunk_size=4000): # Adjust chunk size as needed
    text_chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    summaries = []
    for chunk in text_chunks:
        summary = apply_task(chunk, client, task)  # Reuse your original function
        summaries.append(summary)
    return "\n\n".join(summaries) # Combine or further summarize if needed

def apply_tasks_on_all_transcripts(df, client, task):
    """
    Apply task for transcripts.

    Parameters:
    - df (pd.DataFrame): DataFrame containing video data with 'Transcript' and 'Summary' columns.
    - client (openai.Client): OpenAI API client.
    - task (str): The task description for summarizing the transcript.

    Returns:
    - pd.DataFrame: Updated DataFrame with 'Summary' column.
    """
    if 'Summary' not in df.columns:
        df['Summary'] = pd.NA  # Initialize the 'Summary' column if it doesn't exist

    #summaries = df['Summary'].tolist()
    for index, row in df.iterrows():
        if pd.isna(row['Summary']):
            transcript = row['Transcript']
            if pd.isna(transcript) or transcript == "No transcript for video":
                summary = "No summary"
            else:
                summary = apply_task(transcript, client, task)
                if not summary or summary == "Context length exceeded. Summary not available.":
                    summary = "No summary"
            # Update the DataFrame with the summary
            df.at[index, 'Summary'] = summary

    return df

