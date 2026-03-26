import os

from dotenv import load_dotenv
import logfire
from sanic import Sanic
from sanic.response import text, json
from sanic_ext import Extend
from sanic_ext.exceptions import ValidationError

from settings import settings

# Configure Logfire for observability
logfire.configure()

from blueprints.users import user_bp
from blueprints.transactions import transaction_bp
from blueprints.accounts import account_bp
from blueprints.budgets import budget_bp
from blueprints.categories import category_bp
from blueprints.tags import tag_bp
from blueprints.chats import chat_bp
from blueprints.ai_chat import ai_chat_bp
from blueprints.receipt_scan import receipt_scan_bp
from repositories.container import RepositoryContainer
from settings import settings
from db.config import engine, Base

load_dotenv()

app = Sanic("FinApp")
app.config.SECRET = settings.jwt_secret

# Serve static files
app.static("/static", "./static")

# Configure CORS before Extend
app.config.CORS_ORIGINS = "*"

# Initialize Sanic Extensions with Swagger config, CORS, and OpenAPI security
ext = Extend(
    app,
    config={
        "swagger_ui_configuration": {
            "docExpansion": "none",
        },
        "oas_url_prefix": "/docs",
        "oas_ui_default": "swagger",
        "cors": True,
        "cors_origins": "*",
        "cors_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "cors_headers": ["Content-Type", "Authorization"],
    }
)

# Configure OpenAPI metadata and servers
app.ext.openapi.describe(
    "Finance Analysis API",
    version="1.0.0",
    description="Personal finance tracking API"
)
app.ext.openapi.raw({
    "servers": [
        {"url": "http://localhost:8000", "description": "Local development"}
    ]
})

# Configure OpenAPI security scheme
app.ext.openapi.add_security_scheme(
    "BearerAuth",
    "http",
    scheme="bearer",
    bearer_format="JWT",
    description="JWT token obtained from /users/login endpoint"
)

app.ctx.repo = RepositoryContainer()


@app.before_server_start
async def setup_db(app):
    """Initialize database on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.after_server_stop
async def teardown_db(app):
    """Cleanup database connections on shutdown."""
    await engine.dispose()


app.blueprint(user_bp)
app.blueprint(transaction_bp)
app.blueprint(account_bp)
app.blueprint(budget_bp)
app.blueprint(category_bp)
app.blueprint(tag_bp)
app.blueprint(chat_bp)
app.blueprint(ai_chat_bp)
app.blueprint(receipt_scan_bp)


@app.exception(ValidationError)
async def handle_validation_error(request, exception):
    """Handle Pydantic validation errors with canonical error format (422)."""
    error_message = str(exception).replace("Invalid request body: ", "").replace(". Error: ", ": ")

    return json(
        {
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"validation_message": error_message}
        },
        status=422
    )


@app.get("/")
async def hello_world(request):
    return text("Hello, world.")


# Instrument Sanic with Logfire ASGI middleware for request tracing
# This wraps the ASGI app with OpenTelemetry middleware
# Keep original app available for tests and config access
asgi_app = logfire.instrument_asgi(app, capture_headers=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, dev=True)