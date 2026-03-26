"""
Transaction management tools for AI agents.
"""
from typing import Annotated, Optional
from decimal import Decimal
from datetime import date

from services.ai_tools import ai_tool, ToolParam, AgentContext
from schemas.enums import TransactionType


@ai_tool
async def get_transactions(
    ctx: AgentContext,
    from_date: Annotated[Optional[str], ToolParam("Start date in YYYY-MM-DD format")] = None,
    to_date: Annotated[Optional[str], ToolParam("End date in YYYY-MM-DD format")] = None,
    type: Annotated[Optional[str], ToolParam("Transaction type filter", enum=["income", "expense"])] = None,
    category_id: Annotated[Optional[int], ToolParam("Filter by category ID")] = None,
    account_id: Annotated[Optional[int], ToolParam("Filter by account ID")] = None,
    tag_name: Annotated[Optional[str], ToolParam("Filter by tag name")] = None,
    search: Annotated[Optional[str], ToolParam("Search in transaction descriptions")] = None,
    limit: Annotated[int, ToolParam("Maximum number of transactions to return")] = 20
) -> dict:
    """Search and filter user transactions. Can filter by date range, type, category, tags, and description."""
    transactions = await ctx.repo.transactions.get_user_transactions(
        user_id=ctx.user_id,
        from_date=date.fromisoformat(from_date) if from_date else None,
        to_date=date.fromisoformat(to_date) if to_date else None,
        type=TransactionType(type) if type else None,
        category_id=category_id,
        account_id=account_id,
        tag_name=tag_name,
        search=search
    )

    result_transactions = transactions[:limit]

    return {
        "transactions": [
            {
                "id": t.id,
                "amount": str(abs(t.amount)),
                "type": t.type.value,
                "description": t.description,
                "category": t.category.name if t.category else None,
                "account": t.account.name,
                "tags": [tag.name for tag in t.tags],
                "date": str(t.transaction_date)
            }
            for t in result_transactions
        ],
        "returned_count": len(result_transactions),
        "total_count": len(transactions)
    }


@ai_tool
async def create_transaction(
    ctx: AgentContext,
    amount: Annotated[str, ToolParam("Transaction amount as decimal string, e.g., '50.00'")],
    type: Annotated[str, ToolParam("Transaction type", enum=["income", "expense"])],
    description: Annotated[str, ToolParam("Transaction description")],
    category_id: Annotated[Optional[int], ToolParam("Category ID for the transaction")] = None,
    account_id: Annotated[Optional[int], ToolParam("Account ID (uses default if not specified)")] = None,
    tags: Annotated[Optional[list[str]], ToolParam("List of tag names to attach")] = None,
    transaction_date: Annotated[Optional[str], ToolParam("Transaction date in YYYY-MM-DD format (defaults to today)")] = None
) -> dict:
    """Create a new financial transaction (income or expense)."""
    # Parse amount - expenses should be negative
    amount_decimal = Decimal(amount)
    if type == "expense" and amount_decimal > 0:
        amount_decimal = -amount_decimal

    data = {
        "amount": amount_decimal,
        "type": TransactionType(type),
        "description": description,
        "category": category_id,
        "account": account_id,
        "transaction_date": date.fromisoformat(transaction_date) if transaction_date else date.today()
    }

    try:
        transaction = await ctx.repo.transactions.create_with_tags(
            user_id=ctx.user_id,
            data=data,
            tag_names=tags or []
        )

        full = await ctx.repo.transactions.get_with_relations(transaction.id)

        return {
            "success": True,
            "transaction": {
                "id": full.id,
                "amount": str(abs(full.amount)),
                "type": full.type.value,
                "description": full.description,
                "category": full.category.name if full.category else None,
                "account": full.account.name,
                "tags": [t.name for t in full.tags],
                "date": str(full.transaction_date)
            },
            "message": f"Transaction created: {type} of {abs(amount_decimal)} - {description}"
        }
    except ValueError as e:
        return {"error": str(e)}


@ai_tool
async def get_transaction_by_id(
    ctx: AgentContext,
    transaction_id: Annotated[int, ToolParam("The transaction ID to retrieve")]
) -> dict:
    """Get details of a specific transaction by its ID."""
    transaction = await ctx.repo.transactions.get_by_id_and_user(transaction_id, ctx.user_id)
    if not transaction:
        return {"error": f"Transaction with ID {transaction_id} not found"}

    return {
        "id": transaction.id,
        "amount": str(abs(transaction.amount)),
        "type": transaction.type.value,
        "description": transaction.description,
        "category": transaction.category.name if transaction.category else None,
        "account": transaction.account.name,
        "tags": [t.name for t in transaction.tags],
        "date": str(transaction.transaction_date),
        "is_reviewed": transaction.is_reviewed,
        "created_at": str(transaction.created_at)
    }


@ai_tool
async def delete_transaction(
    ctx: AgentContext,
    transaction_id: Annotated[int, ToolParam("The transaction ID to delete")]
) -> dict:
    """Delete (soft delete) a transaction. The transaction can be recovered later if needed."""
    transaction = await ctx.repo.transactions.get_by_id_and_user(transaction_id, ctx.user_id)
    if not transaction:
        return {"error": f"Transaction with ID {transaction_id} not found"}

    description = transaction.description
    success = await ctx.repo.transactions.soft_delete(transaction_id)

    return {
        "success": success,
        "transaction_id": transaction_id,
        "message": f"Transaction '{description}' deleted successfully" if success else "Failed to delete transaction"
    }
