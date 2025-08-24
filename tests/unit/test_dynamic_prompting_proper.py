"""Proper tests for Dynamic Prompting with exact value validation.

These tests verify the dynamic prompt generation behavior with exact assertions,
no conditional logic, and meaningful validation of actual prompt content.
"""

from src.rails.dynamic_prompts import DynamicPromptGenerator, PromptContext


class TestPromptGeneration:
    """Test prompt generation produces exact expected content."""

    def test_high_confidence_prompt_exact_length(self):
        """High confidence prompts are EXACTLY 40 characters or less."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="lists",
            operation="create",
            confidence_scores={"entity_confidence": 0.95, "operation_confidence": 0.95},
            missing_fields=["list_name"],
        )

        prompt = generator._generate_minimal_prompt(context)

        # EXACT length check
        assert len(prompt) <= 40, f"Prompt too long: {len(prompt)} chars - '{prompt}'"
        assert prompt == "Extract list_name for lists create."
        assert len(prompt) == 35  # Exact character count

    def test_medium_confidence_prompt_exact_range(self):
        """Medium confidence prompts are BETWEEN 50-200 characters."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="tasks",
            operation="reassign",
            confidence_scores={"entity_confidence": 0.75, "operation_confidence": 0.8},
            missing_fields=["task_id", "new_assignee", "reason"],
        )

        prompt = generator._generate_focused_prompt(context)

        # EXACT range check
        assert 20 <= len(prompt) <= 200, f"Prompt outside range: {len(prompt)} chars"
        assert (
            prompt
            == "Process tasks. operation: reassign. Extract: task_id, new_assignee, reason."
        )
        assert len(prompt) == 75  # Exact character count

    def test_system_prompt_includes_exact_context(self):
        """System prompts include EXACT context information."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="field_reports",
            operation="create",
            extracted_data={
                "assignee": "joel",
                "site": "Eagle Lake",
                "time_references": ["tomorrow", "at 3pm"],
            },
            confidence_scores={"entity_confidence": 0.9, "operation_confidence": 0.7},
        )

        prompt = generator.generate_system_prompt(context)

        # EXACT content checks
        assert "field report documentation" in prompt
        assert "Assignee already identified: joel" in prompt
        assert "Site already identified: Eagle Lake" in prompt
        assert "Time context found: tomorrow, at 3pm" in prompt
        assert "The operation is unclear" in prompt  # Due to 0.7 confidence

    def test_extraction_prompt_exact_fields(self):
        """Extraction prompts list EXACT missing fields."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="tasks",
            operation="create",
            extracted_data={"assignee": "sarah"},
            missing_fields=["task_title", "due_date", "priority"],
        )

        prompt = generator.generate_extraction_prompt(context)

        # EXACT field listing
        assert "Extract the following information for tasks create:" in prompt
        assert "- task_title: (A descriptive title for the task)" in prompt
        assert "- due_date:" in prompt
        assert "- priority:" in prompt
        assert "assignee" not in prompt  # Already extracted, should not appear

    def test_function_calling_prompt_exact_format(self):
        """Function calling prompts have EXACT expected format."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="lists",
            operation="add_items",
            extracted_data={"list_name": "groceries"},
            missing_fields=["items"],
        )

        prompt = generator.generate_function_calling_prompt(context)

        # EXACT format checks
        assert prompt.startswith("Call the update_list function")
        assert "- list_name: groceries" in prompt
        assert "Extract these missing parameters from the message: items" in prompt


class TestDirectExecutionDetermination:
    """Test direct execution logic returns exact expected values."""

    def test_direct_execution_requires_exact_conditions(self):
        """Direct execution returns EXACTLY True/False based on conditions."""
        generator = DynamicPromptGenerator()

        # Case 1: 100% confidence, no missing fields -> True
        context = PromptContext(
            entity_type="lists",
            operation="create",
            confidence_scores={"entity_confidence": 1.0, "operation_confidence": 1.0},
            missing_fields=[],
        )
        assert generator.should_use_direct_execution(context) == True

        # Case 2: 100% confidence, has missing fields -> False
        context.missing_fields = ["list_name"]
        assert generator.should_use_direct_execution(context) == False

        # Case 3: 99% confidence, no missing fields -> False (must be 100%)
        context.confidence_scores = {
            "entity_confidence": 0.99,
            "operation_confidence": 1.0,
        }
        context.missing_fields = []
        assert generator.should_use_direct_execution(context) == False

        # Case 4: No confidence scores -> False
        context.confidence_scores = None
        assert generator.should_use_direct_execution(context) == False

    def test_execution_strategy_exact_thresholds(self):
        """Execution strategy returns EXACT strategy based on thresholds."""
        generator = DynamicPromptGenerator()

        test_cases = [
            # (entity_conf, op_conf, missing_fields, expected_strategy)
            (1.0, 1.0, [], "direct"),
            (0.95, 0.95, [], "direct"),
            (0.95, 0.95, ["field1"], "focused_llm"),  # Has missing fields
            (0.8, 0.9, [], "focused_llm"),
            (0.7, 0.7, [], "full_llm"),
            (0.5, 0.5, ["f1", "f2"], "full_llm"),
        ]

        for entity_conf, op_conf, missing, expected in test_cases:
            context = PromptContext(
                confidence_scores={
                    "entity_confidence": entity_conf,
                    "operation_confidence": op_conf,
                },
                missing_fields=missing,
            )
            strategy = generator.determine_execution_strategy(context)
            assert (
                strategy == expected
            ), f"Conf: {entity_conf}/{op_conf}, missing: {missing} -> expected '{expected}' but got '{strategy}'"


class TestTokenCounting:
    """Test token counting produces exact values."""

    def test_token_estimation_exact_calculation(self):
        """Token counts are EXACTLY as calculated."""
        generator = DynamicPromptGenerator()

        # Direct execution = 0 tokens
        context = PromptContext(
            confidence_scores={"entity_confidence": 1.0, "operation_confidence": 1.0},
            entity_type="lists",
            operation="create",
            missing_fields=[],
        )
        metrics = generator.generate_performance_metrics(context)
        assert metrics["estimated_tokens"] == 0
        assert metrics["execution_strategy"] == "direct"

        # Focused prompt with known content
        context.confidence_scores = {
            "entity_confidence": 0.8,
            "operation_confidence": 0.8,
        }
        context.missing_fields = ["list_name"]
        metrics = generator.generate_performance_metrics(context)

        # Calculate exact expected tokens
        prompt = generator._generate_focused_prompt(context)
        expected_tokens = int(len(prompt.split()) * 1.3)
        assert metrics["estimated_tokens"] == expected_tokens
        assert metrics["execution_strategy"] == "focused_llm"

    def test_metrics_exact_values(self):
        """Performance metrics contain EXACT expected values."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="tasks",
            operation="complete",
            confidence_scores={
                "entity_confidence": 0.85,
                "operation_confidence": 0.92,
                "assignee_confidence": 1.0,
            },
            extracted_data={"assignee": "joel", "task_id": "123"},
            missing_fields=["completion_notes"],
        )

        metrics = generator.generate_performance_metrics(context)

        # EXACT metric values
        assert metrics["execution_strategy"] == "focused_llm"
        assert metrics["confidence_scores"]["entity_confidence"] == 0.85
        assert metrics["confidence_scores"]["operation_confidence"] == 0.92
        assert metrics["confidence_scores"]["assignee_confidence"] == 1.0
        assert metrics["missing_fields_count"] == 1
        assert metrics["has_prefilled_data"] == True
        assert isinstance(metrics["prompt_cached"], bool)
        assert isinstance(metrics["estimated_tokens"], int)
        assert metrics["estimated_tokens"] > 0  # Should have tokens for focused_llm


class TestPromptCaching:
    """Test prompt caching returns IDENTICAL results."""

    def test_cache_returns_exact_same_prompt(self):
        """Cached prompts are EXACTLY identical to original."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="lists",
            operation="add_items",
            confidence_scores={"entity_confidence": 0.9, "operation_confidence": 0.9},
            missing_fields=["items"],
        )

        # First call - not cached
        prompt1 = generator.generate_optimized_system_prompt(context)

        # Second call - should be cached
        prompt2 = generator.generate_optimized_system_prompt(context)

        # Must be exactly the same string
        assert prompt1 == prompt2
        assert prompt1 is prompt2  # Should be the same object from cache

    def test_cache_key_generation_exact(self):
        """Cache keys are generated with EXACT format."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="tasks",
            operation="reassign",
            confidence_scores={"entity_confidence": 0.85, "operation_confidence": 0.73},
            missing_fields=["new_assignee", "reason"],
        )

        key = generator._generate_cache_key(context)

        # EXACT key format: entity:operation:missing_count:entity_conf*10:op_conf*10
        assert key == "tasks:reassign:2:8:7"

        # Different context -> different key
        context.missing_fields = ["new_assignee"]
        key2 = generator._generate_cache_key(context)
        assert key2 == "tasks:reassign:1:8:7"
        assert key != key2

    def test_cache_size_limit_exact(self):
        """Cache size limit is EXACTLY enforced."""
        generator = DynamicPromptGenerator()
        generator._cache_size_limit = 3  # Set small limit for testing

        contexts = []
        for i in range(5):
            context = PromptContext(
                entity_type=f"type{i}",
                operation=f"op{i}",
                confidence_scores={
                    "entity_confidence": 0.5 + i * 0.1,
                    "operation_confidence": 0.5,
                },
            )
            contexts.append(context)
            generator.generate_optimized_system_prompt(context)

        # Cache should have exactly 3 items (the limit)
        assert len(generator._prompt_cache) == 3

        # First 2 contexts should be evicted
        assert generator._generate_cache_key(contexts[0]) not in generator._prompt_cache
        assert generator._generate_cache_key(contexts[1]) not in generator._prompt_cache

        # Last 3 should be in cache
        assert generator._generate_cache_key(contexts[2]) in generator._prompt_cache
        assert generator._generate_cache_key(contexts[3]) in generator._prompt_cache
        assert generator._generate_cache_key(contexts[4]) in generator._prompt_cache


class TestFunctionSchemaGeneration:
    """Test function schema generation with exact structure."""

    def test_function_schema_exact_structure(self):
        """Function schemas have EXACT expected structure."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="lists",
            operation="create",
            extracted_data={"suggested_name": "Groceries"},
        )

        schema = generator._generate_function_schema(context)

        # EXACT schema structure
        assert schema["name"] == "create_list"
        assert schema["parameters"]["type"] == "object"
        assert "list_name" in schema["parameters"]["properties"]
        assert schema["parameters"]["properties"]["list_name"]["type"] == "string"
        assert (
            schema["parameters"]["properties"]["list_name"]["description"]
            == "Name of the list"
        )
        assert schema["parameters"]["required"] == ["list_name"]

        # Check default value injection
        assert (
            "default" not in schema["parameters"]["properties"]["list_name"]
        )  # suggested_name != list_name

    def test_function_schema_with_defaults_exact(self):
        """Function schemas include EXACT default values."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="tasks",
            operation="reassign",
            extracted_data={"task_id": "task-123", "new_assignee": "joel"},
        )

        schema = generator._generate_function_schema(context)

        assert schema["name"] == "update_task"
        assert schema["parameters"]["properties"]["task_id"]["default"] == "task-123"
        assert schema["parameters"]["properties"]["new_assignee"]["default"] == "joel"
        assert schema["parameters"]["required"] == ["task_id", "new_assignee"]

    def test_smart_function_prompt_exact_format(self):
        """Smart function prompts have EXACT format with schema."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="field_reports",
            operation="add_followups",
            missing_fields=["followup_items", "priority", "assigned_to"],
        )

        prompt, schema = generator.generate_smart_function_prompt(context)

        # EXACT prompt format
        assert (
            prompt
            == "Call update_field_report function. Extract: followup_items, priority, assigned_to"
        )
        assert schema["name"] == "update_field_report"
        assert isinstance(schema["parameters"], dict)


class TestContextSummary:
    """Test context summary generation with exact format."""

    def test_context_summary_exact_format(self):
        """Context summaries have EXACT expected format."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="tasks",
            operation="complete",
            confidence_scores={
                "entity_confidence": 0.95,
                "operation_confidence": 0.88,
                "assignee_confidence": 1.0,
            },
            extracted_data={
                "assignee": "sarah",
                "site": "Crockett",
                "command_source": "/completetask",
            },
            has_mentions=True,
            has_commands=True,
        )

        summary = generator.generate_context_summary(context)

        # EXACT format: parts joined by " | "
        parts = summary.split(" | ")
        assert len(parts) == 6
        assert parts[0] == "Entity: tasks"
        assert parts[1] == "Operation: complete"
        assert parts[2] == "Confidence: [entity: 95%, operation: 88%, assignee: 100%]"
        assert parts[3] == "Extracted: assignee=sarah, site=Crockett, cmd=/completetask"
        assert parts[4] == "Has @mentions"
        assert parts[5] == "Has /commands"

    def test_empty_context_summary_exact(self):
        """Empty context produces EXACT message."""
        generator = DynamicPromptGenerator()
        context = PromptContext()

        summary = generator.generate_context_summary(context)
        assert summary == "No preprocessing context"


class TestPromptOptimization:
    """Test prompt optimization produces exact expected results."""

    def test_minimal_prompt_conditions_exact(self):
        """Minimal prompts used at EXACT confidence thresholds."""
        generator = DynamicPromptGenerator()

        # >= 0.9 for both -> minimal
        context = PromptContext(
            entity_type="lists",
            operation="create",
            confidence_scores={"entity_confidence": 0.9, "operation_confidence": 0.9},
            missing_fields=["list_name"],
        )
        assert generator._should_use_minimal_prompt(context) == True

        # 0.89 -> not minimal (must be >= 0.9)
        context.confidence_scores = {
            "entity_confidence": 0.89,
            "operation_confidence": 0.9,
        }
        assert generator._should_use_minimal_prompt(context) == False

    def test_focused_prompt_conditions_exact(self):
        """Focused prompts used at EXACT confidence thresholds."""
        generator = DynamicPromptGenerator()

        # >= 0.7 for either -> focused
        context = PromptContext(
            confidence_scores={"entity_confidence": 0.7, "operation_confidence": 0.6}
        )
        assert generator._should_use_focused_prompt(context) == True

        context.confidence_scores = {
            "entity_confidence": 0.6,
            "operation_confidence": 0.7,
        }
        assert generator._should_use_focused_prompt(context) == True

        # Both < 0.7 -> not focused
        context.confidence_scores = {
            "entity_confidence": 0.69,
            "operation_confidence": 0.69,
        }
        assert generator._should_use_focused_prompt(context) == False


class TestEdgeCasesAndValidation:
    """Test edge cases with exact validation."""

    def test_no_entity_type_exact_handling(self):
        """Missing entity type produces EXACT fallback prompts."""
        generator = DynamicPromptGenerator()

        context = PromptContext()  # No entity or operation

        extraction_prompt = generator.generate_extraction_prompt(context)
        assert (
            extraction_prompt
            == "Extract the entity type (lists, tasks, or field_reports) and operation from the message."
        )

        function_prompt = generator.generate_function_calling_prompt(context)
        assert (
            function_prompt
            == "Determine the appropriate function to call based on the user's intent."
        )

    def test_unresolved_mentions_exact_handling(self):
        """Unresolved mentions produce EXACT guidance."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="tasks",
            operation="create",
            extracted_data={"unresolved_mentions": ["unknownuser", "anotheruser"]},
            missing_fields=["assignee", "task_title"],
        )

        prompt = generator.generate_extraction_prompt(context)

        # Should include note about unresolved mentions
        assert "(Note: unresolved mentions ['unknownuser', 'anotheruser'])" in prompt

    def test_all_fields_extracted_exact_message(self):
        """All fields extracted produces EXACT completion message."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="lists",
            operation="create",
            extracted_data={
                "list_name": "Shopping",
                "items": ["milk", "eggs"],
                "list_type": "grocery",
            },
            missing_fields=[],  # Nothing missing
        )

        prompt = generator.generate_extraction_prompt(context)
        assert prompt == "All required fields have been extracted for lists.create."

    def test_unknown_operation_exact_fallback(self):
        """Unknown operations produce EXACT fallback prompts."""
        generator = DynamicPromptGenerator()

        context = PromptContext(
            entity_type="custom_entity", operation="custom_operation"
        )

        prompt = generator.generate_function_calling_prompt(context)
        assert (
            prompt
            == "Determine the appropriate function for custom_entity.custom_operation."
        )

        # Function schema should use fallback
        schema = generator._generate_function_schema(context)
        assert schema["name"] == "process_command"
