#!/usr/bin/env python3
"""
🚀 Local Development Server for Markdown Brain Bot

This script provides an excellent local development experience with:
1. Interactive CLI for sending test messages
2. Full logging and stack traces visible
3. Direct webhook handler simulation
4. No network round-trip delays
5. Easy debugging with breakpoints

Usage:
    python scripts/local_dev.py

    # In the interactive prompt:
    > Create a shopping list with milk and eggs
    > /help
    > Add bread to shopping list
    > quit

Features:
- Simulates Telegram webhook payloads locally
- Shows full request/response logs
- Supports all bot commands and features
- Perfect for development and testing
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# These imports must come after the path setup
from telegram import Update  # noqa: E402

from bot.webhook_bot import WebhookTelegramBot  # noqa: E402

# Set up detailed logging for development
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [🕰️ %(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/local_dev.log", mode="a"),
    ],
)
logger = logging.getLogger("local_dev")

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)


class LocalDevSimulator:
    """
    Local development simulator that mimics Telegram webhook behavior.

    This allows for rapid development and testing without needing ngrok
    or actual Telegram infrastructure.
    """

    def __init__(self):
        """Initialize the local development simulator."""
        # Initialize the webhook bot
        self.bot = WebhookTelegramBot()
        self.chat_id = "local_dev_chat"
        self.user_id = "local_dev_user"
        self.message_id = 1

        logger.info("🚀 Local Development Simulator initialized")
        logger.info(f"Chat ID: {self.chat_id}")
        logger.info(f"User ID: {self.user_id}")

    def create_message_update(
        self, text: str, message_type: str = "text"
    ) -> Dict[str, Any]:
        """
        Create a Telegram Update object for a text message.

        Args:
            text: The message text
            message_type: Type of message ("text", "command")

        Returns:
            Dictionary representing a Telegram update
        """
        return {
            "update_id": self.message_id,
            "message": {
                "message_id": self.message_id,
                "from": {
                    "id": self.user_id,
                    "is_bot": False,
                    "first_name": "Developer",
                    "username": "local_dev",
                    "language_code": "en",
                },
                "chat": {
                    "id": self.chat_id,
                    "first_name": "Developer",
                    "username": "local_dev",
                    "type": "private",
                },
                "date": int(datetime.now().timestamp()),
                "text": text,
            },
        }

    def create_document_update(self, filename: str, content: str) -> Dict[str, Any]:
        """
        Create a Telegram Update object for a document upload.

        Args:
            filename: Name of the file
            content: File content

        Returns:
            Dictionary representing a Telegram document update
        """
        return {
            "update_id": self.message_id,
            "message": {
                "message_id": self.message_id,
                "from": {
                    "id": self.user_id,
                    "is_bot": False,
                    "first_name": "Developer",
                    "username": "local_dev",
                },
                "chat": {
                    "id": self.chat_id,
                    "first_name": "Developer",
                    "username": "local_dev",
                    "type": "private",
                },
                "date": int(datetime.now().timestamp()),
                "document": {
                    "file_name": filename,
                    "mime_type": "text/markdown",
                    "file_id": f"local_file_{self.message_id}",
                    "file_unique_id": f"local_unique_{self.message_id}",
                    "file_size": len(content),
                },
            },
        }

    async def simulate_message(self, text: str) -> bool:
        """
        Simulate sending a message to the bot.

        Args:
            text: The message text to send

        Returns:
            True if successful, False if error occurred
        """
        try:
            # Create the update payload
            update_data = self.create_message_update(text)

            logger.info(f"📥 🏠 Simulating message: '{text}'")
            logger.debug(f"Update payload: {json.dumps(update_data, indent=2)}")

            # Convert to Telegram Update object
            update = Update.de_json(update_data, self.bot.application.bot)

            # Process the update through the bot
            await self.bot.application.process_update(update)

            # Increment message ID for next message
            self.message_id += 1

            logger.info("✅ Message processed successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Error processing message: {e}", exc_info=True)
            return False

    async def simulate_document(self, filename: str, content: str) -> bool:
        """
        Simulate uploading a document to the bot.

        Args:
            filename: Name of the file
            content: File content

        Returns:
            True if successful, False if error occurred
        """
        try:
            # Create the update payload
            update_data = self.create_document_update(filename, content)

            logger.info(f"📎 🏠 Simulating document upload: '{filename}'")
            logger.debug(f"Update payload: {json.dumps(update_data, indent=2)}")

            # Convert to Telegram Update object
            update = Update.de_json(update_data, self.bot.application.bot)

            # Process the update through the bot
            await self.bot.application.process_update(update)

            # Increment message ID for next message
            self.message_id += 1

            logger.info("✅ Document processed successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Error processing document: {e}", exc_info=True)
            return False

    async def run_interactive(self):
        """
        Run the interactive development console.
        """
        print()
        print("🧠 Markdown Brain Bot - Local Development Console")
        print("=" * 50)
        print()
        print("This simulator lets you test the bot locally with full logging.")
        print("Type messages as if you were chatting with the bot.")
        print()
        print("Commands:")
        print("  - Type any message to send to bot")
        print("  - 'upload <filename>' to simulate file upload")
        print("  - 'quit' or 'exit' to stop")
        print("  - 'help' to show bot help")
        print()
        print("Logs are also saved to: logs/local_dev.log")
        print()

        # Start the bot application
        async with self.bot.application:
            await self.bot.application.initialize()
            await self.bot.application.start()

            try:
                while True:
                    # Get input from user
                    try:
                        user_input = input("💬 Enter message (or 'quit'): ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print("\n👋 Goodbye!")
                        break

                    if not user_input:
                        continue

                    # Handle special commands
                    if user_input.lower() in ["quit", "exit"]:
                        print("👋 Goodbye!")
                        break

                    if user_input.lower().startswith("upload "):
                        # Simulate document upload
                        filename = user_input[7:].strip() or "test_document.md"
                        content = f"# Test Document\n\nThis is a test document uploaded via local dev simulator.\n\nFilename: {filename}\nTimestamp: {datetime.now()}"
                        await self.simulate_document(filename, content)
                    else:
                        # Simulate regular message
                        await self.simulate_message(user_input)

                    print()  # Add spacing between interactions

            finally:
                await self.bot.application.stop()


async def main():
    """
    Main entry point for local development simulator.
    """
    simulator = LocalDevSimulator()
    await simulator.run_interactive()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Development session ended.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
