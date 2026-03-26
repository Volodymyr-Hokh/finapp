from datetime import date
from sanic import Blueprint, Request, json
from sanic_ext import validate, openapi
from uuid import UUID

from schemas.transactions import (
    TransactionCreate,
    TransactionRead,
    TransactionUpdate,
    TransactionAIRequest
)
from schemas.shared import ErrorResponse, MessageResponse, UnauthorizedResponse, ValidationErrorResponse
from schemas.responses import TransactionListResponse
from schemas.enums import TransactionType
from services.auth import protected

transaction_bp = Blueprint("Transaction", url_prefix="/transactions")


@transaction_bp.post("/")
@openapi.summary("Create a transaction")
@openapi.description("Creates a new transaction and automatically links or creates tags.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": TransactionCreate.model_json_schema()})
@openapi.response(201, {"application/json": TransactionRead.model_json_schema()}, "Transaction created")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "Invalid account or category")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=TransactionCreate)
async def create_transaction(request: Request, body: TransactionCreate):
    """Endpoint to create a transaction with tag handling."""
    repo = request.app.ctx.repo.transactions
    user_id = request.ctx.user_id

    # Separate tags from the main transaction data for the repository method
    data = body.model_dump(exclude={"tags"})
    tag_names = body.tags

    try:
        new_transaction = await repo.create_with_tags(
            user_id=user_id,
            data=data,
            tag_names=tag_names
        )
    except ValueError as e:
        return json({"error": str(e)}, status=400)

    # Reload with relations (account, category, tags) for the response
    full_transaction = await repo.get_with_relations(new_transaction.id)

    return json(TransactionRead.model_validate(full_transaction).model_dump(mode="json"), status=201)


@transaction_bp.get("/")
@openapi.summary("List transactions")
@openapi.description("""
Returns a list of all active (non-deleted) transactions for the user.

Supports filtering, sorting, and pagination via query parameters.
When pagination parameters are provided, the response includes a `pagination` object with metadata.
""")
@openapi.secured("BearerAuth")
@openapi.parameter("limit", int, location="query", description="Maximum items to return (default: all)", required=False)
@openapi.parameter("offset", int, location="query", description="Items to skip (default: 0)", required=False)
@openapi.parameter("from_date", str, location="query", description="Filter transactions on or after this date (YYYY-MM-DD)", required=False)
@openapi.parameter("to_date", str, location="query", description="Filter transactions on or before this date (YYYY-MM-DD)", required=False)
@openapi.parameter("type", str, location="query", description="Filter by transaction type: income or expense", required=False)
@openapi.parameter("account_id", int, location="query", description="Filter by account ID", required=False)
@openapi.parameter("category_id", int, location="query", description="Filter by category ID", required=False)
@openapi.parameter("tag", str, location="query", description="Filter by tag name", required=False)
@openapi.parameter("search", str, location="query", description="Search in transaction description", required=False)
@openapi.parameter("sort", str, location="query", description="Sort order: date_asc, date_desc, amount_asc, amount_desc (default: date_desc)", required=False)
@openapi.response(200, {"application/json": TransactionListResponse.model_json_schema()}, "List of transactions")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@protected
async def list_transactions(request: Request):
    """Retrieve all transactions belonging to the authenticated user."""
    repo = request.app.ctx.repo.transactions
    user_id = request.ctx.user_id

    # Parse pagination params
    try:
        limit_str = request.args.get("limit")
        limit = int(limit_str) if limit_str else None
        offset_str = request.args.get("offset")
        offset = int(offset_str) if offset_str else 0
    except (ValueError, TypeError):
        return json({"error": "Invalid pagination parameters"}, status=400)

    # Parse filter params
    try:
        from_date_str = request.args.get("from_date")
        from_date_val = date.fromisoformat(from_date_str) if from_date_str else None
        to_date_str = request.args.get("to_date")
        to_date_val = date.fromisoformat(to_date_str) if to_date_str else None
        type_str = request.args.get("type")
        type_val = TransactionType(type_str) if type_str else None
        account_id_str = request.args.get("account_id")
        account_id_val = int(account_id_str) if account_id_str else None
        category_id_str = request.args.get("category_id")
        category_id_val = int(category_id_str) if category_id_str else None
    except (ValueError, TypeError):
        return json({"error": "Invalid filter parameters"}, status=400)
    tag_val = request.args.get("tag")
    search_val = request.args.get("search")
    sort_val = request.args.get("sort")

    # Get filtered transactions
    transactions = await repo.get_user_transactions(
        user_id=user_id,
        from_date=from_date_val,
        to_date=to_date_val,
        type=type_val,
        account_id=account_id_val,
        category_id=category_id_val,
        tag_name=tag_val,
        search=search_val,
        sort=sort_val,
    )

    # Apply pagination if limit provided
    total = len(transactions)
    if limit is not None:
        transactions = transactions[offset:offset + limit]
        return json({
            "transactions": [
                TransactionRead.model_validate(t).model_dump(mode="json") for t in transactions
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            }
        })

    return json({
        "transactions": [
            TransactionRead.model_validate(t).model_dump(mode="json") for t in transactions
        ]
    })


@transaction_bp.get("/<transaction_id:int>")
@openapi.summary("Get transaction details")
@openapi.description("Fetch a single transaction by ID, ensuring user ownership.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": TransactionRead.model_json_schema()})
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Transaction not found")
@protected
async def get_transaction(request: Request, transaction_id: int):
    """Retrieve a specific transaction with all related entities."""
    repo = request.app.ctx.repo.transactions
    user_id = request.ctx.user_id

    # Ensure the transaction exists and belongs to the current user
    transaction = await repo.get_by_id_and_user(transaction_id, user_id)

    if not transaction:
        return json({"error": "Transaction not found"}, status=404)
        
    return json(TransactionRead.model_validate(transaction).model_dump(mode="json"))


@transaction_bp.patch("/<transaction_id:int>")
@openapi.summary("Update transaction")
@openapi.description("Partially update transaction details.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": TransactionUpdate.model_json_schema()})
@openapi.response(200, {"application/json": TransactionRead.model_json_schema()}, "Transaction updated")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "No changes provided")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Transaction not found")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=TransactionUpdate)
async def update_transaction(request: Request, transaction_id: int, body: TransactionUpdate):
    """Update transaction fields if provided."""
    repo = request.app.ctx.repo.transactions
    user_id = request.ctx.user_id

    # Check ownership and existence before updating
    transaction = await repo.get(id=transaction_id, user_id=user_id)
    if not transaction:
        return json({"error": "Transaction not found"}, status=404)

    # Separate tags from the main update data
    tag_names = body.tags

    # Use by_alias=True to get 'category_id'/'account_id' instead of 'category'/'account' (field names)
    # This prevents SQLAlchemy from confusing relationships with FK values
    update_data = body.model_dump(exclude_unset=True, by_alias=True, exclude={"tags"})
    if not update_data and tag_names is None:
        return json({"message": "No changes provided"}, status=400)

    if update_data:
        await repo.update(id=transaction_id, **update_data)

    # Handle tags if provided
    if tag_names is not None:
        await repo.update_tags(transaction_id, user_id, tag_names)

    # Reload updated instance with relationships for the response
    full_transaction = await repo.get_with_relations(transaction_id)

    return json(TransactionRead.model_validate(full_transaction).model_dump(mode="json"))


@transaction_bp.delete("/<transaction_id:int>")
@openapi.summary("Soft delete transaction")
@openapi.description("Marks a transaction as deleted without removing it from the database.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": MessageResponse.model_json_schema()}, "Success message")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Transaction not found")
@openapi.response(500, {"application/json": ErrorResponse.model_json_schema()}, "Delete operation failed")
@protected
async def delete_transaction(request: Request, transaction_id: int):
    """Perform a soft delete on a user's transaction."""
    repo = request.app.ctx.repo.transactions
    user_id = request.ctx.user_id

    # Verify that the transaction belongs to the user
    exists = await repo.get(id=transaction_id, user_id=user_id)
    if not exists or exists.is_deleted:
        return json({"error": "Transaction not found"}, status=404)

    success = await repo.soft_delete(id=transaction_id)
    
    if success:
        return json({"message": "Transaction deleted successfully"}, status=200)
    return json({"error": "Delete operation failed"}, status=500)