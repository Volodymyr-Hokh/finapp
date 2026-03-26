"""
Budget management agent - handles budget tracking and creation.
"""
from openai import AsyncOpenAI

from services.ai_agents.base_agent import BaseAgent
from services.ai_tools import ToolRegistry, create_registry_from_tools
from services.ai_tools.budget_tools import (
    get_budgets_with_progress,
    get_budget_details,
    get_category_spending,
    create_budget,
    update_budget_limit,
)


class BudgetAgent(BaseAgent):
    """Agent specialized for budget management."""

    @property
    def name(self) -> str:
        return "budget_agent"

    @property
    def description(self) -> str:
        return "Manages monthly budgets: view budget progress, create budgets, check spending limits"

    @property
    def system_prompt(self) -> str:
        return """You are a specialized financial assistant for budget management.

Your capabilities:
- View all budgets with current spending progress
- Get detailed budget information including daily allowances
- Check spending for specific categories
- Create new monthly budgets for categories
- Update budget limits

Guidelines:
- Clearly show budget status: UNDER (green), WARNING (80%+, yellow), OVER (red)
- Calculate and show remaining budget and percentage used
- Suggest reasonable budget amounts based on past spending if available
- Warn users when they're approaching or over budget
- Explain the daily allowance concept when relevant
- Help users set realistic budgets

Respond concisely and use visual indicators (like percentages) for budget progress."""

    def get_tool_registry(self) -> ToolRegistry:
        return create_registry_from_tools(
            get_budgets_with_progress,
            get_budget_details,
            get_category_spending,
            create_budget,
            update_budget_limit,
        )
