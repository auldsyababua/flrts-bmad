"""
Unit tests for TaskProcessor direct execution functionality.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.rails.processors.task_processor import TaskProcessor


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
def task_processor(mock_supabase):
    """Create TaskProcessor instance with mocked Supabase."""
    processor = TaskProcessor(mock_supabase)
    # Mock the validation to skip database checks
    processor.validate_operation = AsyncMock(return_value=(True, "Valid"))
    return processor


class TestTaskProcessorDirectExecution:
    """Test direct execution methods for TaskProcessor."""

    @pytest.mark.asyncio
    async def test_execute_create_success(self, task_processor, mock_supabase):
        """Test successful task creation via direct execution."""
        # Setup mock response
        mock_response = Mock()
        mock_response.data = [
            {
                "id": "task-123",
                "title": "Test Task",
                "status": "To Do",
                "priority": "Medium",
            }
        ]
        mock_supabase.execute.return_value = mock_response

        # Execute
        result = await task_processor.execute_direct(
            operation="create",
            extracted_data={
                "task_title": "Test Task",
                "task_description_detailed": "Test description",
                "priority": "Medium",
            },
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "Test Task" in result["message"]
        assert result["task_id"] == "task-123"
        assert result["execution_time"] < 0.5  # Should be under 500ms

        # Verify Supabase was called
        mock_supabase.table.assert_called_with("tasks")
        mock_supabase.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_complete_success(self, task_processor, mock_supabase):
        """Test successful task completion via direct execution."""
        # Setup mock responses
        find_response = Mock()
        find_response.data = [
            {"id": "task-123", "title": "Test Task", "status": "To Do"}
        ]

        update_response = Mock()
        update_response.data = [
            {"id": "task-123", "title": "Test Task", "status": "Completed"}
        ]

        mock_supabase.execute.side_effect = [find_response, update_response]

        # Execute
        result = await task_processor.execute_direct(
            operation="complete",
            extracted_data={"task_title": "Test Task", "completion_notes": "Done!"},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "marked as complete" in result["message"]
        assert result["task_id"] == "task-123"
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_complete_task_not_found(self, task_processor, mock_supabase):
        """Test task completion when task is not found."""
        # Setup mock response with no data
        mock_response = Mock()
        mock_response.data = []
        mock_supabase.execute.return_value = mock_response

        # Execute
        result = await task_processor.execute_direct(
            operation="complete",
            extracted_data={"task_title": "Nonexistent Task"},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is False
        assert "not found" in result["error"]
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_reassign_success(self, task_processor, mock_supabase):
        """Test successful task reassignment."""
        # Setup mock responses
        find_task = Mock()
        find_task.data = [
            {"id": "task-123", "title": "Test Task", "assigned_to": "user-old"}
        ]

        find_user = Mock()
        find_user.data = [{"id": "user-new", "first_name": "NewUser", "aliases": []}]

        update_response = Mock()
        update_response.data = [{"id": "task-123"}]

        mock_supabase.execute.side_effect = [find_task, find_user, update_response]

        # Execute
        result = await task_processor.execute_direct(
            operation="reassign",
            extracted_data={"task_title": "Test Task", "new_assignee": "NewUser"},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "reassigned to NewUser" in result["message"]
        assert result["task_id"] == "task-123"
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_reschedule_success(self, task_processor, mock_supabase):
        """Test successful task rescheduling."""
        # Setup mock responses
        find_response = Mock()
        find_response.data = [
            {"id": "task-123", "title": "Test Task", "due_date": "2024-01-01"}
        ]

        update_response = Mock()
        update_response.data = [{"id": "task-123"}]

        mock_supabase.execute.side_effect = [find_response, update_response]

        # Execute
        result = await task_processor.execute_direct(
            operation="reschedule",
            extracted_data={"task_title": "Test Task", "new_due_date": "tomorrow"},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "rescheduled" in result["message"]
        assert result["task_id"] == "task-123"
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_add_notes_success(self, task_processor, mock_supabase):
        """Test adding notes to a task."""
        # Setup mock responses
        find_response = Mock()
        find_response.data = [
            {"id": "task-123", "title": "Test Task", "notes": "Original notes"}
        ]

        update_response = Mock()
        update_response.data = [{"id": "task-123"}]

        mock_supabase.execute.side_effect = [find_response, update_response]

        # Execute
        result = await task_processor.execute_direct(
            operation="add_notes",
            extracted_data={"task_title": "Test Task", "notes": "Additional notes"},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert "Notes added" in result["message"]
        assert result["task_id"] == "task-123"
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_read_success(self, task_processor, mock_supabase):
        """Test reading/listing tasks."""
        # Setup mock response
        mock_response = Mock()
        mock_response.data = [
            {"id": "task-1", "title": "Task 1", "status": "To Do", "priority": "High"},
            {
                "id": "task-2",
                "title": "Task 2",
                "status": "In Progress",
                "priority": "Medium",
            },
        ]
        mock_supabase.execute.return_value = mock_response

        # Execute
        result = await task_processor.execute_direct(
            operation="read",
            extracted_data={"filters": {"status": "To Do"}},
            user_id="user-123",
        )

        # Verify
        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["tasks"]) == 2
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_invalid_operation(self, task_processor):
        """Test handling of invalid operation."""
        result = await task_processor.execute_direct(
            operation="invalid_op", extracted_data={}, user_id="user-123"
        )

        assert result["success"] is False
        assert "Unknown operation" in result["error"]
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_execute_validation_failure(self, task_processor):
        """Test validation failure handling."""
        # Reset validation to return failure
        task_processor.validate_operation = AsyncMock(
            return_value=(False, "Missing required fields: task_title")
        )

        # Missing required field
        result = await task_processor.execute_direct(
            operation="create",
            extracted_data={},  # Missing task_title
            user_id="user-123",
        )

        assert result["success"] is False
        assert "Missing required fields" in result["error"]
        assert result["execution_time"] < 0.5

    @pytest.mark.asyncio
    async def test_parse_date_relative(self, task_processor):
        """Test date parsing for relative dates."""
        today = datetime.utcnow().date().isoformat()
        tomorrow = (datetime.utcnow() + timedelta(days=1)).date().isoformat()
        next_week = (datetime.utcnow() + timedelta(days=7)).date().isoformat()

        assert task_processor._parse_date("today") == today
        assert task_processor._parse_date("tomorrow") == tomorrow
        assert task_processor._parse_date("next week") == next_week

    @pytest.mark.asyncio
    async def test_performance_benchmark(self, task_processor, mock_supabase):
        """Test that operations are benchmarked."""
        with patch(
            "src.rails.processors.task_processor.async_benchmark"
        ) as mock_benchmark:
            # Setup mock response
            mock_response = Mock()
            mock_response.data = [{"id": "task-123"}]
            mock_supabase.execute.return_value = mock_response

            # The decorator should be applied
            assert hasattr(task_processor.execute_direct, "__wrapped__")
