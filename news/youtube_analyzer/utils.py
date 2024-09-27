import pytz
from datetime import datetime
import re
import logging

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