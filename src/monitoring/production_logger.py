"""
Production Logging for FLRTS-BMAD

Enhanced logging for production monitoring, with special focus on
Story 1.6 direct execution performance and user patterns.
"""

import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Optional


@dataclass
class DirectExecutionMetrics:
    """Metrics for Story 1.6 direct execution."""

    operation: str
    entity_type: str
    confidence: float
    execution_time_ms: float
    success: bool
    user_id: str
    bypassed_llm: bool
    timestamp: str
    error: Optional[str] = None


class ProductionLogger:
    """Enhanced logger for production monitoring."""

    def __init__(self, logger_name: str = "flrts.production"):
        self.logger = logging.getLogger(logger_name)
        self.direct_execution_metrics: list[DirectExecutionMetrics] = []

        # Configure structured logging format
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Add console handler if not exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_direct_execution(
        self,
        operation: str,
        entity_type: str,
        confidence: float,
        execution_time_ms: float,
        success: bool,
        user_id: str,
        bypassed_llm: bool,
        error: Optional[str] = None,
    ) -> None:
        """Log Story 1.6 direct execution metrics."""

        metrics = DirectExecutionMetrics(
            operation=operation,
            entity_type=entity_type,
            confidence=confidence,
            execution_time_ms=execution_time_ms,
            success=success,
            user_id=user_id,
            bypassed_llm=bypassed_llm,
            timestamp=datetime.utcnow().isoformat(),
            error=error,
        )

        # Store metrics
        self.direct_execution_metrics.append(metrics)

        # Log based on performance and success
        log_level = logging.INFO
        if not success:
            log_level = logging.ERROR
        elif execution_time_ms > 500:
            log_level = logging.WARNING

        _ = {
            "direct_execution": asdict(metrics),
            "performance_target": "<500ms",
            "met_target": execution_time_ms < 500,
        }

        self.logger.log(
            log_level,
            f"[STORY-1.6-DIRECT] {operation} for {entity_type}: "
            f"{'SUCCESS' if success else 'FAILED'} in {execution_time_ms:.1f}ms "
            f"(confidence: {confidence:.2f}, bypassed_llm: {bypassed_llm})",
        )

        # Keep metrics list manageable (last 1000 operations)
        if len(self.direct_execution_metrics) > 1000:
            self.direct_execution_metrics = self.direct_execution_metrics[-1000:]

    def log_router_decision(
        self,
        message: str,
        entity_type: Optional[str],
        operation: Optional[str],
        confidence: float,
        use_direct_execution: bool,
        user_id: str,
    ) -> None:
        """Log router routing decisions."""

        _ = {
            "router_decision": {
                "message_length": len(message),
                "entity_type": entity_type,
                "operation": operation,
                "confidence": confidence,
                "use_direct_execution": use_direct_execution,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        self.logger.info(
            f"[STORY-1.6-ROUTER] {entity_type}/{operation} "
            f"(confidence: {confidence:.2f}, direct: {use_direct_execution})"
        )

    def log_performance_warning(
        self,
        component: str,
        operation: str,
        actual_time_ms: float,
        target_time_ms: float,
        user_id: str,
    ) -> None:
        """Log performance warnings."""

        _ = {
            "performance_warning": {
                "component": component,
                "operation": operation,
                "actual_time_ms": actual_time_ms,
                "target_time_ms": target_time_ms,
                "overage_ms": actual_time_ms - target_time_ms,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        self.logger.warning(
            f"[STORY-1.6-PERF] {component} {operation} "
            f"took {actual_time_ms:.1f}ms (target: {target_time_ms:.1f}ms)"
        )

    def log_system_event(
        self, event_type: str, details: Dict[str, Any], level: str = "info"
    ) -> None:
        """Log general system events."""

        _ = {
            "system_event": {
                "event_type": event_type,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        log_level = getattr(logging, level.upper(), logging.INFO)

        self.logger.log(log_level, f"[STORY-1.6-SYSTEM] {event_type}")

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for monitoring."""
        if not self.direct_execution_metrics:
            return {"status": "no_data"}

        recent_metrics = self.direct_execution_metrics[-50:]  # Last 50 operations

        # Calculate statistics
        execution_times = [m.execution_time_ms for m in recent_metrics]
        success_rate = sum(1 for m in recent_metrics if m.success) / len(recent_metrics)

        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)
        under_target = sum(1 for t in execution_times if t < 500) / len(execution_times)

        # Group by entity type
        entity_stats = {}
        for metrics in recent_metrics:
            entity = metrics.entity_type
            if entity not in entity_stats:
                entity_stats[entity] = {
                    "count": 0,
                    "avg_time": 0.0,
                    "success_rate": 0.0,
                }

            entity_stats[entity]["count"] += 1
            entity_stats[entity]["avg_time"] += metrics.execution_time_ms
            entity_stats[entity]["success_rate"] += 1 if metrics.success else 0

        # Finalize entity stats
        for entity, stats in entity_stats.items():
            stats["avg_time"] /= stats["count"]
            stats["success_rate"] /= stats["count"]

        return {
            "summary": {
                "total_operations": len(recent_metrics),
                "success_rate": round(success_rate, 3),
                "avg_execution_time_ms": round(avg_time, 1),
                "max_execution_time_ms": round(max_time, 1),
                "under_500ms_rate": round(under_target, 3),
                "story_1_6_performance": (
                    "optimal"
                    if avg_time < 200
                    else "good" if avg_time < 500 else "needs_attention"
                ),
            },
            "by_entity": entity_stats,
            "timestamp": datetime.utcnow().isoformat(),
        }


def log_direct_execution_performance(logger: ProductionLogger):
    """Decorator to log direct execution performance."""

    def decorator(func):
        @wraps(func)
        async def wrapper(
            self, operation: str, extracted_data: Dict[str, Any], user_id: str
        ):
            start_time = time.perf_counter()
            success = False
            error = None

            try:
                result = await func(self, operation, extracted_data, user_id)
                success = result.get("success", False)
                if not success:
                    error = result.get("error", "Unknown error")
                return result

            except Exception as e:
                error = str(e)
                raise

            finally:
                execution_time_ms = (time.perf_counter() - start_time) * 1000

                # Determine entity type from processor class
                entity_type = "unknown"
                if hasattr(self, "__class__"):
                    if "Task" in self.__class__.__name__:
                        entity_type = "tasks"
                    elif "List" in self.__class__.__name__:
                        entity_type = "lists"
                    elif "FieldReport" in self.__class__.__name__:
                        entity_type = "field_reports"

                logger.log_direct_execution(
                    operation=operation,
                    entity_type=entity_type,
                    confidence=1.0,  # Direct execution means high confidence
                    execution_time_ms=execution_time_ms,
                    success=success,
                    user_id=user_id,
                    bypassed_llm=True,
                    error=error,
                )

        return wrapper

    return decorator


# Global production logger instance
production_logger = ProductionLogger()


def setup_production_logging():
    """Set up production logging configuration."""

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Configure specific loggers
    logging.getLogger("src.rails").setLevel(logging.INFO)
    logging.getLogger("src.rails.processors").setLevel(logging.INFO)
    logging.getLogger("src.health").setLevel(logging.INFO)

    # Log startup
    production_logger.log_system_event(
        "application_startup",
        {
            "story_1_6_enabled": True,
            "direct_execution_ready": True,
            "target_users": "5-20",
            "performance_target": "<500ms",
        },
    )

    logging.getLogger("flrts.production").info(
        "Production logging configured for FLRTS-BMAD with Story 1.6 monitoring"
    )
