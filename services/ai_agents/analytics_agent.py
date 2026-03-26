"""
Analytics agent - handles spending analysis and reporting.
"""
from openai import AsyncOpenAI

from services.ai_agents.base_agent import BaseAgent
from services.ai_tools import ToolRegistry, create_registry_from_tools
from services.ai_tools.analytics_tools import (
    get_spending_summary,
    get_income_expense_comparison,
    get_category_breakdown,
    get_monthly_trend,
)


class AnalyticsAgent(BaseAgent):
    """Agent specialized for financial analytics and reporting."""

    @property
    def name(self) -> str:
        return "analytics_agent"

    @property
    def description(self) -> str:
        return "Provides financial analytics: spending summaries, category breakdowns, trends, income vs expenses"

    @property
    def system_prompt(self) -> str:
        return """You are a specialized financial analyst assistant.

Your capabilities:
- Generate spending summaries for any time period
- Compare income vs expenses with savings rate
- Break down spending by category with percentages
- Analyze monthly trends over time

Guidelines:
- Present data clearly with percentages and comparisons
- Highlight significant findings (biggest expense categories, unusual trends)
- Provide insights, not just numbers
- Use relative terms (e.g., "up 15% from last month")
- Default to current month if no date range specified
- Suggest areas where the user could save money
- Be encouraging about positive trends (good savings rate, reduced spending)

Format numbers clearly and use comparisons to make data meaningful."""

    def get_tool_registry(self) -> ToolRegistry:
        return create_registry_from_tools(
            get_spending_summary,
            get_income_expense_comparison,
            get_category_breakdown,
            get_monthly_trend,
        )
