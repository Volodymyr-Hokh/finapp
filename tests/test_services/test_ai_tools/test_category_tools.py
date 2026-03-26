"""
Tests for category and tag AI tools.
"""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from services.ai_tools import AgentContext
from services.ai_tools.category_tools import (
    get_categories,
    create_category,
    delete_category,
    get_tags,
    create_tags,
    delete_tag,
)


@pytest.fixture
def mock_repo():
    """Create mock repository container."""
    repo = MagicMock()
    repo.categories = AsyncMock()
    repo.tags = AsyncMock()
    return repo


@pytest.fixture
def mock_context(mock_repo):
    """Create mock agent context."""
    return AgentContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        repo=mock_repo
    )


@pytest.fixture
def mock_category():
    """Create a mock category."""
    category = MagicMock()
    category.id = 1
    category.name = "Food"
    category.icon = "🍔"
    category.user_id = None  # System category
    return category


@pytest.fixture
def mock_user_category(mock_context):
    """Create a mock user category."""
    category = MagicMock()
    category.id = 2
    category.name = "Custom"
    category.icon = "💼"
    category.user_id = str(mock_context.user_id)  # User category
    return category


@pytest.fixture
def mock_tag():
    """Create a mock tag."""
    tag = MagicMock()
    tag.id = 1
    tag.name = "groceries"
    return tag


class TestGetCategories:
    """Tests for get_categories tool."""

    @pytest.mark.asyncio
    async def test_returns_categories(self, mock_context, mock_category, mock_user_category):
        """Test getting categories."""
        mock_context.repo.categories.get_available_categories.return_value = [
            mock_category, mock_user_category
        ]

        result = await get_categories(mock_context)

        assert result["count"] == 2
        assert len(result["categories"]) == 2
        # System category
        assert result["categories"][0]["is_system"] is True
        # User category
        assert result["categories"][1]["is_system"] is False

    @pytest.mark.asyncio
    async def test_returns_empty_list(self, mock_context):
        """Test returns empty list when no categories."""
        mock_context.repo.categories.get_available_categories.return_value = []

        result = await get_categories(mock_context)

        assert result["count"] == 0
        assert result["categories"] == []


class TestCreateCategory:
    """Tests for create_category tool."""

    @pytest.mark.asyncio
    async def test_creates_category(self, mock_context, mock_user_category):
        """Test creating a category."""
        mock_context.repo.categories.validate_unique_name.return_value = (True, None)
        mock_context.repo.categories.create.return_value = mock_user_category

        result = await create_category(mock_context, name="Custom", icon="💼")

        assert result["success"] is True
        assert result["category"]["name"] == "Custom"
        mock_context.repo.categories.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_error_for_duplicate_name(self, mock_context):
        """Test error when category name exists."""
        mock_context.repo.categories.validate_unique_name.return_value = (
            False, "Category name already exists"
        )

        result = await create_category(mock_context, name="Existing")

        assert "error" in result
        assert "already exists" in result["error"]


class TestDeleteCategory:
    """Tests for delete_category tool."""

    @pytest.mark.asyncio
    async def test_deletes_user_category(self, mock_context, mock_user_category):
        """Test deleting a user category."""
        mock_context.repo.categories.get_by_id_and_user.return_value = mock_user_category

        result = await delete_category(mock_context, category_id=2)

        assert result["success"] is True
        assert "deleted successfully" in result["message"]
        mock_context.repo.categories.delete_category.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_error_for_system_category(self, mock_context):
        """Test error when trying to delete system category."""
        mock_context.repo.categories.get_by_id_and_user.return_value = None

        result = await delete_category(mock_context, category_id=1)

        assert "error" in result
        assert "not found or is a system category" in result["error"]


class TestGetTags:
    """Tests for get_tags tool."""

    @pytest.mark.asyncio
    async def test_returns_tags(self, mock_context, mock_tag):
        """Test getting tags."""
        mock_context.repo.tags.get_user_tags.return_value = [mock_tag]

        result = await get_tags(mock_context)

        assert result["count"] == 1
        assert result["tags"][0]["name"] == "groceries"


class TestCreateTags:
    """Tests for create_tags tool."""

    @pytest.mark.asyncio
    async def test_creates_tags(self, mock_context, mock_tag):
        """Test creating tags."""
        tag2 = MagicMock()
        tag2.id = 2
        tag2.name = "work"
        mock_context.repo.tags.get_or_create_tags.return_value = [mock_tag, tag2]

        result = await create_tags(mock_context, names=["groceries", "work"])

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["tags"]) == 2


class TestDeleteTag:
    """Tests for delete_tag tool."""

    @pytest.mark.asyncio
    async def test_deletes_tag(self, mock_context, mock_tag):
        """Test deleting a tag."""
        mock_context.repo.tags.get_by_id.return_value = mock_tag

        result = await delete_tag(mock_context, tag_id=1)

        assert result["success"] is True
        mock_context.repo.tags.delete_tag.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_error_for_nonexistent(self, mock_context):
        """Test error when tag not found."""
        mock_context.repo.tags.get_by_id.return_value = None

        result = await delete_tag(mock_context, tag_id=999)

        assert "error" in result
