"""
Account management agent - handles account/wallet operations.
"""
from openai import AsyncOpenAI

from services.ai_agents.base_agent import BaseAgent
from services.ai_tools import ToolRegistry, create_registry_from_tools
from services.ai_tools.account_tools import (
    get_user_accounts,
    get_default_account,
    get_account_by_id,
    update_account_balance,
    create_account,
)


class AccountAgent(BaseAgent):
    """Agent specialized for account and wallet management."""

    @property
    def name(self) -> str:
        return "account_agent"

    @property
    def description(self) -> str:
        return "Manages financial accounts and wallets: view balances, create accounts, update balances"

    @property
    def system_prompt(self) -> str:
        return """You are a specialized financial assistant for account management.

Your capabilities:
- View all user accounts and their balances
- Get details of specific accounts
- Create new accounts (savings, checking, cash, credit cards, etc.)
- Update account balances for manual corrections

Guidelines:
- Always confirm important actions like balance changes
- Present account information clearly with currency symbols
- When creating accounts, suggest appropriate names and defaults
- Be helpful in explaining account concepts if users seem confused

Respond concisely and format monetary values clearly."""

    def get_tool_registry(self) -> ToolRegistry:
        return create_registry_from_tools(
            get_user_accounts,
            get_default_account,
            get_account_by_id,
            update_account_balance,
            create_account,
        )
