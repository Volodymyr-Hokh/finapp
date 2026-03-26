"""
Budget management tools for AI agents.
"""
from typing import Annotated, Optional
from decimal import Decimal
from datetime import date

from services.ai_tools import ai_tool, ToolParam, AgentContext
from services.budget_progress import calculate_budget_progress


@ai_tool
async def get_budgets_with_progress(ctx: AgentContext) -> dict:
    """Get all user budgets with their current spending progress, percentage used, and status."""
    budgets_data = await ctx.repo.budgets.get_user_budgets_with_progress(ctx.user_id)

    budgets = []
    for budget, spent, count in budgets_data:
        progress = calculate_budget_progress(budget, spent, count)

        budgets.append({
            "id": budget.id,
            "category": budget.category.name if budget.category else None,
            "category_id": budget.category.id if budget.category else None,
            "limit_amount": str(budget.limit_amount),
            "spent_amount": str(progress.spent_amount),
            "remaining_amount": str(progress.remaining_amount),
            "percentage_used": progress.percentage_used,
            "status": progress.status.value.upper(),
            "transaction_count": progress.transaction_count,
            "month": budget.month,
            "year": budget.year
        })

    return {
        "budgets": budgets,
        "count": len(budgets)
    }


@ai_tool
async def get_budget_details(
    ctx: AgentContext,
    budget_id: Annotated[int, ToolParam("The budget ID to retrieve")]
) -> dict:
    """Get detailed information about a specific budget including spending progress."""
    result = await ctx.repo.budgets.get_budget_with_progress(budget_id, ctx.user_id)
    if not result:
        return {"error": f"Budget with ID {budget_id} not found"}

    budget, spent, count = result
    progress = calculate_budget_progress(budget, spent, count)

    return {
        "id": budget.id,
        "category": budget.category.name if budget.category else None,
        "category_id": budget.category.id if budget.category else None,
        "limit_amount": str(budget.limit_amount),
        "spent_amount": str(progress.spent_amount),
        "remaining_amount": str(progress.remaining_amount),
        "percentage_used": progress.percentage_used,
        "status": progress.status.value.upper(),
        "transaction_count": progress.transaction_count,
        "month": budget.month,
        "year": budget.year,
        "daily_allowance": str(progress.daily_allowance) if progress.daily_allowance is not None else None,
        "days_remaining": progress.days_remaining
    }


@ai_tool
async def get_category_spending(
    ctx: AgentContext,
    category_id: Annotated[int, ToolParam("The category ID to check spending for")],
    month: Annotated[int, ToolParam("Month (1-12)")],
    year: Annotated[int, ToolParam("Year (e.g., 2024)")]
) -> dict:
    """Get the total spending for a category in a specific month/year."""
    spent, count = await ctx.repo.budgets.get_spent_amount(
        ctx.user_id, category_id, month, year
    )

    # Get category name
    category = await ctx.repo.categories.get(id=category_id)
    category_name = category.name if category else f"Category {category_id}"

    return {
        "category_id": category_id,
        "category_name": category_name,
        "month": month,
        "year": year,
        "total_spent": str(spent),
        "transaction_count": count
    }


@ai_tool
async def create_budget(
    ctx: AgentContext,
    category_id: Annotated[int, ToolParam("The category ID to create a budget for")],
    limit_amount: Annotated[str, ToolParam("Budget limit as decimal string, e.g., '500.00'")],
    month: Annotated[int, ToolParam("Month (1-12)")],
    year: Annotated[int, ToolParam("Year (e.g., 2024)")]
) -> dict:
    """Create a new monthly budget for a category."""
    # Validate category exists
    category = await ctx.repo.categories.get(id=category_id)
    if not category:
        return {"error": f"Category with ID {category_id} not found"}

    # Check if budget already exists
    existing = await ctx.repo.budgets.get_current_budget(ctx.user_id, category_id)
    if existing and existing.month == month and existing.year == year:
        return {"error": f"Budget for {category.name} already exists for {month}/{year}"}

    budget = await ctx.repo.budgets.create(
        user_id=ctx.user_id,
        category_id=category_id,
        limit_amount=Decimal(limit_amount),
        month=month,
        year=year
    )

    return {
        "success": True,
        "budget": {
            "id": budget.id,
            "category": category.name,
            "limit_amount": str(budget.limit_amount),
            "month": budget.month,
            "year": budget.year
        },
        "message": f"Budget of {limit_amount} created for {category.name} ({month}/{year})"
    }


@ai_tool
async def update_budget_limit(
    ctx: AgentContext,
    budget_id: Annotated[int, ToolParam("The budget ID to update")],
    new_limit: Annotated[str, ToolParam("New budget limit as decimal string, e.g., '600.00'")]
) -> dict:
    """Update the limit amount for an existing budget."""
    budget = await ctx.repo.budgets.get_by_id_and_user(budget_id, ctx.user_id)
    if not budget:
        return {"error": f"Budget with ID {budget_id} not found"}

    old_limit = budget.limit_amount
    await budget.update(limit_amount=Decimal(new_limit))

    return {
        "success": True,
        "budget_id": budget_id,
        "old_limit": str(old_limit),
        "new_limit": new_limit,
        "message": f"Budget limit updated from {old_limit} to {new_limit}"
    }
