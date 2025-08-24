"""
Performance benchmarking and monitoring system for BrainBot.

This module provides utilities for tracking and analyzing performance metrics
across all major operations including vector search, LLM calls, and Redis operations.
"""

import json
import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Central performance monitoring and metrics collection."""

    def __init__(self):
        """Initialize the performance monitor with Cloudflare KV cache."""
        # Lazy import to avoid circular dependency
        from storage.cloudflare_cache import CloudflareRedis

        self.redis = CloudflareRedis()
        self.ttl_seconds = 604800  # 7 days

    def track_metric(
        self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None
    ):
        """Track a performance metric.

        Args:
            metric_name: Name of the metric (e.g., "vector_search_duration")
            value: Numeric value of the metric
            tags: Optional tags for categorization
        """
        timestamp = time.time()
        metric_key = f"metrics:{metric_name}"

        # Store as sorted set with timestamp as score
        metric_data = json.dumps({"value": value, "tags": tags or {}})
        self.redis.zadd(metric_key, {metric_data: timestamp})

        # Expire old metrics after 7 days
        self.redis.expire(metric_key, self.ttl_seconds)

        # Update aggregated stats
        self._update_aggregates(metric_name, value)

    def _update_aggregates(self, metric_name: str, value: float):
        """Update aggregated statistics for a metric."""
        stats_key = f"stats:{metric_name}"

        # Get current stats
        current_stats = self.redis.hgetall(stats_key) or {}

        # Update count
        count = int(current_stats.get("count", 0)) + 1
        self.redis.hset(stats_key, "count", count)

        # Update sum for average calculation
        current_sum = float(current_stats.get("sum", 0))
        self.redis.hset(stats_key, "sum", current_sum + value)

        # Update min/max
        current_min = float(current_stats.get("min", float("inf")))
        current_max = float(current_stats.get("max", float("-inf")))

        if value < current_min:
            self.redis.hset(stats_key, "min", value)
        if value > current_max:
            self.redis.hset(stats_key, "max", value)

        # Set expiration
        self.redis.expire(stats_key, self.ttl_seconds)

    def track_vector_search(
        self, query: str, results_count: int, duration: float, cache_hit: bool = False
    ):
        """Track vector search performance metrics."""
        self.track_metric(
            "vector_search_duration",
            duration,
            {
                "results_count": str(results_count),
                "cache_hit": str(cache_hit),
                "query_length": str(len(query)),
            },
        )

        # Track cache hit rate
        if cache_hit:
            self.redis.incr("metrics:vector_cache_hits")
        self.redis.incr("metrics:vector_searches_total")

    def track_llm_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration: float,
        retry_count: int = 0,
    ):
        """Track LLM API call performance metrics."""
        self.track_metric(
            "llm_call_duration",
            duration,
            {
                "model": model,
                "prompt_tokens": str(prompt_tokens),
                "completion_tokens": str(completion_tokens),
                "total_tokens": str(prompt_tokens + completion_tokens),
                "retry_count": str(retry_count),
            },
        )

        # Track token usage
        self.redis.incrby(
            "metrics:total_tokens_used", prompt_tokens + completion_tokens
        )

    def track_conversation_size(self, chat_id: str, message_count: int):
        """Track conversation history size."""
        self.track_metric("conversation_size", message_count, {"chat_id": str(chat_id)})

    def get_performance_summary(
        self, metric_names: Optional[List[str]] = None, time_range_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get performance metrics summary.

        Args:
            metric_names: Optional list of specific metrics to include
            time_range_minutes: Time range to consider for recent metrics

        Returns:
            Dictionary containing performance statistics
        """
        if not metric_names:
            metric_names = [
                "vector_search_duration",
                "llm_call_duration",
                "conversation_size",
            ]

        summary: Dict[str, Any] = {}
        cutoff_time = time.time() - (time_range_minutes * 60)

        for metric_name in metric_names:
            stats_key = f"stats:{metric_name}"
            metric_key = f"metrics:{metric_name}"

            # Get aggregated stats
            stats = self.redis.hgetall(stats_key) or {}
            if stats and stats.get("count"):
                count = int(stats["count"])
                total = float(stats["sum"])

                summary[metric_name] = {
                    "count": count,
                    "average": total / count if count > 0 else 0,
                    "min": float(stats.get("min", 0)),
                    "max": float(stats.get("max", 0)),
                    "total": total,
                }

                # Get recent values for percentiles
                recent_values = self.redis.zrangebyscore(
                    metric_key, cutoff_time, "+inf"
                )

                if recent_values:
                    values = [json.loads(v)["value"] for v in recent_values]
                    values.sort()

                    # Calculate percentiles
                    summary[metric_name]["p50"] = values[len(values) // 2]
                    if len(values) > 1:
                        summary[metric_name]["p95"] = values[int(len(values) * 0.95)]
                        summary[metric_name]["p99"] = values[int(len(values) * 0.99)]

        # Add cache hit rate
        cache_hits = int(self.redis.get("metrics:vector_cache_hits") or 0)
        total_searches = int(self.redis.get("metrics:vector_searches_total") or 0)

        if total_searches > 0:
            summary["cache_hit_rate"] = float(cache_hits) / float(total_searches)
        else:
            summary["cache_hit_rate"] = 0.0

        # Add total token usage
        summary["total_tokens_used"] = int(
            self.redis.get("metrics:total_tokens_used") or 0
        )

        return summary

    def cleanup_old_metrics(self, days_to_keep: int = 7):
        """Clean up metrics older than specified days."""
        cutoff_time = time.time() - (days_to_keep * 86400)

        # Get all metric keys
        metric_keys = self.redis.keys("metrics:*")

        for key in metric_keys:
            if key.startswith("metrics:") and ":" in key[8:]:
                # This is a time-series metric, clean old entries
                self.redis.zremrangebyscore(key, "-inf", cutoff_time)


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


@contextmanager
def benchmark(operation_name: str):
    """Context manager for benchmarking synchronous operations.

    Usage:
        with benchmark("my_operation"):
            # Your code here
            pass
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        logger.info(f"⏱️ {operation_name}: {duration:.3f}s")

        # Track in Redis
        try:
            monitor = get_performance_monitor()
            monitor.track_metric(f"benchmark_{operation_name}", duration)
        except Exception as e:
            logger.warning(f"Failed to track benchmark metric: {e}")


def async_benchmark(operation_name: str):
    """Decorator for benchmarking async functions.

    Usage:
        @async_benchmark("my_async_operation")
        async def my_function():
            # Your async code here
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start
                logger.info(f"⏱️ {operation_name}: {duration:.3f}s")

                # Track in Redis
                try:
                    monitor = get_performance_monitor()
                    monitor.track_metric(f"benchmark_{operation_name}", duration)
                except Exception as e:
                    logger.warning(f"Failed to track benchmark metric: {e}")

        return wrapper

    return decorator


class PerformanceMiddleware:
    """FastAPI middleware for tracking HTTP request performance."""

    def __init__(self):
        self.monitor = None

    async def __call__(self, request, call_next):
        """Track request performance metrics."""
        if not self.monitor:
            self.monitor = get_performance_monitor()

        start_time = time.perf_counter()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.perf_counter() - start_time

        # Track metrics
        try:
            self.monitor.track_metric(
                "http_request_duration",
                duration,
                {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": str(response.status_code),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to track HTTP metric: {e}")

        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration:.3f}"

        return response
