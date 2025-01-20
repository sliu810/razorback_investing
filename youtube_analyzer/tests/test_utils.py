import pytest
from datetime import datetime, timedelta
import pytz
from ..utils import iso_duration_to_minutes, get_formatted_date_today, make_clickable, DateFilter

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

@pytest.fixture
def current_time():
    """Fixture to provide consistent time reference in Chicago timezone"""
    chicago_tz = pytz.timezone('America/Chicago')
    now = datetime.now(pytz.UTC).astimezone(chicago_tz)
    return {
        'now': now,
        'start_of_day': now.replace(hour=0, minute=0, second=0, microsecond=0)
    }

@pytest.fixture
def date_filter():
    """Fixture to provide DateFilter instance"""
    return DateFilter()  # Uses default timezone (America/Chicago)

def test_date_filter_today():
    """Test today's filter returns correct time range in local timezone"""
    filter = DateFilter()
    result = filter.today()
    chicago_tz = pytz.timezone('America/Chicago')
    
    # Convert results back to Chicago time for comparison
    start_time = datetime.fromisoformat(result['publishedAfter'].replace('Z', '+00:00')).astimezone(chicago_tz)
    end_time = datetime.fromisoformat(result['publishedBefore'].replace('Z', '+00:00')).astimezone(chicago_tz)
    
    # Start should be start of day in Chicago time
    assert start_time.hour == 0
    assert start_time.minute == 0
    assert start_time.second == 0
    assert start_time.microsecond == 0
    
    # End should be current time in Chicago
    now = datetime.now(chicago_tz)
    assert end_time.date() == now.date()

def test_date_filter_from_days_ago():
    """Test days ago filter returns correct time range"""
    filter = DateFilter()
    now = datetime.now(pytz.UTC)
    
    # Test 1 day ago
    result = filter.from_days_ago(1)
    result_time = datetime.fromisoformat(result['publishedAfter'].rstrip('Z')).replace(tzinfo=pytz.UTC)
    
    # Should be ~24 hours ago
    time_diff = now - result_time
    assert timedelta(hours=23) < time_diff < timedelta(hours=25)
    
    # Should use Z suffix
    assert result['publishedAfter'].endswith('Z')

def test_date_filter_from_dates():
    """Test custom date range filter with timezone handling"""
    filter = DateFilter()
    chicago_tz = pytz.timezone('America/Chicago')
    
    # Test with UTC dates (should stay in UTC)
    utc_after = datetime(2024, 1, 1, tzinfo=pytz.UTC)
    utc_before = datetime(2024, 3, 1, tzinfo=pytz.UTC)
    
    result = filter.from_dates(after=utc_after, before=utc_before)
    assert result['publishedAfter'] == utc_after.isoformat().replace('+00:00', 'Z')
    assert result['publishedBefore'] == utc_before.isoformat().replace('+00:00', 'Z')
    
    # Test with naive dates (should be interpreted as Chicago time)
    naive_date = datetime(2024, 1, 1, 12, 0)  # noon Chicago time
    result = filter.from_dates(after=naive_date)
    
    # Convert expected Chicago time to UTC
    expected_utc = chicago_tz.localize(naive_date).astimezone(pytz.UTC)
    assert result['publishedAfter'] == expected_utc.isoformat().replace('+00:00', 'Z')

def test_date_filter_timezone_handling():
    """Test DateFilter timezone conversions"""
    chicago_filter = DateFilter('America/Chicago')
    la_filter = DateFilter('America/Los_Angeles')
    
    # Same naive datetime should be interpreted in respective timezones
    naive_date = datetime(2024, 1, 1, 12, 0)  # noon
    chicago_result = chicago_filter.from_dates(after=naive_date)
    la_result = la_filter.from_dates(after=naive_date)
    
    # Results should differ by timezone offset
    assert chicago_result['publishedAfter'] != la_result['publishedAfter']
    
    # UTC dates should remain unchanged regardless of filter timezone
    utc_date = datetime(2024, 1, 1, 12, 0, tzinfo=pytz.UTC)
    chicago_result = chicago_filter.from_dates(after=utc_date)
    la_result = la_filter.from_dates(after=utc_date)
    
    assert chicago_result['publishedAfter'] == la_result['publishedAfter']
    assert chicago_result['publishedAfter'] == utc_date.isoformat().replace('+00:00', 'Z')