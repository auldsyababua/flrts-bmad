#!/usr/bin/env python3
"""
Export metrics from Redis to persistent storage.

This script can be run periodically (e.g., via cron) to export metrics
from Redis to a persistent storage solution for historical analysis.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

from src.core.benchmarks import get_performance_monitor  # noqa: E402
from src.storage.storage_service import StorageService  # noqa: E402

load_dotenv()


class MetricsExporter:
    """Export metrics from Redis to various storage backends."""

    def __init__(self):
        self.monitor = get_performance_monitor()
        self.storage = StorageService()

    async def export_to_json(self, output_dir: str = "metrics_export"):
        """Export metrics to JSON files for archival."""
        Path(output_dir).mkdir(exist_ok=True)

        # Get current metrics
        summary = self.monitor.get_performance_summary(
            time_range_minutes=60 * 24  # Last 24 hours
        )

        # Create timestamped filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/metrics_{timestamp}.json"

        # Add metadata
        export_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "export_version": "1.0",
            "metrics": summary,
            "metadata": {
                "bot_version": "1.0.0",
                "environment": os.getenv("ENVIRONMENT", "production"),
            },
        }

        # Write to file
        with open(filename, "w") as f:
            json.dump(export_data, f, indent=2)

        print(f"✅ Exported metrics to {filename}")
        return filename

    async def export_to_supabase(self):
        """Export metrics to Supabase for SQL analysis."""
        summary = self.monitor.get_performance_summary()

        # Flatten metrics for database storage
        records = []
        timestamp = datetime.utcnow()

        for metric_name, data in summary.items():
            if isinstance(data, dict):
                for stat_name, value in data.items():
                    if isinstance(value, (int, float)):
                        records.append(
                            {
                                "timestamp": timestamp.isoformat(),
                                "metric_name": metric_name,
                                "stat_name": stat_name,
                                "value": float(value),
                                "metric_type": "aggregate",
                            }
                        )
            else:
                # Single value metrics
                records.append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "metric_name": metric_name,
                        "stat_name": "value",
                        "value": float(data),
                        "metric_type": "gauge",
                    }
                )

        # Store in Supabase
        if records:
            success = await self.storage.create_metrics_table()  # Ensure table exists
            if success:
                for record in records:
                    await self.storage.insert_metric(record)
                print(f"✅ Exported {len(records)} metrics to Supabase")
            else:
                print("❌ Failed to create metrics table in Supabase")

        return len(records)

    async def export_to_csv(self, output_dir: str = "metrics_export"):
        """Export metrics to CSV for easy analysis."""
        import csv

        Path(output_dir).mkdir(exist_ok=True)

        summary = self.monitor.get_performance_summary()
        timestamp = datetime.utcnow()

        # Create CSV file
        csv_file = f"{output_dir}/metrics_{timestamp.strftime('%Y%m%d')}.csv"

        with open(csv_file, "a", newline="") as f:
            writer = csv.writer(f)

            # Write header if file is empty
            if f.tell() == 0:
                writer.writerow(
                    [
                        "timestamp",
                        "metric_name",
                        "count",
                        "average",
                        "min",
                        "max",
                        "p50",
                        "p95",
                        "p99",
                    ]
                )

            # Write metrics
            for metric_name, data in summary.items():
                if isinstance(data, dict) and "count" in data:
                    writer.writerow(
                        [
                            timestamp.isoformat(),
                            metric_name,
                            data.get("count", 0),
                            f"{data.get('average', 0):.3f}",
                            f"{data.get('min', 0):.3f}",
                            f"{data.get('max', 0):.3f}",
                            f"{data.get('p50', 0):.3f}",
                            f"{data.get('p95', 0):.3f}",
                            f"{data.get('p99', 0):.3f}",
                        ]
                    )

        print(f"✅ Appended metrics to {csv_file}")
        return csv_file

    async def cleanup_redis_metrics(self, days_to_keep: int = 7):
        """Clean up old metrics from Redis after export."""
        self.monitor.cleanup_old_metrics(days_to_keep)
        print(f"✅ Cleaned up metrics older than {days_to_keep} days")


async def main():
    """Run metric export."""
    exporter = MetricsExporter()

    print("🚀 Starting metrics export...")
    print("=" * 50)

    # Export to multiple formats
    try:
        # JSON export (always do this)
        await exporter.export_to_json()

        # CSV export for easy analysis
        await exporter.export_to_csv()

        # Supabase export (if configured)
        if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY"):
            records = await exporter.export_to_supabase()
            print(f"📊 Exported {records} records to Supabase")
        else:
            print("⚠️  Supabase not configured, skipping database export")

        # Optional: Clean up old Redis metrics
        # await exporter.cleanup_redis_metrics(days_to_keep=30)

        print("\n" + "=" * 50)
        print("✅ Metrics export completed successfully!")

    except Exception as e:
        print(f"\n❌ Export failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
