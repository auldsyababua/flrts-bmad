#!/usr/bin/env python3
"""
Load Test Results Analyzer

Simple script to analyze Locust results and provide recommendations.
Designed for non-coders to understand their bot's performance.
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def analyze_stats(stats_file):
    """Analyze Locust stats and provide recommendations."""
    try:
        with open(stats_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Could not find {stats_file}")
        print("Run a load test first with: ./scripts/run_load_test.sh")
        return
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {stats_file}")
        return

    print("📊 Load Test Analysis")
    print("==================")
    print()

    # Basic info
    if "start_time" in data:
        start_time = datetime.fromtimestamp(data["start_time"])
        print(f"📅 Test Date: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    if "user_count" in data:
        print(f"👥 Total Users: {data['user_count']}")

    print()

    # Analyze each endpoint
    print("🎯 Endpoint Performance:")
    print("-" * 50)

    issues_found = []

    for endpoint, stats in data.get("stats", []).items():
        if endpoint == "Total":
            continue

        print(f"\n🔸 {endpoint}")

        # Response times
        avg_time = stats.get("avg_response_time", 0)
        min_time = stats.get("min_response_time", 0)
        max_time = stats.get("max_response_time", 0)
        p95_time = stats.get("response_time_percentiles", {}).get("95", 0)

        print(f"   Average: {avg_time:.0f}ms")
        print(f"   95th percentile: {p95_time:.0f}ms")
        print(f"   Min/Max: {min_time:.0f}ms / {max_time:.0f}ms")

        # Performance assessment
        if avg_time > 2000:
            print("   ⚠️  TOO SLOW - Users will definitely notice!")
            issues_found.append(f"{endpoint} is too slow ({avg_time:.0f}ms average)")
        elif avg_time > 1000:
            print("   ⚠️  SLOW - Consider optimization")
            issues_found.append(f"{endpoint} is slow ({avg_time:.0f}ms average)")
        else:
            print("   ✅ GOOD")

        # Failure rate
        num_requests = stats.get("num_requests", 0)
        num_failures = stats.get("num_failures", 0)
        if num_requests > 0:
            failure_rate = (num_failures / num_requests) * 100
            print(f"   Failure Rate: {failure_rate:.1f}%")

            if failure_rate > 5:
                print("   🔴 HIGH FAILURE RATE - Critical issue!")
                issues_found.append(f"{endpoint} has {failure_rate:.1f}% failure rate")
            elif failure_rate > 1:
                print("   ⚠️  Some failures detected")
                issues_found.append(f"{endpoint} has {failure_rate:.1f}% failure rate")

        # Requests per second
        rps = stats.get("current_rps", 0)
        print(f"   Throughput: {rps:.1f} requests/second")

    # Overall summary
    total_stats = data.get("stats", []).get("Total", {})
    if total_stats:
        print("\n" + "=" * 50)
        print("🏆 Overall Performance:")
        print("=" * 50)

        total_rps = total_stats.get("current_rps", 0)
        total_failures = total_stats.get("num_failures", 0)
        total_requests = total_stats.get("num_requests", 0)

        print(f"Total Requests: {total_requests:,}")
        print(f"Total Failures: {total_failures:,}")
        print(f"Overall RPS: {total_rps:.1f}")

        if total_requests > 0:
            overall_failure_rate = (total_failures / total_requests) * 100
            print(f"Overall Failure Rate: {overall_failure_rate:.1f}%")

    # Recommendations
    print("\n" + "=" * 50)
    print("💡 Recommendations:")
    print("=" * 50)

    if not issues_found:
        print("✅ Performance looks good!")
        print("   - Your bot is handling the load well")
        print("   - Response times are acceptable")
        print("   - No significant failures detected")
    else:
        print("⚠️  Issues detected:\n")
        for i, issue in enumerate(issues_found, 1):
            print(f"{i}. {issue}")

        print("\n🔧 What to do:")

        # Specific recommendations based on issues
        if any("too slow" in issue.lower() for issue in issues_found):
            print("\nFor SLOW RESPONSE times:")
            print("  1. Check if caching is working (run ./scripts/ai_change_check.sh)")
            print("  2. Ensure Redis is running and accessible")
            print("  3. Consider adding more caching layers")
            print("  4. Check if vector search is optimized")

        if any("failure rate" in issue for issue in issues_found):
            print("\nFor HIGH FAILURE rates:")
            print("  1. Check application logs for errors")
            print("  2. Verify API rate limits aren't being hit")
            print("  3. Ensure database connections aren't exhausted")
            print("  4. Check memory usage during the test")

        print("\n🎯 Next steps:")
        print("  1. Fix the most critical issues first (failures > slowness)")
        print("  2. Run the AI babysitter tests to catch code issues")
        print("  3. Re-run the load test after fixes")
        print("  4. Consider scaling if performance can't be improved")

    # Capacity planning
    print("\n" + "=" * 50)
    print("📦 Capacity Planning:")
    print("=" * 50)

    if total_stats and "user_count" in data:
        users = data["user_count"]
        rps = total_stats.get("current_rps", 0)

        if rps > 0:
            print(f"Current capacity: {rps:.1f} requests/second with {users} users")

            # Estimate capacity
            rps_per_user = rps / users if users > 0 else 0

            # Rough estimates for different team sizes
            team_sizes = [10, 25, 50, 100]
            print("\nEstimated capacity for team sizes:")

            for size in team_sizes:
                estimated_rps = size * rps_per_user * 0.7  # 70% to be conservative
                can_handle = rps >= estimated_rps

                status = "✅ Can handle" if can_handle else "❌ Needs scaling"
                print(f"  {size} users: {status} (~{estimated_rps:.1f} rps needed)")

            print("\n📢 Note: These are rough estimates assuming:")
            print("  - Each user makes ~1 request every 5-10 seconds")
            print("  - Peak usage is around 70% of total users")
            print("  - Add 20-30% buffer for growth")


if __name__ == "__main__":
    # Default to analyzing the most recent basic test
    stats_file = "tests/locust_stats.json"

    if len(sys.argv) > 1:
        stats_file = sys.argv[1]

    # Check if file exists
    if not Path(stats_file).exists():
        # Try common locations
        possible_files = [
            "tests/locust_stats.json",
            "locust_stats.json",
            "tests/load_test_results_basic_stats.json",
            "tests/load_test_results_normal_stats.json",
            "tests/load_test_results_peak_stats.json",
        ]

        for f in possible_files:
            if Path(f).exists():
                stats_file = f
                break
        else:
            print("❌ No load test results found!")
            print("\nRun a load test first:")
            print("  ./scripts/run_load_test.sh --scenario basic")
            sys.exit(1)

    print(f"Analyzing: {stats_file}\n")
    analyze_stats(stats_file)
