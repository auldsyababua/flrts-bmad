"""Database fixtures for integration tests."""

import os
import uuid
from typing import Any, AsyncGenerator, Dict

import pytest
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from src.rails.processors.list_processor import ListProcessor
from src.rails.processors.task_processor import TaskProcessor


class TestDatabaseManager:
    """Manages test database lifecycle and provides utilities."""

    def __init__(self, supabase_client: Client):
        self.client = supabase_client
        self.transaction_id = None

    async def start_transaction(self) -> str:
        """Start a test transaction for isolation."""
        self.transaction_id = str(uuid.uuid4())
        # Note: Supabase doesn't support explicit transactions via API
        # We'll use table prefixing or separate test schemas instead
        return self.transaction_id

    async def rollback_transaction(self):
        """Clean up test data after transaction."""
        if self.transaction_id:
            # Clean up test data created during this transaction
            await self._cleanup_test_data()
            self.transaction_id = None

    async def _cleanup_test_data(self):
        """Remove test data from all tables."""
        tables_to_clean = [
            "tasks",
            "lists",
            "list_items",
            "documents",
            "document_chunks",
            "personnel",
            "sites",
        ]

        for table in tables_to_clean:
            try:
                # Delete records created by tests (identified by test prefixes)
                await self.client.table(table).delete().like(
                    "title", "TEST_%"
                ).execute()
                await self.client.table(table).delete().like("name", "TEST_%").execute()
            except Exception as e:
                print(f"Warning: Could not clean {table}: {e}")

    async def create_test_site(self, name: str = None) -> Dict[str, Any]:
        """Create a test site for use in tests."""
        site_name = name or f"TEST_Site_{uuid.uuid4().hex[:8]}"

        site_data = {
            "site_name": site_name,
            "location": "Test Location",
            "description": "Test site for integration testing",
            "is_active": True,
            "created_at": "now()",
        }

        result = self.client.table("sites").insert(site_data).execute()
        return result.data[0] if result.data else site_data

    async def create_test_personnel(self, first_name: str = None) -> Dict[str, Any]:
        """Create test personnel for use in tests."""
        name = first_name or f"TEST_User_{uuid.uuid4().hex[:8]}"

        personnel_data = {
            "first_name": name,
            "last_name": "Tester",
            "email": f"{name.lower()}@test.com",
            "is_active": True,
            "aliases": [name.lower(), f"{name[0].lower()}"],
            "created_at": "now()",
        }

        result = self.client.table("personnel").insert(personnel_data).execute()
        return result.data[0] if result.data else personnel_data

    async def create_test_task(self, **overrides) -> Dict[str, Any]:
        """Create a test task with optional overrides."""
        task_data = {
            "title": f"TEST_Task_{uuid.uuid4().hex[:8]}",
            "description": "Test task for integration testing",
            "status": "To Do",
            "priority": "Medium",
            "created_at": "now()",
            **overrides,
        }

        result = self.client.table("tasks").insert(task_data).execute()
        return result.data[0] if result.data else task_data

    async def create_test_list(self, **overrides) -> Dict[str, Any]:
        """Create a test list with optional overrides."""
        list_data = {
            "name": f"TEST_List_{uuid.uuid4().hex[:8]}",
            "list_type": "General",
            "status": "Active",
            "created_at": "now()",
            **overrides,
        }

        result = self.client.table("lists").insert(list_data).execute()
        return result.data[0] if result.data else list_data


@pytest.fixture(scope="session")
def test_database_config():
    """Test database configuration."""
    return {
        "url": os.getenv("TEST_SUPABASE_URL", os.getenv("SUPABASE_URL")),
        "anon_key": os.getenv("TEST_SUPABASE_ANON_KEY", os.getenv("SUPABASE_ANON_KEY")),
        "service_key": os.getenv(
            "TEST_SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_SERVICE_KEY")
        ),
    }


@pytest.fixture(scope="session")
async def supabase_test_client(test_database_config):
    """Create Supabase client for testing."""
    config = test_database_config

    if not config["url"] or not config["anon_key"]:
        pytest.skip(
            "Test database not configured. Set TEST_SUPABASE_URL and TEST_SUPABASE_ANON_KEY"
        )

    # Use service key if available for admin operations
    key = config["service_key"] if config["service_key"] else config["anon_key"]

    client = create_client(
        config["url"],
        key,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )

    yield client


@pytest.fixture
async def db_manager(supabase_test_client) -> AsyncGenerator[TestDatabaseManager, None]:
    """Database manager with transaction isolation."""
    manager = TestDatabaseManager(supabase_test_client)

    # Start transaction
    await manager.start_transaction()

    yield manager

    # Cleanup after test
    await manager.rollback_transaction()


@pytest.fixture
async def task_processor(supabase_test_client) -> TaskProcessor:
    """Task processor for integration testing."""
    return TaskProcessor(supabase_test_client)


@pytest.fixture
async def list_processor(supabase_test_client) -> ListProcessor:
    """List processor for integration testing."""
    return ListProcessor(supabase_test_client)


@pytest.fixture
async def test_personnel(db_manager) -> Dict[str, Any]:
    """Create test personnel for use in tests."""
    return await db_manager.create_test_personnel("TestUser")


@pytest.fixture
async def test_site(db_manager) -> Dict[str, Any]:
    """Create test site for use in tests."""
    return await db_manager.create_test_site("TEST_Eagle_Lake")


@pytest.fixture
async def vector_store_cleanup():
    """Clean up vector store after tests."""
    yield
    # Clean up test vectors
    try:
        # Note: This would need vector store cleanup implementation
        # await vector_store.delete_by_prefix("TEST_")
        pass
    except Exception as e:
        print(f"Warning: Could not clean vector store: {e}")
