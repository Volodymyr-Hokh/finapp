"""Date handling utilities for services."""
from datetime import date
from typing import Optional, Tuple


def parse_date_range(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    default_start: str = "month_start"
) -> Tuple[date, date]:
    """
    Parse optional date strings into date objects with sensible defaults.

    Args:
        from_date: ISO format date string (YYYY-MM-DD) or None
        to_date: ISO format date string (YYYY-MM-DD) or None
        default_start: What to use when from_date is None:
            - "month_start": First day of current month (default)
            - "year_start": First day of current year
            - "today": Today's date

    Returns:
        Tuple of (start_date, end_date)
    """
    today = date.today()

    if from_date:
        start = date.fromisoformat(from_date)
    elif default_start == "month_start":
        start = today.replace(day=1)
    elif default_start == "year_start":
        start = today.replace(month=1, day=1)
    else:
        start = today

    end = date.fromisoformat(to_date) if to_date else today

    return start, end
