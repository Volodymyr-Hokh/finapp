from sanic import Blueprint, Request, json
from sanic_ext import validate, openapi

from schemas.accounts import (
    AccountCreate,
    AccountRead,
    AccountUpdate
)
from schemas.shared import ErrorResponse, MessageResponse, UnauthorizedResponse, ValidationErrorResponse
from schemas.responses import AccountListResponse
from services.auth import protected

account_bp = Blueprint("Account", url_prefix="/accounts")


@account_bp.post("/")
@openapi.summary("Create a new account")
@openapi.description("Creates a new financial account/wallet for the authenticated user.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": AccountCreate.model_json_schema()})
@openapi.response(201, {"application/json": AccountRead.model_json_schema()}, "Account created")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=AccountCreate)
async def create_account(request: Request, body: AccountCreate):
    """Endpoint to create a new account linked to the user."""
    repo = request.app.ctx.repo.accounts
    user_id = request.ctx.user_id

    data = body.model_dump()
    new_account = await repo.create(user_id=user_id, **data)

    return json(AccountRead.model_validate(new_account).model_dump(mode="json"), status=201)


@account_bp.get("/")
@openapi.summary("List all user accounts")
@openapi.description("Returns a list of all accounts belonging to the authenticated user.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": AccountListResponse.model_json_schema()}, "List of accounts")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@protected
async def list_accounts(request: Request):
    """Retrieve all accounts for the current user."""
    repo = request.app.ctx.repo.accounts
    user_id = request.ctx.user_id

    # Fetch accounts filtered by user_id
    accounts = await repo.get_user_accounts(user_id)

    return json({
        "accounts": [
            AccountRead.model_validate(a).model_dump(mode="json") for a in accounts
        ]
    })


@account_bp.get("/<account_id:int>")
@openapi.summary("Get account details")
@openapi.description("Fetch a single account by ID, ensuring user ownership.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": AccountRead.model_json_schema()})
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Account not found")
@protected
async def get_account(request: Request, account_id: int):
    """Retrieve a specific account by ID."""
    repo = request.app.ctx.repo.accounts
    user_id = request.ctx.user_id

    account = await repo.get_by_id_and_user(account_id, user_id)

    if not account:
        return json({"error": "Account not found"}, status=404)

    return json(AccountRead.model_validate(account).model_dump(mode="json"))


@account_bp.patch("/<account_id:int>")
@openapi.summary("Update account")
@openapi.description("Partially update account details like name or balance.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": AccountUpdate.model_json_schema()})
@openapi.response(200, {"application/json": AccountRead.model_json_schema()}, "Account updated")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "No changes provided")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Account not found")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=AccountUpdate)
async def update_account(request: Request, account_id: int, body: AccountUpdate):
    """Update account fields if provided."""
    repo = request.app.ctx.repo.accounts
    user_id = request.ctx.user_id

    # Verify existence and ownership
    account = await repo.get(id=account_id, user_id=user_id)
    if not account:
        return json({"error": "Account not found"}, status=404)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return json({"message": "No changes provided"}, status=400)

    # Note: If is_default is updated, you might want to unset other default accounts in the repo
    await repo.update(id=account_id, **update_data)

    updated_account = await repo.get(id=account_id)
    return json(AccountRead.model_validate(updated_account).model_dump(mode="json"))


@account_bp.delete("/<account_id:int>")
@openapi.summary("Delete account")
@openapi.description("Permanently removes an account. Fails if transactions are linked (RESTRICT).")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": MessageResponse.model_json_schema()}, "Success message")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "Cannot delete account with existing transactions")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Account not found")
@protected
async def delete_account(request: Request, account_id: int):
    """Perform a hard delete on a user's account."""
    repo = request.app.ctx.repo.accounts
    user_id = request.ctx.user_id

    account = await repo.get(id=account_id, user_id=user_id)
    if not account:
        return json({"error": "Account not found"}, status=404)

    # Check if account has any transactions (including soft-deleted ones)
    has_transactions = await repo.has_transactions(account)
    if has_transactions:
        return json({"error": "Cannot delete account with existing transactions"}, status=400)

    await repo.delete_account(account)
    return json({"message": "Account deleted successfully"}, status=200)
