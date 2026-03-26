"""
Tests for services/utils/date_utils.py.
"""
import pytest
from datetime import date
from freezegun import freeze_time

from services.utils.date_utils import parse_date_range


@pytest.mark.unit
class TestParseDateRange:
    """Tests for parse_date_range utility."""

    def test_explicit_dates(self):
        """Test parsing explicit from_date and to_date."""
        start, end = parse_date_range("2024-01-15", "2024-02-28")

        assert start == date(2024, 1, 15)
        assert end == date(2024, 2, 28)

    @freeze_time("2024-06-15")
    def test_default_from_date_month_start(self):
        """Test default from_date uses first day of current month."""
        start, end = parse_date_range(to_date="2024-06-30")

        assert start == date(2024, 6, 1)
        assert end == date(2024, 6, 30)

    @freeze_time("2024-06-15")
    def test_default_from_date_year_start(self):
        """Test default_start='year_start' uses January 1st."""
        start, end = parse_date_range(
            to_date="2024-06-30",
            default_start="year_start"
        )

        assert start == date(2024, 1, 1)

    @freeze_time("2024-06-15")
    def test_default_from_date_today(self):
        """Test default_start='today' uses today."""
        start, end = parse_date_range(
            to_date="2024-06-30",
            default_start="today"
        )

        assert start == date(2024, 6, 15)

    @freeze_time("2024-06-15")
    def test_default_to_date_is_today(self):
        """Test that to_date defaults to today when not provided."""
        start, end = parse_date_range(from_date="2024-01-01")

        assert end == date(2024, 6, 15)

    def test_invalid_from_date_raises(self):
        """Test that invalid from_date raises ValueError."""
        with pytest.raises(ValueError):
            parse_date_range(from_date="not-a-date")

    def test_invalid_to_date_raises(self):
        """Test that invalid to_date raises ValueError."""
        with pytest.raises(ValueError):
            parse_date_range(to_date="not-a-date")

    @freeze_time("2024-06-15")
    def test_none_dates_use_defaults(self):
        """Test that None dates use sensible defaults."""
        start, end = parse_date_range()

        assert start == date(2024, 6, 1)
        assert end == date(2024, 6, 15)
