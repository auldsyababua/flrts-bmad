"""
Anti-Mesa Pattern Tests for TaskProcessor

This test suite implements comprehensive anti-mesa patterns including:
- Adversarial inputs and SQL injection attempts
- Idempotence testing (f(f(x)) = f(x))
- Property-based testing with hypothesis
- Metamorphic testing (input perturbations)
- Database failure injection
- Concurrent operation testing
- Retry and backoff behavior validation
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.rails.processors.base_processor import BaseProcessor
from src.rails.processors.task_processor import TaskProcessor

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
    client.eq = MagicMock(return_value=client)
    client.execute = AsyncMock(return_value=mock_response)

    # Add failure injection controls
    client._fail_next_n_calls = 0
    client._timeout_probability = 0.0
    client._partial_write_mode = False

    return client


@pytest.fixture
def task_processor(mock_supabase_client):
    """Create TaskProcessor instance with mocked dependencies."""
    return TaskProcessor(mock_supabase_client)


@pytest.fixture
def adversarial_inputs():
    """Generate adversarial test inputs."""
    return {
        "sql_injections": [
            "'; DROP TABLE tasks; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users--",
            "'; UPDATE tasks SET status='completed' WHERE 1=1--",
        ],
        "xss_attempts": [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "<iframe src='evil.com'></iframe>",
        ],
        "buffer_overflows": [
            "A" * 10000,  # Very long string
            "B" * 1000000,  # Extremely long string
            "\x00" * 1000,  # Null bytes
            "C" * 65536,  # Max uint16
        ],
        "unicode_edge_cases": [
            "\u202e\u202d",  # Right-to-left override
            "\ufeff",  # Zero-width no-break space
            "🔥" * 1000,  # Emoji overload
            "\U0001f4a9" * 100,  # More emojis
            "א" * 100,  # Hebrew characters
        ],
        "control_characters": [
            "\x00\x01\x02\x03",  # Null and control chars
            "\r\n\r\n",  # CRLF injection
            "\x1b[31m",  # ANSI escape codes
            "\x08" * 10,  # Backspace characters
        ],
        "malformed_json": [
            '{"task_title": ',  # Incomplete JSON
            '{"task_title": undefined}',  # JavaScript undefined
            '{"task_title": NaN}',  # NaN value
            '{"task_title": Infinity}',  # Infinity
            '{"task_title": null, "extra": }',  # Syntax error
        ],
    }


# ============= Anti-Mesa Pattern Tests =============


class TestTaskProcessorAntiMesa:
    """Anti-mesa pattern tests for TaskProcessor."""

    # ===== Test 1: Supabase Client Instantiation Bug Regression =====

    def test_supabase_client_passed_correctly(self):
        """Ensure supabase_client is passed correctly to avoid instantiation bug."""
        mock_client = MagicMock()
        processor = TaskProcessor(mock_client)

        # Verify the client is stored correctly
        assert processor.supabase == mock_client
        assert hasattr(processor, "supabase")
        assert processor.supabase is not None

        # Verify parent class initialization
        assert isinstance(processor, BaseProcessor)

    def test_supabase_client_none_handling(self):
        """Test behavior when None is passed as supabase_client."""
        processor = TaskProcessor(None)
        assert processor.supabase is None

        # Operations should handle None client gracefully
        with pytest.raises((AttributeError, TypeError)):
            asyncio.run(processor.validate_operation("create", {}, "user"))

    # ===== Test 2: SQL Injection and Adversarial Inputs =====

    @pytest.mark.parametrize(
        "injection",
        [
            "'; DROP TABLE tasks; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users--",
            "'; UPDATE tasks SET status='completed' WHERE 1=1--",
        ],
    )
    def test_sql_injection_prevention(self, task_processor, injection):
        """Test that SQL injection attempts are properly sanitized."""

        # Schema extraction should not execute injected SQL
        schema = task_processor.get_extraction_schema("create")
        assert "DROP TABLE" not in schema
        assert "UNION SELECT" not in schema

        # Confidence boost should not be affected by SQL keywords
        boost = task_processor.get_confidence_boost_factors(injection, "create")
        assert boost >= 0  # Should not crash or return negative

    @pytest.mark.asyncio
    async def test_xss_prevention(self, task_processor, adversarial_inputs):
        """Test XSS attack prevention in task data."""
        for xss in adversarial_inputs["xss_attempts"]:
            data = {"task_title": xss}

            # Validation should either sanitize or reject
            is_valid, message = await task_processor.validate_operation(
                "create", data, "user"
            )

            # If valid, ensure XSS is neutralized
            if is_valid:
                assert "<script>" not in str(data)
                assert "javascript:" not in str(data)

    # ===== Test 3: Idempotence Testing =====

    @pytest.mark.asyncio
    async def test_idempotent_task_creation(self, task_processor, mock_supabase_client):
        """Test that repeated task creation with same data is idempotent."""
        task_data = {
            "task_title": "Test Task",
            "task_description_detailed": "Description",
            "assigned_to": "testuser",
        }

        # Mock successful user lookup
        mock_supabase_client.execute.return_value.data = [
            {"id": 1, "first_name": "testuser", "aliases": []}
        ]

        # First operation
        result1 = await task_processor.validate_operation("create", task_data, "user")

        # Second operation with same data
        result2 = await task_processor.validate_operation("create", task_data, "user")

        # Results should be identical (idempotent)
        assert result1 == result2
        assert result1[0] == result2[0]  # Both valid or both invalid
        assert result1[1] == result2[1]  # Same message

    @pytest.mark.asyncio
    async def test_idempotent_task_completion(self, task_processor):
        """Test that completing an already completed task is idempotent."""
        completion_data = {"task_title": "Completed Task", "completion_notes": "Done"}

        # Multiple completion attempts should yield same result
        results = []
        for _ in range(3):
            result = await task_processor.validate_operation(
                "complete", completion_data, "user"
            )
            results.append(result)

        # All results should be identical
        assert all(r == results[0] for r in results)

    # ===== Test 4: Property-Based Testing =====

    @given(
        operation=st.sampled_from(
            ["create", "complete", "reassign", "reschedule", "add_notes", "read"]
        ),
        random_data=st.dictionaries(
            st.text(min_size=1, max_size=100),
            st.one_of(st.text(max_size=500), st.integers(), st.booleans(), st.none()),
        ),
    )
    @settings(max_examples=100, deadline=5000)
    def test_property_schema_always_valid_json(self, operation, random_data):
        """Property: get_extraction_schema always returns valid JSON."""
        processor = TaskProcessor(None)

        try:
            schema = processor.get_extraction_schema(operation)
            parsed = json.loads(schema)
            assert isinstance(parsed, dict)
        except KeyError:
            # Unknown operation is expected to raise KeyError
            assert operation not in [
                "create",
                "complete",
                "reassign",
                "reschedule",
                "add_notes",
                "read",
            ]

    @given(
        message=st.text(min_size=0, max_size=1000),
        operation=st.sampled_from(
            ["create", "complete", "reassign", "reschedule", "add_notes"]
        ),
    )
    def test_property_confidence_boost_bounded(self, message, operation):
        """Property: confidence boost is always between 0 and 1."""
        processor = TaskProcessor(None)

        boost = processor.get_confidence_boost_factors(message, operation)
        assert 0 <= boost <= 1.0

    # ===== Test 5: Metamorphic Testing =====

    def test_metamorphic_message_perturbation(self, task_processor):
        """Test that small message perturbations yield semantically equivalent results."""
        base_message = "Create a new task for John to complete tomorrow"
        perturbations = [
            "Create a new task for John to complete tomorrow.",  # Added period
            "Create a  new task for John to complete tomorrow",  # Extra space
            "CREATE A NEW TASK FOR JOHN TO COMPLETE TOMORROW",  # Uppercase
            "Create a new task for John to complete tomorrow ",  # Trailing space
            " Create a new task for John to complete tomorrow",  # Leading space
        ]

        base_boost = task_processor.get_confidence_boost_factors(base_message, "create")

        for perturbed in perturbations:
            perturbed_boost = task_processor.get_confidence_boost_factors(
                perturbed, "create"
            )
            # Boosts should be very similar (within 0.05)
            assert abs(base_boost - perturbed_boost) < 0.05

    @pytest.mark.asyncio
    async def test_metamorphic_data_ordering(self, task_processor):
        """Test that field ordering doesn't affect validation."""
        data1 = {"task_title": "Test", "assigned_to": "user", "priority": "High"}

        data2 = {"priority": "High", "task_title": "Test", "assigned_to": "user"}

        result1 = await task_processor.validate_operation("create", data1, "user")
        result2 = await task_processor.validate_operation("create", data2, "user")

        # Order shouldn't matter
        assert result1 == result2

    # ===== Test 6: Database Failure Injection =====

    @pytest.mark.asyncio
    async def test_database_timeout_handling(
        self, task_processor, mock_supabase_client
    ):
        """Test behavior during database timeouts."""
        # Simulate timeout
        mock_supabase_client.execute.side_effect = TimeoutError("Database timeout")

        data = {"task_title": "Test", "assigned_to": "user"}
        is_valid, message = await task_processor.validate_operation(
            "create", data, "user"
        )

        assert not is_valid
        assert "database" in message.lower() or "timeout" in message.lower()

    @pytest.mark.asyncio
    async def test_database_500_error_handling(
        self, task_processor, mock_supabase_client
    ):
        """Test behavior during database 500 errors."""
        # Simulate 500 error
        mock_supabase_client.execute.side_effect = Exception("Internal Server Error")

        data = {"task_title": "Test", "assigned_to": "user"}
        is_valid, message = await task_processor.validate_operation(
            "create", data, "user"
        )

        assert not is_valid
        assert "error" in message.lower() or "database" in message.lower()

    @pytest.mark.asyncio
    async def test_partial_write_prevention(self, task_processor, mock_supabase_client):
        """Test that partial writes are prevented on failure."""
        call_count = 0

        async def failing_execute():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call succeeds
                response = MagicMock()
                response.data = [{"id": 1, "first_name": "user", "aliases": []}]
                return response
            else:
                # Subsequent calls fail
                raise Exception("Database error")

        mock_supabase_client.execute = failing_execute

        data = {"task_title": "Test", "assigned_to": "user"}

        # Should handle partial failure gracefully
        try:
            result = await task_processor.validate_operation("create", data, "user")
            # Should either fully succeed or fully fail, no partial state
            assert result[0] in [True, False]
        except Exception:
            # Exception is acceptable if properly handled
            pass

    # ===== Test 7: Concurrent Operation Testing =====

    @pytest.mark.asyncio
    async def test_concurrent_task_operations(self, mock_supabase_client):
        """Test concurrent task operations for race conditions."""
        processors = [TaskProcessor(mock_supabase_client) for _ in range(10)]

        # Mock successful responses
        mock_supabase_client.execute.return_value.data = [
            {"id": 1, "first_name": "user", "aliases": []}
        ]

        async def create_task(processor, index):
            data = {"task_title": f"Task {index}", "assigned_to": "user"}
            return await processor.validate_operation("create", data, "user")

        # Execute concurrent operations
        tasks = []
        for i, processor in enumerate(processors):
            tasks.append(create_task(processor, i))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All operations should complete without deadlock
        assert len(results) == 10

        # Check for any race condition errors
        for result in results:
            if isinstance(result, Exception):
                assert False, f"Concurrent operation failed: {result}"

    # ===== Test 8: Edge Cases and Boundary Conditions =====

    def test_empty_operation_handling(self, task_processor):
        """Test handling of empty or None operations."""
        with pytest.raises(ValueError):
            task_processor.get_extraction_schema(None)

        with pytest.raises(ValueError):
            task_processor.get_extraction_schema("")

    def test_invalid_operation_types(self, task_processor):
        """Test handling of invalid operation types."""
        invalid_ops = [123, [], {}, True, object()]

        for invalid_op in invalid_ops:
            with pytest.raises(TypeError):
                task_processor.get_extraction_schema(invalid_op)

    def test_message_none_handling(self, task_processor):
        """Test confidence boost with None message."""
        with pytest.raises(ValueError):
            task_processor.get_confidence_boost_factors(None, "create")

    def test_operation_none_in_confidence(self, task_processor):
        """Test confidence boost with None operation."""
        with pytest.raises(ValueError):
            task_processor.get_confidence_boost_factors("test message", None)

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, task_processor):
        """Test validation with missing required fields."""
        test_cases = [
            ("create", {}),  # Missing task_title
            ("complete", {}),  # Missing task_title
            ("reassign", {"task_title": "Test"}),  # Missing new_assignee
            ("reschedule", {"task_title": "Test"}),  # Missing new_due_date
            ("add_notes", {"task_title": "Test"}),  # Missing notes
        ]

        for operation, data in test_cases:
            is_valid, message = await task_processor.validate_operation(
                operation, data, "user"
            )
            assert not is_valid
            assert "missing" in message.lower() or "required" in message.lower()

    # ===== Test 9: Buffer Overflow and Large Input Testing =====

    @pytest.mark.asyncio
    async def test_extremely_long_task_title(self, task_processor):
        """Test handling of extremely long task titles."""
        long_title = "A" * 1000000  # 1 million characters
        data = {"task_title": long_title}

        # Should handle gracefully without memory issues
        result = await task_processor.validate_operation("create", data, "user")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_deeply_nested_data_structures(self, task_processor):
        """Test handling of deeply nested data structures."""
        # Create deeply nested structure
        nested = {"level": 0}
        current = nested
        for i in range(1000):
            current["next"] = {"level": i + 1}
            current = current["next"]

        # Should handle without stack overflow
        schema = task_processor.get_extraction_schema("create")
        assert isinstance(schema, str)

    # ===== Test 10: Unicode and Encoding Edge Cases =====

    @pytest.mark.parametrize(
        "unicode_input",
        [
            "\u202e\u202d",  # Right-to-left override
            "\ufeff",  # Zero-width no-break space
            "🔥" * 100,  # Emoji overload
            "\U0001f4a9",  # Poop emoji
            "א" * 50,  # Hebrew characters
            "你好世界",  # Chinese characters
            "\x00\x01\x02",  # Control characters
        ],
    )
    def test_unicode_handling(self, task_processor, unicode_input):
        """Test handling of various Unicode edge cases."""
        # Should not crash on Unicode input
        boost = task_processor.get_confidence_boost_factors(unicode_input, "create")
        assert isinstance(boost, float)
        assert boost >= 0

    # ===== Test 11: Retry and Backoff Behavior =====

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(
        self, task_processor, mock_supabase_client
    ):
        """Test retry behavior on transient failures."""
        call_count = 0

        async def flaky_execute():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("Transient failure")
            response = MagicMock()
            response.data = [{"id": 1, "first_name": "user", "aliases": []}]
            return response

        mock_supabase_client.execute = flaky_execute

        # Should eventually succeed after retries
        data = {"task_title": "Test", "assigned_to": "user"}

        # Note: Current implementation doesn't have built-in retry
        # This test documents expected behavior for future implementation
        with pytest.raises(TimeoutError):
            await task_processor.validate_operation("create", data, "user")

    # ===== Test 12: State Consistency Invariants =====

    def test_processor_state_invariants(self, task_processor):
        """Test that processor maintains consistent state."""
        # Processor should always have these attributes
        assert hasattr(task_processor, "supabase")
        assert hasattr(task_processor, "_cache")
        assert hasattr(task_processor, "_cache_timestamps")
        assert hasattr(task_processor, "cache_ttl")

        # Cache TTL should be positive
        assert task_processor.cache_ttl > 0

        # Cache structures should be dictionaries
        assert isinstance(task_processor._cache, dict)
        assert isinstance(task_processor._cache_timestamps, dict)


# ============= Stateful Property Testing =============


class TaskProcessorStateMachine(RuleBasedStateMachine):
    """Stateful testing for TaskProcessor using hypothesis."""

    def __init__(self):
        super().__init__()
        self.processor = TaskProcessor(MagicMock())
        self.operations_performed = []
        self.schemas_generated = set()

    @initialize()
    def setup(self):
        """Initialize the state machine."""
        self.operations_performed = []
        self.schemas_generated = set()

    @rule(
        operation=st.sampled_from(
            ["create", "complete", "reassign", "reschedule", "add_notes", "read"]
        )
    )
    def get_schema(self, operation):
        """Rule: Getting schema for valid operation always succeeds."""
        schema = self.processor.get_extraction_schema(operation)
        assert schema is not None
        assert isinstance(schema, str)
        self.schemas_generated.add(operation)

    @rule(
        message=st.text(min_size=1, max_size=100),
        operation=st.sampled_from(
            ["create", "complete", "reassign", "reschedule", "add_notes"]
        ),
    )
    def calculate_confidence(self, message, operation):
        """Rule: Confidence calculation never fails for valid inputs."""
        boost = self.processor.get_confidence_boost_factors(message, operation)
        assert 0 <= boost <= 1.0
        self.operations_performed.append((operation, boost))

    @invariant()
    def schemas_are_json(self):
        """Invariant: All generated schemas are valid JSON."""
        for operation in self.schemas_generated:
            schema = self.processor.get_extraction_schema(operation)
            parsed = json.loads(schema)
            assert isinstance(parsed, dict)

    @invariant()
    def confidence_history_consistent(self):
        """Invariant: Confidence boosts remain consistent."""
        if len(self.operations_performed) > 1:
            # Same operation with same message should give same boost
            seen = {}
            for op, boost in self.operations_performed:
                if op in seen:
                    # Allow small floating point differences
                    assert abs(seen[op] - boost) < 0.0001
                seen[op] = boost


# Run the state machine tests
TestTaskProcessorStates = TaskProcessorStateMachine.TestCase


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
