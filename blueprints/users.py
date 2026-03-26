from sanic import Blueprint, Request, json
from sanic_ext import validate, openapi

from schemas.users import UserCreate, UserRead, UserUpdate, UserLogin
from schemas.shared import ErrorResponse, LoginResponse, UnauthorizedResponse, ValidationErrorResponse
from services.auth import protected, verify_password, hash_password, create_access_token

user_bp = Blueprint("User", url_prefix="/users")


@user_bp.post("/register")
@openapi.summary("Register a new user")
@openapi.description("Creates a new user account and hashes the password.")
@openapi.body({"application/json": UserCreate.model_json_schema()})
@openapi.response(201, {"application/json": UserRead.model_json_schema()}, "User created successfully")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "Email already registered")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@validate(json=UserCreate)
async def register_user(request: Request, body: UserCreate):
    """Endpoint for new user registration."""
    repo = request.app.ctx.repo.users
    acc_repo = request.app.ctx.repo.accounts

    # Check if the email is already taken
    if await repo.get_by_email(body.email):
        return json({"error": "Email already registered"}, status=400)

    # Prepare data and hash the password
    user_data = body.model_dump(exclude={"password"})
    user_data["hashed_password"] = hash_password(body.password)

    new_user = await repo.create(**user_data)
    await acc_repo.create(
        name="Default Wallet",
        currency=new_user.base_currency,
        user_id=new_user.id,
        is_default=True
    )
    return json(UserRead.model_validate(new_user).model_dump(mode="json"), status=201)


@user_bp.post("/login")
@openapi.summary("User Login")
@openapi.description("Authenticates user and returns a JWT access token.")
@openapi.body({"application/json": UserLogin.model_json_schema()})
@openapi.response(200, {"application/json": LoginResponse.model_json_schema()}, "Successful login")
@openapi.response(401, {"application/json": ErrorResponse.model_json_schema()}, "Invalid credentials")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@validate(json=UserLogin)
async def login_user(request: Request, body: UserLogin):
    """Authenticate user and return JWT."""
    repo = request.app.ctx.repo.users
    user = await repo.get_by_email(body.email)

    # 1. Verify password hash
    if not user or not verify_password(body.password, user.hashed_password):
        return json({"error": "Invalid email or password"}, status=401)

    # 2. Generate real JWT
    expires_delta = 24 * 60 * 60  # 24 hours in seconds
    token = create_access_token(
        user_id=str(user.id),
        secret=request.app.config.SECRET.get_secret_value(),
        expires_delta=expires_delta
    )

    return json({"access_token": token, "token_type": "bearer", "expires_in": expires_delta})


@user_bp.get("/me")
@openapi.summary("Get Current Profile")
@openapi.description("Retrieves profile information for the authenticated user.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": UserRead.model_json_schema()}, "User profile data")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "User not found")
@protected
async def get_profile(request: Request):
    """Retrieve authenticated user's profile."""
    user_id = request.ctx.user_id
    user = await request.app.ctx.repo.users.get(id=user_id)

    if not user:
        return json({"error": "User not found"}, status=404)

    return json(UserRead.model_validate(user).model_dump(mode="json"))


@user_bp.patch("/me")
@openapi.summary("Update Profile")
@openapi.description("Updates specific fields in the user's profile.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": UserUpdate.model_json_schema()})
@openapi.response(200, {"application/json": UserRead.model_json_schema()}, "Updated profile data")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "No changes provided")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=UserUpdate)
async def update_profile(request: Request, body: UserUpdate):
    """Update user preferences or profile info."""
    user_id = request.ctx.user_id
    updated_data = body.model_dump(exclude_unset=True)

    if not updated_data:
        return json({"message": "Nothing to update"}, status=400)

    # Hash password if it is being updated
    if "password" in updated_data:
        updated_data["hashed_password"] = hash_password(updated_data.pop("password"))

    updated_user = await request.app.ctx.repo.users.update(id=user_id, **updated_data)
    return json(UserRead.model_validate(updated_user).model_dump(mode="json"))
