import unittest
from datetime import datetime
import pytz
from utils import iso_duration_to_minutes, get_formatted_date_today
from unittest.mock import patch

class TestUtils(unittest.TestCase):

    def test_iso_duration_to_minutes(self):
        # Test cases for iso_duration_to_minutes
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
            with self.subTest(duration=duration):
                self.assertEqual(iso_duration_to_minutes(duration), expected)

    @patch('utils.datetime')
    # def test_get_formatted_date_today(self, mock_datetime):
    #     # Mock the datetime to return a specific date
    #     mock_date = datetime(2023, 5, 15, 12, 0, tzinfo=pytz.timezone('America/Chicago'))
    #     mock_datetime.now.return_value = mock_date

    #     # Test with default timezone
    #     self.assertEqual(get_formatted_date_today(), '2023-05-15')

    #     # Test with a different timezone
    #     self.assertEqual(get_formatted_date_today('Asia/Tokyo'), '2023-05-16')

    def test_get_formatted_date_today_real(self):
        # Test with the actual current date
        # This test might fail if run exactly at midnight
        today = datetime.now().strftime('%Y-%m-%d')
        self.assertEqual(get_formatted_date_today(), today)


if __name__ == '__main__':
    unittest.main()