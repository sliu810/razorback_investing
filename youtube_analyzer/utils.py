import pytz
from datetime import datetime, date, timedelta
import re
import logging
from isodate import parse_duration
from typing import Tuple

def iso_duration_to_minutes(duration: str) -> int:
    """Convert ISO 8601 duration to minutes
    
    Examples:
        PT1H30M -> 90 (1 hour 30 minutes)
        PT30M -> 30 (30 minutes)
        P1DT2H30M -> 1590 (1 day 2 hours 30 minutes)
    """
    try:
        # Extract days, hours, minutes, and seconds using regex
        days = re.search(r'(\d+)D', duration)
        hours = re.search(r'(\d+)H', duration)
        minutes = re.search(r'(\d+)M', duration)
        seconds = re.search(r'(\d+)S', duration)
        
        total_minutes = 0
        
        # Convert each component to minutes
        if days:
            total_minutes += int(days.group(1)) * 24 * 60
        if hours:
            total_minutes += int(hours.group(1)) * 60
        if minutes:
            total_minutes += int(minutes.group(1))
        if seconds:
            # Round up seconds to nearest minute
            total_minutes += (int(seconds.group(1)) + 59) // 60
            
        return total_minutes
        
    except Exception as e:
        logging.warning(f"Invalid ISO duration format: {duration}")
        return 0

def get_formatted_date_today(timezone_str='America/Chicago'):
    timezone = pytz.timezone(timezone_str)
    now = datetime.now(timezone)
    formatted_date = now.strftime('%Y-%m-%d')
    return formatted_date

def make_clickable(text, link):
    """
    Creates a clickable link for HTML display.

    Args:
        text (str): The text to be displayed as a link.
        link (str): The URL for the link.

    Returns:
        str: HTML string representing a clickable link.
    """
    return f'<a href="{link}" target="_blank">{text}</a>'

def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a string to be used as a filename.
    
    Args:
    filename (str): The string to be sanitized.
    max_length (int): The maximum length of the resulting filename. Default is 255.
    
    Returns:
    str: The sanitized filename.
    """
    # Replace spaces with underscores and remove non-alphanumeric characters
    sanitized = re.sub(r'[^\w\-_\. ]', '', filename)
    sanitized = re.sub(r'\s+', '_', sanitized)
    
    # Trim the filename if it's too long
    return sanitized[:max_length]

def get_start_end_dates_for_year(year: int = None) -> Tuple[datetime, datetime]:
    """
    Get the start and end dates for a given year.
    
    If no year is provided or if the provided year is the current year,
    the end date will be set to today.

    Args:
        year (int, optional): The year for which to get the date range. 
                              If None, the current year is used.

    Returns:
        Tuple[datetime, datetime]: A tuple containing the start and end dates for the specified year.
    """
    current_year = date.today().year
    
    if year is None or year == current_year:
        year = current_year
        start_date = datetime(year, 1, 1)
        end_date = datetime.now()
    else:
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
    
    return start_date, end_date

def get_start_end_dates_for_period(period_type: str, number: int = 1, timezone: str = 'America/Chicago') -> Tuple[datetime, datetime]:
    """
    Generate a date range based on the specified period type and number.

    Args:
        period_type (str): The type of period ('today', 'days', 'weeks', 'months').
        number (int): The number of periods to go back (default is 1).
        timezone (str): The timezone to use for the date range (default is 'America/Chicago').

    Returns:
        Tuple[datetime, datetime]: A tuple containing the start and end dates.

    Raises:
        ValueError: If an unsupported period type is specified.
    """
    local_timezone = pytz.timezone(timezone)
    now = datetime.now(pytz.utc).astimezone(local_timezone)
    
    if period_type == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period_type == 'days':
        start_date = (now - timedelta(days=number-1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period_type == 'weeks':
        start_date = (now - timedelta(weeks=number)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period_type == 'months':
        start_date = (now - timedelta(days=30*number)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        raise ValueError("Unsupported period type specified.")
    
    return start_date, end_date

def extract_video_id(video_input: str) -> str:
    """Extract video ID from URL or return the ID if directly provided
    
    Args:
        video_input: YouTube video URL or video ID
        
    Returns:
        str: YouTube video ID
    """
    if "youtube.com/watch?v=" in video_input:
        return video_input.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in video_input:
        return video_input.split("youtu.be/")[-1].split("?")[0]
    return video_input  # Assume it's already a video ID