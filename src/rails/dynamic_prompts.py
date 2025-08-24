"""Dynamic prompt generation for Smart Rails (Phase 2.1).

This module provides dynamic, context-aware prompt generation based on
preprocessing results, ensuring the LLM receives optimal instructions
for each message type.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PromptContext:
    """Context for dynamic prompt generation."""

    entity_type: Optional[str] = None
    operation: Optional[str] = None
    extracted_data: Dict[str, Any] = None
    confidence_scores: Dict[str, float] = None
    cleaned_message: str = ""
    original_message: str = ""
    has_mentions: bool = False
    has_commands: bool = False
    missing_fields: List[str] = None


class DynamicPromptGenerator:
    """Generates dynamic prompts based on preprocessing results.

    Phase 2.1.2 Enhancement: Advanced dynamic prompting with context-aware
    prompt generation, conditional execution logic, and performance optimization.
    """

    def __init__(self):
        """Initialize the dynamic prompt generator."""
        # Cache for compiled prompts
        self._prompt_cache = {}
        self._cache_size_limit = 50

        self.entity_prompts = {
            "lists": {
                "focus": "list management operations",
                "examples": ["shopping lists", "todo lists", "inventory"],
                "key_fields": ["list_name", "items", "list_type"],
            },
            "tasks": {
                "focus": "task and reminder management",
                "examples": ["maintenance tasks", "reminders", "assignments"],
                "key_fields": ["task_title", "assignee", "due_date", "priority"],
            },
            "field_reports": {
                "focus": "field report documentation",
                "examples": ["site reports", "inspection logs", "incident reports"],
                "key_fields": ["site", "report_content", "report_type", "followups"],
            },
        }

        self.operation_prompts = {
            "create": "Extract all information needed to create a new {entity}",
            "read": "Identify which {entity} to retrieve and any filters",
            "update": "Determine what changes to make to the {entity}",
            "delete": "Identify which {entity} to remove",
            "add_items": "Extract items to add to the specified list",
            "remove_items": "Extract items to remove from the specified list",
            "complete": "Identify the task to mark as complete",
            "reassign": "Identify the task and new assignee",
            "reschedule": "Extract the task and new schedule information",
            "add_notes": "Extract notes to add to the task",
            "add_followups": "Extract followup items for the report",
            "update_status": "Determine the new status for the report",
        }

    def generate_system_prompt(self, context: PromptContext) -> str:
        """Generate a dynamic system prompt based on context.

        T2.1.1: Creates targeted prompts that guide the LLM based on
        what was already extracted during preprocessing.
        """
        base_prompt = "You are a smart assistant helping with "

        # Add entity-specific context if known
        if context.entity_type:
            entity_info = self.entity_prompts.get(context.entity_type, {})
            base_prompt += f"{entity_info.get('focus', context.entity_type)}. "

            # Add operation-specific guidance
            if context.operation:
                op_template = self.operation_prompts.get(
                    context.operation, "Process the {entity} operation"
                )
                base_prompt += op_template.format(entity=context.entity_type) + ". "
        else:
            base_prompt += "various operational tasks. Determine the intent and extract relevant information. "

        # Add extraction guidance based on what's missing
        if context.missing_fields:
            base_prompt += (
                f"\n\nFocus on extracting: {', '.join(context.missing_fields)}. "
            )

        # Add context about preprocessed data
        if context.extracted_data:
            if context.extracted_data.get("assignee"):
                base_prompt += f"\n\nAssignee already identified: {context.extracted_data['assignee']}. "
            if context.extracted_data.get("site"):
                base_prompt += (
                    f"\n\nSite already identified: {context.extracted_data['site']}. "
                )
            if context.extracted_data.get("time_references"):
                base_prompt += f"\n\nTime context found: {', '.join(context.extracted_data['time_references'])}. "

        # Add confidence-based guidance
        if context.confidence_scores:
            if context.confidence_scores.get("entity_confidence", 0) < 0.8:
                base_prompt += "\n\nThe entity type is uncertain. Carefully determine if this is about lists, tasks, or field reports. "
            if context.confidence_scores.get("operation_confidence", 0) < 0.8:
                base_prompt += "\n\nThe operation is unclear. Determine what action the user wants to perform. "

        return base_prompt

    def generate_extraction_prompt(self, context: PromptContext) -> str:
        """Generate a focused extraction prompt.

        T2.1.1: Creates prompts that only ask for missing information,
        avoiding re-extraction of already determined fields.
        """
        if not context.entity_type:
            return "Extract the entity type (lists, tasks, or field_reports) and operation from the message."

        entity_info = self.entity_prompts.get(context.entity_type, {})
        required_fields = entity_info.get("key_fields", [])

        # Filter out already extracted fields
        existing_fields = (
            set(context.extracted_data.keys()) if context.extracted_data else set()
        )
        missing_fields = [f for f in required_fields if f not in existing_fields]

        if not missing_fields:
            return f"All required fields have been extracted for {context.entity_type}.{context.operation}."

        prompt = f"Extract the following information for {context.entity_type} {context.operation}:\n"
        for field in missing_fields:
            prompt += f"- {field}: "

            # Add field-specific guidance
            if field == "assignee" and context.extracted_data.get(
                "unresolved_mentions"
            ):
                prompt += f"(Note: unresolved mentions {context.extracted_data['unresolved_mentions']})"
            elif field == "list_name":
                prompt += "(The name of the list to operate on)"
            elif field == "task_title":
                prompt += "(A descriptive title for the task)"
            elif field == "items":
                prompt += "(List of items, comma-separated)"
            elif field == "site":
                prompt += "(The site name for the report)"

            prompt += "\n"

        return prompt

    def generate_function_calling_prompt(self, context: PromptContext) -> str:
        """Generate a prompt optimized for function calling.

        T2.1.1: Creates prompts that guide the LLM to use the correct
        function with properly formatted parameters.
        """
        if not context.entity_type or not context.operation:
            return (
                "Determine the appropriate function to call based on the user's intent."
            )

        # Map to function names
        function_map = {
            ("lists", "create"): "create_list",
            ("lists", "read"): "read_list",
            ("lists", "add_items"): "update_list",
            ("lists", "remove_items"): "update_list",
            ("lists", "delete"): "delete_list",
            ("tasks", "create"): "create_task",
            ("tasks", "read"): "list_tasks",
            ("tasks", "complete"): "update_task",
            ("tasks", "reassign"): "update_task",
            ("tasks", "reschedule"): "update_task",
            ("field_reports", "create"): "create_field_report",
            ("field_reports", "read"): "read_field_report",
            ("field_reports", "update_status"): "update_field_report",
            ("field_reports", "add_followups"): "update_field_report",
        }

        function_name = function_map.get((context.entity_type, context.operation))

        if not function_name:
            return f"Determine the appropriate function for {context.entity_type}.{context.operation}."

        prompt = f"Call the {function_name} function with the following parameters:\n"

        # Add parameter guidance based on extracted data
        if context.extracted_data:
            for key, value in context.extracted_data.items():
                if key not in [
                    "cleaned_message",
                    "command_source",
                    "preprocessing_extractions",
                ]:
                    prompt += f"- {key}: {value}\n"

        # Note missing required parameters
        if context.missing_fields:
            prompt += f"\nExtract these missing parameters from the message: {', '.join(context.missing_fields)}"

        return prompt

    def should_use_direct_execution(self, context: PromptContext) -> bool:
        """Determine if direct execution should be used.

        T2.1.1: Returns True for 100% confidence routes that should
        bypass the LLM entirely.
        """
        if not context.confidence_scores:
            return False

        # Direct execution for 100% confidence on both entity and operation
        entity_conf = context.confidence_scores.get("entity_confidence", 0)
        operation_conf = context.confidence_scores.get("operation_confidence", 0)

        # Also check if we have all required fields
        has_all_fields = True
        if context.entity_type and context.missing_fields:
            has_all_fields = len(context.missing_fields) == 0

        return entity_conf >= 1.0 and operation_conf >= 1.0 and has_all_fields

    def generate_context_summary(self, context: PromptContext) -> str:
        """Generate a summary of the preprocessing context.

        Useful for logging and debugging.
        """
        summary = []

        if context.entity_type:
            summary.append(f"Entity: {context.entity_type}")
        if context.operation:
            summary.append(f"Operation: {context.operation}")

        if context.confidence_scores:
            conf_items = []
            for key, value in context.confidence_scores.items():
                conf_items.append(f"{key.replace('_confidence', '')}: {value:.0%}")
            if conf_items:
                summary.append(f"Confidence: [{', '.join(conf_items)}]")

        if context.extracted_data:
            extracted = []
            if context.extracted_data.get("assignee"):
                extracted.append(f"assignee={context.extracted_data['assignee']}")
            if context.extracted_data.get("site"):
                extracted.append(f"site={context.extracted_data['site']}")
            if context.extracted_data.get("command_source"):
                extracted.append(f"cmd={context.extracted_data['command_source']}")
            if extracted:
                summary.append(f"Extracted: {', '.join(extracted)}")

        if context.has_mentions:
            summary.append("Has @mentions")
        if context.has_commands:
            summary.append("Has /commands")

        return " | ".join(summary) if summary else "No preprocessing context"

    def generate_optimized_system_prompt(self, context: PromptContext) -> str:
        """Generate highly optimized system prompt for minimal token usage.

        T2.1.2: Creates ultra-focused prompts that minimize token usage
        while maintaining accuracy.
        """
        # Check cache first
        cache_key = self._generate_cache_key(context)
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        # Build minimal prompt based on confidence levels
        if self._should_use_minimal_prompt(context):
            prompt = self._generate_minimal_prompt(context)
        elif self._should_use_focused_prompt(context):
            prompt = self._generate_focused_prompt(context)
        else:
            prompt = self.generate_system_prompt(context)

        # Cache the result
        self._cache_prompt(cache_key, prompt)
        return prompt

    def _should_use_minimal_prompt(self, context: PromptContext) -> bool:
        """Determine if minimal prompt is sufficient.

        T2.1.2: Use minimal prompts for high-confidence scenarios.
        """
        if not context.confidence_scores:
            return False

        entity_conf = context.confidence_scores.get("entity_confidence", 0)
        op_conf = context.confidence_scores.get("operation_confidence", 0)

        # Minimal prompt if we have very high confidence
        return entity_conf >= 0.9 and op_conf >= 0.9

    def _should_use_focused_prompt(self, context: PromptContext) -> bool:
        """Determine if focused prompt should be used.

        T2.1.2: Use focused prompts for medium-confidence scenarios.
        """
        if not context.confidence_scores:
            return False

        entity_conf = context.confidence_scores.get("entity_confidence", 0)
        op_conf = context.confidence_scores.get("operation_confidence", 0)

        # Focused prompt if we have medium confidence
        return entity_conf >= 0.7 or op_conf >= 0.7

    def _generate_minimal_prompt(self, context: PromptContext) -> str:
        """Generate minimal prompt for high-confidence scenarios.

        T2.1.2: Ultra-concise prompts that only ask for missing fields.
        """
        entity = context.entity_type or "operation"
        operation = context.operation or "process"

        # Build minimal prompt
        if context.missing_fields:
            return (
                f"Extract {', '.join(context.missing_fields)} for {entity} {operation}."
            )
        else:
            return f"Execute {entity} {operation} with provided data."

    def _generate_focused_prompt(self, context: PromptContext) -> str:
        """Generate focused prompt for medium-confidence scenarios.

        T2.1.2: Targeted prompts that guide without excess verbosity.
        """
        parts = []

        if context.entity_type:
            parts.append(f"Process {context.entity_type}")
        else:
            parts.append("Determine entity type")

        if context.operation:
            parts.append(f"operation: {context.operation}")
        else:
            parts.append("and operation")

        if context.missing_fields:
            parts.append(
                f"Extract: {', '.join(context.missing_fields[:3])}"
            )  # Limit to 3 fields

        return ". ".join(parts) + "."

    def _generate_cache_key(self, context: PromptContext) -> str:
        """Generate cache key for prompt."""
        key_parts = [
            context.entity_type or "none",
            context.operation or "none",
            str(len(context.missing_fields)) if context.missing_fields else "0",
            (
                str(int(context.confidence_scores.get("entity_confidence", 0) * 10))
                if context.confidence_scores
                else "0"
            ),
            (
                str(int(context.confidence_scores.get("operation_confidence", 0) * 10))
                if context.confidence_scores
                else "0"
            ),
        ]
        return ":".join(key_parts)

    def _cache_prompt(self, key: str, prompt: str):
        """Cache a prompt with size limit enforcement."""
        if len(self._prompt_cache) >= self._cache_size_limit:
            # Remove oldest entry (simple FIFO)
            first_key = next(iter(self._prompt_cache))
            del self._prompt_cache[first_key]
        self._prompt_cache[key] = prompt

    def generate_smart_function_prompt(
        self, context: PromptContext
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Generate smart function calling prompt with schema.

        T2.1.2: Returns both prompt and function schema for direct injection.
        """
        if not context.entity_type or not context.operation:
            return "Analyze the message and determine the appropriate function.", None

        # Generate function-specific schema
        function_schema = self._generate_function_schema(context)

        # Generate targeted prompt
        if context.missing_fields and len(context.missing_fields) > 0:
            prompt = f"Call {function_schema['name']} function. Extract: {', '.join(context.missing_fields[:5])}"
        else:
            prompt = f"Call {function_schema['name']} with the extracted parameters."

        return prompt, function_schema

    def _generate_function_schema(self, context: PromptContext) -> Dict[str, Any]:
        """Generate function schema based on context.

        T2.1.2: Dynamic schema generation for optimal function calling.
        """
        # Map to function names
        function_map = {
            ("lists", "create"): "create_list",
            ("lists", "read"): "read_list",
            ("lists", "add_items"): "update_list",
            ("lists", "remove_items"): "update_list",
            ("lists", "delete"): "delete_list",
            ("tasks", "create"): "create_task",
            ("tasks", "read"): "list_tasks",
            ("tasks", "complete"): "update_task",
            ("tasks", "reassign"): "update_task",
            ("tasks", "reschedule"): "update_task",
            ("field_reports", "create"): "create_field_report",
            ("field_reports", "read"): "read_field_report",
            ("field_reports", "update_status"): "update_field_report",
            ("field_reports", "add_followups"): "update_field_report",
        }

        function_name = function_map.get(
            (context.entity_type, context.operation), "process_command"
        )

        # Build parameter schema dynamically
        parameters: Dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        # Add fields based on entity type and operation
        if context.entity_type == "lists":
            if context.operation == "create":
                parameters["properties"]["list_name"] = {
                    "type": "string",
                    "description": "Name of the list",
                }
                parameters["properties"]["items"] = {
                    "type": "array",
                    "items": {"type": "string"},
                }
                parameters["required"].append("list_name")
            elif context.operation in ["add_items", "remove_items"]:
                parameters["properties"]["list_name"] = {"type": "string"}
                parameters["properties"]["items"] = {
                    "type": "array",
                    "items": {"type": "string"},
                }
                parameters["required"].extend(["list_name", "items"])
        elif context.entity_type == "tasks":
            if context.operation == "create":
                parameters["properties"]["task_title"] = {
                    "type": "string",
                    "description": "Task title",
                }
                parameters["properties"]["assignee"] = {
                    "type": "string",
                    "description": "Person assigned",
                }
                parameters["properties"]["due_date"] = {
                    "type": "string",
                    "description": "Due date",
                }
                parameters["required"].append("task_title")
            elif context.operation == "reassign":
                parameters["properties"]["task_id"] = {"type": "string"}
                parameters["properties"]["new_assignee"] = {"type": "string"}
                parameters["required"].extend(["task_id", "new_assignee"])

        # Add extracted data as defaults
        if context.extracted_data:
            for key, value in context.extracted_data.items():
                if key in parameters["properties"]:
                    parameters["properties"][key]["default"] = value

        return {"name": function_name, "parameters": parameters}

    def determine_execution_strategy(self, context: PromptContext) -> str:
        """Determine the optimal execution strategy.

        T2.1.2: Returns one of: 'direct', 'focused_llm', 'full_llm'
        """
        if not context.confidence_scores:
            return "full_llm"

        entity_conf = context.confidence_scores.get("entity_confidence", 0)
        op_conf = context.confidence_scores.get("operation_confidence", 0)
        assignee_conf = context.confidence_scores.get("assignee_confidence", 0)

        # Direct execution for very high confidence with all required fields
        if entity_conf >= 0.95 and op_conf >= 0.95:
            if not context.missing_fields or len(context.missing_fields) == 0:
                return "direct"
            elif len(context.missing_fields) <= 2 and assignee_conf >= 0.9:
                return "direct"  # Can still execute with minor missing fields

        # Focused LLM for medium-high confidence
        if entity_conf >= 0.8 or op_conf >= 0.8:
            return "focused_llm"

        # Full LLM for low confidence or complex scenarios
        return "full_llm"

    def generate_performance_metrics(self, context: PromptContext) -> Dict[str, Any]:
        """Generate metrics for prompt performance tracking.

        T2.1.2: Track prompt efficiency and optimization opportunities.
        """
        strategy = self.determine_execution_strategy(context)

        # Estimate token usage
        if strategy == "direct":
            estimated_tokens = 0  # No LLM usage
        elif strategy == "focused_llm":
            prompt = self._generate_focused_prompt(context)
            estimated_tokens = int(len(prompt.split()) * 1.3)  # Rough estimate
        else:
            prompt = self.generate_system_prompt(context)
            estimated_tokens = int(len(prompt.split()) * 1.3)

        return {
            "execution_strategy": strategy,
            "estimated_tokens": int(estimated_tokens),
            "confidence_scores": context.confidence_scores or {},
            "missing_fields_count": (
                len(context.missing_fields) if context.missing_fields else 0
            ),
            "has_prefilled_data": bool(context.extracted_data),
            "prompt_cached": self._generate_cache_key(context) in self._prompt_cache,
        }
