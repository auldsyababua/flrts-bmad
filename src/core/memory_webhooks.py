"""
Memory webhook system for real-time memory event notifications.

This module provides a centralized webhook handler for memory-related events
such as memory addition, updates, deletions, and optimization operations.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class MemoryWebhookEvent(Enum):
    """Enumeration of memory webhook events."""

    MEMORY_ADDED = "memory_added"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_DELETED = "memory_deleted"
    MEMORY_RETRIEVED = "memory_retrieved"
    MEMORY_SEARCHED = "memory_searched"
    MEMORY_OPTIMIZED = "memory_optimized"
    MEMORY_ERROR = "memory_error"
    BATCH_OPERATION_COMPLETED = "batch_operation_completed"
    GRAPH_RELATIONSHIP_ADDED = "graph_relationship_added"
    GRAPH_RELATIONSHIP_UPDATED = "graph_relationship_updated"
    GRAPH_RELATIONSHIP_DELETED = "graph_relationship_deleted"
    PREFERENCE_STORED = "preference_stored"
    CORRECTION_STORED = "correction_stored"
    RELATIONSHIP_ADDED = "relationship_added"
    GRAPH_BUILT = "graph_built"


@dataclass
class WebhookConfig:
    """Configuration for webhook delivery."""

    url: Optional[str] = None
    headers: Dict[str, str] = None
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    enabled: bool = True

    def __post_init__(self):
        if self.headers is None:
            self.headers = {"Content-Type": "application/json"}


class MemoryWebhookHandler:
    """
    Centralized handler for memory webhook events.

    Provides reliable webhook delivery with retry logic, error handling,
    and configurable delivery options.
    """

    def __init__(self):
        """Initialize webhook handler with configuration from environment."""
        self.config = WebhookConfig(
            url=os.getenv("MEMORY_WEBHOOK_URL"),
            headers=self._get_webhook_headers(),
            timeout=int(os.getenv("MEMORY_WEBHOOK_TIMEOUT", "30")),
            retry_attempts=int(os.getenv("MEMORY_WEBHOOK_RETRY_ATTEMPTS", "3")),
            retry_delay=float(os.getenv("MEMORY_WEBHOOK_RETRY_DELAY", "1.0")),
            enabled=os.getenv("MEMORY_WEBHOOK_ENABLED", "true").lower() == "true",
        )

    def _get_webhook_headers(self) -> Dict[str, str]:
        """Get webhook headers from environment configuration."""
        headers = {"Content-Type": "application/json"}

        # Add authorization header if configured
        auth_header = os.getenv("MEMORY_WEBHOOK_AUTH_HEADER")
        if auth_header:
            headers["Authorization"] = auth_header

        # Add custom headers from environment
        custom_headers = os.getenv("MEMORY_WEBHOOK_HEADERS")
        if custom_headers:
            try:
                import json

                headers.update(json.loads(custom_headers))
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in MEMORY_WEBHOOK_HEADERS, ignoring")

        return headers

    async def send_webhook(
        self,
        event: MemoryWebhookEvent,
        user_id: str,
        data: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send a webhook notification for a memory event.

        Args:
            event: The type of memory event
            user_id: ID of the user associated with the event
            data: Event-specific data payload
            metadata: Additional metadata for the event

        Returns:
            bool: True if webhook was successfully delivered, False otherwise
        """
        if not self.config.enabled or not self.config.url:
            logger.debug("Webhook delivery disabled or URL not configured")
            return False

        payload = {
            "event": event.value,
            "user_id": user_id,
            "data": data,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "service": "markdown-brain-bot",
            "version": "1.0",
        }

        for attempt in range(self.config.retry_attempts):
            try:
                success = await self._deliver_webhook(payload)
                if success:
                    logger.info(
                        f"Webhook delivered successfully: {event.value} for user {user_id}"
                    )
                    return True

            except Exception as e:
                logger.warning(f"Webhook delivery attempt {attempt + 1} failed: {e}")

            # Wait before retry (except on last attempt)
            if attempt < self.config.retry_attempts - 1:
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        logger.error(
            f"Webhook delivery failed after {self.config.retry_attempts} attempts"
        )
        return False

    async def _deliver_webhook(self, payload: Dict[str, Any]) -> bool:
        """
        Deliver a webhook payload to the configured endpoint.

        Args:
            payload: The webhook payload to send

        Returns:
            bool: True if delivery was successful, False otherwise
        """
        try:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.config.url,
                    json=payload,
                    headers=self.config.headers,
                ) as response:
                    # Consider 2xx status codes as success
                    if 200 <= response.status < 300:
                        return True
                    else:
                        logger.warning(
                            f"Webhook endpoint returned status {response.status}: "
                            f"{await response.text()}"
                        )
                        return False

        except asyncio.TimeoutError:
            logger.warning(f"Webhook delivery timed out after {self.config.timeout}s")
            return False
        except aiohttp.ClientError as e:
            logger.warning(f"HTTP client error during webhook delivery: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during webhook delivery: {e}")
            return False

    def is_enabled(self) -> bool:
        """Check if webhook delivery is enabled and configured."""
        return self.config.enabled and bool(self.config.url)

    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current webhook configuration."""
        return {
            "enabled": self.config.enabled,
            "url_configured": bool(self.config.url),
            "timeout": self.config.timeout,
            "retry_attempts": self.config.retry_attempts,
            "retry_delay": self.config.retry_delay,
            "headers_count": len(self.config.headers),
        }


# Global webhook handler instance
memory_webhook_handler = MemoryWebhookHandler()


# Convenience functions for common webhook events
async def notify_memory_added(user_id: str, memory_data: Any) -> bool:
    """Send webhook notification for memory addition."""
    return await memory_webhook_handler.send_webhook(
        event=MemoryWebhookEvent.MEMORY_ADDED,
        user_id=user_id,
        data=memory_data,
    )


async def notify_memory_error(user_id: str, operation: str, error: str) -> bool:
    """Send webhook notification for memory errors."""
    return await memory_webhook_handler.send_webhook(
        event=MemoryWebhookEvent.MEMORY_ERROR,
        user_id=user_id,
        data={"operation": operation, "error": error},
    )


async def notify_batch_completed(
    user_id: str, operation: str, results: Dict[str, Any]
) -> bool:
    """Send webhook notification for batch operation completion."""
    return await memory_webhook_handler.send_webhook(
        event=MemoryWebhookEvent.BATCH_OPERATION_COMPLETED,
        user_id=user_id,
        data={"operation": operation, **results},
    )


async def notify_graph_relationship_added(
    user_id: str, relationship_data: Dict[str, Any]
) -> bool:
    """Send webhook notification for graph relationship addition."""
    return await memory_webhook_handler.send_webhook(
        event=MemoryWebhookEvent.GRAPH_RELATIONSHIP_ADDED,
        user_id=user_id,
        data=relationship_data,
    )
