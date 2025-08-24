"""Integration test configuration and fixtures."""

import asyncio
import os

import pytest

# Import all fixtures from the fixtures module
from tests.fixtures.database import (
    db_manager,
    list_processor,
    supabase_test_client,
    task_processor,
    test_database_config,
    test_personnel,
    test_site,
    vector_store_cleanup,
)

# Make fixtures available to all integration tests
__all__ = [
    "test_database_config",
    "supabase_test_client",
    "db_manager",
    "task_processor",
    "list_processor",
    "test_personnel",
    "test_site",
    "vector_store_cleanup",
]


@pytest.fixture(autouse=True, scope="session")
def integration_test_environment():
    """Set up integration test environment variables."""

    # Ensure integration test environment is configured
    required_env_vars = ["TEST_SUPABASE_URL", "TEST_SUPABASE_ANON_KEY"]

    # Check if we're using test environment or fallback to main
    test_env_available = all(os.getenv(var) for var in required_env_vars)
    main_env_available = all(
        os.getenv(var.replace("TEST_", "")) for var in required_env_vars
    )

    if not test_env_available and not main_env_available:
        pytest.skip(
            "Integration tests require either TEST_SUPABASE_URL + TEST_SUPABASE_ANON_KEY "
            "or SUPABASE_URL + SUPABASE_ANON_KEY environment variables"
        )

    if not test_env_available:
        print("\nWarning: Using production database for integration tests!")
        print("Set TEST_SUPABASE_URL and TEST_SUPABASE_ANON_KEY for safer testing.")

    yield


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def integration_test_isolation():
    """
    Ensure test isolation for integration tests.

    This fixture runs before and after each integration test to ensure
    clean state and prevent test contamination.
    """
    # Pre-test setup
    yield

    # Post-test cleanup is handled by individual fixtures like db_manager


# Pytest markers for different test categories
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may be slow)"
    )
    config.addinivalue_line(
        "markers", "database: marks tests that require database access"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests that measure performance"
    )
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""

    for item in items:
        # Add integration marker to all tests in integration directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Add database marker to tests that use database fixtures
        if any(
            fixture in item.fixturenames
            for fixture in [
                "db_manager",
                "supabase_test_client",
                "task_processor",
                "list_processor",
            ]
        ):
            item.add_marker(pytest.mark.database)


# Integration test command line options
def pytest_addoption(parser):
    """Add custom command line options for integration tests."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests (requires database setup)",
    )

    parser.addoption(
        "--integration-only",
        action="store_true",
        default=False,
        help="run only integration tests",
    )

    parser.addoption(
        "--skip-performance",
        action="store_true",
        default=False,
        help="skip performance tests (they can be slow)",
    )


def pytest_runtest_setup(item):
    """Set up test execution based on markers and command line options."""

    # Skip integration tests unless explicitly requested
    if item.get_closest_marker("integration"):
        if not item.config.getoption("--run-integration") and not item.config.getoption(
            "--integration-only"
        ):
            pytest.skip(
                "Integration tests require --run-integration or --integration-only flag"
            )

    # Skip non-integration tests if integration-only is specified
    if item.config.getoption("--integration-only"):
        if not item.get_closest_marker("integration"):
            pytest.skip("Skipping non-integration test (--integration-only specified)")

    # Skip performance tests if requested
    if item.get_closest_marker("performance"):
        if item.config.getoption("--skip-performance"):
            pytest.skip("Performance tests skipped (--skip-performance specified)")


@pytest.fixture
def integration_test_metadata():
    """Provide metadata about integration test environment."""
    return {
        "test_database_url": os.getenv("TEST_SUPABASE_URL", "Not configured"),
        "using_production_db": not bool(os.getenv("TEST_SUPABASE_URL")),
        "test_prefix": "TEST_",
        "cleanup_enabled": True,
    }
