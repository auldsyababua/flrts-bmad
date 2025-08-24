#!/usr/bin/env python3
"""
Anti-Mesa Test Runner for FLRTS Processors

This script runs all anti-mesa pattern tests with comprehensive reporting.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def run_anti_mesa_tests():
    """Run all anti-mesa pattern tests with detailed reporting."""

    print("=" * 80)
    print("FLRTS Anti-Mesa Pattern Test Suite")
    print("=" * 80)
    print(f"Started at: {datetime.now().isoformat()}")
    print()

    # Define test files
    test_files = [
        "test_task_processor_anti_mesa.py",
        "test_list_processor_anti_mesa.py",
        "test_field_report_processor_anti_mesa.py",
    ]

    # Test configuration
    pytest_args = [
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--strict-markers",  # Strict marker checking
        "--color=yes",  # Colored output
        "-x",  # Stop on first failure (remove for full run)
        "--maxfail=10",  # Stop after 10 failures
        "--durations=10",  # Show 10 slowest tests
        "--html=anti_mesa_report.html",  # HTML report (requires pytest-html)
        "--self-contained-html",  # Include CSS/JS in HTML
        "--json-report",  # JSON report (requires pytest-json-report)
        "--json-report-file=anti_mesa_results.json",
        "--cov=src.rails.processors",  # Coverage for processors
        "--cov-report=term-missing",  # Show missing lines
        "--cov-report=html:htmlcov_anti_mesa",  # HTML coverage report
        "--cov-fail-under=80",  # Fail if coverage < 80%
    ]

    # Add test files to arguments
    for test_file in test_files:
        test_path = Path(__file__).parent / test_file
        if test_path.exists():
            pytest_args.append(str(test_path))
        else:
            print(f"Warning: Test file not found: {test_file}")

    # Run tests
    print("Running tests with arguments:", " ".join(pytest_args))
    print("-" * 80)

    exit_code = pytest.main(pytest_args)

    print("-" * 80)
    print(f"Completed at: {datetime.now().isoformat()}")

    # Print summary
    if exit_code == 0:
        print("\n✅ All anti-mesa tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code: {exit_code}")

    # Try to load and display JSON results if available
    try:
        with open("anti_mesa_results.json", "r") as f:
            results = json.load(f)

        print("\n" + "=" * 80)
        print("Test Summary:")
        print(f"  Total tests: {results['summary']['total']}")
        print(f"  Passed: {results['summary']['passed']}")
        print(f"  Failed: {results['summary']['failed']}")
        print(f"  Skipped: {results['summary'].get('skipped', 0)}")
        print(f"  Duration: {results['duration']:.2f} seconds")

        # Show failed tests if any
        if results["summary"]["failed"] > 0:
            print("\nFailed Tests:")
            for test in results["tests"]:
                if test["outcome"] == "failed":
                    print(f"  - {test['nodeid']}")
                    if "call" in test and "longrepr" in test["call"]:
                        print(f"    Error: {test['call']['longrepr'][:200]}...")

    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # JSON report not available or parsing failed
        pass

    print("=" * 80)

    return exit_code


def run_specific_test(test_name):
    """Run a specific anti-mesa test."""

    print(f"Running specific test: {test_name}")

    pytest_args = [
        "-v",
        "--tb=short",
        "-k",
        test_name,  # Run only tests matching this name
        "--color=yes",
    ]

    # Add all test files
    test_files = [
        "test_task_processor_anti_mesa.py",
        "test_list_processor_anti_mesa.py",
        "test_field_report_processor_anti_mesa.py",
    ]

    for test_file in test_files:
        test_path = Path(__file__).parent / test_file
        if test_path.exists():
            pytest_args.append(str(test_path))

    return pytest.main(pytest_args)


def run_property_tests_only():
    """Run only property-based tests."""

    print("Running property-based tests only...")

    pytest_args = [
        "-v",
        "--tb=short",
        "-k",
        "property",  # Run only property tests
        "--hypothesis-show-statistics",  # Show hypothesis statistics
        "--color=yes",
    ]

    # Add all test files
    test_files = [
        "test_task_processor_anti_mesa.py",
        "test_list_processor_anti_mesa.py",
        "test_field_report_processor_anti_mesa.py",
    ]

    for test_file in test_files:
        test_path = Path(__file__).parent / test_file
        if test_path.exists():
            pytest_args.append(str(test_path))

    return pytest.main(pytest_args)


def run_concurrent_tests_only():
    """Run only concurrent/race condition tests."""

    print("Running concurrent tests only...")

    pytest_args = [
        "-v",
        "--tb=short",
        "-k",
        "concurrent",  # Run only concurrent tests
        "--color=yes",
    ]

    # Add all test files
    test_files = [
        "test_task_processor_anti_mesa.py",
        "test_list_processor_anti_mesa.py",
        "test_field_report_processor_anti_mesa.py",
    ]

    for test_file in test_files:
        test_path = Path(__file__).parent / test_file
        if test_path.exists():
            pytest_args.append(str(test_path))

    return pytest.main(pytest_args)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--property":
            exit_code = run_property_tests_only()
        elif sys.argv[1] == "--concurrent":
            exit_code = run_concurrent_tests_only()
        elif sys.argv[1] == "--test":
            if len(sys.argv) > 2:
                exit_code = run_specific_test(sys.argv[2])
            else:
                print("Please specify a test name")
                exit_code = 1
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Usage:")
            print("  python run_anti_mesa_tests.py          # Run all tests")
            print(
                "  python run_anti_mesa_tests.py --property  # Run property tests only"
            )
            print(
                "  python run_anti_mesa_tests.py --concurrent  # Run concurrent tests only"
            )
            print("  python run_anti_mesa_tests.py --test <name>  # Run specific test")
            exit_code = 1
    else:
        exit_code = run_anti_mesa_tests()

    sys.exit(exit_code)
