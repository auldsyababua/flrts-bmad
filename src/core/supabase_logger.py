"""Supabase-backed logging for real-time log access."""

import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

# Get Supabase credentials from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")


class SupabaseLogHandler(logging.Handler):
    """Custom log handler that writes to Supabase for real-time access."""

    def __init__(
        self,
        supabase_client: Optional[Client] = None,
        batch_size: int = 10,
        flush_interval: int = 5,
    ):
        super().__init__()
        self.supabase = supabase_client or create_client(SUPABASE_URL, SUPABASE_KEY)
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.log_buffer: List[Dict[str, Any]] = []
        self.last_flush = time.time()

    def emit(self, record: logging.LogRecord) -> None:
        """Handle a log record."""
        try:
            # Build log entry
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "component": record.name,
                "message": self.format(record),
            }

            # Extract custom attributes if present
            custom_attrs = [
                "user_id",
                "chat_id",
                "operation",
                "entity_type",
                "confidence",
                "response_time_ms",
                "error",
            ]

            for attr in custom_attrs:
                if hasattr(record, attr):
                    value = getattr(record, attr)
                    # Convert non-serializable types
                    if isinstance(value, (list, dict)):
                        log_entry[attr] = value
                    else:
                        log_entry[attr] = str(value) if value is not None else None

            # Add any metadata
            if hasattr(record, "metadata"):
                log_entry["metadata"] = record.metadata

            # Add to buffer
            self.log_buffer.append(log_entry)

            # Check if we should flush
            should_flush = (
                len(self.log_buffer) >= self.batch_size
                or time.time() - self.last_flush > self.flush_interval
                or record.levelname in ["ERROR", "CRITICAL"]
            )

            if should_flush:
                self.flush()

        except Exception as e:
            # Don't let logging errors break the app
            print(f"Error in SupabaseLogHandler: {e}")

    def flush(self) -> None:
        """Write buffered logs to Supabase."""
        if not self.log_buffer:
            return

        try:
            # Insert logs in batch
            self.supabase.table("bot_logs").insert(self.log_buffer).execute()
            self.log_buffer = []
            self.last_flush = time.time()
        except Exception as e:
            print(f"Error flushing logs to Supabase: {e}")
            # Clear buffer to prevent memory issues
            self.log_buffer = []
            self.last_flush = time.time()


def setup_supabase_logging(
    logger: logging.Logger = None, level: int = logging.INFO
) -> SupabaseLogHandler:
    """Set up Supabase logging handler."""
    if logger is None:
        logger = logging.getLogger()

    # Create handler
    handler = SupabaseLogHandler()
    handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    # Add to logger
    logger.addHandler(handler)

    return handler


def log_operation(logger: logging.Logger, level: int, message: str, **kwargs) -> None:
    """Log with structured data for easy querying.

    Args:
        logger: Logger instance
        level: Log level (e.g., logging.INFO)
        message: Log message
        **kwargs: Additional fields (user_id, operation, entity_type, etc.)
    """
    # Create a log record with extra fields
    extra: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if value is not None:
            extra[key] = value

    logger.log(level, message, extra=extra)


# Convenience functions
def log_routing_decision(
    logger: logging.Logger,
    message: str,
    entity_type: str,
    operation: str,
    confidence: float,
    user_id: int = None,
    **kwargs,
) -> None:
    """Log a routing decision with all relevant data."""
    log_operation(
        logger,
        logging.INFO,
        f"Routed: {message[:50]}...",
        entity_type=entity_type,
        operation=operation,
        confidence=confidence,
        user_id=user_id,
        **kwargs,
    )


def log_performance(
    logger: logging.Logger,
    operation: str,
    duration_ms: int,
    user_id: int = None,
    **kwargs,
) -> None:
    """Log performance metrics."""
    level = logging.WARNING if duration_ms > 1000 else logging.INFO
    log_operation(
        logger,
        level,
        f"{operation} took {duration_ms}ms",
        operation=operation,
        response_time_ms=duration_ms,
        user_id=user_id,
        **kwargs,
    )
