"""
Account management tools for AI agents.
"""
from typing import Annotated, Optional
from decimal import Decimal

from services.ai_tools import ai_tool, ToolParam, AgentContext


@ai_tool
async def get_user_accounts(ctx: AgentContext) -> dict:
    """Get all financial accounts/wallets for the user with their balances and currencies."""
    accounts = await ctx.repo.accounts.get_user_accounts(ctx.user_id)
    return {
        "accounts": [
            {
                "id": a.id,
                "name": a.name,
                "balance": str(a.balance),
                "currency": a.currency,
                "is_default": a.is_default
            }
            for a in accounts
        ],
        "count": len(accounts)
    }


@ai_tool
async def get_default_account(ctx: AgentContext) -> dict:
    """Get the user's default account used for new transactions."""
    account = await ctx.repo.accounts.get_default_for_user(ctx.user_id)
    if not account:
        return {"error": "No default account found. Please create an account first."}
    return {
        "id": account.id,
        "name": account.name,
        "balance": str(account.balance),
        "currency": account.currency
    }


@ai_tool
async def get_account_by_id(
    ctx: AgentContext,
    account_id: Annotated[int, ToolParam("The account ID to retrieve")]
) -> dict:
    """Get details of a specific account by its ID."""
    account = await ctx.repo.accounts.get_by_id_and_user(account_id, ctx.user_id)
    if not account:
        return {"error": f"Account with ID {account_id} not found"}
    return {
        "id": account.id,
        "name": account.name,
        "balance": str(account.balance),
        "currency": account.currency,
        "is_default": account.is_default
    }


@ai_tool
async def update_account_balance(
    ctx: AgentContext,
    account_id: Annotated[int, ToolParam("The account ID to update")],
    amount_change: Annotated[str, ToolParam("Amount to add (positive) or subtract (negative), e.g., '100.00' or '-50.00'")]
) -> dict:
    """Adjust an account balance by a positive or negative amount. Use this for manual corrections only."""
    account = await ctx.repo.accounts.get_by_id_and_user(account_id, ctx.user_id)
    if not account:
        return {"error": f"Account with ID {account_id} not found"}

    old_balance = account.balance
    await ctx.repo.accounts.update_balance(account_id, Decimal(amount_change))

    updated = await ctx.repo.accounts.get_by_id_and_user(account_id, ctx.user_id)
    return {
        "success": True,
        "account_id": account_id,
        "old_balance": str(old_balance),
        "new_balance": str(updated.balance),
        "change": amount_change,
        "message": f"Balance updated from {old_balance} to {updated.balance}"
    }


@ai_tool
async def create_account(
    ctx: AgentContext,
    name: Annotated[str, ToolParam("Account name, e.g., 'Savings', 'Cash', 'Credit Card'")],
    currency: Annotated[str, ToolParam("3-letter currency code, e.g., 'UAH', 'USD', 'EUR'")] = "UAH",
    initial_balance: Annotated[str, ToolParam("Starting balance as decimal string, e.g., '1000.00'")] = "0.00",
    is_default: Annotated[bool, ToolParam("Whether this should be the default account for new transactions")] = False
) -> dict:
    """Create a new financial account/wallet for the user."""
    account = await ctx.repo.accounts.create(
        user_id=ctx.user_id,
        name=name,
        currency=currency.upper(),
        balance=Decimal(initial_balance),
        is_default=is_default
    )
    return {
        "success": True,
        "account": {
            "id": account.id,
            "name": account.name,
            "balance": str(account.balance),
            "currency": account.currency,
            "is_default": account.is_default
        },
        "message": f"Account '{name}' created successfully"
    }
