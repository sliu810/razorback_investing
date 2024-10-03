import pytz
from datetime import datetime, date
import re
import logging
from isodate import parse_duration

def iso_duration_to_minutes(iso_duration):
    """
    Convert ISO 8601 duration format to total minutes.

    Args:
        iso_duration (str): Duration in ISO 8601 format.

    Returns:
        int: Total duration in minutes, rounded up if there are any seconds.
    """
    pattern = re.compile(r'PT((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+)S)?')
    matches = pattern.match(iso_duration)
    if not matches:
        logging.warning(f"Invalid ISO duration format: {iso_duration}")
        return 0  # Return 0 if the pattern does not match

    hours = int(matches.group('hours') or 0)
    minutes = int(matches.group('minutes') or 0)
    seconds = int(matches.group('seconds') or 0)

    # Calculate total minutes, rounding up if there are any remaining seconds
    total_minutes = hours * 60 + minutes
    if seconds > 0:
        total_minutes += 1  # Round up if there are any remaining seconds

    return total_minutes

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

def get_year_date_range(year: int = None) -> tuple[datetime, datetime]:
    """
    Get the start and end dates for a given year.
    
    If no year is provided or if the provided year is the current year,
    the end date will be set to today.

    Args:
        year (int, optional): The year for which to get the date range. 
                              If None, the current year is used.

    Returns:
        tuple[datetime, datetime]: A tuple containing the start and end dates for the specified year.
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