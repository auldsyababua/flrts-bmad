#!/usr/bin/env python3
"""
🔧 Core message handlers for Telegram bot

This module contains all the bot message handling logic that is shared
between polling (local development) and webhook (production) modes.

Handlers:
- Command handlers (/start, /help, /reset, /continue, /version)
- Message handlers (text messages, documents)
- Error handling
"""

import json
import logging
import os
import tempfile
import time
from datetime import datetime
from typing import Any, Dict

from telegram import Update
from telegram.ext import ContextTypes

from core.auth import is_user_authorized
from core.chunking import chunk_markdown_document
from core.llm import process_message
from core.memory import bot_memory
from core.version import LATEST_CHANGES, VERSION
from storage import vector_store
from storage.redis_store import redis_store
from storage.storage_service import DocumentStorage

# Set up logging
logger = logging.getLogger(__name__)

# Import structured logging helpers if available
try:
    from core.supabase_logger import log_operation, log_performance
except ImportError:
    # Fallback if supabase_logger not available
    def log_operation(logger, level, message, **kwargs):
        logger.log(level, message)

    def log_performance(logger, operation, duration_ms, **kwargs):
        logger.info(f"{operation} took {duration_ms}ms")


# Index initialization removed - using Supabase storage


# Helper function for authorization check
async def check_authorization(update: Update) -> bool:
    """Check if user is authorized and send rejection message if not.

    Returns:
        bool: True if authorized, False otherwise
    """
    if not update.effective_user or not update.message:
        logger.warning("Update or message is missing, cannot check authorization.")
        return False
    user = update.effective_user
    if not is_user_authorized(username=user.username, user_id=user.id):
        await update.message.reply_text(
            f"Hello {user.first_name}! 👋\n\n"  # Corrected newline escaping
            "This bot is currently available only to authorized 10NetZero team members.\n"  # Corrected newline escaping
            "Please contact your administrator for access.\n\n"  # Corrected newline escaping
            f"Your username: @{user.username or 'not set'}\n"  # Corrected newline escaping
            f"Your ID: {user.id}"
        )
        logger.warning(
            f"Unauthorized access attempt (command): @{user.username} (ID: {user.id})"
        )
        return False
    return True


# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    if not await check_authorization(update) or not update.message:
        return

    welcome_message = (
        "🧠 Welcome to the Markdown Brain Bot!\n\n"
        "I'm your shared knowledge assistant. I can help you:\n\n"
        "• Create notes and lists\n"
        "• Add information to existing notes\n"
        "• Search and retrieve information\n\n"
        "**Available Commands:**\n"
        "• /start - Show this welcome message\n"
        "• /help - Show detailed help and examples\n"
        "• /reset - Start a new conversation (clears memory)\n"
        "• /continue - Restore previous conversation\n"
        "• /version - Show bot version and diagnostics\n"
        "• /report - Generate a report of current conversation for debugging\n\n"
        "Just send me a message with what you'd like to do!\n\n"
        "Examples:\n"
        '- "Create a shopping list with milk, eggs, and bread"\n'
        '- "Add coffee to the shopping list"\n'
        '- "What\'s on my shopping list?"\n'
        '- "Tell me what kind of GPU I have"\n'
        '- "Find all notes about projects"'
    )
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command."""
    if not await check_authorization(update) or not update.message:
        return

    help_message = (
        "📚 **How to use the Markdown Brain Bot**\n\n"
        "**Creating content:**\n"
        '• "Create a [type] about [topic]" - Creates a new note\n'
        '• "Make a list of [items]" - Creates a new list\n\n'
        "**Adding content:**\n"
        '• "Add [content] to [note name]" - Appends to existing note\n\n'
        "**Reading content:**\n"
        '• "What\'s in [note name]?" - Shows note content\n'
        '• "Show me [note name]" - Shows note content\n\n'
        "**Searching:**\n"
        '• "Find notes about [topic]" - Searches all notes\n'
        '• "Search for [keyword]" - Searches all content\n\n'
        "**Listing:**\n"
        '• "List all notes" - Shows all stored notes\n'
        '• "What notes do we have?" - Shows all stored notes\n\n'
        "**Commands:**\n"
        "• /start - Welcome message\n"
        "• /help - Show this help\n"
        "• /reset - Start a new conversation\n"
        "• /continue - Restore previous conversation\n\n"
        "**🧠 Memory Commands:**\n"
        "• /remember [fact] - Tell me something to remember\n"
        "• /correct [wrong -> right] - Teach me corrections\n"
        "• /memories - See what I remember about you\n"
        "• /graph [entity] - Explore knowledge graph connections\n"
        "• /forget - Clear all your memories"
    )
    await update.message.reply_text(help_message, parse_mode="Markdown")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /reset command to start a new conversation."""
    if (
        not await check_authorization(update)
        or not update.effective_chat
        or not update.message
    ):
        return

    chat_id = str(update.effective_chat.id)

    # Import the reset function from llm
    from core.llm import reset_conversation

    # Reset conversation for this chat
    await reset_conversation(chat_id)

    await update.message.reply_text(
        "🔄 Conversation reset! I've cleared my memory of our previous messages. "
        "Let's start fresh! How can I help you?"
    )


async def continue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /continue command to restore previous conversation."""
    if (
        not await check_authorization(update)
        or not update.effective_chat
        or not update.message
    ):
        return

    chat_id = str(update.effective_chat.id)

    # Import the restore function from llm
    from core.llm import restore_conversation

    # Try to restore conversation for this chat
    if await restore_conversation(chat_id):
        await update.message.reply_text(
            "✅ Previous conversation restored! I remember what we were talking about. "
            "You can continue where we left off."
        )
    else:
        await update.message.reply_text(
            "❌ No previous conversation found to restore. "
            "We're already in a fresh conversation!"
        )


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /report command - generates a conversation report for debugging."""
    if (
        not await check_authorization(update)
        or not update.effective_chat
        or not update.message
        or not update.effective_user
    ):
        return

    try:
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Show processing message
        processing_msg = await update.message.reply_text(
            "📊 Generating conversation report...\n" "This may take a moment."
        )

        # Collect conversation data
        report_data = {
            "timestamp": timestamp,
            "user": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "chat_id": chat_id,
            "conversation_history": [],
            "vector_searches": [],
            "errors": [],
            "metadata": {
                "bot_version": VERSION,
                "report_generated_at": datetime.now().isoformat(),
            },
        }

        # Get conversation history from Redis
        conversation_key = f"conversation:{chat_id}"
        messages = await redis_store.get_conversation(conversation_key)
        report_data["conversation_history"] = messages

        # Get recent vector searches (if tracked)
        # TODO: Add vector search logging to track queries and results

        # Create report content
        report_content = "# Conversation Report\n\n"
        report_content += (
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        report_content += f"**User**: @{user.username or 'N/A'} (ID: {user.id})\n"
        report_content += f"**Bot Version**: {VERSION}\n\n"

        report_content += f"## Conversation History ({len(messages)} messages)\n\n"
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            report_content += f"### Message {i+1} ({role})\n"
            report_content += (
                f"```\n{content[:500]}{'...' if len(content) > 500 else ''}\n```\n\n"
            )

        # Save report to file
        report_filename = f"conversation_report_{chat_id}_{timestamp}.md"
        report_path = f"logs/reports/{report_filename}"

        # Ensure reports directory exists
        os.makedirs("logs/reports", exist_ok=True)

        # Write report file
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
            f.write("\n\n## Raw Data (JSON)\n\n")
            f.write("```json\n")
            f.write(json.dumps(report_data, indent=2, ensure_ascii=False))
            f.write("\n```\n")

        # Update processing message
        await processing_msg.edit_text(
            f"✅ **Conversation report generated!**\n\n"
            f"📄 Report saved to: `{report_filename}`\n\n"
            f"The report includes:\n"
            f"• {len(messages)} conversation messages\n"
            f"• User information\n"
            f"• Timestamp and version info\n\n"
            f"Please share this file with your administrator for debugging."
        )

        # Send the report file
        with open(report_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=report_filename,
                caption="📎 Here's your conversation report for debugging.",
            )

    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await update.message.reply_text(
            "❌ Sorry, I couldn't generate the report.\n"
            f"Error: {str(e)}\n\n"
            "Please try again or contact your administrator."
        )


async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /version command to show bot version and capabilities."""
    if not await check_authorization(update) or not update.message:
        return

    version_message = (
        f"🤖 **Markdown Brain Bot v{VERSION}**\n\n" "**Latest Changes:**\n"
    )

    for change in LATEST_CHANGES:
        version_message += f"• {change}\n"

    version_message += (
        "\n**Diagnostic Info:**\n"
        f"• Vector search: {'✅ Enabled' if vector_store else '❌ Disabled'}\n"
        f"• Search method: Full document retrieval\n"
        f"• Chunk size: 1000 chars with 200 char overlap\n"
        "\nIf I'm not finding your documents, please ask your admin to:\n"
        "1. Check the vector store migration\n"
        "2. Run: `python diagnose_vector.py`"
    )

    await update.message.reply_text(version_message)


# Message handlers
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    start_time = time.time()
    if not update.effective_user or not update.message or not update.effective_chat:
        logger.warning("Update, message, or chat is missing, cannot handle message.")
        return
    try:
        user = update.effective_user
        user_message = update.message.text
        chat_id = update.effective_chat.id

        # Check authorization
        if not await check_authorization(update):
            return

        # Log first-time authorized users for future whitelist updates
        if user.username and user.username in [
            "Colin_10NetZero",
            "Bryan_10NetZero",
            "Joel_10NetZero",
        ]:
            logger.info(
                f"Authorized user detected - Username: @{user.username}, ID: {user.id}"
            )
            logger.info(
                f"Consider adding to AUTHORIZED_USER_IDS: {user.id}  # {user.username}"
            )

        # Log incoming message with structured data
        log_operation(
            logger,
            logging.INFO,
            f"Received message: {user_message[:50]}...",
            user_id=user.id,
            chat_id=chat_id,
            operation="handle_message",
            message_length=len(user_message),
        )

        # Show typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        # Process the message with LLM (pass chat_id for conversation memory)
        llm_start = time.time()
        response = await process_message(user_message, str(chat_id))
        llm_duration = int((time.time() - llm_start) * 1000)

        # Log LLM performance
        log_performance(
            logger,
            "llm_processing",
            llm_duration,
            user_id=user.id,
            chat_id=chat_id,
            response_length=len(response),
        )

        # Send the response
        await update.message.reply_text(response, parse_mode="Markdown")

        # Log total handling time
        total_duration = int((time.time() - start_time) * 1000)
        log_performance(
            logger,
            "message_handling",
            total_duration,
            user_id=user.id,
            chat_id=chat_id,
            operation="handle_message",
        )

    except Exception as e:
        # Log error with structured data
        log_operation(
            logger,
            logging.ERROR,
            f"Error handling message: {str(e)}",
            user_id=user.id if "user" in locals() else None,
            chat_id=chat_id if "chat_id" in locals() else None,
            error=str(e),
            operation="handle_message",
        )

        error_message = (
            "😔 Sorry, I encountered an error processing your message. "
            "Please try again or contact the administrator if the problem persists.\n\n"
            "💡 Tip: Use /help to see available commands and examples."
        )
        await update.message.reply_text(error_message)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming document files."""
    if not update.effective_user or not update.message or not update.effective_chat:
        logger.warning("Update, message, or chat is missing, cannot handle document.")
        return
    try:
        user = update.effective_user
        document = update.message.document
        chat_id = update.effective_chat.id

        # Check authorization
        if not await check_authorization(update):
            return

        # Check if it's a markdown file
        if document.file_name and (
            document.file_name.endswith(".md")
            or document.file_name.endswith(".markdown")
        ):
            logger.info(
                f"📎 Received markdown file from {chat_id}: {document.file_name}"
            )

            # Show typing indicator
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")

            # Download the file
            file = await context.bot.get_file(document.file_id)

            # Create temporary file to store the content
            with tempfile.NamedTemporaryFile(
                mode="w+", suffix=".md", delete=False
            ) as tmp_file:
                await file.download_to_drive(tmp_file.name)
                tmp_file_path = tmp_file.name

            # Read the file content
            with open(tmp_file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Clean up temp file
            os.unlink(tmp_file_path)

            # Extract title from filename (remove extension)
            title = os.path.splitext(document.file_name)[0]

            # Determine if this should go in a specific folder based on the filename
            folder = None
            if "network" in title.lower() or "infrastructure" in title.lower():
                folder = "hardware"
            elif "config" in title.lower() or "setup" in title.lower():
                folder = "development"

            # Store document in Supabase
            document_storage = DocumentStorage()
            file_path = f"{folder or 'documents'}/{title}.md"

            doc_id = await document_storage.store_document(
                file_path=file_path,
                content=content,
                metadata={
                    "title": title,
                    "type": "note",
                    "source": "telegram-upload",
                },
                category=folder,
                tags=["imported", "telegram-attachment"],
                telegram_chat_id=chat_id,
                telegram_user_id=user.id,
                created_by="bot",
            )

            # Chunk the document for better semantic search
            chunks = chunk_markdown_document(
                content=content,
                file_path=file_path,
                metadata={
                    "title": title,
                    "type": "note",
                    "tags": ["imported", "telegram-attachment"],
                    "folder": folder or "root",
                    "doc_id": doc_id,
                    "source": "telegram-upload",
                },
                chunk_size=1000,
                chunk_overlap=200,
            )

            # Store each chunk in vector database
            logger.info(f"📄 Chunking document into {len(chunks)} chunks")
            for i, (chunk_text, chunk_metadata) in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                await vector_store.embed_and_store(
                    document_id=chunk_id,
                    content=chunk_text,
                    metadata=chunk_metadata,
                    namespace="",
                )

                # Store chunk reference in Supabase
                await document_storage.store_document_chunk(
                    document_id=doc_id,
                    chunk_index=i,
                    chunk_text=chunk_text,
                    vector_id=chunk_id,
                    start_char=chunk_metadata["start_char"],
                    end_char=chunk_metadata["end_char"],
                    metadata=chunk_metadata,
                )

            # Let the LLM know about the imported file
            llm_message = f"I just imported a document called '{document.file_name}'. The document contains:\n\n{content[:500]}..."
            llm_response = await process_message(llm_message, str(chat_id))

            response = (
                f"✅ Successfully imported '{document.file_name}'\n\n{llm_response}"
            )
            await update.message.reply_text(response)

        else:
            await update.message.reply_text(
                "📎 I can only process text-based documents. "
                "Please send a text file to import it into the knowledge base."
            )

    except Exception as e:
        logger.error(f"Error handling document: {e}")
        error_message = (
            "😔 Sorry, I encountered an error processing your file. "
            "Please try again or contact the administrator if the problem persists."
        )
        await update.message.reply_text(error_message)


# Memory-related command handlers
async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remember command to explicitly store facts about the user."""
    if (
        not await check_authorization(update)
        or not update.effective_chat
        or not update.message
    ):
        return

    chat_id = str(update.effective_chat.id)
    text = update.message.text.replace("/remember", "").strip()

    if text:
        try:
            await bot_memory.store_preference(chat_id, text, category="user_fact")
            await update.message.reply_text(
                f"✅ I'll remember that!\n\n" f"📝 Stored: _{text}_",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            await update.message.reply_text("❌ Sorry, I couldn't store that memory.")
    else:
        await update.message.reply_text(
            "Please tell me what to remember!\n\n"
            "Usage: `/remember I prefer morning reports`"
        )


async def correct_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /correct command for teaching the bot corrections."""
    if (
        not await check_authorization(update)
        or not update.effective_chat
        or not update.message
    ):
        return

    chat_id = str(update.effective_chat.id)
    text = update.message.text.replace("/correct", "").strip()

    if "->" in text:
        try:
            original, corrected = text.split("->", 1)
            await bot_memory.store_correction(
                chat_id, original.strip(), corrected.strip()
            )
            await update.message.reply_text(
                "📝 Thanks for the correction! I'll learn from this.\n\n"
                f"❌ Wrong: _{original.strip()}_\n"
                f"✅ Right: _{corrected.strip()}_",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error storing correction: {e}")
            await update.message.reply_text(
                "❌ Sorry, I couldn't store that correction."
            )
    else:
        await update.message.reply_text(
            "Please provide a correction in the format:\n\n"
            "`/correct wrong answer -> correct answer`\n\n"
            "Example: `/correct pump at site A -> pump at Eagle Lake`",
            parse_mode="Markdown",
        )


async def memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user what the bot remembers about them."""
    if (
        not await check_authorization(update)
        or not update.effective_chat
        or not update.message
    ):
        return

    chat_id = str(update.effective_chat.id)

    try:
        # Get all user memories
        memories = await bot_memory.get_all_memories(chat_id)

        # Get memory statistics
        stats = await bot_memory.get_memory_stats(chat_id)

        if memories:
            response = "🧠 **Here's what I remember about you:**\n\n"

            # Group memories by type
            preferences = []
            corrections = []
            other = []

            for mem in memories[:20]:  # Limit to 20 to avoid too long message
                memory_text = mem.get("memory", "")
                metadata = mem.get("metadata", {})
                mem_type = metadata.get("type", "other")

                if mem_type == "preference":
                    preferences.append(memory_text)
                elif mem_type == "correction":
                    corrections.append(
                        f"{metadata.get('original', '')} → {metadata.get('corrected', '')}"
                    )
                else:
                    other.append(memory_text)

            if preferences:
                response += "📌 **Your Preferences:**\n"
                for pref in preferences:
                    response += f"• {pref}\n"
                response += "\n"

            if corrections:
                response += "✏️ **Corrections I've Learned:**\n"
                for corr in corrections:
                    response += f"• {corr}\n"
                response += "\n"

            if other:
                response += "💭 **Other Memories:**\n"
                for mem in other:
                    response += f"• {mem}\n"

            if len(memories) > 20:
                response += f"\n_...and {len(memories) - 20} more memories_"

            # Add graph memory stats if available
            if stats.get("has_graph") and stats.get("graph_relationships", 0) > 0:
                response += "\n\n🕸️ **Knowledge Graph:**\n"
                response += f"• {stats['graph_entities']} entities\n"
                response += f"• {stats['graph_relationships']} relationships\n"
                response += "_Use `/graph` to explore connections_"

            response += "\n\nUse `/forget` to clear all memories."

        else:
            response = (
                "🧠 I don't have any memories about you yet!\n\n"
                "As we chat, I'll learn about your preferences and needs.\n"
                "You can also use `/remember` to tell me specific things to remember."
            )

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error retrieving memories: {e}")
        await update.message.reply_text("❌ Sorry, I couldn't retrieve your memories.")


async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /forget command to clear user memories."""
    if (
        not await check_authorization(update)
        or not update.effective_chat
        or not update.message
    ):
        return

    chat_id = str(update.effective_chat.id)

    try:
        await bot_memory.forget_memories(chat_id)
        await update.message.reply_text(
            "🧹 I've forgotten everything I knew about you.\n\n"
            "Your memories have been cleared. We can start fresh!"
        )
    except Exception as e:
        logger.error(f"Error forgetting memories: {e}")
        await update.message.reply_text("❌ Sorry, I couldn't clear your memories.")


async def graph_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /graph command to explore knowledge graph relationships."""
    if (
        not await check_authorization(update)
        or not update.effective_chat
        or not update.message
    ):
        return

    chat_id = str(update.effective_chat.id)

    # Check if graph is available
    if not bot_memory.has_graph:
        await update.message.reply_text(
            "🕸️ **Knowledge Graph not available**\n\n"
            "The graph memory feature requires Neo4j to be configured.\n"
            "See the documentation for setup instructions."
        )
        return

    # Get entity from command arguments if provided
    text = update.message.text.replace("/graph", "").strip()

    try:
        if text:
            # Query specific entity
            relationships = await bot_memory.get_graph_relationships(
                chat_id, entity=text
            )

            if relationships:
                response = f"🕸️ **Connections for '{text}':**\n\n"

                for rel in relationships[:10]:  # Limit to 10
                    if isinstance(rel, dict):
                        source = rel.get("source", "?")
                        relation = rel.get("relationship", "related to")
                        target = rel.get("target", "?")
                        response += f"• {source} → _{relation}_ → {target}\n"
                    else:
                        response += f"• {rel}\n"

                if len(relationships) > 10:
                    response += f"\n_...and {len(relationships) - 10} more connections_"
            else:
                response = f"No connections found for '{text}'"

        else:
            # Show all relationships
            relationships = await bot_memory.get_graph_relationships(chat_id)

            if relationships:
                response = "🕸️ **Your Knowledge Graph:**\n\n"

                # Group by entity
                entity_map: Dict[str, Any] = {}
                for rel in relationships:
                    if isinstance(rel, dict):
                        source = rel.get("source", "")
                        if source and source not in entity_map:
                            entity_map[source] = []
                        if source:
                            entity_map[source].append(rel)

                # Show top entities
                for entity, rels in list(entity_map.items())[:5]:
                    response += f"**{entity}:**\n"
                    for rel in rels[:3]:
                        relation = rel.get("relationship", "related to")
                        target = rel.get("target", "?")
                        response += f"  • _{relation}_ → {target}\n"
                    if len(rels) > 3:
                        response += f"  _...and {len(rels) - 3} more_\n"
                    response += "\n"

                if len(entity_map) > 5:
                    response += f"_...and {len(entity_map) - 5} more entities_\n\n"

                response += "💡 Use `/graph [entity]` to explore specific connections"
            else:
                response = (
                    "🕸️ **No knowledge graph yet!**\n\n"
                    "As we chat, I'll build a graph of entities and their relationships.\n"
                    "The more we interact, the richer your knowledge graph becomes!"
                )

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error exploring graph: {e}")
        await update.message.reply_text(
            "❌ Sorry, I couldn't explore the knowledge graph."
        )
