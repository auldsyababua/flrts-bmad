"""Test enhanced router with new phrasing variations for Story 1.5."""

import pytest

from src.rails.router import KeywordRouter


class TestEnhancedPhrasingVariations:
    """Test suite for enhanced natural language phrase recognition."""

    @pytest.fixture
    def router(self):
        """Create a router instance for testing."""
        return KeywordRouter()

    # Task Creation Variations
    def test_task_creation_variations(self, router):
        """Test various natural ways to create tasks."""
        task_creation_phrases = [
            # Traditional phrases
            ("new task check the generator", "tasks", "create", 0.8),
            ("create task for maintenance", "tasks", "create", 0.8),
            ("add task clean filters", "tasks", "create", 0.8),
            # Natural language variations
            ("remind me to call the supplier", "tasks", "create", 0.7),
            ("need to check the pumps tomorrow", "tasks", "create", 0.7),
            ("have to finish the report by Friday", "tasks", "create", 0.7),
            ("must replace the batteries", "tasks", "create", 0.7),
            ("should inspect the site", "tasks", "create", 0.7),
            ("don't forget to order parts", "tasks", "create", 0.7),
            ("remember to submit timesheet", "tasks", "create", 0.7),
            ("make sure to lock the gate", "tasks", "create", 0.7),
            # Casual phrases
            ("todo buy more supplies", "tasks", "create", 0.8),
            ("to do check water levels", "tasks", "create", 0.8),
        ]

        for (
            phrase,
            expected_entity,
            expected_op,
            min_confidence,
        ) in task_creation_phrases:
            result = router.route(phrase)
            assert result.entity_type == expected_entity, f"Failed for: {phrase}"
            assert result.operation == expected_op, f"Failed for: {phrase}"
            assert (
                result.confidence >= min_confidence
            ), f"Confidence too low for: {phrase}"

    # Task Reading Variations
    def test_task_reading_variations(self, router):
        """Test various ways to query tasks."""
        task_reading_phrases = [
            # Traditional phrases
            ("show tasks", "tasks", "read", 0.7),
            ("list tasks", "tasks", "read", 0.7),
            ("my tasks", "tasks", "read", 0.7),
            # Natural variations
            ("show my todos", "tasks", "read", 0.7),
            ("what's on my plate", "tasks", "read", 0.7),
            ("what do i have to do", "tasks", "read", 0.7),
            ("pending tasks", "tasks", "read", 0.7),
            ("active tasks", "tasks", "read", 0.7),
            ("open tasks", "tasks", "read", 0.7),
        ]

        for (
            phrase,
            expected_entity,
            expected_op,
            min_confidence,
        ) in task_reading_phrases:
            result = router.route(phrase)
            assert result.entity_type == expected_entity, f"Failed for: {phrase}"
            assert result.operation == expected_op, f"Failed for: {phrase}"
            assert (
                result.confidence >= min_confidence
            ), f"Confidence too low for: {phrase}"

    # Task Completion Variations
    def test_task_completion_variations(self, router):
        """Test various ways to complete tasks."""
        completion_phrases = [
            # Traditional phrases
            ("mark complete generator task", "tasks", "complete", 0.9),
            ("finish task maintenance", "tasks", "complete", 0.9),
            # Natural variations
            ("done with the inspection", "tasks", "complete", 0.9),
            ("finished checking pumps", "tasks", "complete", 0.9),
            ("completed the report", "tasks", "complete", 0.9),
            ("task done", "tasks", "complete", 0.9),
            ("check off maintenance", "tasks", "complete", 0.9),
            ("mark as done generator check", "tasks", "complete", 0.9),
            ("close task", "tasks", "complete", 0.9),
            ("resolved the issue", "tasks", "complete", 0.9),
        ]

        for phrase, expected_entity, expected_op, min_confidence in completion_phrases:
            result = router.route(phrase)
            assert result.entity_type == expected_entity, f"Failed for: {phrase}"
            assert result.operation == expected_op, f"Failed for: {phrase}"
            assert (
                result.confidence >= min_confidence
            ), f"Confidence too low for: {phrase}"

    # List Creation Variations
    def test_list_creation_variations(self, router):
        """Test various ways to create lists."""
        list_creation_phrases = [
            # Traditional phrases
            ("new list shopping", "lists", "create", 0.8),
            ("create list supplies", "lists", "create", 0.8),
            # Natural variations
            ("make a list for groceries", "lists", "create", 0.8),
            ("start a list of parts needed", "lists", "create", 0.8),
            ("begin list for maintenance items", "lists", "create", 0.8),
            ("list for equipment", "lists", "create", 0.8),
            ("list of supplies", "lists", "create", 0.8),
            ("create grocery list", "lists", "create", 0.8),
            ("create shopping list", "lists", "create", 0.8),
        ]

        for (
            phrase,
            expected_entity,
            expected_op,
            min_confidence,
        ) in list_creation_phrases:
            result = router.route(phrase)
            assert result.entity_type == expected_entity, f"Failed for: {phrase}"
            assert result.operation == expected_op, f"Failed for: {phrase}"
            assert (
                result.confidence >= min_confidence
            ), f"Confidence too low for: {phrase}"

    # List Item Addition Variations
    def test_list_add_items_variations(self, router):
        """Test various ways to add items to lists."""
        add_item_phrases = [
            # Traditional phrases
            ("add milk to shopping list", "lists", "add_items", 0.85),
            ("append eggs to list", "lists", "add_items", 0.85),
            # Natural variations
            ("we need bread", "lists", "add_items", 0.85),
            ("also need batteries", "lists", "add_items", 0.85),
            ("don't forget oil filters", "lists", "add_items", 0.85),
            ("include spare parts", "lists", "add_items", 0.85),
            ("put down generator oil", "lists", "add_items", 0.85),
            ("write down pump seals", "lists", "add_items", 0.85),
            ("add item gloves", "lists", "add_items", 0.85),
            ("add items boots, helmet", "lists", "add_items", 0.85),
        ]

        for phrase, expected_entity, expected_op, min_confidence in add_item_phrases:
            result = router.route(phrase)
            assert result.entity_type == expected_entity, f"Failed for: {phrase}"
            assert result.operation == expected_op, f"Failed for: {phrase}"
            assert (
                result.confidence >= min_confidence
            ), f"Confidence too low for: {phrase}"

    # List Item Removal Variations
    def test_list_remove_items_variations(self, router):
        """Test various ways to remove items from lists."""
        remove_item_phrases = [
            # Traditional phrases
            ("remove milk from list", "lists", "remove_items", 0.85),
            ("take off bread", "lists", "remove_items", 0.85),
            # Natural variations
            ("strike from list", "lists", "remove_items", 0.85),
            ("cross off eggs", "lists", "remove_items", 0.85),
            ("scratch off milk", "lists", "remove_items", 0.85),
            ("we have batteries", "lists", "remove_items", 0.85),
            ("got the oil", "lists", "remove_items", 0.85),
            ("already have filters", "lists", "remove_items", 0.85),
            ("don't need gloves", "lists", "remove_items", 0.85),
            ("no longer need boots", "lists", "remove_items", 0.85),
        ]

        for phrase, expected_entity, expected_op, min_confidence in remove_item_phrases:
            result = router.route(phrase)
            assert result.entity_type == expected_entity, f"Failed for: {phrase}"
            assert result.operation == expected_op, f"Failed for: {phrase}"
            assert (
                result.confidence >= min_confidence
            ), f"Confidence too low for: {phrase}"

    # Task Assignment Variations
    def test_task_assignment_variations(self, router):
        """Test various ways to assign and reassign tasks."""
        assignment_phrases = [
            # Traditional phrases
            ("assign to Joel", "tasks", "reassign", 0.9),
            ("reassign to Bryan", "tasks", "reassign", 0.9),
            # Natural variations
            ("give to Colin", "tasks", "reassign", 0.9),
            ("hand to Joel", "tasks", "reassign", 0.9),
            ("delegate to Bryan", "tasks", "reassign", 0.9),
            ("pass to Colin", "tasks", "reassign", 0.9),
            ("hand off to Joel", "tasks", "reassign", 0.9),
            ("switch to Bryan", "tasks", "reassign", 0.9),
            ("change owner to Colin", "tasks", "reassign", 0.9),
            ("transfer to Joel", "tasks", "reassign", 0.9),
        ]

        for phrase, expected_entity, expected_op, min_confidence in assignment_phrases:
            result = router.route(phrase)
            assert result.entity_type == expected_entity, f"Failed for: {phrase}"
            assert result.operation == expected_op, f"Failed for: {phrase}"
            assert (
                result.confidence >= min_confidence
            ), f"Confidence too low for: {phrase}"

    # Task Rescheduling Variations
    def test_task_rescheduling_variations(self, router):
        """Test various ways to reschedule tasks."""
        reschedule_phrases = [
            # Traditional phrases
            ("reschedule to tomorrow", "tasks", "reschedule", 0.75),
            ("move to next week", "tasks", "reschedule", 0.75),
            # Natural variations
            ("change date to Friday", "tasks", "reschedule", 0.75),
            ("push to Monday", "tasks", "reschedule", 0.75),
            ("defer to next month", "tasks", "reschedule", 0.75),
            ("postpone to tomorrow", "tasks", "reschedule", 0.75),
            ("delay to next week", "tasks", "reschedule", 0.75),
            ("bump to Friday", "tasks", "reschedule", 0.75),
            ("shift to Monday", "tasks", "reschedule", 0.75),
            ("change time to 3pm", "tasks", "reschedule", 0.75),
        ]

        for phrase, expected_entity, expected_op, min_confidence in reschedule_phrases:
            result = router.route(phrase)
            assert result.entity_type == expected_entity, f"Failed for: {phrase}"
            assert result.operation == expected_op, f"Failed for: {phrase}"
            assert (
                result.confidence >= min_confidence
            ), f"Confidence too low for: {phrase}"

    # Complex Natural Language Patterns
    def test_complex_natural_patterns(self, router):
        """Test complex, conversational patterns."""
        complex_phrases = [
            # Multi-part commands
            (
                "remind me to check the generator tomorrow at 3pm",
                "tasks",
                "create",
                0.8,
            ),
            (
                "we need milk, eggs, and bread on the shopping list",
                "lists",
                "add_items",
                0.85,
            ),
            (
                "mark the maintenance task as complete and assign inspection to Joel",
                "tasks",
                "complete",
                0.9,
            ),
            # Contextual phrases
            ("don't forget we need to order parts by Friday", "tasks", "create", 0.8),
            ("make sure Joel knows about the pump maintenance", "tasks", "create", 0.8),
            ("I finished checking all the equipment", "tasks", "complete", 0.9),
        ]

        for phrase, expected_entity, expected_op, min_confidence in complex_phrases:
            result = router.route(phrase)
            assert result.entity_type == expected_entity, f"Failed for: {phrase}"
            assert result.operation == expected_op, f"Failed for: {phrase}"
            assert (
                result.confidence >= min_confidence
            ), f"Confidence too low for: {phrase}"

    # Confidence Score Validation
    def test_confidence_scoring_improvements(self, router):
        """Test that confidence scoring has improved with the enhancements."""

        # Very clear commands should have high confidence
        high_confidence_phrases = [
            "mark complete generator task",
            "delete list shopping",
            "reassign to Joel",
            "done with maintenance",
        ]

        for phrase in high_confidence_phrases:
            result = router.route(phrase)
            assert (
                result.confidence >= 0.85
            ), f"Confidence too low for clear command: {phrase}"

        # Ambiguous phrases should have lower confidence
        low_confidence_phrases = [
            "maybe add milk",
            "could you show tasks",
            "possibly reschedule",
            "what about the generator",
        ]

        for phrase in low_confidence_phrases:
            result = router.route(phrase)
            assert (
                result.confidence < 0.7
            ), f"Confidence too high for ambiguous phrase: {phrase}"

        # Questions should reduce confidence
        question_phrases = [
            "what tasks do I have",
            "when is the maintenance due",
            "who is assigned to generator check",
        ]

        for phrase in question_phrases:
            result = router.route(phrase)
            # Questions might still route but with lower confidence
            if result.entity_type:
                assert (
                    result.confidence < 0.8
                ), f"Confidence too high for question: {phrase}"
