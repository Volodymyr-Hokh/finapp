"""Budget progress calculation utilities."""
from datetime import date
from decimal import Decimal
import calendar

from db.models import Budget
from schemas.budgets import BudgetProgress, BudgetStatus, BudgetReadWithProgress
from schemas.shared import CategorySummary

# Budget threshold constants
BUDGET_WARNING_THRESHOLD = 80  # Percentage at which to show warning status
BUDGET_OVER_THRESHOLD = 100    # Percentage at which budget is considered exceeded


def calculate_budget_progress(
    budget: Budget,
    spent_amount: Decimal,
    transaction_count: int
) -> BudgetProgress:
    """
    Calculate budget progress metrics.

    Args:
        budget: The Budget model instance
        spent_amount: Total spent (absolute value)
        transaction_count: Number of transactions

    Returns:
        BudgetProgress with all calculated fields
    """
    limit = budget.limit_amount
    remaining = limit - spent_amount

    # Calculate percentage (handle zero budget edge case)
    if limit > 0:
        percentage = float((spent_amount / limit) * 100)
    else:
        percentage = 100.0 if spent_amount > 0 else 0.0

    # Determine status using threshold constants
    if percentage >= BUDGET_OVER_THRESHOLD:
        status = BudgetStatus.OVER
    elif percentage >= BUDGET_WARNING_THRESHOLD:
        status = BudgetStatus.WARNING
    else:
        status = BudgetStatus.UNDER

    # Calculate daily allowance only for current month
    today = date.today()
    daily_allowance = None
    days_remaining = None

    if budget.year == today.year and budget.month == today.month:
        # Current month budget
        last_day_of_month = calendar.monthrange(budget.year, budget.month)[1]
        days_remaining = last_day_of_month - today.day + 1  # Include today

        if days_remaining > 0 and remaining > 0:
            daily_allowance = remaining / Decimal(days_remaining)
        elif days_remaining > 0:
            daily_allowance = Decimal("0")
    elif budget.year < today.year or (budget.year == today.year and budget.month < today.month):
        # Past month - no daily allowance, period is complete
        days_remaining = 0
        daily_allowance = Decimal("0")
    # Future month - daily_allowance stays None

    return BudgetProgress(
        spent_amount=spent_amount,
        remaining_amount=remaining,
        percentage_used=round(percentage, 2),
        status=status,
        daily_allowance=daily_allowance,
        days_remaining=days_remaining,
        transaction_count=transaction_count,
    )


def budget_to_response_with_progress(
    budget: Budget,
    spent_amount: Decimal,
    transaction_count: int
) -> BudgetReadWithProgress:
    """Convert a Budget model to BudgetReadWithProgress response."""
    progress = calculate_budget_progress(budget, spent_amount, transaction_count)

    return BudgetReadWithProgress(
        id=budget.id,
        limit_amount=budget.limit_amount,
        category=CategorySummary(
            id=budget.category.id,
            name=budget.category.name,
            icon=budget.category.icon
        ),
        month=budget.month,
        year=budget.year,
        created_at=budget.created_at,
        updated_at=budget.updated_at,
        progress=progress,
    )
