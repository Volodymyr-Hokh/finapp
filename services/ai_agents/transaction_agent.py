"""
Transaction management agent - handles transaction CRUD operations.
"""
from openai import AsyncOpenAI

from services.ai_agents.base_agent import BaseAgent
from services.ai_tools import ToolRegistry, create_registry_from_tools
from services.ai_tools.transaction_tools import (
    get_transactions,
    create_transaction,
    get_transaction_by_id,
    delete_transaction,
)


class TransactionAgent(BaseAgent):
    """Agent specialized for transaction management."""

    @property
    def name(self) -> str:
        return "transaction_agent"

    @property
    def description(self) -> str:
        return "Manages financial transactions: record income/expenses, search transactions, delete entries, scan receipts/checks"

    @property
    def system_prompt(self) -> str:
        return """You are a specialized financial assistant for transaction management.

Your capabilities:
- Search and filter transactions by date, type, category, tags
- Create new income and expense transactions
- View transaction details
- Delete transactions
- Scan receipts and checks from images to extract transaction data

Guidelines:
- When recording transactions, ask for description, amount, type (income/expense), and optionally category
- Suggest appropriate categories based on the description
- Use date filters to help users find specific transactions
- Present transaction lists in a clear, readable format
- Confirm before deleting transactions
- Default to today's date if not specified for new transactions
- When a user sends a receipt/check image, analyze it and extract the transaction data (amount, description, date, type, category)
- Present the extracted data to the user for confirmation before creating the transaction
- For scanned receipts, clearly show the extracted amount, description, and suggested category

Respond concisely and format monetary values clearly."""

    def get_tool_registry(self) -> ToolRegistry:
        return create_registry_from_tools(
            get_transactions,
            create_transaction,
            get_transaction_by_id,
            delete_transaction,
        )
