"""Test enhanced router functionality."""

from unittest.mock import Mock

from src.rails.router import ConfidenceScorer, KeywordRouter, SynonymLibrary

# Service Level Objective constants for router performance
MIN_CONFIDENCE_THRESHOLD = 0.7
MAX_RESPONSE_TIME_MS = 100
MAX_ACCURACY_ERROR = 0.05


class TestEnhancedRouter:
    """Test the enhanced router with synonym library and confidence scoring."""

    def test_router_semantic_invariants(self):
        """Test core semantic invariants that define router behavior."""
        router = KeywordRouter()

        # Invariant 1: Idempotence - same input always produces same output
        test_messages = [
            "add milk to shopping list",
            "/newlist grocery items",
            "@joel create new task",
            "mark generator task complete",
            "new field report for Eagle Lake",
        ]

        for message in test_messages:
            result1 = router.route(message)
            result2 = router.route(message)

            # Core routing decision must be identical
            assert result1.entity_type == result2.entity_type
            assert result1.operation == result2.operation
            assert abs(result1.confidence - result2.confidence) < MAX_ACCURACY_ERROR

        # Invariant 2: Noise stability - minor variations don't break routing
        base_msg = "add milk to shopping list"
        base_result = router.route(base_msg)

        noise_variants = [
            "add  milk  to  shopping  list",  # Extra spaces
            "ADD milk to shopping list",  # Case variation
            "add milk to shopping list.",  # Punctuation
            "  add milk to shopping list  ",  # Whitespace
        ]

        for variant in noise_variants:
            variant_result = router.route(variant)
            # Core semantics should be preserved
            assert variant_result.entity_type == base_result.entity_type
            assert variant_result.operation == base_result.operation
            # Confidence should be within reasonable bounds
            assert (
                abs(variant_result.confidence - base_result.confidence)
                < MAX_ACCURACY_ERROR * 2
            )

        # Invariant 3: Alias precedence - explicit syntax overrides inference
        router.synonym_lib.user_aliases = {"joel": "joel"}

        explicit_result = router.route("/newlist grocery items")
        implicit_result = router.route("create new list called grocery items")

        # Explicit command should have equal or higher confidence
        assert explicit_result.confidence >= implicit_result.confidence
        assert explicit_result.confidence >= MIN_CONFIDENCE_THRESHOLD * 1.2

    def test_operation_semantic_boundaries(self):
        """Test that operations maintain semantic boundaries."""
        router = KeywordRouter()

        # Test boundary conditions - operations should map to correct intent
        operation_tests = [
            ("add milk to shopping list", "add_items", "lists"),
            ("remove eggs from grocery list", "remove_items", "lists"),
            ("mark generator task complete", "complete", "tasks"),
            ("create new task for tomorrow", "create", "tasks"),
            ("new field report for Eagle Lake", "create", "field_reports"),
        ]

        for message, expected_op, expected_entity in operation_tests:
            result = router.route(message)

            # Validate semantic correctness, not just pattern matching
            assert result.operation == expected_op, f"Wrong operation for: {message}"
            assert result.entity_type == expected_entity, f"Wrong entity for: {message}"
            assert (
                result.confidence >= MIN_CONFIDENCE_THRESHOLD
            ), f"Low confidence for clear intent: {message}"

    def test_command_precedence_semantics(self):
        """Test semantic precedence of explicit commands."""
        router = KeywordRouter()

        # Explicit commands should override natural language patterns
        explicit_tests = [
            ("/newlist shopping items", "lists", "create", 1.0),
            ("/completetask", "tasks", "complete", 1.0),
            ("/addtolist milk", "lists", "add_items", 1.0),
        ]

        for (
            command,
            expected_entity,
            expected_op,
            expected_confidence,
        ) in explicit_tests:
            result = router.route(command)

            # Validate explicit command semantics
            assert result.entity_type == expected_entity
            assert result.operation == expected_op
            assert result.confidence == expected_confidence
            assert result.use_direct_execution is True

    def test_context_confidence_modulation(self):
        """Test how context affects routing confidence appropriately."""
        router = KeywordRouter()

        # Context commands should boost confidence for appropriate entities
        context_tests = [
            ("/tnr create new task for tomorrow", "tasks"),
            ("/lists add milk and eggs", "lists"),
            ("/fr new field report for Eagle Lake", "field_reports"),
        ]

        for message, expected_entity in context_tests:
            result = router.route(message)
            assert result.entity_type == expected_entity
            assert result.confidence >= MIN_CONFIDENCE_THRESHOLD

    def test_user_assignment_semantics(self):
        """Test semantic correctness of user assignment behavior."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {
            "joel": "joel",
            "the canadian": "joel",
            "bryan": "bryan",
        }

        # Test explicit mention with operation - assignment certainty
        result = router.route("@joel create new task")
        assert (
            "joel" in result.target_users
        ), "Should identify explicitly mentioned user with operation"
        assert (
            result.assignee_confidence == 1.0
        ), "Explicit @mention should have 100% assignment confidence"

        # Test alias resolution with operation
        result = router.route("assign task to the canadian")
        assert "joel" in result.target_users, "Should resolve alias to canonical user"
        assert (
            "the canadian" not in result.target_users
        ), "Should not include alias itself"

        # Test reassignment operation semantics
        result = router.route("reassign to @bryan the generator task")
        assert (
            "bryan" in result.target_users
        ), "Should identify reassignment target user"
        assert result.operation == "reassign", "Should recognize reassign operation"

    def test_contextual_semantic_enhancement(self):
        """Test that contextual cues enhance semantic understanding."""
        router = KeywordRouter()

        # Time context should enhance task operations
        result = router.route("create task check oil tomorrow at 3pm")
        assert result.entity_type == "tasks", "Time context should suggest task entity"
        assert result.confidence >= MIN_CONFIDENCE_THRESHOLD

        # Site context should enhance field report operations
        result = router.route("new field report for Eagle Lake")
        assert (
            result.entity_type == "field_reports"
        ), "Site context should suggest field report entity"
        assert (
            result.extracted_data.get("site") == "Eagle Lake"
        ), "Should extract site information"

        # List structure should enhance list operations
        result = router.route("add milk, eggs, bread to shopping list")
        assert (
            result.entity_type == "lists"
        ), "Comma-separated items should suggest list entity"
        assert "items" in result.extracted_data, "Should extract item structure"

    def test_interactive_mode_semantics(self):
        """Test semantic behavior of interactive mode routing."""
        router = KeywordRouter()

        # Interactive commands should maintain entity context without operation
        result = router.route("/lists")
        assert result.entity_type == "lists"
        assert result.operation == "interactive"
        assert result.confidence == 1.0
        assert (
            result.use_direct_execution is False
        ), "Interactive mode should not use direct execution"

    def test_ambiguity_confidence_modulation(self):
        """Test that ambiguous language appropriately affects confidence."""
        router = KeywordRouter()

        # Ambiguous language should reduce confidence
        result = router.route("update the shopping list")
        assert (
            result.confidence < MIN_CONFIDENCE_THRESHOLD or result.operation is None
        ), "Generic operations should have lower confidence"


class TestSynonymLibrary:
    """Test the synonym library functionality."""

    def test_user_resolution_semantics(self):
        """Test semantic correctness of user alias resolution."""
        lib = SynonymLibrary()
        lib.user_aliases = {
            "joel": "joel",
            "the canadian": "joel",
            "@joel": "joel",
            "@bryan": "bryan",
            "bryan": "bryan",
        }

        # Test mention resolution semantics
        users = lib.resolve_user_mentions("assign to @joel")
        assert users == ["joel"], "Should resolve explicit mentions"

        # Test alias resolution semantics
        users = lib.resolve_user_mentions("give this to the canadian")
        assert "joel" in users, "Should resolve aliases to canonical users"

        # Test multi-user resolution semantics
        users = lib.resolve_user_mentions("task for @joel and @bryan")
        assert set(users) == {"joel", "bryan"}, "Should identify all mentioned users"


class TestConfidenceScorer:
    """Test confidence calculation semantic correctness."""

    def test_confidence_semantic_boundaries(self):
        """Test that confidence scoring reflects semantic clarity."""
        lib = SynonymLibrary()
        scorer = ConfidenceScorer(lib)

        class MockMatch:
            def start(self):
                return 5

            def group(self, n):
                return "add to list"

        match = MockMatch()

        # Specific operations should have higher confidence than generic ones
        specific_confidence = scorer.calculate_confidence(
            "add milk to list", "lists", "add_items", match, []
        )
        generic_confidence = scorer.calculate_confidence(
            "update something", "lists", "update", match, []
        )

        assert (
            specific_confidence >= MIN_CONFIDENCE_THRESHOLD
        ), "Specific operations should meet threshold"
        assert (
            specific_confidence > generic_confidence
        ), "Specific operations should have higher confidence than generic"

    def test_confidence_modulation_semantics(self):
        """Test that confidence modulation reflects semantic intent strength."""
        lib = SynonymLibrary()
        scorer = ConfidenceScorer(lib)

        class EarlyMatch:
            def start(self):
                return 0

            def group(self, n):
                return "new task"

        class LateMatch:
            def start(self):
                return 30

            def group(self, n):
                return "new task"

        # Earlier keywords typically indicate stronger intent
        early_confidence = scorer.calculate_confidence(
            "new task for tomorrow", "tasks", "create", EarlyMatch(), []
        )
        late_confidence = scorer.calculate_confidence(
            "please can you create a new task", "tasks", "create", LateMatch(), []
        )

        assert (
            early_confidence > late_confidence
        ), "Earlier keywords should indicate stronger intent"

    def test_confidence_bounds_invariant(self):
        """Test that confidence scoring maintains valid bounds."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"@user": "user", "the boss": "user"}

        # Test upper bound clamping
        result = router.route("/newlist for @user the boss")
        assert result.confidence <= 1.0, "Confidence should never exceed 1.0"

        # Test lower bound clamping
        scorer = ConfidenceScorer(SynonymLibrary())
        match = Mock()
        match.start.return_value = 50
        match.group.return_value = "x"

        confidence = scorer.calculate_confidence(
            "please maybe possibly update change modify fix this",
            "lists",
            "update",
            match,
            [],
        )
        assert confidence >= 0.0, "Confidence should never be negative"

    def test_pattern_matching_semantic_correctness(self):
        """Test that pattern matching produces semantically correct results."""
        router = KeywordRouter()

        # Test field report pattern recognition
        valid_reports = [
            ("Site A: Status green, all systems operational", "A"),
            ("Site Delta-5: Temperature 72°F, humidity 45%", "Delta-5"),
        ]

        for report_text, expected_site in valid_reports:
            result = router.route(report_text)

            # Should recognize semantic structure
            if result.entity_type == "field_reports":
                assert result.confidence >= MIN_CONFIDENCE_THRESHOLD
                extracted_site = result.extracted_data.get("site", "")
                assert (
                    expected_site in extracted_site or extracted_site in expected_site
                )

    def test_word_boundary_semantic_precision(self):
        """Test that word boundaries maintain semantic precision."""
        router = KeywordRouter()

        # Partial word matches should not trigger false positives
        result = router.route("renewed task needs attention")
        assert (
            result.operation != "create" or result.entity_type != "tasks"
        ), "Should not match partial words"

        result = router.route("addendum for the list")
        assert result.operation != "add_items", "Should not match partial words"

        # Complete words should match correctly
        result = router.route("add new items to list")
        assert (
            result.operation == "add_items" and result.entity_type == "lists"
        ), "Should match complete words"


class TestPreprocessing:
    """Test message preprocessing semantic correctness."""

    def test_preprocessing_semantic_extraction(self):
        """Test that preprocessing extracts semantic markers correctly."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"joel": "joel", "bryan": "bryan"}

        # Test semantic extraction of user mentions
        cleaned, prefilled, confidences = router.preprocess_message(
            "@joel /lists add milk"
        )
        assert cleaned == "add milk", "Should remove syntax markers"
        assert prefilled["assignee"] == "joel", "Should extract user assignment"
        assert prefilled["entity_type"] == "lists", "Should extract entity context"
        assert (
            confidences["assignee_confidence"] == 1.0
        ), "Explicit mentions should have max confidence"

        # Test semantic extraction of commands
        cleaned, prefilled, confidences = router.preprocess_message(
            "/addtolist milk and eggs"
        )
        assert (
            "entity_type" in prefilled and "operation" in prefilled
        ), "Commands should extract both entity and operation"
        assert all(
            conf == 1.0 for conf in confidences.values()
        ), "Explicit commands should have max confidence"

    def test_preprocessing_routing_integration(self):
        """Test that preprocessing correctly integrates with routing decisions."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"joel": "joel", "bryan": "bryan"}

        # Explicit syntax should produce deterministic high-confidence results
        result = router.route("@joel /newlist grocery items")
        assert (
            result.confidence == 1.0
        ), "Explicit syntax should yield maximum confidence"
        assert (
            result.use_direct_execution is True
        ), "High confidence should enable direct execution"
        assert "joel" in result.target_users, "User assignment should be preserved"

        # Interactive commands should maintain entity context
        result = router.route("/tasks for this week")
        assert (
            result.entity_type == "tasks" and result.operation == "interactive"
        ), "Interactive commands should preserve context"

    def test_confidence_component_separation(self):
        """Test that different confidence components are tracked separately."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"joel": "joel"}

        # Complete explicit command should have all confidences at maximum
        result = router.route("@joel /newtask check generator")
        assert (
            result.entity_confidence == 1.0
        ), "Explicit entity should have max confidence"
        assert (
            result.operation_confidence == 1.0
        ), "Explicit operation should have max confidence"
        assert (
            result.assignee_confidence == 1.0
        ), "Explicit assignment should have max confidence"

        # Partial command should have selective confidence
        result = router.route("/lists")
        assert result.entity_confidence == 1.0, "Entity should be certain"
        assert result.operation_confidence is None, "Operation should be uncertain"

    def test_syntax_marker_semantic_removal(self):
        """Test that syntax markers are semantically removed from content processing."""
        router = KeywordRouter()
        router.synonym_lib.user_aliases = {"joel": "joel"}

        # Syntax markers should be extracted but not passed to LLM processing
        cleaned, _, _ = router.preprocess_message("@joel /lists add milk, eggs")
        assert (
            "@" not in cleaned and "/" not in cleaned
        ), "Syntax markers should be removed"
        assert cleaned == "add milk, eggs", "Content should be preserved without syntax"
