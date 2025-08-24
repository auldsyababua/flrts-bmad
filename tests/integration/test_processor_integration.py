"""Integration tests for processors."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import processors
from src.rails.processors.list_processor import ListProcessor
from src.rails.processors.task_processor import TaskProcessor


class MockSupabaseResponse:
    """Mock Supabase response."""

    def __init__(self, data=None, error=None):
        self.data = data or []
        self.error = error


class TestProcessorIntegration:
    """Test processor integration."""

    @pytest.mark.asyncio
    async def test_list_processor_create(self):
        """Test list creation."""
        # Mock supabase client
        mock_supabase = MagicMock()

        # Mock the insert response
        mock_response = MockSupabaseResponse([{"id": "test-list-id"}])
        mock_supabase.table().insert().execute = AsyncMock(return_value=mock_response)
        mock_supabase.table().select().eq().single().execute = AsyncMock(
            return_value=None
        )

        processor = ListProcessor(mock_supabase)

        params = {
            "operation": "create",
            "list_name": "Test Shopping List",
            "items": ["milk", "eggs", "bread"],
            "list_type": "Shopping List",
            "chat_id": "test-chat-123",
        }

        result = await processor.process(params)
        assert "✅" in result
        assert "Created list 'Test Shopping List'" in result
        assert "with 3 items" in result

    @pytest.mark.asyncio
    async def test_task_processor_create(self):
        """Test task creation."""
        # Mock supabase client
        mock_supabase = MagicMock()

        # Mock personnel lookup
        personnel_response = MockSupabaseResponse(
            [{"id": "joel-id", "first_name": "Joel", "aliases": ["j", "joel"]}]
        )

        # Mock task insert
        task_response = MockSupabaseResponse([{"id": "test-task-id"}])

        # Set up mock returns
        mock_supabase.table().select().eq().execute = AsyncMock(
            return_value=personnel_response
        )
        mock_supabase.table().insert().execute = AsyncMock(return_value=task_response)

        processor = TaskProcessor(mock_supabase)

        params = {
            "operation": "create",
            "task_title": "Check generator",
            "task_description_detailed": "Check oil levels and run diagnostics",
            "assigned_to": "joel",
            "due_date": "tomorrow",
            "priority": "High",
            "chat_id": "test-chat-123",
        }

        result = await processor.process(params)
        assert "✅" in result
        assert "Created task 'Check generator'" in result
        assert "assigned to joel" in result
        assert "due tomorrow" in result

    @pytest.mark.asyncio
    async def test_list_processor_add_items(self):
        """Test adding items to list."""

        mock_supabase = MagicMock()
        processor = ListProcessor(mock_supabase)

        # Mock finding the list - single() returns an object, not an array
        list_response = MockSupabaseResponse({"id": "existing-list-id"})

        # Mock getting max position - this returns an array since it's not using single()
        pos_response = MockSupabaseResponse([{"position": 5}])

        # Mock insert response - returns array of inserted items
        insert_response = MockSupabaseResponse([{"id": "item1"}, {"id": "item2"}])

        # Mock sites response for validation
        sites_response = MockSupabaseResponse([])  # No sites, so no protection needed

        # Keep track of which call we're on
        call_count = 0

        async def mock_safe_db_operation(operation, default=None):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: checking sites for validation
                return sites_response
            elif call_count == 2:
                # Second call: finding the list
                return list_response
            elif call_count == 3:
                # Third call: getting max position
                return pos_response
            elif call_count == 4:
                # Fourth call: inserting items
                return insert_response

            return default

        # Patch the _safe_db_operation method
        with patch.object(
            processor, "_safe_db_operation", side_effect=mock_safe_db_operation
        ):
            params = {
                "operation": "add_items",
                "list_name": "Shopping List",
                "items": ["butter", "cheese"],
                "chat_id": "test-chat-123",
            }

            result = await processor.process(params)
            assert "✅" in result
            assert "Added 2 items to 'Shopping List'" in result

    @pytest.mark.asyncio
    async def test_task_processor_complete(self):
        """Test completing a task."""
        mock_supabase = MagicMock()

        # Mock finding the task
        task_response = MockSupabaseResponse(
            [
                {
                    "id": "task-123",
                    "title": "Check generator oil",
                    "description": "Monthly check",
                }
            ]
        )

        # Mock update response
        update_response = MockSupabaseResponse([{"id": "task-123"}])

        # Configure mock
        mock_table = mock_supabase.table()
        mock_table.select().eq().ilike().eq().limit().execute = AsyncMock(
            return_value=task_response
        )
        mock_table.update().eq().execute = AsyncMock(return_value=update_response)

        processor = TaskProcessor(mock_supabase)

        params = {
            "operation": "complete",
            "task_title": "generator",
            "completion_notes": "Oil level good, no leaks found",
            "chat_id": "test-chat-123",
        }

        result = await processor.process(params)
        assert "✅" in result
        assert "Completed task 'Check generator oil'" in result

    @pytest.mark.asyncio
    async def test_processor_validation_errors(self):
        """Test validation error handling."""
        mock_supabase = MagicMock()

        # Test ListProcessor missing required fields
        list_processor = ListProcessor(mock_supabase)
        params = {
            "operation": "add_items",
            "chat_id": "test-chat-123",
            # Missing list_name and items
        }

        result = await list_processor.process(params)
        assert "❌" in result
        assert "Missing required fields" in result

        # Test TaskProcessor missing required fields
        task_processor = TaskProcessor(mock_supabase)
        params = {
            "operation": "create",
            "chat_id": "test-chat-123",
            # Missing task_title
        }

        result = await task_processor.process(params)
        assert "❌" in result
        assert "Missing required fields" in result
