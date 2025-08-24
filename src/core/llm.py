import gc
import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from core.agents import detect_agent_in_message, load_agent_prompt
from core.api_client import RetryConfig, get_resilient_client
from core.benchmarks import async_benchmark, get_performance_monitor
from core.chunking import chunk_markdown_document
from core.config import (CONVERSATION_MAX_MESSAGES, CONVERSATION_TTL_HOURS,
                         GPT_MODEL, MAX_TOKENS, OPENAI_API_KEY, SYSTEM_PROMPT,
                         TEMPERATURE)
from core.memory import bot_memory
from src.rails.dynamic_prompts import DynamicPromptGenerator, PromptContext
from src.rails.router import KeywordRouter, RouteResult
from storage import vector_store
# Legacy tools.py imports removed - production only uses Supabase + Vector
# from src.core.tools import (...) - REMOVED
from storage.redis_store import redis_store

# Initialize resilient OpenAI client with custom retry config
retry_config = RetryConfig(
    max_retries=3, base_delay=1.0, max_delay=30.0, exponential_base=2.0, jitter=True
)
resilient_client = get_resilient_client(retry_config)

# Keep original client for backwards compatibility
client = OpenAI(api_key=OPENAI_API_KEY)

# Note: Conversation history is now stored in Redis via redis_store
# Previous conversations are also stored in Redis with a "prev:" prefix

FUNCTION_DEFINITIONS = [
    {
        "name": "create_document",
        "description": "Create a new document in Supabase with vector indexing",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the document",
                },
                "content": {
                    "type": "string",
                    "description": "Markdown content of the document",
                },
                "folder": {
                    "type": "string",
                    "description": "Optional folder/category to organize the document",
                },
                "type": {
                    "type": "string",
                    "description": "Type of document (note, list, recipe, etc)",
                    "default": "note",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for categorization",
                },
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "append_to_document",
        "description": "Append content to an existing document by ID or title",
        "parameters": {
            "type": "object",
            "properties": {
                "document_reference": {
                    "type": "string",
                    "description": "Document ID (UUID) or document title to append to",
                },
                "content": {"type": "string", "description": "Content to append"},
            },
            "required": ["document_reference", "content"],
        },
    },
    {
        "name": "read_document",
        "description": "Read content from a document by ID or title",
        "parameters": {
            "type": "object",
            "properties": {
                "document_reference": {
                    "type": "string",
                    "description": "Document ID (UUID) or document title to read",
                }
            },
            "required": ["document_reference"],
        },
    },
    {
        "name": "search_documents",
        "description": "Search for documents containing specific text using Supabase",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to search for"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_documents",
        "description": "List documents from Supabase with optional filtering",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional limit (default 20)",
                },
            },
        },
    },
]


class ConversationManager:
    """Manages conversation history with sliding window and performance tracking."""

    def __init__(self, max_messages: int = 20, ttl_hours: int = 24):
        """Initialize conversation manager.

        Args:
            max_messages: Maximum messages to keep in sliding window
            ttl_hours: Hours before conversation expires
        """
        self.max_messages = max_messages
        self.ttl_seconds = ttl_hours * 3600
        self.monitor: Optional[Any] = None

    async def _ensure_monitor(self):
        """Ensure performance monitor is initialized."""
        if self.monitor is None:
            self.monitor = get_performance_monitor()

    async def get_conversation_history(self, chat_id: str) -> List[Dict[str, str]]:
        """Get conversation history with sliding window management."""
        # Memory optimization: Use weak references and limit object retention
        messages = await redis_store.get_conversation(chat_id)

        # If no conversation exists, create a new one
        if messages is None:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            await redis_store.save_conversation(chat_id, messages)
        else:
            # Extend TTL on active conversation
            await redis_store.extend_conversation_ttl(chat_id)

        # Apply sliding window (keep system prompt + last N messages)
        if len(messages) > self.max_messages + 1:  # +1 for system prompt
            # Keep system prompt and last max_messages
            messages = [messages[0]] + messages[-(self.max_messages) :]
            # Save trimmed conversation back to Redis
            await redis_store.save_conversation(chat_id, messages)

        # Track conversation size
        await self._ensure_monitor()
        self.monitor.track_conversation_size(chat_id, len(messages))

        # Memory optimization: Return copy to prevent external modifications
        return [msg.copy() for msg in messages]

    async def add_message(self, chat_id: str, role: str, content: str):
        """Add a message to conversation with automatic sliding window."""
        # Memory optimization: Limit string retention and use efficient updates
        messages = await redis_store.get_conversation(chat_id)

        if messages is not None:
            # Add new message
            messages.append({"role": role, "content": content})

            # Apply sliding window if needed
            if len(messages) > self.max_messages + 1:  # +1 for system prompt
                # Keep system prompt and last max_messages
                messages = [messages[0]] + messages[-(self.max_messages) :]

            # Save back to Redis with TTL
            await redis_store.save_conversation(chat_id, messages)

            # Track updated size
            await self._ensure_monitor()
            self.monitor.track_conversation_size(chat_id, len(messages))

            # Memory optimization: Clear large content references
            del content

    async def cleanup_old_conversations(self, days_inactive: int = 7):
        """Cleanup conversations older than specified days.

        Note: This is handled automatically by Redis TTL, but this method
        can be used for manual cleanup or different retention policies.
        """
        # Since we're using Redis TTL, this is mostly a placeholder
        # In a production system, you might want to:
        # 1. Archive old conversations to S3/storage
        # 2. Generate summaries before deletion
        # 3. Track cleanup metrics
        logger = logging.getLogger(__name__)
        logger.info(
            f"Cleanup requested for conversations older than {days_inactive} days"
        )

    async def get_conversation_stats(self, chat_id: str) -> Dict[str, Any]:
        """Get statistics about a conversation."""
        messages = await redis_store.get_conversation(chat_id)

        if messages is None:
            return {"exists": False}

        # Calculate stats
        user_messages = sum(1 for m in messages if m.get("role") == "user")
        assistant_messages = sum(1 for m in messages if m.get("role") == "assistant")
        total_chars = sum(len(m.get("content", "")) for m in messages)

        return {
            "exists": True,
            "total_messages": len(messages),
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "total_characters": total_chars,
            "estimated_tokens": total_chars // 4,  # Rough estimate
            "has_system_prompt": any(m.get("role") == "system" for m in messages),
        }


# Global conversation manager instance with config values
conversation_manager = ConversationManager(
    max_messages=CONVERSATION_MAX_MESSAGES, ttl_hours=CONVERSATION_TTL_HOURS
)

# Cache for function results and schemas with memory limits
_function_result_cache: Dict[str, Any] = {}
_function_schema_cache: Optional[List[Dict[str, Any]]] = None
_MAX_CACHE_SIZE = 100
_CACHE_TTL_SECONDS = 3600
_cache_timestamps: Dict[str, float] = {}

# Initialize the Rails KeywordRouter and DynamicPromptGenerator
try:
    # Import storage service to get supabase client
    from storage.storage_service import DocumentStorage

    storage = DocumentStorage()
    keyword_router: Optional[KeywordRouter] = KeywordRouter(
        supabase_client=storage.supabase
    )
    # Load user aliases asynchronously on first use

    # Initialize dynamic prompt generator for T2.1.2
    prompt_generator: Optional[DynamicPromptGenerator] = DynamicPromptGenerator()
except Exception as e:
    logging.getLogger(__name__).error(f"Failed to initialize Rails components: {e}")
    keyword_router = None
    prompt_generator = None


async def get_conversation_history(
    chat_id: str, max_messages: Optional[int] = None
) -> List[Dict[str, str]]:
    """Get conversation history for a chat.

    This is a compatibility wrapper for the new ConversationManager.
    """
    if max_messages is not None:
        # Create temporary manager with custom max_messages
        temp_manager = ConversationManager(max_messages=max_messages)
        return await temp_manager.get_conversation_history(chat_id)
    else:
        return await conversation_manager.get_conversation_history(chat_id)


async def add_to_conversation_history(chat_id: str, role: str, content: str):
    """Add a message to conversation history.

    This is a compatibility wrapper for the new ConversationManager.
    """
    await conversation_manager.add_message(chat_id, role, content)


async def reset_conversation(chat_id: str):
    """Reset conversation but save it for potential restoration."""
    # Get current conversation
    messages = await redis_store.get_conversation(chat_id)

    if messages is not None:
        # Save to previous conversations with different key
        prev_key = f"prev:{chat_id}"
        await redis_store.save_conversation(prev_key, messages)
        # Delete current conversation
        await redis_store.delete_conversation(chat_id)


async def restore_conversation(chat_id: str) -> bool:
    """Restore previous conversation if available."""
    # Try to get previous conversation
    prev_key = f"prev:{chat_id}"
    messages = await redis_store.get_conversation(prev_key)

    if messages is not None:
        # Restore to current conversation
        await redis_store.save_conversation(chat_id, messages)
        # Delete the previous conversation backup
        await redis_store.delete_conversation(prev_key)
        return True
    return False


async def search_knowledge_base(
    query: str, chat_id: Optional[str] = None
) -> List[Dict]:
    """Search the vector knowledge base for relevant context with full document retrieval."""
    logger = logging.getLogger(__name__)
    try:
        # Use the new search_with_full_content method to get full documents
        # Note: search_with_full_content doesn't support namespace parameter yet
        # We need to use the regular search method with namespace
        if vector_store:
            results = await vector_store.search(
                query, top_k=3, include_metadata=True, namespace=""
            )
            logger.info(
                f"Vector search for '{query}' (namespace={chat_id}) returned {len(results)} results"
            )
            return results
        return []
    except Exception as e:
        logger.error(f"Vector search error for query '{query}': {e}")
        # Fallback to Supabase search if vector search fails
        try:
            from storage.storage_service import document_storage

            if document_storage:
                supabase_results = await document_storage.search_documents(query)
                if supabase_results:
                    return [
                        {
                            "id": r.get("id", ""),
                            "content": r.get("content", ""),
                            "score": 0.5,
                            "metadata": r.get("metadata", {}),
                        }
                        for r in supabase_results[:3]
                    ]
        except Exception as fallback_error:
            logger.error(f"Fallback search also failed: {fallback_error}")

        # Return empty results if both searches fail
        return []


async def _process_rails_command(
    route_result: RouteResult, chat_id: str, original_message: Optional[str] = None
) -> Optional[str]:
    """
    Process a command routed by the KeywordRouter.

    Phase 2.1 Enhancement: Handles both direct execution (100% confidence)
    and LLM-assisted execution with cleaned messages.

    Args:
        route_result: The RouteResult from the router.
        chat_id: The ID of the chat.
        original_message: The original user message before preprocessing.

    Returns:
        The response from the processor, or None if processing fails.
    """
    logger = logging.getLogger(__name__)

    # RouteResult has entity_type (e.g., 'lists', 'tasks', 'field_reports')
    entity_type = route_result.entity_type
    operation = route_result.operation
    extracted_data = route_result.extracted_data or {}

    if not entity_type:
        logger.warning("Router returned a result without an entity type.")
        return None

    try:
        # Import and instantiate the appropriate processor
        from src.rails.processors.base_processor import BaseProcessor

        processor_instance: Optional[BaseProcessor] = None

        if storage and storage.supabase:
            if entity_type == "lists":
                from src.rails.processors.list_processor import ListProcessor

                processor_instance = ListProcessor(supabase_client=storage.supabase)
            elif entity_type == "tasks":
                from src.rails.processors.task_processor import TaskProcessor

                processor_instance = TaskProcessor(supabase_client=storage.supabase)
            # Field reports - pushed to post-MVP
            # elif entity_type == "field_reports":
            #     from src.rails.processors.field_report_processor import FieldReportProcessor
            #     processor_instance = FieldReportProcessor(supabase_client=storage.supabase)
            else:
                logger.error(f"Unknown entity type: {entity_type}")
                return f"Error: Unknown command type '{entity_type}'."

        if not processor_instance:
            return f"Error: Command processor for '{entity_type}' is not available."

        # Execute the processor using execute_direct method
        response = await processor_instance.execute_direct(
            operation=operation,
            extracted_data=extracted_data,
            user_id=chat_id,  # Using chat_id as user_id
        )
        if response:
            return response.get("message", "Operation completed successfully")
        return "Operation completed successfully"

    except Exception as e:
        logger.error(
            f"Error executing processor for '{entity_type}': {e}", exc_info=True
        )
        return f"An error occurred while processing your {entity_type} command. Please try again."


@async_benchmark("process_message")
async def process_message(user_message: str, chat_id: str = "default") -> str:
    """Process a user message using GPT-4o and execute any necessary document operations."""
    logger = logging.getLogger(__name__)
    logger.info(
        f"Processing message for chat_id={chat_id}: {(user_message or '')[:50]}..."
    )

    # Sub-agent selection via `.claude/agents`
    selected_agent, cleaned_for_agent = detect_agent_in_message(user_message)
    agent_system_prompt = None
    if selected_agent:
        agent_prompt = load_agent_prompt(selected_agent)
        if agent_prompt:
            agent_system_prompt = agent_prompt
            user_message = cleaned_for_agent or user_message
            logger.info(f"Using sub-agent: {selected_agent}")

    # ** Enhanced Rails Router Integration (Phase 2.1) **
    # Try routing all messages through the keyword router first
    if keyword_router:
        try:
            # Ensure aliases are loaded before routing
            await keyword_router.ensure_aliases_loaded()
            route_result = keyword_router.route(user_message)

            # T2.1.2: Enhanced execution strategy based on dynamic prompting
            if route_result and route_result.entity_type and prompt_generator:
                # Build prompt context from route result
                prompt_context = PromptContext(
                    entity_type=route_result.entity_type,
                    operation=route_result.operation,
                    extracted_data=route_result.extracted_data or {},
                    confidence_scores={
                        "entity_confidence": route_result.entity_confidence
                        or route_result.confidence,
                        "operation_confidence": route_result.operation_confidence
                        or route_result.confidence,
                        "assignee_confidence": route_result.assignee_confidence or 0.0,
                    },
                    cleaned_message=(
                        route_result.extracted_data.get("cleaned_message", user_message)
                        if route_result.extracted_data
                        else user_message
                    ),
                    original_message=user_message,
                    has_mentions="@" in user_message,
                    has_commands="/" in user_message,
                    missing_fields=_determine_missing_fields(route_result),
                )

                # Determine execution strategy using T2.1.2 logic
                execution_strategy = prompt_generator.determine_execution_strategy(
                    prompt_context
                )

                # Log performance metrics
                metrics = prompt_generator.generate_performance_metrics(prompt_context)
                logger.info(
                    f"T2.1.2 Execution Strategy: {execution_strategy} | Metrics: {metrics}"
                )

                if execution_strategy == "direct":
                    # Direct execution without LLM
                    logger.info(
                        f"Direct execution (confidence={route_result.confidence}): {route_result.entity_type}.{route_result.operation}"
                    )
                    response = await _process_rails_command(
                        route_result, chat_id, user_message
                    )
                    if response:
                        logger.info(
                            f"Direct execution successful, saved ~{metrics['estimated_tokens']} tokens"
                        )
                        return response
                    else:
                        logger.warning(
                            "Direct execution failed. Falling back to focused LLM."
                        )
                        execution_strategy = "focused_llm"

                if (
                    execution_strategy == "focused_llm"
                    and route_result.confidence >= 0.7
                ):
                    # Use focused LLM with optimized prompts
                    logger.info(
                        f"Focused LLM execution for {route_result.entity_type}.{route_result.operation}"
                    )
                    # Context for LLM processing - not used in current implementation
                    # route_result.prompt_context = prompt_context
                    # route_result.dynamic_prompt = (
                    #     prompt_generator.generate_optimized_system_prompt(
                    #         prompt_context
                    #     )
                    # )
                    # Process with Rails command using focused approach
                    response = await _process_rails_command(
                        route_result, chat_id, user_message
                    )
                    if response:
                        return response
                    else:
                        logger.warning(
                            "Focused execution failed. Falling back to full LLM."
                        )
                elif execution_strategy == "full_llm":
                    logger.info(
                        f"Full LLM analysis required (confidence={route_result.confidence})"
                    )
                    # Continue to standard LLM processing
                    if route_result.extracted_data and route_result.extracted_data.get(
                        "cleaned_message"
                    ):
                        user_message = route_result.extracted_data["cleaned_message"]
                        logger.debug(f"Using cleaned message for LLM: {user_message}")
            elif route_result and route_result.entity_type:
                # Low confidence but has entity
                logger.info(
                    f"Rails router confidence too low ({route_result.confidence}), using LLM with context"
                )
                if route_result.extracted_data and route_result.extracted_data.get(
                    "cleaned_message"
                ):
                    user_message = route_result.extracted_data["cleaned_message"]
                    logger.debug(f"Using cleaned message for LLM: {user_message}")
        except Exception as e:
            logger.error(f"Rails router failed: {e}. Falling back to LLM.")
    # ** End Enhanced Rails Router Integration **

    # Track conversation size
    monitor = get_performance_monitor()

    try:
        # Memory optimization: Limit context size and use generators
        search_results = await search_knowledge_base(user_message, chat_id)

        # NEW: Recall user memories for personalized context
        user_memories = await bot_memory.recall_context(user_message, chat_id, limit=3)
        memory_context = ""
        if user_memories:
            memory_context = "\n[User Context from Memory]\n"
            for memory in user_memories:
                if isinstance(memory, dict) and memory.get("memory"):
                    memory_context += f"• {memory['memory']}\n"

        # Build context from search results with size limits
        context_parts = []
        source_documents = []
        max_context_length = 2000  # Limit total context size

        for result in search_results:
            # Memory optimization: Use efficient content extraction
            content = result.get("content", "")
            if not content and result.get("metadata"):
                content = result["metadata"].get("content_preview", "")

            if content and content.strip():
                # Memory optimization: Limit string operations
                title = result.get("metadata", {}).get("title", "")
                if not title:
                    file_path = result.get("metadata", {}).get("file_path", "")
                    title = (
                        file_path.split("/")[-1].replace(".md", "")
                        if file_path
                        else "unknown"
                    )

                # Memory optimization: Use string formatting efficiently
                source_info = f"Source: {title}"
                if result.get("document_url"):
                    source_info += f" ({result['document_url']})"
                    source_documents.append(
                        {
                            "title": title,
                            "url": result["document_url"],
                            "score": result.get("score", 0),
                        }
                    )

                # Memory optimization: Limit content preview size
                preview = content[: min(500, max_context_length // len(search_results))]
                context_parts.append(
                    f"[{source_info} - Score: {result.get('score', 0):.2f}]\n{preview}..."
                )

                # Memory optimization: Early exit if context is large enough
                if sum(len(part) for part in context_parts) > max_context_length:
                    break

        # Get conversation history
        messages = await get_conversation_history(chat_id)

        # If a sub-agent was selected, override or prepend a specialized system prompt
        if agent_system_prompt:
            # Replace existing system message if present, else insert at start
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = agent_system_prompt
            else:
                messages.insert(0, {"role": "system", "content": agent_system_prompt})

        # Track conversation size
        if monitor:
            monitor.track_conversation_size(chat_id, len(messages))

        # T2.1.2: Build enhanced message with dynamic prompting
        enhanced_message = user_message

        # Check if we have a route result with dynamic prompt context
        if keyword_router and hasattr(locals(), "route_result") and route_result:
            if hasattr(route_result, "prompt_context") and route_result.prompt_context:
                # Use the pre-generated dynamic prompt
                if hasattr(route_result, "dynamic_prompt"):
                    enhanced_message = f"[System Instruction: {route_result.dynamic_prompt}]\n\n{user_message}"

                # Add extracted context
                if route_result.extracted_data:
                    context_info = []
                    if route_result.extracted_data.get("assignee"):
                        context_info.append(
                            f"Assignee: {route_result.extracted_data['assignee']}"
                        )
                    if route_result.extracted_data.get("site"):
                        context_info.append(
                            f"Site: {route_result.extracted_data['site']}"
                        )
                    if route_result.extracted_data.get("time_references"):
                        context_info.append(
                            f"Time: {', '.join(route_result.extracted_data['time_references'])}"
                        )

                    if context_info:
                        enhanced_message += "\n\n[Extracted Context]\n" + "\n".join(
                            context_info
                        )

        # Add knowledge base context if available
        if context_parts:
            enhanced_message += f"\n\n[System: Found relevant context from knowledge base]\n{chr(10).join(context_parts)}"

        # Add memory context if available
        if memory_context:
            enhanced_message += f"\n{memory_context}"

        # Add the new user message
        messages.append({"role": "user", "content": enhanced_message})
        await add_to_conversation_history(chat_id, "user", user_message)

        # Use optimized function definitions (cached and filtered)
        functions_to_send = _get_optimized_functions(messages)

        response = await resilient_client.chat_completion(
            messages=messages,
            model=GPT_MODEL,
            functions=functions_to_send,
            function_call="auto",
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        if not response:
            return "I'm sorry, I couldn't process your request."

        message = response.choices[0].message

        # If GPT wants to call a function
        if message and message.function_call:
            function_name = message.function_call.name
            function_args = json.loads(message.function_call.arguments)

            # Add chat_id to function args for namespace support
            function_args["chat_id"] = chat_id

            # Execute the function with caching and memory management
            cache_key = f"{function_name}:{json.dumps(function_args, sort_keys=True)}"

            # Clean expired cache entries
            _cleanup_expired_cache()

            if cache_key in _function_result_cache:
                function_result = _function_result_cache[cache_key]
            else:
                function_result = await execute_function(function_name, function_args)
                _function_result_cache[cache_key] = function_result
                _cache_timestamps[cache_key] = time.time()

                # Enforce cache size limit
                _enforce_cache_size_limit()

                # Explicit cleanup of large objects
                if hasattr(function_result, "__dict__"):
                    # Use weak references for large objects
                    function_result = _create_weakref_safe_copy(function_result)

            # Send the result back to GPT for a final response
            messages.append(message)
            messages.append(
                {
                    "role": "function",
                    "name": function_name,
                    "content": json.dumps(function_result, separators=((",", ":"))),
                }
            )

            # Use resilient client for final response
            final_response = await resilient_client.chat_completion(
                messages=messages,
                model=GPT_MODEL,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )

            if not final_response:
                return "I'm sorry, I couldn't process your request."

            final_content = final_response.choices[0].message.content

            # Add source documents if available
            if source_documents:
                sources_text = "\n\n📚 Sources:\n" + "\n".join(
                    [f"• {doc['title']} - {doc['url']}" for doc in source_documents[:3]]
                )
                if final_content:
                    final_content += sources_text

            await add_to_conversation_history(chat_id, "assistant", final_content)

            # NEW: Extract and store memories from conversation
            recent_messages = await get_conversation_history(chat_id)
            if len(recent_messages) > 1:  # Skip if only system message
                # Get last 4 messages (2 exchanges) for memory extraction
                messages_for_memory = (
                    recent_messages[-4:]
                    if len(recent_messages) > 4
                    else recent_messages[1:]
                )
                await bot_memory.remember_from_conversation(
                    messages_for_memory, chat_id
                )

            # Memory optimization: Explicit cleanup of large objects
            del search_results
            del context_parts
            del source_documents
            del messages
            del response
            del final_response

            # Force garbage collection for large objects
            gc.collect()

            return final_content

        # If no function call, return the direct response
        assistant_content = message.content

        # Add source documents if available (optimized string building)
        if source_documents:
            sources_text = "\n\n📚 Sources:\n" + "\n".join(
                [f"• {doc['title']} - {doc['url']}" for doc in source_documents[:3]]
            )
            if assistant_content:
                assistant_content += sources_text

        await add_to_conversation_history(chat_id, "assistant", assistant_content)

        # NEW: Extract and store memories from conversation (non-function path)
        recent_messages = await get_conversation_history(chat_id)
        if len(recent_messages) > 1:
            messages_for_memory = (
                recent_messages[-4:]
                if len(recent_messages) > 4
                else recent_messages[1:]
            )
            await bot_memory.remember_from_conversation(messages_for_memory, chat_id)

        # Memory optimization: Explicit cleanup
        del search_results
        del context_parts
        del source_documents
        del messages
        del response

        # Force garbage collection
        gc.collect()

        return assistant_content

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return f"I encountered an error processing your request: {str(e)}"


def is_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    uuid_pattern = re.compile(
        r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", re.IGNORECASE
    )
    return bool(uuid_pattern.match(value))


async def resolve_document_reference(
    reference: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve a document reference to (file_path, document_id, content).

    Args:
        reference: Either a file path or a Supabase document ID

    Returns:
        Tuple of (file_path, document_id, content) - some may be None
    """
    logger = logging.getLogger(__name__)

    if not reference:
        return None, None, None

    # Check if it's a UUID (Supabase document ID)
    if is_uuid(reference):
        logger.info(f"Detected Supabase document ID: {reference}")
        from storage.storage_service import document_storage

        if document_storage:
            try:
                doc = await document_storage.get_document_by_id(reference)
                if doc:
                    return doc.get("file_path"), reference, doc.get("content")
                else:
                    logger.warning(f"Document ID {reference} not found in Supabase")
            except Exception as e:
                logger.error(f"Error fetching document by ID: {e}")

        return None, reference, None

    # Otherwise, treat it as a file path
    elif reference.endswith(".md"):
        # It's already a file path
        return reference, None, None

    else:
        # It might be a title - search for it in Supabase
        try:
            from storage.storage_service import document_storage

            if document_storage:
                search_results = await document_storage.search_documents(reference)
                if search_results:
                    doc = search_results[0]
                    return doc.get("file_path"), doc.get("id"), doc.get("content")
        except Exception as e:
            logger.error(f"Error searching for document by title: {e}")

        return None, None, None


def _get_optimized_functions(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Return optimized function definitions based on context."""
    global _function_schema_cache

    if _function_schema_cache is None:
        # Cache the full schema once
        _function_schema_cache = FUNCTION_DEFINITIONS

    # For now, return all functions - can be enhanced to filter based on context
    return _function_schema_cache


def _cleanup_expired_cache():
    """Remove expired cache entries."""
    import time

    current_time = time.time()
    expired_keys = [
        key
        for key, timestamp in _cache_timestamps.items()
        if current_time - timestamp > _CACHE_TTL_SECONDS
    ]

    for key in expired_keys:
        if key in _function_result_cache:
            del _function_result_cache[key]
        del _cache_timestamps[key]


def _enforce_cache_size_limit():
    """Enforce maximum cache size."""
    if len(_function_result_cache) > _MAX_CACHE_SIZE:
        # Remove oldest entries
        sorted_keys = sorted(
            _cache_timestamps.keys(), key=lambda k: _cache_timestamps[k]
        )
        keys_to_remove = sorted_keys[: len(sorted_keys) - _MAX_CACHE_SIZE]

        for key in keys_to_remove:
            if key in _function_result_cache:
                del _function_result_cache[key]
            if key in _cache_timestamps:
                del _cache_timestamps[key]


def _create_weakref_safe_copy(obj):
    """Create a memory-efficient copy of large objects."""
    if isinstance(obj, dict):
        return {k: v for k, v in obj.items() if not callable(v)}
    elif isinstance(obj, list):
        return [item for item in obj if not callable(item)]
    return obj


def _determine_missing_fields(route_result: RouteResult) -> List[str]:
    """Determine which required fields are missing from the route result.

    T2.1.2: Helper function to identify missing fields for dynamic prompting.
    """
    missing = []

    if not route_result.entity_type or not route_result.operation:
        return ["entity_type", "operation"]

    extracted = route_result.extracted_data or {}

    # Check based on entity type and operation
    if route_result.entity_type == "lists":
        if (
            route_result.operation == "create"
            and "list_name" not in extracted
            and "suggested_name" not in extracted
        ):
            missing.append("list_name")
        elif route_result.operation in ["add_items", "remove_items"]:
            if "list_name" not in extracted:
                missing.append("list_name")
            if "items" not in extracted:
                missing.append("items")
    elif route_result.entity_type == "tasks":
        if route_result.operation == "create" and "task_title" not in extracted:
            missing.append("task_title")
        elif route_result.operation == "reassign":
            if "new_assignee" not in extracted and "assignee" not in extracted:
                missing.append("new_assignee")
        # Field reports - pushed to post-MVP
        # elif route_result.entity_type == "field_reports":
        if (
            route_result.operation == "create"
            and "site" not in extracted
            and "site_references" not in extracted
        ):
            missing.append("site")

    return missing


async def execute_function(function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a function based on GPT's decision."""
    try:
        if function_name == "create_document":
            # Extract arguments with defaults
            title = args.get("title")
            content = args.get("content")
            folder = args.get("folder")
            doc_type = args.get("type", "note")
            tags = args.get("tags", [])

            if not title or not content:
                return {"success": False, "error": "Title and content are required."}

            # Get chat_id from context if available
            chat_id = args.get("chat_id", "default")

            # Store in Supabase (primary storage)
            from storage.storage_service import document_storage

            if not document_storage:
                return {
                    "success": False,
                    "error": "Document storage not available",
                }

            try:
                # Convert chat_id to integer for telegram_chat_id, or None if not a valid integer
                telegram_chat_id = None
                if chat_id and chat_id != "default":
                    try:
                        telegram_chat_id = int(chat_id)
                    except ValueError:
                        # If chat_id is not a valid integer (e.g., "user1"), pass None
                        telegram_chat_id = None

                # Create synthetic file_path for compatibility
                file_path = (
                    f"{folder}/{title.lower().replace(' ', '-')}.md"
                    if folder
                    else f"{title.lower().replace(' ', '-')}.md"
                )

                metadata = {
                    "title": title,
                    "type": doc_type,
                    "tags": tags,
                    "folder": folder or "root",
                    "file_path": file_path,
                }

                # Store in Supabase with async connection handling
                doc_id = await document_storage.store_document(
                    file_path=file_path,
                    content=content,
                    metadata=metadata,
                    category=folder,
                    tags=tags,
                    telegram_chat_id=telegram_chat_id,
                    created_by="bot",
                )

                # doc_id is returned directly as a string
                if not doc_id:
                    doc_id = file_path.replace("/", "_").replace(".md", "")

                # Chunk the document for better semantic search
                chunks = chunk_markdown_document(
                    content=content,
                    file_path=file_path,
                    metadata=metadata,
                    chunk_size=1000,
                    chunk_overlap=200,
                )

                # Store each chunk in vector database
                logging.info(f"📄 Chunking document into {len(chunks)} chunks")
                for i, (chunk_text, chunk_metadata) in enumerate(chunks):
                    chunk_id = f"{doc_id}_chunk_{i}"
                    if vector_store:
                        await vector_store.embed_and_store(
                            document_id=chunk_id,
                            content=chunk_text,
                            metadata=chunk_metadata,
                            namespace="",
                        )

                    # Store chunk reference in Supabase
                    await document_storage.store_document_chunk(
                        document_id=str(doc_id),
                        chunk_index=i,
                        chunk_text=chunk_text,
                        vector_id=chunk_id,
                        start_char=chunk_metadata["start_char"],
                        end_char=chunk_metadata["end_char"],
                        metadata=chunk_metadata,
                    )

                return {
                    "success": True,
                    "message": f"Created document: {title}",
                    "document_id": doc_id,
                    "file_path": file_path,
                }

            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error creating document: {e}")
                return {
                    "success": False,
                    "error": f"Failed to create document: {str(e)}",
                }

        elif function_name == "append_to_document":
            reference = args.get("document_reference")
            content = args.get("content")

            # Resolve the reference to document ID and existing content
            file_path, document_id, existing_content = await resolve_document_reference(
                reference
            )

            if not document_id and not file_path:
                return {
                    "success": False,
                    "error": f"Could not find document matching '{reference}'",
                }

            from storage.storage_service import document_storage

            if not document_storage:
                return {
                    "success": False,
                    "error": "Document storage not available",
                }

            try:
                # Append to the existing content
                updated_content = (existing_content or "") + "\n\n" + content

                # Update in Supabase
                if document_id:
                    success = await document_storage.update_document_by_id(
                        document_id, updated_content
                    )
                    doc_ref = document_id
                else:
                    # Use file path for backward compatibility
                    if file_path:
                        success = await document_storage.update_document(
                            file_path, updated_content
                        )
                        doc_ref = file_path.replace("/", "_").replace(".md", "")
                    else:
                        success = False
                        doc_ref = ""

                if success:
                    # Delete old chunks from vector store
                    logging.info(f"🗑️ Removing old chunks for document {doc_ref}")
                    old_chunks = await document_storage.get_document_chunks(
                        document_id or doc_ref
                    )
                    if old_chunks:
                        for chunk in old_chunks:
                            if vector_store:
                                await vector_store.delete_document(
                                    chunk["vector_id"], namespace=""
                                )

                    # Re-chunk and store the updated document
                    metadata = {
                        "document_id": document_id or doc_ref,
                        "file_path": file_path,
                        "last_updated": datetime.now().isoformat(),
                        "source_ids": [
                            doc_ref,
                            f"{doc_ref}_append_{datetime.now().timestamp()}",
                        ],
                        "operation": "merge",
                    }

                    chunks = chunk_markdown_document(
                        content=updated_content,
                        file_path=file_path,
                        metadata=metadata,
                        chunk_size=1000,
                        chunk_overlap=200,
                    )

                    # Store each chunk
                    logging.info(f"📄 Re-chunking document into {len(chunks)} chunks")
                    for i, (chunk_text, chunk_metadata) in enumerate(chunks):
                        chunk_id = f"{document_id or doc_ref}_chunk_{i}"
                        if vector_store:
                            await vector_store.embed_and_store(
                                document_id=chunk_id,
                                content=chunk_text,
                                metadata=chunk_metadata,
                                namespace="",
                            )

                        # Store chunk reference
                        await document_storage.store_document_chunk(
                            document_id=str(document_id or doc_ref),
                            chunk_index=i,
                            chunk_text=chunk_text,
                            vector_id=chunk_id,
                            start_char=chunk_metadata["start_char"],
                            end_char=chunk_metadata["end_char"],
                            metadata=chunk_metadata,
                        )

                    return {
                        "success": True,
                        "message": f"Updated document: {reference}",
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to update document: {reference}",
                    }

            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error updating document: {e}")
                return {
                    "success": False,
                    "error": f"Failed to append to document: {str(e)}",
                }

        elif function_name == "read_document":
            reference = args.get("document_reference")

            # Resolve the reference to document ID and content
            file_path, document_id, content = await resolve_document_reference(
                reference
            )

            if not document_id and not file_path:
                return {
                    "success": False,
                    "error": f"Could not find document matching '{reference}'",
                }

            # If we have content from Supabase, use it
            if content is not None:
                return {"success": True, "content": content}

            # Try to get content from Supabase if we have an ID
            if document_id:
                from storage.storage_service import document_storage

                if document_storage:
                    try:
                        doc = await document_storage.get_document_by_id(document_id)
                        if doc and doc.get("content"):
                            return {"success": True, "content": doc["content"]}
                    except Exception as e:
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error reading document from Supabase: {e}")

            return {
                "success": False,
                "error": f"Could not read content for document '{reference}'",
            }

        elif function_name == "search_documents":
            query = args.get("query")

            from storage.storage_service import document_storage

            if not document_storage:
                return {
                    "success": False,
                    "error": "Document storage not available",
                }

            try:
                # Search documents in Supabase
                results = await document_storage.search_documents(query)

                # Convert to expected format
                formatted_results = []
                if results:
                    for doc in results:
                        formatted_results.append(
                            {
                                "id": doc.get("id"),
                                "title": doc.get("metadata", {}).get(
                                    "title", "Untitled"
                                ),
                                "snippet": (
                                    doc.get("content", "")[:200] + "..."
                                    if len(doc.get("content", "")) > 200
                                    else doc.get("content", "")
                                ),
                                "path": doc.get("file_path", ""),
                                "category": doc.get("category"),
                                "tags": doc.get("tags", []),
                            }
                        )

                return {
                    "success": True,
                    "results": formatted_results,
                    "count": len(formatted_results),
                }

            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error searching documents: {e}")
                return {
                    "success": False,
                    "error": f"Search failed: {str(e)}",
                }

        elif function_name == "list_documents":
            category = args.get("category")
            limit = args.get("limit", 20)

            from storage.storage_service import document_storage

            if not document_storage:
                return {
                    "success": False,
                    "error": "Document storage not available",
                }

            try:
                # List documents from Supabase
                documents = await document_storage.list_documents(
                    category=category, limit=limit
                )

                # Convert to expected format
                formatted_docs = []
                if documents:
                    for doc in documents:
                        formatted_docs.append(
                            {
                                "id": doc.get("id"),
                                "title": doc.get("metadata", {}).get(
                                    "title", "Untitled"
                                ),
                                "type": doc.get("metadata", {}).get("type", "note"),
                                "category": doc.get("category"),
                                "created": doc.get("created_at"),
                                "path": doc.get("file_path", ""),
                                "tags": doc.get("tags", []),
                            }
                        )

                return {
                    "success": True,
                    "files": formatted_docs,
                    "count": len(formatted_docs),
                }

            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error listing documents: {e}")
                return {
                    "success": False,
                    "error": f"List failed: {str(e)}",
                }

        else:
            return {"success": False, "error": f"Unknown function: {function_name}"}

    except Exception as e:
        return {"success": False, "error": str(e)}
