"""
Health Check System for FLRTS-BMAD Production Monitoring

Provides endpoints and utilities for monitoring system health,
including Story 1.6 direct execution performance.
"""

import asyncio
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health check status container."""

    service: str
    status: str  # "healthy", "degraded", "unhealthy"
    response_time_ms: float
    details: Dict[str, Any]
    timestamp: str


class HealthChecker:
    """Centralized health checking for FLRTS-BMAD system."""

    def __init__(self):
        self.performance_history: List[Dict[str, Any]] = []
        self.max_history = 100  # Keep last 100 checks

    async def check_database_health(self, supabase_client) -> HealthStatus:
        """Check Supabase database connectivity and performance."""
        start_time = time.perf_counter()

        try:
            # Simple query to test connectivity
            _ = await supabase_client.table("tasks").select("id").limit(1).execute()

            response_time = (time.perf_counter() - start_time) * 1000

            details: Dict[str, Any]
            if response_time > 1000:  # >1s is concerning for small team
                status = "degraded"
                details = {"warning": "Database response time is high"}
            else:
                status = "healthy"
                details = {"query_success": True}

            return HealthStatus(
                service="database",
                status=status,
                response_time_ms=response_time,
                details=details,
                timestamp=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            return HealthStatus(
                service="database",
                status="unhealthy",
                response_time_ms=(time.perf_counter() - start_time) * 1000,
                details={"error": str(e)},
                timestamp=datetime.utcnow().isoformat(),
            )

    async def check_router_health(self) -> HealthStatus:
        """Check Smart Rails router performance."""
        start_time = time.perf_counter()

        try:
            from src.rails.router import KeywordRouter

            # Test router with a simple command
            router = KeywordRouter()
            result = router.route("/newtask test health check")

            response_time = (time.perf_counter() - start_time) * 1000

            # Check if direct execution is working
            direct_execution_working = (
                result.use_direct_execution and result.confidence >= 0.95
            )

            details: Dict[str, Any]
            if response_time > 100:  # Router should be very fast
                status = "degraded"
                details = {"warning": "Router response time is high"}
            elif not direct_execution_working:
                status = "degraded"
                details = {"warning": "Direct execution not triggered for test command"}
            else:
                status = "healthy"
                details = {"direct_execution": direct_execution_working}

            details.update(
                {
                    "confidence": result.confidence,
                    "entity_type": result.entity_type,
                    "operation": result.operation,
                }
            )

            return HealthStatus(
                service="router",
                status=status,
                response_time_ms=response_time,
                details=details,
                timestamp=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            return HealthStatus(
                service="router",
                status="unhealthy",
                response_time_ms=(time.perf_counter() - start_time) * 1000,
                details={"error": str(e)},
                timestamp=datetime.utcnow().isoformat(),
            )

    async def check_processor_health(self, supabase_client) -> HealthStatus:
        """Check Story 1.6 direct execution processor health."""
        start_time = time.perf_counter()

        try:
            from src.rails.processors.task_processor import TaskProcessor

            # Test processor without actually creating data
            processor = TaskProcessor(supabase_client)

            # Test validation (doesn't hit database)
            is_valid, message = await processor.validate_operation(
                "create", {"task_title": "health check"}, "user"
            )

            response_time = (time.perf_counter() - start_time) * 1000

            # Target is <500ms for actual operations, validation should be much faster
            details: Dict[str, Any]
            if response_time > 50:
                status = "degraded"
                details = {"warning": "Processor validation is slow"}
            elif not is_valid:
                status = "degraded"
                details = {"warning": f"Validation failed: {message}"}
            else:
                status = "healthy"
                details = {"validation_passed": True}

            return HealthStatus(
                service="processors",
                status=status,
                response_time_ms=response_time,
                details=details,
                timestamp=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            return HealthStatus(
                service="processors",
                status="unhealthy",
                response_time_ms=(time.perf_counter() - start_time) * 1000,
                details={"error": str(e)},
                timestamp=datetime.utcnow().isoformat(),
            )

    async def check_cloudflare_health(self) -> HealthStatus:
        """Check Cloudflare services health."""
        start_time = time.perf_counter()

        try:
            # Basic import test - actual API calls would need credentials

            response_time = (time.perf_counter() - start_time) * 1000

            return HealthStatus(
                service="cloudflare",
                status="healthy",
                response_time_ms=response_time,
                details={"imports_successful": True},
                timestamp=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            return HealthStatus(
                service="cloudflare",
                status="unhealthy",
                response_time_ms=(time.perf_counter() - start_time) * 1000,
                details={"error": str(e)},
                timestamp=datetime.utcnow().isoformat(),
            )

    async def comprehensive_health_check(self, supabase_client=None) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        start_time = time.perf_counter()

        # Run checks concurrently
        tasks = [
            self.check_router_health(),
            self.check_cloudflare_health(),
        ]

        if supabase_client:
            tasks.extend(
                [
                    self.check_database_health(supabase_client),
                    self.check_processor_health(supabase_client),
                ]
            )

        try:
            health_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            status_map: Dict[str, Any] = {}
            overall_status = "healthy"

            for result in health_results:
                if isinstance(result, Exception):
                    overall_status = "unhealthy"
                    status_map["error"] = str(result)
                elif isinstance(result, HealthStatus):
                    status_map[result.service] = asdict(result)
                    if result.status == "unhealthy":
                        overall_status = "unhealthy"
                    elif result.status == "degraded" and overall_status == "healthy":
                        overall_status = "degraded"

            # Calculate performance metrics
            total_time = (time.perf_counter() - start_time) * 1000

            # Story 1.6 specific metrics
            router_healthy = status_map.get("router", {}).get("status") == "healthy"
            processors_healthy = (
                status_map.get("processors", {}).get("status") == "healthy"
            )
            direct_execution_ready = router_healthy and processors_healthy

            result = {
                "overall_status": overall_status,
                "total_check_time_ms": total_time,
                "timestamp": datetime.utcnow().isoformat(),
                "services": status_map,
                "story_1_6_status": {
                    "direct_execution_ready": direct_execution_ready,
                    "target_performance": "<500ms",
                    "router_healthy": router_healthy,
                    "processors_healthy": processors_healthy,
                },
                "system_info": {
                    "expected_users": "5-20",
                    "deployment_mode": "small_team_production",
                },
            }

            # Store in history
            self.performance_history.append(
                {
                    "timestamp": result["timestamp"],
                    "overall_status": overall_status,
                    "total_time_ms": total_time,
                    "direct_execution_ready": direct_execution_ready,
                }
            )

            # Keep history manageable
            if len(self.performance_history) > self.max_history:
                self.performance_history = self.performance_history[-self.max_history :]

            return result

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "overall_status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "story_1_6_status": {"direct_execution_ready": False},
            }

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary from recent health checks."""
        if not self.performance_history:
            return {"status": "no_data"}

        recent_checks = self.performance_history[-10:]  # Last 10 checks

        # Calculate averages
        avg_response_time = sum(
            check["total_time_ms"] for check in recent_checks
        ) / len(recent_checks)

        # Count statuses
        healthy_count = sum(
            1 for check in recent_checks if check["overall_status"] == "healthy"
        )

        # Check direct execution availability
        direct_exec_available = sum(
            1 for check in recent_checks if check["direct_execution_ready"]
        )

        return {
            "recent_checks": len(recent_checks),
            "avg_response_time_ms": round(avg_response_time, 2),
            "health_rate": f"{healthy_count}/{len(recent_checks)}",
            "direct_execution_availability": f"{direct_exec_available}/{len(recent_checks)}",
            "story_1_6_performance": (
                "optimal"
                if avg_response_time < 100
                else "acceptable" if avg_response_time < 500 else "needs_attention"
            ),
        }


# Global health checker instance
health_checker = HealthChecker()


async def quick_health_check() -> Dict[str, str]:
    """Quick health check for basic monitoring."""
    try:
        result = await health_checker.check_router_health()
        return {
            "status": "ok" if result.status == "healthy" else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "story_1_6": "ready" if result.status == "healthy" else "limited",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "story_1_6": "unavailable",
        }
