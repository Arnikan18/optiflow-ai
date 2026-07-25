import os
import pytest
import asyncio

# Force SQLite in-memory database configuration for isolated unit tests
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.database.models import Base
from app.database.session import engine

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes schema tables inside SQLite in-memory for unit testing."""
    loop = asyncio.get_event_loop()
    
    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
    loop.run_until_complete(create_tables())
    yield
