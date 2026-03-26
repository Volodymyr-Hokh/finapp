"""
Analytics and reporting tools for AI agents.
"""
from typing import Annotated, Optional
from decimal import Decimal
from datetime import date, timedelta
from collections import defaultdict

from services.ai_tools import ai_tool, ToolParam, AgentContext
from services.utils.date_utils import parse_date_range
from schemas.enums import TransactionType


@ai_tool
async def get_spending_summary(
    ctx: AgentContext,
    from_date: Annotated[Optional[str], ToolParam("Start date in YYYY-MM-DD format (defaults to start of current month)")] = None,
    to_date: Annotated[Optional[str], ToolParam("End date in YYYY-MM-DD format (defaults to today)")] = None
) -> dict:
    """Get a summary of spending for a time period including total income, expenses, and net change."""
    from_date_obj, to_date_obj = parse_date_range(from_date, to_date)

    transactions = await ctx.repo.transactions.get_user_transactions(
        user_id=ctx.user_id,
        from_date=from_date_obj,
        to_date=to_date_obj
    )

    total_income = Decimal("0.00")
    total_expenses = Decimal("0.00")

    for t in transactions:
        if t.type == TransactionType.INCOME:
            total_income += abs(t.amount)
        else:
            total_expenses += abs(t.amount)

    net_change = total_income - total_expenses

    return {
        "period": {
            "from": str(from_date_obj),
            "to": str(to_date_obj)
        },
        "total_income": str(total_income),
        "total_expenses": str(total_expenses),
        "net_change": str(net_change),
        "transaction_count": len(transactions),
        "summary": f"Income: {total_income}, Expenses: {total_expenses}, Net: {'+' if net_change >= 0 else ''}{net_change}"
    }


@ai_tool
async def get_income_expense_comparison(
    ctx: AgentContext,
    from_date: Annotated[Optional[str], ToolParam("Start date in YYYY-MM-DD format")] = None,
    to_date: Annotated[Optional[str], ToolParam("End date in YYYY-MM-DD format")] = None
) -> dict:
    """Compare total income vs expenses for a time period with percentage breakdown."""
    from_date_obj, to_date_obj = parse_date_range(from_date, to_date)

    transactions = await ctx.repo.transactions.get_user_transactions(
        user_id=ctx.user_id,
        from_date=from_date_obj,
        to_date=to_date_obj
    )

    total_income = Decimal("0.00")
    total_expenses = Decimal("0.00")
    income_count = 0
    expense_count = 0

    for t in transactions:
        if t.type == TransactionType.INCOME:
            total_income += abs(t.amount)
            income_count += 1
        else:
            total_expenses += abs(t.amount)
            expense_count += 1

    total = total_income + total_expenses
    income_percentage = float(total_income / total * 100) if total > 0 else 0
    expense_percentage = float(total_expenses / total * 100) if total > 0 else 0
    savings_rate = float((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0

    return {
        "period": {
            "from": str(from_date_obj),
            "to": str(to_date_obj)
        },
        "income": {
            "total": str(total_income),
            "count": income_count,
            "percentage": round(income_percentage, 1)
        },
        "expenses": {
            "total": str(total_expenses),
            "count": expense_count,
            "percentage": round(expense_percentage, 1)
        },
        "savings_rate": round(savings_rate, 1),
        "net_balance": str(total_income - total_expenses)
    }


@ai_tool
async def get_category_breakdown(
    ctx: AgentContext,
    from_date: Annotated[Optional[str], ToolParam("Start date in YYYY-MM-DD format")] = None,
    to_date: Annotated[Optional[str], ToolParam("End date in YYYY-MM-DD format")] = None,
    type: Annotated[str, ToolParam("Transaction type to analyze", enum=["income", "expense"])] = "expense"
) -> dict:
    """Get spending breakdown by category for a time period."""
    from_date_obj, to_date_obj = parse_date_range(from_date, to_date)

    transactions = await ctx.repo.transactions.get_user_transactions(
        user_id=ctx.user_id,
        from_date=from_date_obj,
        to_date=to_date_obj,
        type=TransactionType(type)
    )

    # Group by category
    category_totals: dict[str, Decimal] = defaultdict(Decimal)
    category_counts: dict[str, int] = defaultdict(int)

    for t in transactions:
        category_name = t.category.name if t.category else "Uncategorized"
        category_totals[category_name] += abs(t.amount)
        category_counts[category_name] += 1

    total = sum(category_totals.values())

    # Sort by amount descending
    sorted_categories = sorted(
        category_totals.items(),
        key=lambda x: x[1],
        reverse=True
    )

    categories = []
    for cat_name, amount in sorted_categories:
        percentage = float(amount / total * 100) if total > 0 else 0
        categories.append({
            "category": cat_name,
            "amount": f"{amount:.2f}",
            "percentage": round(percentage, 1),
            "transaction_count": category_counts[cat_name]
        })

    return {
        "period": {
            "from": str(from_date_obj),
            "to": str(to_date_obj)
        },
        "type": type,
        "total": f"{total:.2f}",
        "categories": categories
    }


@ai_tool
async def get_monthly_trend(
    ctx: AgentContext,
    months: Annotated[int, ToolParam("Number of months to analyze (including current month)")] = 6,
    type: Annotated[str, ToolParam("What to analyze", enum=["income", "expense", "both"])] = "both"
) -> dict:
    """Get monthly spending/income trends over the past N months."""
    today = date.today()

    # Calculate date range
    start_date = (today.replace(day=1) - timedelta(days=(months - 1) * 30)).replace(day=1)
    end_date = today

    transactions = await ctx.repo.transactions.get_user_transactions(
        user_id=ctx.user_id,
        from_date=start_date,
        to_date=end_date
    )

    # Group by month
    monthly_data: dict[str, dict] = {}

    for t in transactions:
        month_key = t.transaction_date.strftime("%Y-%m")
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                "income": Decimal("0.00"),
                "expense": Decimal("0.00"),
                "income_count": 0,
                "expense_count": 0
            }

        if t.type == TransactionType.INCOME:
            monthly_data[month_key]["income"] += abs(t.amount)
            monthly_data[month_key]["income_count"] += 1
        else:
            monthly_data[month_key]["expense"] += abs(t.amount)
            monthly_data[month_key]["expense_count"] += 1

    # Sort by month
    sorted_months = sorted(monthly_data.keys())

    trend = []
    for month_key in sorted_months:
        data = monthly_data[month_key]
        entry = {
            "month": month_key,
            "net": str(data["income"] - data["expense"])
        }

        if type in ["income", "both"]:
            entry["income"] = str(data["income"])
            entry["income_count"] = data["income_count"]

        if type in ["expense", "both"]:
            entry["expense"] = str(data["expense"])
            entry["expense_count"] = data["expense_count"]

        trend.append(entry)

    # Calculate averages
    if trend:
        avg_income = sum(Decimal(t.get("income", "0")) for t in trend) / len(trend)
        avg_expense = sum(Decimal(t.get("expense", "0")) for t in trend) / len(trend)
    else:
        avg_income = Decimal("0")
        avg_expense = Decimal("0")

    return {
        "period": {
            "from": str(start_date),
            "to": str(end_date),
            "months": months
        },
        "trend": trend,
        "averages": {
            "monthly_income": str(avg_income.quantize(Decimal("0.01"))),
            "monthly_expense": str(avg_expense.quantize(Decimal("0.01"))),
            "monthly_net": str((avg_income - avg_expense).quantize(Decimal("0.01")))
        }
    }
