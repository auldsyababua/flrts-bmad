"""
Unit tests for ListProcessor direct execution functionality.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.rails.processors.list_processor import ListProcessor


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    mock = Mock()
    mock.table = Mock(return_value=mock)
    mock.select = Mock(return_value=mock)
    mock.insert = Mock(return_value=mock)
    mock.update = Mock(return_value=mock)
    mock.delete = Mock(return_value=mock)
    mock.eq = Mock(return_value=mock)
    mock.ilike = Mock(return_value=mock)
    mock.limit = Mock(return_value=mock)
    mock.execute = AsyncMock()
    return mock


@pytest.fixture
def list_processor(mock_supabase):
    """Create ListProcessor instance with mocked Supabase."""
    processor = ListProcessor(mock_supabase)
    # Mock the validation to skip database checks
    processor.validate_operation = AsyncMock(return_value=(True, "Valid"))
    return processor


class TestListProcessorDirectExecution:
    """Test direct execution methods for ListProcessor."""

    @pytest.mark.asyncio
    async def test_execute_create_success(self, list_processor, mock_supabase):
        """Test successful list creation via direct execution."""
        # Setup mock response
        mock_response = Mock()
        mock_response.data = [
            {"id": "list-123", "name": "Shopping List", "type": "Shopping List"}
        ]
        mock_supabase.execute.return_value = mock_response

        # Execute
        result = await list_processor.execute_direct(
            operation="create",
            extracted_data={
                "list_name": "Shopping List",
                "list_type": "Shopping List",
                "items": ["Milk", "Bread", "Eggs"],
            },
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "Shopping List" in result["message"]
        assert "3 items" in result["message"]
        assert result["list_id"] == "list-123"
        assert result["execution_time"] < 0.5  # Should be under 500ms

    @pytest.mark.asyncio
    async def test_execute_add_items_success(self, list_processor, mock_supabase):
        """Test adding items to an existing list."""
        # Setup mock responses
        find_response = Mock()
        find_response.data = [{"id": "list-123", "name": "Shopping List"}]

        insert_response = Mock()
        insert_response.data = [
            {"id": "item-1", "content": "Butter"},
            {"id": "item-2", "content": "Cheese"},
        ]

        mock_supabase.execute.side_effect = [find_response, insert_response]

        # Execute
        result = await list_processor.execute_direct(
            operation="add_items",
            extracted_data={
                "list_name": "Shopping List",
                "items": ["Butter", "Cheese"],
            },
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "Added 2 items" in result["message"]
        assert result["list_id"] == "list-123"
        assert result["items_added"] == 2
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_add_items_list_not_found(
        self, list_processor, mock_supabase
    ):
        """Test adding items when list is not found."""
        # Setup mock response with no data
        mock_response = Mock()
        mock_response.data = []
        mock_supabase.execute.return_value = mock_response

        # Execute
        result = await list_processor.execute_direct(
            operation="add_items",
            extracted_data={"list_name": "Nonexistent List", "items": ["Item1"]},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is False
        assert "not found" in result["error"]
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_remove_items_success(self, list_processor, mock_supabase):
        """Test removing items from a list."""
        # Setup mock responses
        find_response = Mock()
        find_response.data = [{"id": "list-123", "name": "Shopping List"}]

        delete_response = Mock()
        delete_response.data = [{"id": "item-1"}]

        mock_supabase.execute.side_effect = [find_response, delete_response]

        # Execute
        result = await list_processor.execute_direct(
            operation="remove_items",
            extracted_data={"list_name": "Shopping List", "items": ["Milk"]},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "Removed" in result["message"]
        assert result["list_id"] == "list-123"
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_rename_success(self, list_processor, mock_supabase):
        """Test renaming a list."""
        # Setup mock responses
        find_response = Mock()
        find_response.data = [{"id": "list-123", "name": "Old Name"}]

        update_response = Mock()
        update_response.data = [{"id": "list-123", "name": "New Name"}]

        mock_supabase.execute.side_effect = [find_response, update_response]

        # Execute
        result = await list_processor.execute_direct(
            operation="rename",
            extracted_data={
                "current_list_name": "Old Name",
                "new_list_name": "New Name",
            },
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "renamed to 'New Name'" in result["message"]
        assert result["list_id"] == "list-123"
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_clear_success(self, list_processor, mock_supabase):
        """Test clearing all items from a list."""
        # Setup mock responses
        find_response = Mock()
        find_response.data = [{"id": "list-123", "name": "Shopping List"}]

        delete_response = Mock()
        delete_response.data = []  # Empty after clearing

        mock_supabase.execute.side_effect = [find_response, delete_response]

        # Execute
        result = await list_processor.execute_direct(
            operation="clear",
            extracted_data={"list_name": "Shopping List"},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "Cleared all items" in result["message"]
        assert result["list_id"] == "list-123"
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_read_success(self, list_processor, mock_supabase):
        """Test reading a list and its items."""
        # Setup mock responses
        find_list = Mock()
        find_list.data = [
            {"id": "list-123", "name": "Shopping List", "type": "Shopping List"}
        ]

        get_items = Mock()
        get_items.data = [
            {"id": "item-1", "content": "Milk", "is_completed": False},
            {"id": "item-2", "content": "Bread", "is_completed": True},
        ]

        mock_supabase.execute.side_effect = [find_list, get_items]

        # Execute
        result = await list_processor.execute_direct(
            operation="read",
            extracted_data={
                "list_name": "Shopping List",
                "filters": {"show_completed": True},
            },
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "2 items" in result["message"]
        assert result["list"]["name"] == "Shopping List"
        assert len(result["items"]) == 2
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_read_all_lists(self, list_processor, mock_supabase):
        """Test reading all lists when no specific list is requested."""
        # Setup mock responses - first call returns no specific list
        find_list = Mock()
        find_list.data = []

        all_lists = Mock()
        all_lists.data = [
            {"id": "list-1", "name": "List 1"},
            {"id": "list-2", "name": "List 2"},
        ]

        mock_supabase.execute.side_effect = [find_list, all_lists]

        # Execute
        result = await list_processor.execute_direct(
            operation="read",
            extracted_data={"list_name": "nonexistent"},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "Found 2 lists" in result["message"]
        assert len(result["lists"]) == 2
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_delete_success(self, list_processor, mock_supabase):
        """Test deleting a list."""
        # Setup mock responses
        find_response = Mock()
        find_response.data = [{"id": "list-123", "name": "Shopping List"}]

        delete_items = Mock()
        delete_items.data = []

        delete_list = Mock()
        delete_list.data = [{"id": "list-123"}]

        mock_supabase.execute.side_effect = [find_response, delete_items, delete_list]

        # Execute
        result = await list_processor.execute_direct(
            operation="delete",
            extracted_data={"list_name": "Shopping List"},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "deleted" in result["message"]
        assert result["list_id"] == "list-123"
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_invalid_operation(self, list_processor):
        """Test handling of invalid operation."""
        result = await list_processor.execute_direct(
            operation="invalid_op", extracted_data={}, user_id="user-123"
        )

        assert result["success"] is False
        assert "Unknown operation" in result["error"]
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_validation_failure(self, list_processor):
        """Test validation failure handling."""
        # Reset validation to return failure
        list_processor.validate_operation = AsyncMock(
            return_value=(False, "Missing required fields: list_name")
        )

        # Missing required field
        result = await list_processor.execute_direct(
            operation="create",
            extracted_data={},  # Missing list_name
            user_id="user-123",
        )

        assert result["success"] is False
        assert "Missing required fields" in result["error"]
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_performance_under_500ms(self, list_processor, mock_supabase):
        """Test that all operations complete under 500ms."""
        # Setup mock response
        mock_response = Mock()
        mock_response.data = [{"id": "list-123", "name": "Test List"}]
        mock_supabase.execute.return_value = mock_response

        operations = ["create", "read"]

        for operation in operations:
            result = await list_processor.execute_direct(
                operation=operation,
                extracted_data={"list_name": "Test List"},
                user_id="user-123",
            )

            assert (
                result["execution_time"] < 0.5
            ), f"{operation} took {result['execution_time']}s"

    @pytest.mark.asyncio
    async def test_error_handling(self, list_processor, mock_supabase):
        """Test error handling in direct execution."""
        # Setup mock to raise an exception
        mock_supabase.execute.side_effect = Exception("Database error")

        result = await list_processor.execute_direct(
            operation="create",
            extracted_data={"list_name": "Test List"},
            user_id="user-123",
        )

        assert result["success"] is False
        assert "Failed to create list" in result["error"]
        assert result["execution_time"] < 0.5
