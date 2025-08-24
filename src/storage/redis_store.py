"""
Redis store for persistent conversation memory using Cloudflare KV.
Provides compatibility layer for existing code that uses RedisStore.
"""

import json
from typing import Dict, List, Optional

from dotenv import load_dotenv

from .cloudflare_cache import CloudflareRedis

# Load environment variables
load_dotenv()


class RedisStore:
    """Handles persistent conversation storage using Cloudflare KV."""

    def __init__(self):
        """Initialize Redis-compatible client."""
        self.redis = CloudflareRedis()
        self.ttl_seconds = (
            86400  # 24 hours default TTL - matches ConversationManager default
        )

    async def get_conversation(self, chat_id: str) -> Optional[List[Dict]]:
        """
        Retrieve conversation history for a given chat ID.

        Args:
            chat_id: Unique identifier for the chat/conversation

        Returns:
            List of message dictionaries or None if not found
        """
        try:
            key = f"conv:{chat_id}"
            data = self.redis.get(key)

            if data is None:
                return None

            # Parse JSON string back to list
            return json.loads(data)
        except Exception as e:
            print(f"Error retrieving conversation {chat_id}: {e}")
            return None

    async def save_conversation(self, chat_id: str, messages: List[Dict]) -> bool:
        """
        Save conversation history with automatic expiration.

        Args:
            chat_id: Unique identifier for the chat/conversation
            messages: List of message dictionaries to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            key = f"conv:{chat_id}"
            # Convert messages to JSON string
            data = json.dumps(messages)

            # Set with expiration
            self.redis.setex(key, self.ttl_seconds, data)
            return True
        except Exception as e:
            print(f"Error saving conversation {chat_id}: {e}")
            return False

    async def extend_conversation_ttl(self, chat_id: str) -> bool:
        """
        Extend the TTL of an existing conversation.

        Args:
            chat_id: Unique identifier for the chat/conversation

        Returns:
            True if TTL extended successfully, False otherwise
        """
        try:
            key = f"conv:{chat_id}"
            return self.redis.expire(key, self.ttl_seconds)
        except Exception as e:
            print(f"Error extending TTL for {chat_id}: {e}")
            return False

    async def delete_conversation(self, chat_id: str) -> bool:
        """
        Delete a conversation from Redis.

        Args:
            chat_id: Unique identifier for the chat/conversation

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            key = f"conv:{chat_id}"
            self.redis.delete(key)
            return True
        except Exception as e:
            print(f"Error deleting conversation {chat_id}: {e}")
            return False

    async def get_active_conversations(self) -> List[str]:
        """
        Get list of all active conversation IDs.

        Returns:
            List of chat IDs that have active conversations
        """
        try:
            # Note: Upstash doesn't support SCAN, so we'll need to track active conversations differently
            # For now, this is a placeholder that would need a different implementation
            # Consider maintaining a separate set of active chat IDs
            keys = []
            return keys
        except Exception as e:
            print(f"Error getting active conversations: {e}")
            return []

    async def get_conversation_metadata(self, chat_id: str) -> Optional[Dict]:
        """
        Get metadata about a conversation (TTL, size, etc).

        Args:
            chat_id: Unique identifier for the chat/conversation

        Returns:
            Dictionary with metadata or None if not found
        """
        try:
            key = f"conv:{chat_id}"

            # Get TTL
            ttl = self.redis.ttl(key)
            if ttl == -2:  # Key doesn't exist
                return None

            # Get conversation data to check size
            data = self.redis.get(key)
            if data is None:
                return None

            messages = json.loads(data)

            return {
                "chat_id": chat_id,
                "ttl_seconds": ttl if ttl > 0 else None,
                "message_count": len(messages),
                "size_bytes": len(data),
            }
        except Exception as e:
            print(f"Error getting metadata for {chat_id}: {e}")
            return None


# Singleton instance
redis_store = RedisStore()
