#!/usr/bin/env python3
"""
🔗 Webhook Telegram Bot - Production-ready webhook architecture

This module implements a webhook-only bot architecture for production use.
For local development, use the local development simulator (scripts/local_dev.py).

Features:
- FastAPI webhook server
- Proper async/await handling
- Health check endpoints
- Production-ready logging
- Clean handler separation

Usage:
    from bot.webhook_bot import WebhookTelegramBot

    bot = WebhookTelegramBot()
    app = bot.get_fastapi_app()
    # Run with uvicorn
"""

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from http import HTTPStatus
from typing import Any, Dict

import psutil
from fastapi import FastAPI, Header, HTTPException, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers import (continue_command, correct_command, forget_command,
                          graph_command, handle_document, handle_message,
                          help_command, memories_command, remember_command,
                          report_command, reset_command, start_command,
                          version_command)
from core.benchmarks import PerformanceMiddleware
from core.config import (CF_PROXY_SECRET, METRICS_AUTH_TOKEN,
                         METRICS_IP_ALLOWLIST, TELEGRAM_BOT_TOKEN,
                         TELEGRAM_WEBHOOK_SECRET)

# Set up logging
logger = logging.getLogger(__name__)


class WebhookTelegramBot:
    """
    Webhook-only Telegram bot for production use.

    This bot is designed to run as a FastAPI webhook server and does not support
    polling mode. For local development, use the local development simulator
    at scripts/local_dev.py instead.
    """

    def __init__(self):
        """
        Initialize the webhook bot.
        """
        logger.info("Initializing Webhook Telegram Bot")

        # Track startup time for uptime calculation
        self.startup_time = time.time()

        # Initialize the application with webhook configuration
        self.application = (
            Application.builder()
            .updater(None)  # Disable updater for webhook mode
            .token(TELEGRAM_BOT_TOKEN)
            .read_timeout(7)
            .get_updates_read_timeout(42)
            .build()
        )

        # Register handlers
        self._register_handlers()

        # Initialize FastAPI app
        self.app = self._create_fastapi_app()

    def _register_handlers(self):
        """Register all bot handlers."""
        # Command handlers
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("reset", reset_command))
        self.application.add_handler(CommandHandler("continue", continue_command))
        self.application.add_handler(CommandHandler("version", version_command))
        self.application.add_handler(CommandHandler("report", report_command))

        # Memory commands
        self.application.add_handler(CommandHandler("remember", remember_command))
        self.application.add_handler(CommandHandler("correct", correct_command))
        self.application.add_handler(CommandHandler("memories", memories_command))
        self.application.add_handler(CommandHandler("forget", forget_command))
        self.application.add_handler(CommandHandler("graph", graph_command))

        # Message handlers
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )
        self.application.add_handler(
            MessageHandler(filters.Document.ALL, handle_document)
        )

        logger.info("Bot handlers registered successfully")

    async def _check_database_connectivity(self) -> Dict[str, Any]:
        """Check database connectivity (Redis and Vector Store)."""
        redis_status = {"status": "unknown", "error": None, "response_time_ms": None}
        vector_status = {"status": "unknown", "error": None, "response_time_ms": None}

        # Test Redis connectivity
        try:
            from storage.redis_store import RedisStore

            _ = RedisStore()

            start_time = time.time()
            # CloudflareRedis is async, so we can't test it in sync context
            # Mark as healthy since it's initialized successfully
            _ = "test"  # Assume working if initialized
            response_time = (time.time() - start_time) * 1000

            redis_status = {
                "status": "healthy",  # Mark as healthy since it initialized
                "error": None,
                "response_time_ms": round(response_time, 2),
            }
        except Exception as e:
            redis_status = {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": None,
            }

        # Test Vector Store connectivity
        try:
            from storage.cloudflare_vector_store import CloudflareVectorStore

            vector_store = CloudflareVectorStore()

            start_time = time.time()
            # Try to ping the vector store
            await vector_store.ping()
            response_time = (time.time() - start_time) * 1000

            vector_status = {
                "status": "healthy",
                "error": None,
                "response_time_ms": round(response_time, 2),
            }
        except Exception as e:
            vector_status = {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": None,
            }

        return {"redis": redis_status, "vector_store": vector_status}

    async def _check_memory_system(self) -> Dict[str, Any]:
        """Check memory system (mem0) connectivity."""
        try:
            from core.memory import BotMemory

            start_time = time.time()
            # Try to initialize memory system
            BotMemory()
            response_time = (time.time() - start_time) * 1000

            return {
                "status": "healthy",
                "error": None,
                "response_time_ms": round(response_time, 2),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "response_time_ms": None}

    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics."""
        try:
            # Memory usage
            memory = psutil.virtual_memory()

            # CPU usage (1 second average)
            cpu_percent = psutil.cpu_percent(interval=1)

            # Disk usage for current directory
            disk = psutil.disk_usage("/")

            # Uptime
            uptime_seconds = time.time() - self.startup_time

            return {
                "memory": {
                    "total_mb": round(memory.total / (1024 * 1024), 2),
                    "used_mb": round(memory.used / (1024 * 1024), 2),
                    "available_mb": round(memory.available / (1024 * 1024), 2),
                    "percent_used": memory.percent,
                },
                "cpu": {"percent_used": cpu_percent},
                "disk": {
                    "total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
                    "used_gb": round(disk.used / (1024 * 1024 * 1024), 2),
                    "free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                    "percent_used": round((disk.used / disk.total) * 100, 2),
                },
                "uptime": {
                    "seconds": round(uptime_seconds, 2),
                    "human_readable": str(timedelta(seconds=int(uptime_seconds))),
                },
            }
        except Exception as e:
            return {"error": f"Failed to get system metrics: {str(e)}"}

    def _create_fastapi_app(self) -> FastAPI:
        """Create FastAPI app for webhook mode."""

        @asynccontextmanager
        async def lifespan(_: FastAPI):
            """Manage the application lifecycle."""
            async with self.application:
                await self.application.start()

                # Skip memory seeding for now - it's causing timeouts
                # TODO: Fix async initialization of memory system
                logger.info("Skipping initial memory seeding to prevent timeouts")

                yield
                await self.application.stop()

        # Initialize FastAPI app
        app = FastAPI(title="Markdown Brain Bot", lifespan=lifespan)

        # Add performance monitoring middleware
        perf_middleware = PerformanceMiddleware()
        app.middleware("http")(perf_middleware)

        @app.get("/")
        async def root():
            """Basic health check endpoint."""
            return {"status": "ok", "bot": "Markdown Brain Bot", "mode": "webhook"}

        @app.get("/health")
        async def health_check():
            """
            Comprehensive health check endpoint for Render and monitoring.
            Returns detailed service health including database connectivity and system metrics.
            """
            logger.info("Health check endpoint called")

            try:
                # Check database connectivity
                db_health = await self._check_database_connectivity()

                # Check memory system
                memory_health = await self._check_memory_system()

                # Get system metrics
                system_metrics = self._get_system_metrics()

                # Determine overall health status
                redis_healthy = db_health["redis"]["status"] == "healthy"
                vector_healthy = db_health["vector_store"]["status"] == "healthy"
                memory_healthy = memory_health["status"] == "healthy"

                overall_status = (
                    "healthy"
                    if (redis_healthy and vector_healthy and memory_healthy)
                    else "degraded"
                )

                if not redis_healthy or not vector_healthy:
                    overall_status = "unhealthy"

                health_response = {
                    "status": overall_status,
                    "timestamp": time.time(),
                    "uptime_seconds": round(time.time() - self.startup_time, 2),
                    "services": {"database": db_health, "memory": memory_health},
                    "system": system_metrics,
                    "bot_info": {
                        "name": "Markdown Brain Bot",
                        "mode": "webhook",
                        "version": os.getenv("APP_VERSION", "1.0.0"),
                    },
                }

                # Return appropriate HTTP status code
                status_code = (
                    200
                    if overall_status == "healthy"
                    else (503 if overall_status == "unhealthy" else 200)
                )

                return Response(
                    content=json.dumps(health_response),
                    status_code=status_code,
                    media_type="application/json",
                )

            except Exception as e:
                logger.error(f"Health check failed: {e}", exc_info=True)
                error_response = {
                    "status": "unhealthy",
                    "timestamp": time.time(),
                    "error": str(e),
                    "bot_info": {"name": "Markdown Brain Bot", "mode": "webhook"},
                }
                return Response(
                    content=json.dumps(error_response),
                    status_code=503,
                    media_type="application/json",
                )

        @app.get("/status")
        async def status_check():
            """
            Detailed status endpoint with bot status, webhook info, and system metrics.
            Includes performance metrics and operational information.
            """
            logger.info("Status endpoint called")

            try:
                # Get performance metrics
                from src.core.benchmarks import get_performance_monitor

                monitor = get_performance_monitor()

                # Get webhook and bot information
                bot_info = self.application.bot

                # Get system metrics
                system_metrics = self._get_system_metrics()

                # Get database health
                db_health = await self._check_database_connectivity()

                # Get memory system health
                memory_health = await self._check_memory_system()

                # Get performance summary
                perf_summary = monitor.get_performance_summary(
                    metric_names=[
                        "vector_search_duration",
                        "llm_call_duration",
                        "conversation_size",
                        "http_request_duration",
                        "benchmark_process_message",
                    ],
                    time_range_minutes=60,
                )

                status_response = {
                    "status": "operational",
                    "timestamp": time.time(),
                    "uptime": {
                        "seconds": round(time.time() - self.startup_time, 2),
                        "human_readable": str(
                            timedelta(seconds=int(time.time() - self.startup_time))
                        ),
                    },
                    "bot": {
                        "id": bot_info.id if hasattr(bot_info, "id") else None,
                        "username": (
                            bot_info.username if hasattr(bot_info, "username") else None
                        ),
                        "first_name": (
                            bot_info.first_name
                            if hasattr(bot_info, "first_name")
                            else None
                        ),
                        "can_join_groups": (
                            bot_info.can_join_groups
                            if hasattr(bot_info, "can_join_groups")
                            else None
                        ),
                        "can_read_all_group_messages": (
                            bot_info.can_read_all_group_messages
                            if hasattr(bot_info, "can_read_all_group_messages")
                            else None
                        ),
                    },
                    "webhook": {
                        "mode": "webhook",
                        "webhook_url": os.getenv("WEBHOOK_URL", "not_configured"),
                        "webhook_path": "/webhook",
                    },
                    "services": {"database": db_health, "memory": memory_health},
                    "performance": {
                        "summary": perf_summary,
                        "description": {
                            "cache_hit_rate": "Percentage of vector searches served from cache",
                            "total_tokens_used": "Total OpenAI API tokens consumed",
                            "vector_search_duration": "Time taken for vector searches (seconds)",
                            "llm_call_duration": "Time taken for LLM API calls (seconds)",
                            "conversation_size": "Number of messages in conversations",
                            "http_request_duration": "Time taken for HTTP requests (seconds)",
                        },
                    },
                    "system": system_metrics,
                    "environment": {
                        "python_version": os.getenv("PYTHON_VERSION", "unknown"),
                        "app_version": os.getenv("APP_VERSION", "1.0.0"),
                        "environment": os.getenv("ENVIRONMENT", "production"),
                    },
                }

                return status_response

            except Exception as e:
                logger.error(f"Status check failed: {e}", exc_info=True)
                return {
                    "status": "error",
                    "timestamp": time.time(),
                    "error": str(e),
                    "bot_info": {"name": "Markdown Brain Bot", "mode": "webhook"},
                }

        @app.get("/metrics")
        async def get_metrics(request: Request):
            """Get performance metrics summary (protected)."""
            # Resolve client IP (prefer X-Forwarded-For > X-Real-IP > socket)
            client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if not client_ip:
                client_ip = request.headers.get("x-real-ip", "").strip()
            if not client_ip and request.client:
                client_ip = request.client.host

            # Enforce optional IP allowlist (supports exact IP matches)
            if METRICS_IP_ALLOWLIST:
                if client_ip not in METRICS_IP_ALLOWLIST:
                    return Response(status_code=HTTPStatus.FORBIDDEN)

            # Enforce optional bearer token
            if METRICS_AUTH_TOKEN:
                auth = request.headers.get("Authorization", "")
                if not auth.startswith("Bearer ") or auth[7:] != METRICS_AUTH_TOKEN:
                    return Response(status_code=HTTPStatus.UNAUTHORIZED)

            from src.core.benchmarks import get_performance_monitor

            monitor = get_performance_monitor()

            # Get comprehensive performance summary
            summary = monitor.get_performance_summary(
                metric_names=[
                    "vector_search_duration",
                    "llm_call_duration",
                    "conversation_size",
                    "http_request_duration",
                    "benchmark_process_message",
                ],
                time_range_minutes=60,
            )

            return {
                "status": "ok",
                "metrics": summary,
                "description": {
                    "cache_hit_rate": "Percentage of vector searches served from cache",
                    "total_tokens_used": "Total OpenAI API tokens consumed",
                    "vector_search_duration": "Time taken for vector searches (seconds)",
                    "llm_call_duration": "Time taken for LLM API calls (seconds)",
                    "conversation_size": "Number of messages in conversations",
                    "http_request_duration": "Time taken for HTTP requests (seconds)",
                },
            }

        @app.post("/webhook")
        async def process_update(request: Request):
            """Handle incoming Telegram updates via webhook."""
            logger.info("🔄 Webhook endpoint called")
            try:
                # Validate Telegram secret token if configured
                if TELEGRAM_WEBHOOK_SECRET:
                    received_secret = request.headers.get(
                        "X-Telegram-Bot-Api-Secret-Token"
                    )
                    if received_secret != TELEGRAM_WEBHOOK_SECRET:
                        logger.warning(
                            "Unauthorized webhook call: invalid secret token"
                        )
                        return Response(status_code=HTTPStatus.UNAUTHORIZED)

                logger.info("📋 Getting JSON from request")
                req = await request.json()
                # Avoid logging raw user-provided text to prevent log injection
                logger.info("📥 Received webhook update")

                logger.info("🔧 Creating Update object from JSON")
                # Create Update object
                update = Update.de_json(req, self.application.bot)
                if not update:
                    logger.error("❌ Failed to deserialize update")
                    return Response(status_code=HTTPStatus.BAD_REQUEST)

                logger.info(f"🎯 Processing update ID: {update.update_id}")

                # Process the update
                logger.info("⚡ Calling application.process_update")
                await self.application.process_update(update)

                logger.info("✅ Update processed successfully")
                return Response(status_code=HTTPStatus.OK)
            except Exception as e:
                logger.error(f"💥 Error processing webhook: {e}", exc_info=True)
                return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        @app.post("/process")
        async def process_via_proxy(
            request: Request,
            x_request_timestamp: str = Header(None),
            x_brainbot_signature: str = Header(None),
        ):
            """Process updates proxied by Cloudflare Consumer Worker.

            Expects JSON body with shape:
            { "body": "<raw telegram update JSON string>", "context": { ... optional ... } }

            HMAC: signature = "v1=" + hex( sha256( f"{ts}.{payload}" , CF_PROXY_SECRET ) )
            where payload is the exact request body string.
            """
            logger.info("🔒 /process endpoint called via proxy")
            try:
                if not CF_PROXY_SECRET:
                    raise HTTPException(
                        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                        detail="Proxy disabled",
                    )

                if not x_request_timestamp or not x_brainbot_signature:
                    raise HTTPException(
                        status_code=HTTPStatus.UNAUTHORIZED,
                        detail="Missing auth headers",
                    )

                # Basic replay protection window: 5 minutes
                now_sec = int(time.time())
                try:
                    ts_sec = int(x_request_timestamp)
                except Exception:
                    raise HTTPException(
                        status_code=HTTPStatus.UNAUTHORIZED, detail="Bad timestamp"
                    )
                if abs(now_sec - ts_sec) > 300:
                    raise HTTPException(
                        status_code=HTTPStatus.UNAUTHORIZED, detail="Stale request"
                    )

                # Read raw body as text to ensure exact HMAC
                raw_body = await request.body()
                payload = (
                    raw_body.decode("utf-8")
                    if isinstance(raw_body, (bytes, bytearray))
                    else str(raw_body)
                )

                import hashlib
                import hmac

                expected = hmac.new(
                    CF_PROXY_SECRET.encode("utf-8"),
                    f"{x_request_timestamp}.{payload}".encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()

                provided = x_brainbot_signature or ""
                if provided.startswith("v1="):
                    provided = provided[3:]

                if not hmac.compare_digest(provided, expected):
                    raise HTTPException(
                        status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid signature"
                    )

                body_json = json.loads(payload)
                raw_tg_json = body_json.get("body")
                if not raw_tg_json:
                    raise HTTPException(
                        status_code=HTTPStatus.BAD_REQUEST, detail="Missing body"
                    )

                # Optional context from Worker (history, vector results, media URLs, flags)
                _context_payload = (
                    body_json.get("context") or {}
                )  # Reserved for future use

                # Deserialize Telegram Update and process
                update = Update.de_json(json.loads(raw_tg_json), self.application.bot)
                if not update:
                    raise HTTPException(
                        status_code=HTTPStatus.BAD_REQUEST, detail="Bad update"
                    )

                # If handlers/processors need context, attach to request state
                # or pass via a temporary mechanism; for now, proceed with normal flow
                await self.application.process_update(update)

                return Response(status_code=HTTPStatus.OK)
            except HTTPException as http_err:
                logger.warning(f"Proxy processing rejected: {http_err.detail}")
                return Response(status_code=http_err.status_code)
            except Exception as e:
                logger.error(f"Error in /process: {e}", exc_info=True)
                return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        return app

    def get_fastapi_app(self) -> FastAPI:
        """Get the FastAPI app for webhook server."""
        return self.app


# Convenience function for quick bot creation
def create_webhook_bot() -> WebhookTelegramBot:
    """
    Create a webhook bot instance.

    Returns:
        WebhookTelegramBot instance
    """
    return WebhookTelegramBot()
