"""
Shared fixtures and utilities for anti-mesa pattern testing.

This module provides reusable test fixtures, mock generators, and
utility functions for comprehensive processor testing.
"""

import asyncio
import json
import random
import string
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock


class MockSupabaseClient:
    """
    Advanced mock Supabase client with failure injection capabilities.

    Features:
    - Configurable failure modes (timeout, error, partial write)
    - Latency simulation
    - Data consistency tracking
    - Query recording for verification
    """

    def __init__(self):
        """Initialize the mock client."""
        self.table_name = None
        self.query_chain = []
        self.data_store = {}
        self.query_history = []

        # Failure injection controls
        self.failure_mode = None
        self.failure_probability = 0.0
        self.latency_ms = 0
        self.partial_write_after = None
        self.timeout_after_ms = None

        # Statistics
        self.total_queries = 0
        self.failed_queries = 0
        self.successful_queries = 0

    def table(self, name: str):
        """Mock table selection."""
        self.table_name = name
        self.query_chain = [f"table({name})"]
        return self

    def select(self, columns: str = "*"):
        """Mock select operation."""
        self.query_chain.append(f"select({columns})")
        return self

    def insert(self, data: Dict[str, Any]):
        """Mock insert operation."""
        self.query_chain.append(f"insert({json.dumps(data)})")
        return self

    def update(self, data: Dict[str, Any]):
        """Mock update operation."""
        self.query_chain.append(f"update({json.dumps(data)})")
        return self

    def delete(self):
        """Mock delete operation."""
        self.query_chain.append("delete()")
        return self

    def eq(self, column: str, value: Any):
        """Mock equality filter."""
        self.query_chain.append(f"eq({column}, {value})")
        return self

    def neq(self, column: str, value: Any):
        """Mock not-equal filter."""
        self.query_chain.append(f"neq({column}, {value})")
        return self

    def gt(self, column: str, value: Any):
        """Mock greater-than filter."""
        self.query_chain.append(f"gt({column}, {value})")
        return self

    def gte(self, column: str, value: Any):
        """Mock greater-than-or-equal filter."""
        self.query_chain.append(f"gte({column}, {value})")
        return self

    def lt(self, column: str, value: Any):
        """Mock less-than filter."""
        self.query_chain.append(f"lt({column}, {value})")
        return self

    def lte(self, column: str, value: Any):
        """Mock less-than-or-equal filter."""
        self.query_chain.append(f"lte({column}, {value})")
        return self

    def order(self, column: str, ascending: bool = True):
        """Mock ordering."""
        self.query_chain.append(f"order({column}, {ascending})")
        return self

    def limit(self, count: int):
        """Mock limit."""
        self.query_chain.append(f"limit({count})")
        return self

    async def execute(self):
        """Execute the mock query with failure injection."""
        self.total_queries += 1
        self.query_history.append(" -> ".join(self.query_chain))

        # Simulate latency
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

        # Check for timeout
        if self.timeout_after_ms and self.total_queries * 100 > self.timeout_after_ms:
            self.failed_queries += 1
            raise TimeoutError(f"Query timeout after {self.timeout_after_ms}ms")

        # Random failure injection
        if self.failure_probability > 0 and random.random() < self.failure_probability:
            self.failed_queries += 1
            if self.failure_mode == "timeout":
                raise TimeoutError("Injected timeout failure")
            elif self.failure_mode == "500":
                raise Exception("Internal Server Error (500)")
            elif self.failure_mode == "network":
                raise ConnectionError("Network connection failed")
            else:
                raise Exception("Generic database failure")

        # Partial write simulation
        if self.partial_write_after and self.total_queries > self.partial_write_after:
            self.failed_queries += 1
            raise Exception("Partial write failure")

        # Return mock response
        self.successful_queries += 1
        response = MagicMock()
        response.data = self._get_mock_data()
        response.error = None
        return response

    def _get_mock_data(self) -> List[Dict[str, Any]]:
        """Generate mock data based on table and query."""
        if self.table_name == "sites":
            return [
                {"site_name": "Eagle Lake", "id": 1},
                {"site_name": "Crockett", "id": 2},
                {"site_name": "Mathis", "id": 3},
            ]
        elif self.table_name == "personnel":
            return [
                {
                    "id": 1,
                    "first_name": "John",
                    "aliases": ["johnny", "j"],
                    "is_active": True,
                },
                {
                    "id": 2,
                    "first_name": "Jane",
                    "aliases": ["janey"],
                    "is_active": True,
                },
                {"id": 3, "first_name": "Bob", "aliases": [], "is_active": True},
            ]
        elif self.table_name == "tasks":
            return [
                {"id": 1, "title": "Test Task", "status": "To Do"},
                {"id": 2, "title": "Another Task", "status": "In Progress"},
            ]
        elif self.table_name == "lists":
            return [
                {"id": 1, "list_name": "Test List", "list_type": "Shopping List"},
                {
                    "id": 2,
                    "list_name": "Eagle Lake Inventory",
                    "list_type": "Tools Inventory",
                },
            ]
        elif self.table_name == "field_reports":
            return [
                {
                    "id": 1,
                    "site_name": "Eagle Lake",
                    "report_type": "Daily Operational Summary",
                },
                {"id": 2, "site_name": "Crockett", "report_type": "Incident Report"},
            ]
        else:
            return []

    def set_failure_mode(self, mode: str, probability: float = 1.0):
        """Configure failure injection."""
        self.failure_mode = mode
        self.failure_probability = probability

    def set_latency(self, ms: int):
        """Set simulated latency in milliseconds."""
        self.latency_ms = ms

    def reset_stats(self):
        """Reset query statistics."""
        self.total_queries = 0
        self.failed_queries = 0
        self.successful_queries = 0
        self.query_history = []

    def get_stats(self) -> Dict[str, Any]:
        """Get query statistics."""
        return {
            "total_queries": self.total_queries,
            "successful_queries": self.successful_queries,
            "failed_queries": self.failed_queries,
            "failure_rate": self.failed_queries / max(self.total_queries, 1),
            "query_history": self.query_history,
        }


class MockRedisStore:
    """
    Mock Redis store for testing caching behavior.
    """

    def __init__(self):
        """Initialize the mock store."""
        self.data = {}
        self.ttls = {}
        self.operation_count = 0
        self.get_count = 0
        self.set_count = 0
        self.delete_count = 0

    async def get(self, key: str) -> Optional[str]:
        """Get value from store."""
        self.operation_count += 1
        self.get_count += 1

        if key in self.ttls:
            if datetime.now() > self.ttls[key]:
                del self.data[key]
                del self.ttls[key]
                return None

        return self.data.get(key)

    async def set(self, key: str, value: str, ttl: int = None):
        """Set value in store."""
        self.operation_count += 1
        self.set_count += 1

        self.data[key] = value
        if ttl:
            self.ttls[key] = datetime.now() + timedelta(seconds=ttl)

    async def delete(self, key: str):
        """Delete value from store."""
        self.operation_count += 1
        self.delete_count += 1

        self.data.pop(key, None)
        self.ttls.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return key in self.data

    def reset(self):
        """Reset the store."""
        self.data = {}
        self.ttls = {}
        self.operation_count = 0
        self.get_count = 0
        self.set_count = 0
        self.delete_count = 0

    def get_stats(self) -> Dict[str, int]:
        """Get operation statistics."""
        return {
            "total_operations": self.operation_count,
            "gets": self.get_count,
            "sets": self.set_count,
            "deletes": self.delete_count,
            "keys_stored": len(self.data),
        }


def generate_random_data(data_type: str, **kwargs) -> Any:
    """
    Generate random test data of specified type.

    Args:
        data_type: Type of data to generate
        **kwargs: Additional parameters for generation

    Returns:
        Generated test data
    """
    if data_type == "task":
        return {
            "task_title": f"Task {''.join(random.choices(string.ascii_letters, k=10))}",
            "task_description_detailed": f"Description {''.join(random.choices(string.ascii_letters + ' ', k=50))}",
            "assigned_to": random.choice(["John", "Jane", "Bob"]),
            "priority": random.choice(["High", "Medium", "Low"]),
            "due_date": (
                datetime.now() + timedelta(days=random.randint(1, 30))
            ).strftime("%Y-%m-%d"),
        }

    elif data_type == "list":
        return {
            "list_name": f"List {''.join(random.choices(string.ascii_letters, k=8))}",
            "items": [f"Item {i}" for i in range(random.randint(1, 10))],
            "list_type": random.choice(
                ["Shopping List", "Tools Inventory", "Safety Checklist"]
            ),
        }

    elif data_type == "field_report":
        return {
            "site_name": random.choice(["Eagle Lake", "Crockett", "Mathis"]),
            "report_type": random.choice(
                [
                    "Daily Operational Summary",
                    "Incident Report",
                    "Maintenance Log",
                    "Safety Observation",
                ]
            ),
            "report_title_summary": f"Report {''.join(random.choices(string.ascii_letters, k=15))}",
            "report_content_full": f"Content {''.join(random.choices(string.ascii_letters + ' ', k=100))}",
            "report_status": random.choice(["Draft", "Submitted"]),
        }

    elif data_type == "malicious":
        malicious_patterns = [
            "'; DROP TABLE tasks; --",
            "<script>alert('xss')</script>",
            "../../etc/passwd",
            "\x00\x01\x02\x03",
            "A" * 10000,
            '{"__proto__": {"isAdmin": true}}',
        ]
        return random.choice(malicious_patterns)

    else:
        return None


@contextmanager
def chaos_testing(failure_rate: float = 0.1):
    """
    Context manager for chaos testing with random failures.

    Args:
        failure_rate: Probability of failure (0.0 to 1.0)

    Usage:
        with chaos_testing(0.2):
            # 20% chance of random failure
            result = await some_operation()
    """
    if random.random() < failure_rate:
        failure_types = [
            TimeoutError("Chaos: Random timeout"),
            ConnectionError("Chaos: Connection lost"),
            ValueError("Chaos: Invalid value"),
            RuntimeError("Chaos: Runtime error"),
            MemoryError("Chaos: Out of memory"),
        ]
        raise random.choice(failure_types)
    yield


class ConcurrentTestHarness:
    """
    Harness for testing concurrent operations.
    """

    def __init__(self, num_workers: int = 10):
        """Initialize the harness."""
        self.num_workers = num_workers
        self.results = []
        self.errors = []

    async def run_concurrent(self, operation: Callable, *args, **kwargs):
        """
        Run an operation concurrently with multiple workers.

        Args:
            operation: Async function to run
            *args: Arguments for the operation
            **kwargs: Keyword arguments for the operation

        Returns:
            List of results from all workers
        """
        tasks = []
        for i in range(self.num_workers):
            # Create task with unique identifier
            task_args = args
            task_kwargs = {**kwargs, "worker_id": i}
            tasks.append(operation(*task_args, **task_kwargs))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate results and errors
        self.results = [r for r in results if not isinstance(r, Exception)]
        self.errors = [r for r in results if isinstance(r, Exception)]

        return results

    def assert_no_errors(self):
        """Assert that no errors occurred during concurrent execution."""
        if self.errors:
            raise AssertionError(
                f"Concurrent execution had {len(self.errors)} errors: {self.errors}"
            )

    def assert_all_successful(self):
        """Assert that all operations completed successfully."""
        assert (
            len(self.results) == self.num_workers
        ), f"Expected {self.num_workers} results, got {len(self.results)}"
        self.assert_no_errors()


def create_fuzzer(seed: int = None) -> "DataFuzzer":
    """
    Create a data fuzzer for generating edge case inputs.

    Args:
        seed: Random seed for reproducibility

    Returns:
        DataFuzzer instance
    """
    return DataFuzzer(seed)


class DataFuzzer:
    """
    Fuzzer for generating edge case and malformed inputs.
    """

    def __init__(self, seed: int = None):
        """Initialize the fuzzer."""
        if seed:
            random.seed(seed)

        self.mutation_strategies = [
            self._add_special_chars,
            self._add_unicode,
            self._add_control_chars,
            self._make_very_long,
            self._make_empty,
            self._add_sql_injection,
            self._add_xss,
            self._add_path_traversal,
        ]

    def fuzz(self, data: Any) -> Any:
        """
        Apply random mutations to input data.

        Args:
            data: Original data to fuzz

        Returns:
            Fuzzed data
        """
        if isinstance(data, str):
            strategy = random.choice(self.mutation_strategies)
            return strategy(data)
        elif isinstance(data, dict):
            fuzzed = {}
            for key, value in data.items():
                if random.random() < 0.3:  # 30% chance to fuzz each field
                    fuzzed[key] = self.fuzz(value)
                else:
                    fuzzed[key] = value
            return fuzzed
        elif isinstance(data, list):
            return [self.fuzz(item) if random.random() < 0.3 else item for item in data]
        else:
            return data

    def _add_special_chars(self, s: str) -> str:
        """Add special characters to string."""
        special = "!@#$%^&*(){}[]|\\:;\"'<>?,./`~"
        position = random.randint(0, len(s))
        chars = "".join(random.choices(special, k=random.randint(1, 5)))
        return s[:position] + chars + s[position:]

    def _add_unicode(self, s: str) -> str:
        """Add unicode characters to string."""
        unicode_chars = "🔥💀🤖👻🎃😈🦄🌈"
        position = random.randint(0, len(s))
        chars = "".join(random.choices(unicode_chars, k=random.randint(1, 3)))
        return s[:position] + chars + s[position:]

    def _add_control_chars(self, s: str) -> str:
        """Add control characters to string."""
        control = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
        position = random.randint(0, len(s))
        chars = "".join(random.choices(control, k=random.randint(1, 3)))
        return s[:position] + chars + s[position:]

    def _make_very_long(self, s: str) -> str:
        """Make string very long."""
        return s * random.randint(100, 1000)

    def _make_empty(self, s: str) -> str:
        """Make string empty."""
        return ""

    def _add_sql_injection(self, s: str) -> str:
        """Add SQL injection attempt."""
        injections = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "1; DELETE FROM tasks WHERE 1=1; --",
            "' UNION SELECT * FROM passwords --",
        ]
        return s + random.choice(injections)

    def _add_xss(self, s: str) -> str:
        """Add XSS attempt."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(document.cookie)",
            "<iframe src='evil.com'></iframe>",
        ]
        return s + random.choice(xss_payloads)

    def _add_path_traversal(self, s: str) -> str:
        """Add path traversal attempt."""
        traversals = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "file:///etc/passwd",
            "\\\\server\\share\\file",
        ]
        return s + random.choice(traversals)


# Export commonly used fixtures
__all__ = [
    "MockSupabaseClient",
    "MockRedisStore",
    "generate_random_data",
    "chaos_testing",
    "ConcurrentTestHarness",
    "create_fuzzer",
    "DataFuzzer",
]
