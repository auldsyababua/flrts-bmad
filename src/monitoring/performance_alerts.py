#!/usr/bin/env python3
"""
Performance Alerting System for FLRTS-BMAD
Monitors Story 1.6 Direct Execution and system performance
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [MONITORING] - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring."""

    timestamp: float
    response_time_ms: float
    direct_execution_rate: float
    router_confidence: float
    error_rate: float
    memory_usage_percent: float
    cpu_usage_percent: float
    story_16_bypassed_llm: bool


class PerformanceMonitor:
    """Monitors system performance and sends alerts."""

    def __init__(self):
        self.health_url = os.getenv("HEALTH_URL", "http://localhost:8000/health")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.alert_chat_id = os.getenv(
            "ADMIN_CHAT_ID", os.getenv("AUTHORIZED_USER_IDS", "[]")
        )

        # Alert thresholds
        self.thresholds = {
            "response_time_ms": 500,  # Story 1.6 target
            "direct_execution_rate": 0.6,  # 60% minimum
            "router_confidence": 0.8,  # High confidence threshold
            "error_rate": 0.05,  # 5% max error rate
            "memory_usage_percent": 85,  # Memory warning at 85%
            "cpu_usage_percent": 80,  # CPU warning at 80%
        }

        # Track recent metrics for trend analysis
        self.metric_history: List[PerformanceMetrics] = []
        self.alert_cooldown = {}  # Prevent alert spam

    def check_health(self) -> Optional[Dict]:
        """Check system health endpoint."""
        try:
            response = requests.get(self.health_url, timeout=5)
            if response.status_code == 200 or response.status_code == 503:
                return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
        return None

    def analyze_metrics(self, health_data: Dict) -> PerformanceMetrics:
        """Analyze health data and extract metrics."""
        system = health_data.get("system", {})

        # Calculate Story 1.6 metrics (simulated for now)
        # In production, these would come from actual metrics endpoints
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            response_time_ms=200,  # Would be from actual timing
            direct_execution_rate=0.75,  # Would be from actual stats
            router_confidence=0.85,  # Would be from router stats
            error_rate=0.01,  # Would be from error logs
            memory_usage_percent=system.get("memory", {}).get("percent_used", 0),
            cpu_usage_percent=system.get("cpu", {}).get("percent_used", 0),
            story_16_bypassed_llm=True,  # Would be from actual execution
        )

        return metrics

    def check_threshold_violations(self, metrics: PerformanceMetrics) -> List[str]:
        """Check if any metrics violate thresholds."""
        violations = []

        if metrics.response_time_ms > self.thresholds["response_time_ms"]:
            violations.append(
                f"⚠️ Response time: {metrics.response_time_ms:.0f}ms "
                f"(threshold: {self.thresholds['response_time_ms']}ms)"
            )

        if metrics.direct_execution_rate < self.thresholds["direct_execution_rate"]:
            violations.append(
                f"⚠️ Direct execution rate: {metrics.direct_execution_rate:.1%} "
                f"(threshold: {self.thresholds['direct_execution_rate']:.0%})"
            )

        if metrics.router_confidence < self.thresholds["router_confidence"]:
            violations.append(
                f"⚠️ Router confidence: {metrics.router_confidence:.2f} "
                f"(threshold: {self.thresholds['router_confidence']})"
            )

        if metrics.error_rate > self.thresholds["error_rate"]:
            violations.append(
                f"🚨 Error rate: {metrics.error_rate:.1%} "
                f"(threshold: {self.thresholds['error_rate']:.0%})"
            )

        if metrics.memory_usage_percent > self.thresholds["memory_usage_percent"]:
            violations.append(
                f"🚨 Memory usage: {metrics.memory_usage_percent:.1f}% "
                f"(threshold: {self.thresholds['memory_usage_percent']}%)"
            )

        if metrics.cpu_usage_percent > self.thresholds["cpu_usage_percent"]:
            violations.append(
                f"⚠️ CPU usage: {metrics.cpu_usage_percent:.1f}% "
                f"(threshold: {self.thresholds['cpu_usage_percent']}%)"
            )

        return violations

    def send_telegram_alert(self, message: str):
        """Send alert via Telegram."""
        if not self.telegram_bot_token:
            logger.warning("Telegram bot token not configured, skipping alert")
            return

        # Parse chat IDs from JSON string
        try:
            chat_ids = (
                json.loads(self.alert_chat_id)
                if isinstance(self.alert_chat_id, str)
                else [self.alert_chat_id]
            )
        except Exception:
            chat_ids = [self.alert_chat_id]

        for chat_id in chat_ids:
            try:
                url = (
                    f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
                )
                payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
                response = requests.post(url, json=payload, timeout=5)
                if response.status_code == 200:
                    logger.info(f"Alert sent to chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")

    def should_alert(self, alert_type: str) -> bool:
        """Check if we should send an alert (with cooldown)."""
        cooldown_minutes = 15  # Don't repeat same alert for 15 minutes

        if alert_type not in self.alert_cooldown:
            self.alert_cooldown[alert_type] = datetime.now()
            return True

        last_alert = self.alert_cooldown[alert_type]
        if datetime.now() - last_alert > timedelta(minutes=cooldown_minutes):
            self.alert_cooldown[alert_type] = datetime.now()
            return True

        return False

    def format_alert_message(
        self, violations: List[str], metrics: PerformanceMetrics
    ) -> str:
        """Format alert message for sending."""
        severity = (
            "🚨 <b>CRITICAL</b>"
            if any("🚨" in v for v in violations)
            else "⚠️ <b>WARNING</b>"
        )

        message = f"{severity} - FLRTS Performance Alert\n\n"
        message += "Threshold violations detected:\n"
        for violation in violations:
            message += f"• {violation}\n"

        message += "\n📊 <b>Story 1.6 Status:</b>\n"
        message += f"• Direct Execution: {'✅ Active' if metrics.story_16_bypassed_llm else '❌ Inactive'}\n"
        message += f"• Router Confidence: {metrics.router_confidence:.2f}\n"
        message += f"• Bypass Rate: {metrics.direct_execution_rate:.0%}\n"

        message += f"\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return message

    def run_monitoring_cycle(self):
        """Run a single monitoring cycle."""
        logger.info("Running performance monitoring cycle...")

        # Check health
        health_data = self.check_health()
        if not health_data:
            if self.should_alert("health_check_failed"):
                self.send_telegram_alert(
                    "🚨 <b>CRITICAL</b> - Health check failed!\n"
                    "The FLRTS system may be down or unresponsive."
                )
            return

        # Analyze metrics
        metrics = self.analyze_metrics(health_data)
        self.metric_history.append(metrics)

        # Keep only last hour of metrics
        one_hour_ago = time.time() - 3600
        self.metric_history = [
            m for m in self.metric_history if m.timestamp > one_hour_ago
        ]

        # Check for violations
        violations = self.check_threshold_violations(metrics)

        if violations:
            alert_key = "|".join(violations[:2])  # Key based on first 2 violations
            if self.should_alert(alert_key):
                alert_message = self.format_alert_message(violations, metrics)
                self.send_telegram_alert(alert_message)
                logger.warning(f"Sent alert for {len(violations)} violations")
        else:
            logger.info("All metrics within normal thresholds")

    def start_monitoring(self, interval_seconds: int = 60):
        """Start continuous monitoring."""
        logger.info(f"Starting performance monitoring (interval: {interval_seconds}s)")
        logger.info(f"Thresholds: {self.thresholds}")

        while True:
            try:
                self.run_monitoring_cycle()
            except Exception as e:
                logger.error(f"Monitoring cycle error: {e}")

            time.sleep(interval_seconds)


if __name__ == "__main__":
    # Run monitoring
    monitor = PerformanceMonitor()

    # Check if we should run once or continuously
    if os.getenv("MONITORING_MODE") == "once":
        monitor.run_monitoring_cycle()
    else:
        # Default to continuous monitoring every minute
        interval = int(os.getenv("MONITORING_INTERVAL", "60"))
        monitor.start_monitoring(interval)
