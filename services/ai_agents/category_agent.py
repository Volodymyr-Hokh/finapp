"""
Category and tag management agent.
"""
from openai import AsyncOpenAI

from services.ai_agents.base_agent import BaseAgent
from services.ai_tools import ToolRegistry, create_registry_from_tools
from services.ai_tools.category_tools import (
    get_categories,
    create_category,
    delete_category,
    get_tags,
    create_tags,
    delete_tag,
)


class CategoryAgent(BaseAgent):
    """Agent specialized for category and tag management."""

    @property
    def name(self) -> str:
        return "category_agent"

    @property
    def description(self) -> str:
        return "Manages categories and tags: view, create, delete categories and tags for organizing transactions"

    @property
    def system_prompt(self) -> str:
        return """You are a specialized assistant for organizing financial transactions.

Your capabilities:
- View all available categories (system and custom)
- Create new custom categories with optional emoji icons
- Delete custom categories (system categories cannot be deleted)
- View all user tags
- Create new tags
- Delete tags

Guidelines:
- Suggest appropriate emoji icons for new categories (e.g., 🍔 for Food, 🚗 for Transport)
- Explain the difference between system categories (built-in) and custom categories
- Warn users before deleting categories or tags that may be in use
- Suggest useful tags for transaction organization (e.g., "work", "personal", "recurring")
- Help users create a logical category structure

Keep responses concise and helpful."""

    def get_tool_registry(self) -> ToolRegistry:
        return create_registry_from_tools(
            get_categories,
            create_category,
            delete_category,
            get_tags,
            create_tags,
            delete_tag,
        )
