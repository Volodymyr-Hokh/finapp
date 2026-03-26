"""
Script to seed the database with general (system-wide) categories.
These categories have NULL user_id and are available to all users.

Usage:
    python seed_categories.py
"""

import asyncio
from sqlalchemy import select

from db.config import engine, Base
from db.session import get_session
from db.models import Category


# List of general categories with icons
SYSTEM_CATEGORIES = [
    {"name": "Food & Dining", "icon": "🍔"},
    {"name": "Groceries", "icon": "🛒"},
    {"name": "Transportation", "icon": "🚗"},
    {"name": "Shopping", "icon": "🛍️"},
    {"name": "Entertainment", "icon": "🎬"},
    {"name": "Utilities", "icon": "💡"},
    {"name": "Healthcare", "icon": "🏥"},
    {"name": "Education", "icon": "📚"},
    {"name": "Travel", "icon": "✈️"},
    {"name": "Housing", "icon": "🏠"},
    {"name": "Insurance", "icon": "🛡️"},
    {"name": "Fitness", "icon": "💪"},
    {"name": "Clothing", "icon": "👕"},
    {"name": "Personal Care", "icon": "💅"},
    {"name": "Gifts & Donations", "icon": "🎁"},
    {"name": "Subscriptions", "icon": "📱"},
    {"name": "Salary", "icon": "💰"},
    {"name": "Investment", "icon": "📈"},
    {"name": "Business", "icon": "💼"},
    {"name": "Other", "icon": "📦"},
]


async def seed_categories():
    """Create system categories in the database."""
    try:
        # Ensure tables exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Database tables ready")

        async with get_session() as session:
            # Check existing categories
            stmt = select(Category).where(Category.user_id.is_(None))
            result = await session.execute(stmt)
            existing_categories = list(result.scalars().all())
            existing_names = {cat.name for cat in existing_categories}

            print(f"Found {len(existing_categories)} existing system categories")

            # Create new categories
            created_count = 0
            for category_data in SYSTEM_CATEGORIES:
                if category_data["name"] not in existing_names:
                    category = Category(
                        name=category_data["name"],
                        icon=category_data["icon"],
                        user_id=None  # NULL user_id makes it a system category
                    )
                    session.add(category)
                    created_count += 1
                    print(f"Created: {category_data['name']}")
                else:
                    print(f"- Skipped: {category_data['name']} (already exists)")

            print(f"\nDone! Created {created_count} new system categories")
            print(f"Total system categories: {len(existing_categories) + created_count}")

    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        await engine.dispose()
        print("\nDatabase connection closed")


if __name__ == "__main__":
    print("Seeding system categories...\n")
    asyncio.run(seed_categories())
