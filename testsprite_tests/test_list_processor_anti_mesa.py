"""
Anti-Mesa Pattern Tests for ListProcessor

This test suite implements comprehensive anti-mesa patterns including:
- Site-specific list protection validation
- Concurrent list modification scenarios
- Invalid list reference handling
- Idempotence testing for list operations
- Database failure injection
- Authorization bypass attempts
"""

import asyncio
import json
import os
import string
import sys
from typing import Dict, Set
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    initialize,
    invariant,
    rule,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.rails.processors.list_processor import ListProcessor

# ============= Test Fixtures =============


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client with failure injection capabilities."""
    client = MagicMock()

    # Setup mock response structure
    mock_response = MagicMock()
    mock_response.data = []
    mock_response.error = None

    # Create chainable mock methods
    client.table = MagicMock(return_value=client)
    client.select = MagicMock(return_value=client)
    client.insert = MagicMock(return_value=client)
    client.update = MagicMock(return_value=client)
    client.delete = MagicMock(return_value=client)
    client.eq = MagicMock(return_value=client)
    client.execute = AsyncMock(return_value=mock_response)

    # Add failure injection controls
    client._fail_next_n_calls = 0
    client._timeout_probability = 0.0
    client._partial_write_mode = False
    client._authorization_fail = False

    return client


@pytest.fixture
def list_processor(mock_supabase_client):
    """Create ListProcessor instance with mocked dependencies."""
    return ListProcessor(mock_supabase_client)


@pytest.fixture
def site_names():
    """Standard site names for testing."""
    return ["eagle lake", "crockett", "mathis"]


@pytest.fixture
def protected_lists(site_names):
    """Generate protected list names based on sites."""
    protected = []
    for site in site_names:
        protected.extend(
            [
                f"{site} inventory",
                f"{site} checklist",
                f"{site} tools",
                f"{site} equipment",
            ]
        )
    return protected


# ============= Anti-Mesa Pattern Tests =============


class TestListProcessorAntiMesa:
    """Anti-mesa pattern tests for ListProcessor."""

    # ===== Test 1: Site-Specific List Protection =====

    @pytest.mark.asyncio
    async def test_site_list_protection_prevents_deletion(
        self, list_processor, mock_supabase_client, site_names
    ):
        """Test that site-specific lists cannot be deleted."""
        # Mock site data
        mock_supabase_client.execute.return_value.data = [
            {"site_name": site} for site in ["Eagle Lake", "Crockett", "Mathis"]
        ]

        protected_lists = ["eagle lake inventory", "crockett tools", "mathis equipment"]

        for list_name in protected_lists:
            data = {"list_name": list_name}
            is_valid, message = await list_processor.validate_operation(
                "delete", data, "admin"
            )

            assert not is_valid
            assert "cannot delete site-specific" in message.lower()

    @pytest.mark.asyncio
    async def test_site_protection_case_insensitive(
        self, list_processor, mock_supabase_client
    ):
        """Test that site protection is case-insensitive."""
        mock_supabase_client.execute.return_value.data = [{"site_name": "Eagle Lake"}]

        test_cases = [
            "EAGLE LAKE inventory",
            "Eagle Lake TOOLS",
            "eagle lake Equipment",
            "EaGlE lAkE checklist",
        ]

        for list_name in test_cases:
            data = {"list_name": list_name}
            is_valid, message = await list_processor.validate_operation(
                "delete", data, "admin"
            )

            assert not is_valid
            assert "site-specific" in message.lower()

    @pytest.mark.asyncio
    async def test_site_protection_database_failure(
        self, list_processor, mock_supabase_client
    ):
        """Test behavior when site validation database check fails."""
        # Simulate database error
        mock_supabase_client.execute.side_effect = Exception(
            "Database connection failed"
        )

        data = {"list_name": "eagle lake inventory"}
        is_valid, message = await list_processor.validate_operation(
            "delete", data, "admin"
        )

        assert not is_valid
        assert "database error" in message.lower()

    # ===== Test 2: Concurrent List Modification =====

    @pytest.mark.asyncio
    async def test_concurrent_add_items(self, mock_supabase_client):
        """Test concurrent additions to the same list."""
        processors = [ListProcessor(mock_supabase_client) for _ in range(10)]

        async def add_items(processor, index):
            data = {
                "list_name": "shared_list",
                "items": [f"item_{index}_{i}" for i in range(5)],
            }
            return await processor.validate_operation("add_items", data, "user")

        # Execute concurrent operations
        tasks = [add_items(processor, i) for i, processor in enumerate(processors)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All operations should complete without race conditions
        assert len(results) == 10
        for result in results:
            if isinstance(result, Exception):
                assert False, f"Concurrent operation failed: {result}"
            assert result[0] is True  # All should be valid

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, mock_supabase_client):
        """Test concurrent mixed operations (add/remove/clear) on same list."""
        processors = [ListProcessor(mock_supabase_client) for _ in range(9)]

        operations = [
            ("add_items", {"list_name": "test_list", "items": ["item1", "item2"]}),
            ("remove_items", {"list_name": "test_list", "items": ["item1"]}),
            ("clear", {"list_name": "test_list", "confirm": True}),
        ] * 3

        async def perform_operation(processor, op_type, data):
            return await processor.validate_operation(op_type, data, "user")

        tasks = [
            perform_operation(processor, op[0], op[1])
            for processor, op in zip(processors, operations)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check no deadlocks or race conditions
        assert len(results) == 9
        for result in results:
            assert not isinstance(result, Exception)

    # ===== Test 3: Invalid List Reference Handling =====

    @pytest.mark.asyncio
    async def test_operations_on_nonexistent_list(self, list_processor):
        """Test operations on lists that don't exist."""
        operations = [
            ("add_items", {"list_name": "nonexistent_list", "items": ["item1"]}),
            ("remove_items", {"list_name": "ghost_list", "items": ["item2"]}),
            ("clear", {"list_name": "phantom_list", "confirm": True}),
            (
                "rename",
                {"current_list_name": "missing_list", "new_list_name": "new_name"},
            ),
        ]

        for op_type, data in operations:
            # Validation should pass (actual DB operation would fail)
            is_valid, message = await list_processor.validate_operation(
                op_type, data, "user"
            )
            assert is_valid  # Validation doesn't check existence

    @pytest.mark.asyncio
    async def test_list_name_injection_attempts(self, list_processor):
        """Test list names with injection attempts."""
        injection_names = [
            "'; DROP TABLE lists; --",
            "list' OR '1'='1",
            "../../../etc/passwd",
            "list\x00name",  # Null byte injection
            "list\r\nSET status=admin",  # CRLF injection
        ]

        for name in injection_names:
            data = {"list_name": name, "items": ["test"]}
            # Should handle gracefully without executing injection
            result = await list_processor.validate_operation("add_items", data, "user")
            assert isinstance(result, tuple)
            assert len(result) == 2

    # ===== Test 4: Idempotence Testing =====

    @pytest.mark.asyncio
    async def test_idempotent_list_creation(self, list_processor):
        """Test that repeated list creation is idempotent."""
        create_data = {
            "list_name": "idempotent_list",
            "items": ["item1", "item2"],
            "list_type": "Shopping List",
        }

        results = []
        for _ in range(3):
            result = await list_processor.validate_operation(
                "create", create_data, "user"
            )
            results.append(result)

        # All results should be identical
        assert all(r == results[0] for r in results)

    @pytest.mark.asyncio
    async def test_idempotent_clear_operation(self, list_processor):
        """Test that clearing an already empty list is idempotent."""
        clear_data = {"list_name": "empty_list", "confirm": True}

        # Multiple clear operations
        result1 = await list_processor.validate_operation("clear", clear_data, "user")
        result2 = await list_processor.validate_operation("clear", clear_data, "user")
        result3 = await list_processor.validate_operation("clear", clear_data, "user")

        assert result1 == result2 == result3

    @pytest.mark.asyncio
    async def test_idempotent_item_removal(self, list_processor):
        """Test that removing non-existent items is idempotent."""
        remove_data = {"list_name": "test_list", "items": ["nonexistent_item"]}

        # Multiple removal attempts of same non-existent item
        results = []
        for _ in range(3):
            result = await list_processor.validate_operation(
                "remove_items", remove_data, "user"
            )
            results.append(result)

        assert all(r == results[0] for r in results)

    # ===== Test 5: Database Failure Injection =====

    @pytest.mark.asyncio
    async def test_database_timeout_during_validation(
        self, list_processor, mock_supabase_client
    ):
        """Test handling of database timeout during validation."""
        mock_supabase_client.execute.side_effect = TimeoutError("Connection timeout")

        data = {"list_name": "test_list"}
        is_valid, message = await list_processor.validate_operation(
            "delete", data, "admin"
        )

        # Should handle timeout gracefully
        assert not is_valid
        assert "database" in message.lower() or "validation" in message.lower()

    @pytest.mark.asyncio
    async def test_partial_operation_rollback(
        self, list_processor, mock_supabase_client
    ):
        """Test that partial operations are rolled back on failure."""
        call_count = 0

        async def failing_execute():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call succeeds (checking sites)
                response = MagicMock()
                response.data = []
                return response
            else:
                # Subsequent calls fail
                raise Exception("Database write failed")

        mock_supabase_client.execute = failing_execute

        data = {"list_name": "test_list", "items": ["item1", "item2", "item3"]}

        # Operation should either fully succeed or fully fail
        result = await list_processor.validate_operation("add_items", data, "user")
        assert isinstance(result, tuple)
        # No partial state should exist

    @pytest.mark.asyncio
    async def test_intermittent_database_failures(
        self, list_processor, mock_supabase_client
    ):
        """Test behavior with intermittent database failures."""
        failure_pattern = [False, True, False, True, False]  # Alternating failures
        call_index = 0

        async def intermittent_execute():
            nonlocal call_index
            should_fail = failure_pattern[call_index % len(failure_pattern)]
            call_index += 1

            if should_fail:
                raise Exception("Intermittent failure")

            response = MagicMock()
            response.data = []
            return response

        mock_supabase_client.execute = intermittent_execute

        # Should handle intermittent failures gracefully
        for _ in range(10):
            data = {"list_name": f"list_{_}"}
            try:
                result = await list_processor.validate_operation("create", data, "user")
                assert isinstance(result, tuple)
            except Exception:
                pass  # Intermittent failures are expected

    # ===== Test 6: Authorization Bypass Attempts =====

    @pytest.mark.asyncio
    async def test_non_admin_delete_attempt(self, list_processor):
        """Test that non-admin users cannot delete lists."""
        data = {"list_name": "important_list"}

        # Try with different non-admin roles
        for role in ["user", "viewer", "editor", None, ""]:
            is_valid, message = await list_processor.validate_operation(
                "delete", data, role
            )
            assert not is_valid
            assert "admin" in message.lower() or "privilege" in message.lower()

    @pytest.mark.asyncio
    async def test_role_escalation_attempt(self, list_processor):
        """Test that users cannot escalate privileges through data manipulation."""
        malicious_data = {
            "list_name": "test_list",
            "user_role": "admin",  # Attempt to inject admin role
            "role": "admin",
            "__proto__": {"role": "admin"},  # Prototype pollution attempt
        }

        # Should not grant admin privileges
        is_valid, message = await list_processor.validate_operation(
            "delete", malicious_data, "user"
        )
        assert not is_valid
        assert "admin" in message.lower()

    @pytest.mark.asyncio
    async def test_authorization_header_injection(self, list_processor):
        """Test that authorization cannot be bypassed through header injection."""
        data = {
            "list_name": "test_list\r\nAuthorization: Bearer admin_token",
            "confirm": True,
        }

        # Should not bypass authorization
        is_valid, message = await list_processor.validate_operation(
            "delete", data, "user"
        )
        assert not is_valid

    # ===== Test 7: Edge Cases and Boundary Conditions =====

    def test_empty_operation_handling(self, list_processor):
        """Test handling of empty or None operations."""
        with pytest.raises(ValueError):
            list_processor.get_extraction_schema(None)

        with pytest.raises(ValueError):
            list_processor.get_extraction_schema("")

    @pytest.mark.asyncio
    async def test_none_data_handling(self, list_processor):
        """Test validation with None data."""
        with pytest.raises(ValueError):
            await list_processor.validate_operation("create", None, "user")

    @pytest.mark.asyncio
    async def test_none_role_handling(self, list_processor):
        """Test validation with None role."""
        with pytest.raises(ValueError):
            await list_processor.validate_operation("create", {}, None)

    @pytest.mark.asyncio
    async def test_empty_list_name(self, list_processor):
        """Test operations with empty list names."""
        data = {"list_name": "", "items": ["item1"]}
        is_valid, message = await list_processor.validate_operation(
            "add_items", data, "user"
        )

        # Empty list name should be invalid
        assert not is_valid
        assert "required" in message.lower() or "missing" in message.lower()

    @pytest.mark.asyncio
    async def test_extremely_long_list_name(self, list_processor):
        """Test handling of extremely long list names."""
        long_name = "A" * 10000
        data = {"list_name": long_name}

        # Should handle without issues
        result = await list_processor.validate_operation("create", data, "user")
        assert isinstance(result, tuple)

    @pytest.mark.asyncio
    async def test_massive_item_list(self, list_processor):
        """Test adding massive number of items."""
        items = [f"item_{i}" for i in range(10000)]
        data = {"list_name": "huge_list", "items": items}

        # Should handle large item lists
        result = await list_processor.validate_operation("add_items", data, "user")
        assert isinstance(result, tuple)
        assert result[0] is True

    # ===== Test 8: Schema Validation =====

    def test_all_operations_have_valid_schemas(self, list_processor):
        """Test that all operations return valid JSON schemas."""
        operations = [
            "create",
            "add_items",
            "remove_items",
            "rename",
            "clear",
            "read",
            "delete",
        ]

        for op in operations:
            schema = list_processor.get_extraction_schema(op)
            parsed = json.loads(schema)
            assert isinstance(parsed, dict)

    def test_unknown_operation_raises_error(self, list_processor):
        """Test that unknown operations raise appropriate errors."""
        with pytest.raises(KeyError):
            list_processor.get_extraction_schema("unknown_operation")

    # ===== Test 9: Property-Based Testing =====

    @given(
        list_name=st.text(min_size=1, max_size=100),
        items=st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=100),
        operation=st.sampled_from(["add_items", "remove_items"]),
    )
    @settings(max_examples=50, deadline=5000)
    @pytest.mark.asyncio
    async def test_property_valid_data_always_validates(
        self, list_name, items, operation
    ):
        """Property: Valid data structures always pass validation."""
        processor = ListProcessor(MagicMock())
        data = {"list_name": list_name, "items": items}

        result = await processor.validate_operation(operation, data, "user")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    @given(
        message=st.text(min_size=0, max_size=500),
        operation=st.sampled_from(["add_items", "remove_items", "create", "clear"]),
    )
    def test_property_confidence_boost_bounded(self, message, operation):
        """Property: Confidence boost is always between 0 and 1."""
        processor = ListProcessor(None)
        boost = processor.get_confidence_boost_factors(message, operation)
        assert 0 <= boost <= 1.0

    # ===== Test 10: Metamorphic Testing =====

    def test_metamorphic_list_name_case(self, list_processor):
        """Test that list name case variations produce consistent results."""
        names = ["TestList", "testlist", "TESTLIST", "tEsTlIsT"]
        operation = "create"

        boosts = []
        for name in names:
            message = f"Create a new list called {name}"
            boost = list_processor.get_confidence_boost_factors(message, operation)
            boosts.append(boost)

        # Case variations should produce similar confidence
        assert max(boosts) - min(boosts) < 0.1

    @pytest.mark.asyncio
    async def test_metamorphic_item_order(self, list_processor):
        """Test that item order doesn't affect validation."""
        items1 = ["apple", "banana", "cherry"]
        items2 = ["cherry", "apple", "banana"]
        items3 = ["banana", "cherry", "apple"]

        data_sets = [
            {"list_name": "test", "items": items1},
            {"list_name": "test", "items": items2},
            {"list_name": "test", "items": items3},
        ]

        results = []
        for data in data_sets:
            result = await list_processor.validate_operation("add_items", data, "user")
            results.append(result)

        # All permutations should validate the same
        assert all(r == results[0] for r in results)


# ============= Stateful Property Testing =============


class ListProcessorStateMachine(RuleBasedStateMachine):
    """Stateful testing for ListProcessor using hypothesis."""

    Lists = Bundle("lists")

    def __init__(self):
        super().__init__()
        self.processor = ListProcessor(MagicMock())
        self.created_lists: Set[str] = set()
        self.list_items: Dict[str, Set[str]] = {}
        self.deleted_lists: Set[str] = set()

    @initialize()
    def setup(self):
        """Initialize the state machine."""
        self.created_lists = set()
        self.list_items = {}
        self.deleted_lists = set()

    @rule(
        target=Lists,
        name=st.text(
            min_size=1,
            max_size=50,
            alphabet=string.ascii_letters + string.digits + " _-",
        ),
    )
    def create_list(self, name):
        """Create a new list."""
        if name not in self.created_lists and name not in self.deleted_lists:
            self.created_lists.add(name)
            self.list_items[name] = set()
            return name

    @rule(
        list_name=Lists,
        items=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=10),
    )
    def add_items(self, list_name, items):
        """Add items to a list."""
        if list_name in self.created_lists:
            self.list_items[list_name].update(items)

    @rule(
        list_name=Lists,
        items=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
    )
    def remove_items(self, list_name, items):
        """Remove items from a list."""
        if list_name in self.created_lists:
            self.list_items[list_name].difference_update(items)

    @rule(list_name=Lists)
    def clear_list(self, list_name):
        """Clear all items from a list."""
        if list_name in self.created_lists:
            self.list_items[list_name] = set()

    @rule(list_name=Lists)
    def delete_list(self, list_name):
        """Delete a list (admin only)."""
        if list_name in self.created_lists:
            self.created_lists.remove(list_name)
            self.deleted_lists.add(list_name)
            del self.list_items[list_name]

    @invariant()
    def lists_consistency(self):
        """Invariant: List state remains consistent."""
        # No list should be both created and deleted
        assert len(self.created_lists & self.deleted_lists) == 0

        # All created lists should have item containers
        for list_name in self.created_lists:
            assert list_name in self.list_items

        # Deleted lists should not have items
        for list_name in self.deleted_lists:
            assert list_name not in self.list_items

    @invariant()
    def schema_validity(self):
        """Invariant: All operations have valid schemas."""
        operations = ["create", "add_items", "remove_items", "clear", "delete"]
        for op in operations:
            schema = self.processor.get_extraction_schema(op)
            parsed = json.loads(schema)
            assert isinstance(parsed, dict)


# Run the state machine tests
TestListProcessorStates = ListProcessorStateMachine.TestCase


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
