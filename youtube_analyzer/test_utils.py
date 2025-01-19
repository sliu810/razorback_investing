import pytest
from datetime import datetime
import pytz
from utils import iso_duration_to_minutes, get_formatted_date_today, make_clickable

def test_iso_duration_to_minutes():
    """Test conversion of ISO duration to minutes"""
    test_cases = [
        ("PT1H30M", 90),
        ("PT1H", 60),
        ("PT30M", 30),
        ("PT1M30S", 2),  # Rounds up to 2 minutes
        ("PT59S", 1),    # Rounds up to 1 minute
        ("PT0S", 0),
        ("P1DT2H30M", 1590),  # 1 day, 2 hours, 30 minutes
        ("Invalid", 0),  # Should return 0 for invalid input
    ]

    for duration, expected in test_cases:
        result = iso_duration_to_minutes(duration)
        assert result == expected, f"Failed for duration {duration}: expected {expected}, got {result}"

def test_get_formatted_date_today():
    """Test getting today's formatted date"""
    today = datetime.now().strftime('%Y-%m-%d')
    result = get_formatted_date_today()
    print(f"result: {result}")
    assert result == today

def test_make_clickable():
    """Test making clickable links"""
    text = "Blastoff! SpaceX launches Starship on Flight 7 — catches booster, loses ship"
    link = "https://www.youtube.com/watch?v=qzWMEegqbLs"
    result = make_clickable(text, link)
    assert result == f'<a href="{link}" target="_blank">{text}</a>'