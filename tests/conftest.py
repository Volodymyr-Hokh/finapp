"""
Shared test fixtures for the finance analysis API.
"""
import uuid
import datetime
import json
import asyncio
from decimal import Decimal
from typing import AsyncGenerator

import pytest
from faker import Faker
from sanic import Sanic
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from main import app as main_app
from db.config import Base, async_session_factory
from db.models import (
    User,
    Account,
    Category,
    Tag,
    Transaction,
    Budget,
    Chat,
    ChatMessage,
    AILog,
    TransactionTag,
)
from repositories.container import RepositoryContainer
from services.auth import hash_password, create_access_token
from schemas.enums import TransactionType
import db.session as db_session_module

fake = Faker()


# ============================================================================
# APP & CLIENT FIXTURES
# ============================================================================


@pytest.fixture
def app() -> Sanic:
    """Provides the Sanic app instance configured for testing."""
    main_app.config.update(
        {
            "TESTING": True,
        }
    )
    # Clear any cached ASGI client to avoid event loop conflicts between async tests
    if hasattr(main_app, "_asgi_client"):
        main_app._asgi_client = None
    return main_app


@pytest.fixture
async def test_client(app):
    """Provides synchronous test client within an async context."""
    return app.test_client


# ============================================================================
# DATABASE FIXTURES
# ============================================================================


@pytest.fixture(autouse=True, scope="function")
async def setup_database():
    """
    Setup and teardown database for each test.
    Uses an in-memory SQLite database to ensure complete isolation.
    Each test gets a fresh database.
    """
    # Create async engine with in-memory SQLite
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign keys for SQLite on every connection
    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create test session factory
    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Store original session factory
    original_session_factory = db_session_module.async_session_factory

    # Monkey-patch the session factory for tests
    db_session_module.async_session_factory = test_session_factory

    yield test_session_factory

    # Restore original session factory
    db_session_module.async_session_factory = original_session_factory

    # Cleanup
    await test_engine.dispose()


@pytest.fixture
def repo() -> RepositoryContainer:
    """Provides repository container."""
    return RepositoryContainer()


# ============================================================================
# USER FIXTURES
# ============================================================================


@pytest.fixture
async def sample_user(setup_database) -> User:
    """Creates a sample user for testing."""
    async with setup_database() as session:
        user = User(
            email=fake.email(),
            hashed_password=hash_password("TestPassword123!"),
            base_currency="UAH",
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        await session.commit()
        return user


@pytest.fixture
async def another_user(setup_database) -> User:
    """Creates another user to test data isolation."""
    async with setup_database() as session:
        user = User(
            email=fake.email(),
            hashed_password=hash_password("AnotherPassword123!"),
            base_currency="USD",
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        await session.commit()
        return user


@pytest.fixture
def auth_token(app, sample_user: User) -> str:
    """Generates a valid JWT token for the sample user."""
    token = create_access_token(
        user_id=str(sample_user.id),
        secret=app.config.SECRET.get_secret_value(),
        expires_delta=3600,
    )
    return token


@pytest.fixture
def expired_token(app, sample_user: User) -> str:
    """Generates an expired JWT token."""
    token = create_access_token(
        user_id=str(sample_user.id),
        secret=app.config.SECRET.get_secret_value(),
        expires_delta=-100,  # Negative delta makes it expired
    )
    return token


# ============================================================================
# ACCOUNT FIXTURES
# ============================================================================


@pytest.fixture
async def sample_account(setup_database, sample_user: User) -> Account:
    """Creates a sample account for the user."""
    async with setup_database() as session:
        account = Account(
            name="Test Wallet",
            currency="UAH",
            balance=Decimal("1000.00"),
            is_default=True,
            user_id=sample_user.id,
        )
        session.add(account)
        await session.flush()
        await session.refresh(account)
        await session.commit()
        return account


@pytest.fixture
async def another_account(setup_database, sample_user: User) -> Account:
    """Creates another account for the same user."""
    async with setup_database() as session:
        account = Account(
            name="Savings Account",
            currency="UAH",
            balance=Decimal("5000.00"),
            is_default=False,
            user_id=sample_user.id,
        )
        session.add(account)
        await session.flush()
        await session.refresh(account)
        await session.commit()
        return account


# ============================================================================
# CATEGORY FIXTURES
# ============================================================================


@pytest.fixture
async def system_category(setup_database) -> Category:
    """Creates a system-wide category (no user)."""
    async with setup_database() as session:
        category = Category(
            name="Food",
            icon="🍔",
            user_id=None,  # System category
        )
        session.add(category)
        await session.flush()
        await session.refresh(category)
        await session.commit()
        return category


@pytest.fixture
async def user_category(setup_database, sample_user: User) -> Category:
    """Creates a user-specific category."""
    async with setup_database() as session:
        category = Category(
            name="Custom Category",
            icon="💼",
            user_id=sample_user.id,
        )
        session.add(category)
        await session.flush()
        await session.refresh(category)
        await session.commit()
        return category


# ============================================================================
# TAG FIXTURES
# ============================================================================


@pytest.fixture
async def sample_tag(setup_database, sample_user: User) -> Tag:
    """Creates a sample tag for the user."""
    async with setup_database() as session:
        tag = Tag(name="groceries", user_id=sample_user.id)
        session.add(tag)
        await session.flush()
        await session.refresh(tag)
        await session.commit()
        return tag


@pytest.fixture
async def sample_tags(setup_database, sample_user: User) -> list[Tag]:
    """Creates multiple tags for the user."""
    tags = []
    async with setup_database() as session:
        for name in ["work", "personal", "urgent"]:
            tag = Tag(name=name, user_id=sample_user.id)
            session.add(tag)
            await session.flush()
            await session.refresh(tag)
            tags.append(tag)
        await session.commit()
    return tags


# ============================================================================
# TRANSACTION FIXTURES
# ============================================================================


@pytest.fixture
async def sample_transaction(
    setup_database, sample_user: User, sample_account: Account, system_category: Category
) -> Transaction:
    """Creates a sample transaction."""
    async with setup_database() as session:
        transaction = Transaction(
            amount=Decimal("-50.00"),
            type=TransactionType.EXPENSE,
            description="Test expense",
            transaction_date=datetime.date.today(),
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id,
            is_reviewed=False,
        )
        session.add(transaction)
        await session.flush()
        await session.refresh(transaction)
        await session.commit()
        return transaction


@pytest.fixture
async def income_transaction(
    setup_database, sample_user: User, sample_account: Account
) -> Transaction:
    """Creates an income transaction."""
    async with setup_database() as session:
        transaction = Transaction(
            amount=Decimal("1000.00"),
            type=TransactionType.INCOME,
            description="Salary",
            transaction_date=datetime.date.today(),
            user_id=sample_user.id,
            account_id=sample_account.id,
            is_reviewed=True,
        )
        session.add(transaction)
        await session.flush()
        await session.refresh(transaction)
        await session.commit()
        return transaction


# ============================================================================
# BUDGET FIXTURES
# ============================================================================


@pytest.fixture
async def sample_budget(
    setup_database, sample_user: User, system_category: Category
) -> Budget:
    """Creates a sample budget."""
    today = datetime.date.today()
    async with setup_database() as session:
        budget = Budget(
            limit_amount=Decimal("500.00"),
            month=today.month,
            year=today.year,
            user_id=sample_user.id,
            category_id=system_category.id,
        )
        session.add(budget)
        await session.flush()
        await session.refresh(budget)
        await session.commit()
        return budget


# ============================================================================
# HELPER FIXTURES
# ============================================================================


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Returns authorization headers with valid token."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def fake_uuid() -> uuid.UUID:
    """Returns a random UUID for testing."""
    return uuid.uuid4()


# ============================================================================
# AI MOCK FIXTURES
# ============================================================================


@pytest.fixture
def mock_transaction_repo():
    """Mock TransactionRepository for AI testing."""
    from unittest.mock import AsyncMock
    from repositories.transactions import TransactionRepository

    return AsyncMock(spec=TransactionRepository)


@pytest.fixture
def mock_account_repo():
    """Mock AccountRepository for AI testing."""
    from unittest.mock import AsyncMock
    from repositories.accounts import AccountRepository

    return AsyncMock(spec=AccountRepository)


@pytest.fixture
def mock_budget_repo():
    """Mock BudgetRepository for AI testing."""
    from unittest.mock import AsyncMock
    from repositories.budgets import BudgetRepository

    return AsyncMock(spec=BudgetRepository)


# ============================================================================
# AI LOG FIXTURES
# ============================================================================


@pytest.fixture
async def sample_ai_log(setup_database, sample_user):
    """Creates a sample AI log entry."""
    async with setup_database() as session:
        log = AILog(
            user_id=sample_user.id,
            prompt="Test prompt",
            response="Test response",
            ai_model="gpt-4o-mini",
            tokens_used=100,
        )
        session.add(log)
        await session.flush()
        await session.refresh(log)
        await session.commit()
        return log


@pytest.fixture
async def multiple_ai_logs(setup_database, sample_user):
    """Creates multiple AI log entries for testing."""
    logs = []
    async with setup_database() as session:
        for i in range(5):
            log = AILog(
                user_id=sample_user.id,
                prompt=f"Test prompt {i}",
                response=f"Test response {i}",
                ai_model="gpt-4o-mini",
                tokens_used=100 * (i + 1),
            )
            session.add(log)
            await session.flush()
            await session.refresh(log)
            logs.append(log)
            await asyncio.sleep(0.01)  # Ensure different created_at
        await session.commit()
    return logs


# ============================================================================
# CHAT FIXTURES
# ============================================================================


@pytest.fixture
async def sample_chat(setup_database, sample_user: User) -> Chat:
    """Creates a sample chat for testing."""
    async with setup_database() as session:
        chat = Chat(user_id=sample_user.id, name="Test Chat")
        session.add(chat)
        await session.flush()
        await session.refresh(chat)
        await session.commit()
        return chat


@pytest.fixture
async def another_chat(setup_database, sample_user: User) -> Chat:
    """Creates another chat for the same user."""
    async with setup_database() as session:
        chat = Chat(user_id=sample_user.id, name="Another Chat")
        session.add(chat)
        await session.flush()
        await session.refresh(chat)
        await session.commit()
        return chat


@pytest.fixture
async def sample_chat_message(setup_database, sample_chat: Chat) -> ChatMessage:
    """Creates a sample chat message in LangChain format."""
    # LangChain message format
    message_json = json.dumps(
        {
            "type": "human",
            "data": {"content": "Hello", "additional_kwargs": {}, "type": "human"},
        }
    )
    async with setup_database() as session:
        message = ChatMessage(
            chat_id=sample_chat.id,
            message_json=message_json,
            role="user",
            sequence_number=1,
        )
        session.add(message)
        await session.flush()
        await session.refresh(message)
        await session.commit()
        return message


@pytest.fixture
async def chat_with_history(
    setup_database, sample_chat: Chat
) -> tuple[Chat, list[ChatMessage]]:
    """Creates a chat with multiple messages for history testing."""
    messages = []
    conversation = [
        ("user", "What is my balance?"),
        ("assistant", "Your balance is $1000."),
        ("user", "Show my recent transactions"),
        ("assistant", "Here are your recent transactions..."),
    ]

    async with setup_database() as session:
        for i, (role, content) in enumerate(conversation, start=1):
            # LangChain message format
            if role == "user":
                msg_data = {
                    "type": "human",
                    "data": {
                        "content": content,
                        "additional_kwargs": {},
                        "type": "human",
                    },
                }
            else:
                msg_data = {
                    "type": "ai",
                    "data": {"content": content, "additional_kwargs": {}, "type": "ai"},
                }

            msg = ChatMessage(
                chat_id=sample_chat.id,
                message_json=json.dumps(msg_data),
                role=role,
                sequence_number=i,
            )
            session.add(msg)
            await session.flush()
            await session.refresh(msg)
            messages.append(msg)
            await asyncio.sleep(0.01)  # Ensure different timestamps
        await session.commit()

    return sample_chat, messages


# ============================================================================
# CHAT MOCK FIXTURES
# ============================================================================


@pytest.fixture
def mock_chat_repo():
    """Mock ChatRepository for service testing."""
    from unittest.mock import AsyncMock
    from repositories.chats import ChatRepository

    return AsyncMock(spec=ChatRepository)


@pytest.fixture
def mock_chat_message_repo():
    """Mock ChatMessageRepository for service testing."""
    from unittest.mock import AsyncMock
    from repositories.chat_messages import ChatMessageRepository

    return AsyncMock(spec=ChatMessageRepository)


# ============================================================================
# SQLALCHEMY TEST HELPERS
# ============================================================================


@pytest.fixture
def create_model(setup_database):
    """
    Factory fixture for creating model instances in tests.
    
    Usage:
        async def test_something(create_model, sample_user):
            chat = await create_model(Chat, user_id=sample_user.id, name="Test")
            message = await create_model(ChatMessage, chat_id=chat.id, ...)
    """
    async def _create_model(model_class, **kwargs):
        async with setup_database() as session:
            instance = model_class(**kwargs)
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            await session.commit()
            return instance
    return _create_model


@pytest.fixture
def create_models(setup_database):
    """
    Factory fixture for creating multiple model instances in a single transaction.
    
    Usage:
        async def test_something(create_models):
            chats = await create_models(Chat, [
                {"user_id": user.id, "name": "Chat 1"},
                {"user_id": user.id, "name": "Chat 2"},
            ])
    """
    async def _create_models(model_class, items: list[dict]):
        results = []
        async with setup_database() as session:
            for kwargs in items:
                instance = model_class(**kwargs)
                session.add(instance)
                await session.flush()
                await session.refresh(instance)
                results.append(instance)
            await session.commit()
        return results
    return _create_models
