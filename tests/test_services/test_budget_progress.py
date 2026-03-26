"""Tests for budget progress calculation service."""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock
from freezegun import freeze_time

from services.budget_progress import calculate_budget_progress, budget_to_response_with_progress
from schemas.budgets import BudgetStatus


class TestCalculateBudgetProgress:
    """Tests for calculate_budget_progress function."""

    def create_mock_budget(self, limit: str, month: int, year: int):
        """Create a mock budget for testing."""
        budget = Mock()
        budget.limit_amount = Decimal(limit)
        budget.month = month
        budget.year = year
        budget.category = Mock()
        budget.category.id = 1
        budget.category.name = "Food"
        budget.category.icon = "🍔"
        return budget

    @freeze_time("2026-01-15")
    def test_under_budget_status(self):
        """< 80% usage returns UNDER status."""
        budget = self.create_mock_budget("500.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("200.00"), 5)

        assert progress.status == BudgetStatus.UNDER
        assert progress.percentage_used == 40.0
        assert progress.spent_amount == Decimal("200.00")
        assert progress.remaining_amount == Decimal("300.00")

    @freeze_time("2026-01-15")
    def test_warning_budget_status(self):
        """80-100% usage returns WARNING status."""
        budget = self.create_mock_budget("500.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("450.00"), 10)

        assert progress.status == BudgetStatus.WARNING
        assert progress.percentage_used == 90.0

    @freeze_time("2026-01-15")
    def test_over_budget_status(self):
        """> 100% usage returns OVER status."""
        budget = self.create_mock_budget("500.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("600.00"), 20)

        assert progress.status == BudgetStatus.OVER
        assert progress.percentage_used == 120.0
        assert progress.remaining_amount == Decimal("-100.00")

    @freeze_time("2026-01-15")
    def test_exactly_80_percent_is_warning(self):
        """Exactly 80% usage returns WARNING status."""
        budget = self.create_mock_budget("500.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("400.00"), 8)

        assert progress.status == BudgetStatus.WARNING
        assert progress.percentage_used == 80.0

    @freeze_time("2026-01-15")
    def test_exactly_100_percent_is_over(self):
        """Exactly 100% usage returns OVER status."""
        budget = self.create_mock_budget("500.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("500.00"), 10)

        assert progress.status == BudgetStatus.OVER
        assert progress.percentage_used == 100.0

    @freeze_time("2026-01-15")
    def test_daily_allowance_current_month(self):
        """Daily allowance calculated for current month."""
        budget = self.create_mock_budget("500.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("200.00"), 5)

        # Jan 15, 2026 - 17 days remaining (15-31 inclusive)
        assert progress.days_remaining == 17
        # 300 remaining / 17 days
        expected_daily = Decimal("300.00") / Decimal("17")
        assert progress.daily_allowance == expected_daily

    @freeze_time("2026-01-15")
    def test_daily_allowance_past_month(self):
        """Daily allowance is 0 for past months."""
        budget = self.create_mock_budget("500.00", 12, 2025)
        progress = calculate_budget_progress(budget, Decimal("400.00"), 15)

        assert progress.days_remaining == 0
        assert progress.daily_allowance == Decimal("0")

    @freeze_time("2026-01-15")
    def test_daily_allowance_future_month(self):
        """Daily allowance is None for future months."""
        budget = self.create_mock_budget("500.00", 2, 2026)
        progress = calculate_budget_progress(budget, Decimal("0"), 0)

        assert progress.days_remaining is None
        assert progress.daily_allowance is None

    @freeze_time("2026-01-15")
    def test_daily_allowance_future_year(self):
        """Daily allowance is None for future year budgets."""
        budget = self.create_mock_budget("500.00", 1, 2027)
        progress = calculate_budget_progress(budget, Decimal("0"), 0)

        assert progress.days_remaining is None
        assert progress.daily_allowance is None

    def test_no_transactions(self):
        """Empty budget returns zeros."""
        budget = self.create_mock_budget("500.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("0"), 0)

        assert progress.spent_amount == Decimal("0")
        assert progress.remaining_amount == Decimal("500.00")
        assert progress.percentage_used == 0.0
        assert progress.status == BudgetStatus.UNDER
        assert progress.transaction_count == 0

    def test_zero_limit_with_spending(self):
        """Zero limit with spending shows 100%."""
        budget = self.create_mock_budget("0.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("50.00"), 3)

        assert progress.percentage_used == 100.0
        assert progress.status == BudgetStatus.OVER

    def test_zero_limit_no_spending(self):
        """Zero limit with no spending shows 0%."""
        budget = self.create_mock_budget("0.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("0"), 0)

        assert progress.percentage_used == 0.0

    @freeze_time("2026-01-31")
    def test_last_day_of_month(self):
        """Daily allowance on last day of month equals remaining."""
        budget = self.create_mock_budget("500.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("400.00"), 10)

        assert progress.days_remaining == 1
        assert progress.daily_allowance == Decimal("100.00")

    @freeze_time("2026-01-15")
    def test_daily_allowance_when_over_budget(self):
        """Daily allowance is 0 when over budget."""
        budget = self.create_mock_budget("500.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("600.00"), 20)

        assert progress.days_remaining == 17
        assert progress.daily_allowance == Decimal("0")

    @freeze_time("2026-02-15")
    def test_february_days(self):
        """Correctly calculates days for February."""
        budget = self.create_mock_budget("500.00", 2, 2026)
        progress = calculate_budget_progress(budget, Decimal("200.00"), 5)

        # Feb 2026 has 28 days, Feb 15 means 14 days remaining (15-28 inclusive)
        assert progress.days_remaining == 14

    def test_transaction_count_preserved(self):
        """Transaction count is correctly preserved in progress."""
        budget = self.create_mock_budget("500.00", 1, 2026)
        progress = calculate_budget_progress(budget, Decimal("100.00"), 42)

        assert progress.transaction_count == 42


class TestBudgetToResponseWithProgress:
    """Tests for budget_to_response_with_progress function."""

    @freeze_time("2026-01-15")
    def test_converts_budget_to_response(self):
        """Converts Budget model to BudgetReadWithProgress response."""
        from datetime import datetime

        budget = Mock()
        budget.id = 1
        budget.limit_amount = Decimal("500.00")
        budget.month = 1
        budget.year = 2026
        budget.created_at = datetime(2026, 1, 1, 10, 0, 0)
        budget.updated_at = datetime(2026, 1, 15, 10, 0, 0)
        budget.category = Mock()
        budget.category.id = 1
        budget.category.name = "Food"
        budget.category.icon = "🍔"

        response = budget_to_response_with_progress(budget, Decimal("200.00"), 5)

        assert response.id == 1
        assert response.limit_amount == Decimal("500.00")
        assert response.category.name == "Food"
        assert response.category.icon == "🍔"
        assert response.month == 1
        assert response.year == 2026
        assert response.progress.spent_amount == Decimal("200.00")
        assert response.progress.remaining_amount == Decimal("300.00")
        assert response.progress.status == BudgetStatus.UNDER
