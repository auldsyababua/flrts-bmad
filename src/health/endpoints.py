"""
Health Check Endpoints for FLRTS-BMAD Flask Application

Provides HTTP endpoints for monitoring system health in production.
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify

from .health_checks import health_checker, quick_health_check

logger = logging.getLogger(__name__)

# Create health check blueprint
health_bp = Blueprint("health", __name__, url_prefix="/health")


@health_bp.route("/", methods=["GET"])
async def basic_health():
    """Basic health check endpoint - fast response for load balancers."""
    try:
        result = await quick_health_check()
        status_code = 200 if result["status"] == "ok" else 503
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Basic health check failed: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            503,
        )


@health_bp.route("/detailed", methods=["GET"])
async def detailed_health():
    """Detailed health check with all service statuses."""
    try:
        # Import here to avoid circular dependencies
        from src.core.database import get_supabase_client

        supabase_client = get_supabase_client()
        result = await health_checker.comprehensive_health_check(supabase_client)

        status_code = 200
        if result["overall_status"] == "unhealthy":
            status_code = 503
        elif result["overall_status"] == "degraded":
            status_code = 200  # Still functional

        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return (
            jsonify(
                {
                    "overall_status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            503,
        )


@health_bp.route("/performance", methods=["GET"])
def performance_summary():
    """Get performance summary for monitoring dashboards."""
    try:
        summary = health_checker.get_performance_summary()
        return jsonify(
            {
                "performance_summary": summary,
                "timestamp": datetime.utcnow().isoformat(),
                "story_1_6_info": {
                    "feature": "Direct Execution Path",
                    "target_response_time": "<500ms",
                    "expected_users": "5-20",
                    "status": summary.get("story_1_6_performance", "unknown"),
                },
            }
        )
    except Exception as e:
        logger.error(f"Performance summary failed: {e}")
        return (
            jsonify({"error": str(e), "timestamp": datetime.utcnow().isoformat()}),
            500,
        )


@health_bp.route("/story-1-6", methods=["GET"])
async def story_1_6_status():
    """Specific health check for Story 1.6 Direct Execution feature."""
    try:
        # Test just the router and processor components
        router_result = await health_checker.check_router_health()

        # Check if direct execution is working
        direct_exec_working = (
            router_result.status == "healthy"
            and router_result.details.get("direct_execution", False)
        )

        performance_level = "optimal"
        if router_result.response_time_ms > 100:
            performance_level = "acceptable"
        if router_result.response_time_ms > 500:
            performance_level = "degraded"

        result = {
            "story_1_6_status": "operational" if direct_exec_working else "limited",
            "direct_execution_ready": direct_exec_working,
            "router_response_time_ms": router_result.response_time_ms,
            "performance_level": performance_level,
            "target_performance": "<500ms",
            "confidence_threshold": "≥95%",
            "last_test": {
                "confidence": router_result.details.get("confidence"),
                "entity_type": router_result.details.get("entity_type"),
                "operation": router_result.details.get("operation"),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        status_code = 200 if direct_exec_working else 503
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Story 1.6 health check failed: {e}")
        return (
            jsonify(
                {
                    "story_1_6_status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            503,
        )


@health_bp.route("/ready", methods=["GET"])
async def readiness_check():
    """Kubernetes-style readiness check."""
    try:
        result = await quick_health_check()

        if result["status"] == "ok":
            return jsonify({"ready": True}), 200
        else:
            return (
                jsonify({"ready": False, "reason": result.get("error", "degraded")}),
                503,
            )

    except Exception as e:
        return jsonify({"ready": False, "reason": str(e)}), 503


@health_bp.route("/live", methods=["GET"])
def liveness_check():
    """Kubernetes-style liveness check - just verify the app is running."""
    return (
        jsonify(
            {
                "alive": True,
                "timestamp": datetime.utcnow().isoformat(),
                "story_1_6": "implemented",
            }
        ),
        200,
    )


def register_health_endpoints(app):
    """Register health check endpoints with Flask app."""
    app.register_blueprint(health_bp)

    # Add CORS headers for health checks
    @health_bp.after_request
    def after_request(response):
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add(
            "Access-Control-Allow-Headers", "Content-Type,Authorization"
        )
        response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE")
        return response

    logger.info("Health check endpoints registered")
    logger.info("Available endpoints:")
    logger.info("  GET /health/ - Basic health check")
    logger.info("  GET /health/detailed - Comprehensive health check")
    logger.info("  GET /health/performance - Performance summary")
    logger.info("  GET /health/story-1-6 - Story 1.6 specific status")
    logger.info("  GET /health/ready - Kubernetes readiness")
    logger.info("  GET /health/live - Kubernetes liveness")
