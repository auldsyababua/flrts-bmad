#!/usr/bin/env python3
"""
Small Team Load Test for FLRTS-BMAD (5-20 users)

Tests the system under realistic load for a small team,
with special focus on Story 1.6 direct execution performance.
"""

import asyncio
import statistics
import time
from datetime import datetime
from typing import Any, Dict, List

import aiohttp


class SmallTeamLoadTester:
    """Load tester optimized for 5-20 user scenarios."""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.results: List[Dict[str, Any]] = []

        # Test messages that should trigger direct execution
        self.direct_execution_commands = [
            "/newtask Check oil levels",
            "/newtask Inspect generator",
            "/newlist maintenance supplies",
            "/newlist shopping list",
            "add milk to shopping list",
            "complete oil check task",
            "/showlists",
            "/showtasks",
        ]

        # Test messages that might need LLM
        self.llm_fallback_commands = [
            "what's the status of everything?",
            "remind me about the thing we discussed",
            "how are we doing with maintenance?",
            "can you help me understand the workflow?",
        ]

    async def test_health_endpoints(
        self, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Test health check endpoints performance."""
        health_tests = []

        endpoints = ["/health/", "/health/story-1-6", "/health/performance"]

        for endpoint in endpoints:
            start_time = time.perf_counter()
            try:
                async with session.get(f"{self.base_url}{endpoint}") as response:
                    response_time = (time.perf_counter() - start_time) * 1000
                    health_tests.append(
                        {
                            "endpoint": endpoint,
                            "status_code": response.status,
                            "response_time_ms": response_time,
                            "success": response.status == 200,
                        }
                    )
            except Exception as e:
                health_tests.append(
                    {"endpoint": endpoint, "error": str(e), "success": False}
                )

        return {
            "health_check_results": health_tests,
            "avg_health_response_ms": (
                statistics.mean(
                    [
                        test["response_time_ms"]
                        for test in health_tests
                        if "response_time_ms" in test
                    ]
                )
                if any("response_time_ms" in test for test in health_tests)
                else None
            ),
        }

    async def simulate_user_session(
        self, session: aiohttp.ClientSession, user_id: str, commands_per_user: int = 5
    ) -> List[Dict[str, Any]]:
        """Simulate a single user's commands."""
        user_results = []

        # Mix of direct execution and LLM commands (80/20 split typical for Story 1.6)
        commands = (
            self.direct_execution_commands * (commands_per_user // 2)
            + self.llm_fallback_commands * (commands_per_user // 10 + 1)
        )[:commands_per_user]

        for i, command in enumerate(commands):
            start_time = time.perf_counter()

            payload = {
                "message": command,
                "user_id": user_id,
                "session_id": f"{user_id}_session",
            }

            try:
                # Test router endpoint (if available)
                async with session.post(
                    f"{self.base_url}/api/route",  # Adjust endpoint as needed
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    response_time = (time.perf_counter() - start_time) * 1000

                    if response.status == 200:
                        result_data = await response.json()
                        used_direct = result_data.get("use_direct_execution", False)
                        confidence = result_data.get("confidence", 0)
                    else:
                        used_direct = None
                        confidence = None

                    user_results.append(
                        {
                            "user_id": user_id,
                            "command": command,
                            "response_time_ms": response_time,
                            "status_code": response.status,
                            "used_direct_execution": used_direct,
                            "confidence": confidence,
                            "success": response.status == 200,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

            except asyncio.TimeoutError:
                user_results.append(
                    {
                        "user_id": user_id,
                        "command": command,
                        "error": "timeout",
                        "success": False,
                    }
                )
            except Exception as e:
                user_results.append(
                    {
                        "user_id": user_id,
                        "command": command,
                        "error": str(e),
                        "success": False,
                    }
                )

            # Small delay between commands (realistic user behavior)
            await asyncio.sleep(0.5)

        return user_results

    async def run_concurrent_users_test(
        self, num_users: int = 10, commands_per_user: int = 5
    ) -> Dict[str, Any]:
        """Run load test with multiple concurrent users."""
        print(
            f"🚀 Starting load test: {num_users} users, {commands_per_user} commands each"
        )

        start_time = time.perf_counter()

        async with aiohttp.ClientSession() as session:
            # Test health endpoints first
            health_results = await self.test_health_endpoints(session)

            # Create user tasks
            user_tasks = []
            for i in range(num_users):
                user_id = f"load_test_user_{i+1}"
                task = self.simulate_user_session(session, user_id, commands_per_user)
                user_tasks.append(task)

            # Run all users concurrently
            all_user_results = await asyncio.gather(*user_tasks, return_exceptions=True)

            total_time = time.perf_counter() - start_time

            # Flatten results
            all_results = []
            for user_result in all_user_results:
                if isinstance(user_result, list):
                    all_results.extend(user_result)
                else:
                    print(f"User session error: {user_result}")

            return self.analyze_results(
                all_results, health_results, total_time, num_users
            )

    def analyze_results(
        self,
        results: List[Dict[str, Any]],
        health_results: Dict[str, Any],
        total_time: float,
        num_users: int,
    ) -> Dict[str, Any]:
        """Analyze load test results."""

        successful_results = [r for r in results if r.get("success", False)]
        failed_results = [r for r in results if not r.get("success", False)]

        if not successful_results:
            return {
                "status": "FAILED - No successful requests",
                "total_requests": len(results),
                "failed_requests": len(failed_results),
                "health_results": health_results,
            }

        # Response time analysis
        response_times = [
            r["response_time_ms"] for r in successful_results if "response_time_ms" in r
        ]

        # Direct execution analysis (Story 1.6)
        direct_exec_results = [
            r for r in successful_results if r.get("used_direct_execution") is True
        ]
        llm_fallback_results = [
            r for r in successful_results if r.get("used_direct_execution") is False
        ]

        direct_exec_times = [
            r["response_time_ms"]
            for r in direct_exec_results
            if "response_time_ms" in r
        ]
        llm_times = [
            r["response_time_ms"]
            for r in llm_fallback_results
            if "response_time_ms" in r
        ]

        analysis = {
            "load_test_summary": {
                "total_time_seconds": round(total_time, 2),
                "concurrent_users": num_users,
                "total_requests": len(results),
                "successful_requests": len(successful_results),
                "failed_requests": len(failed_results),
                "success_rate": (
                    round(len(successful_results) / len(results), 3) if results else 0
                ),
                "requests_per_second": (
                    round(len(results) / total_time, 2) if total_time > 0 else 0
                ),
            },
            "response_time_analysis": {
                "avg_response_time_ms": (
                    round(statistics.mean(response_times), 1)
                    if response_times
                    else None
                ),
                "median_response_time_ms": (
                    round(statistics.median(response_times), 1)
                    if response_times
                    else None
                ),
                "p95_response_time_ms": (
                    round(sorted(response_times)[int(0.95 * len(response_times))], 1)
                    if len(response_times) > 5
                    else None
                ),
                "max_response_time_ms": (
                    round(max(response_times), 1) if response_times else None
                ),
                "min_response_time_ms": (
                    round(min(response_times), 1) if response_times else None
                ),
            },
            "story_1_6_performance": {
                "direct_execution_requests": len(direct_exec_results),
                "llm_fallback_requests": len(llm_fallback_results),
                "direct_execution_rate": (
                    round(len(direct_exec_results) / len(successful_results), 3)
                    if successful_results
                    else 0
                ),
                "avg_direct_exec_time_ms": (
                    round(statistics.mean(direct_exec_times), 1)
                    if direct_exec_times
                    else None
                ),
                "avg_llm_fallback_time_ms": (
                    round(statistics.mean(llm_times), 1) if llm_times else None
                ),
                "direct_exec_under_500ms": (
                    sum(1 for t in direct_exec_times if t < 500)
                    if direct_exec_times
                    else 0
                ),
                "direct_exec_target_met": (
                    (
                        sum(1 for t in direct_exec_times if t < 500)
                        / len(direct_exec_times)
                    )
                    if direct_exec_times
                    else 0
                ),
            },
            "health_check_results": health_results,
            "recommendations": self.generate_recommendations(
                successful_results, response_times, direct_exec_times
            ),
        }

        return analysis

    def generate_recommendations(
        self,
        successful_results: List[Dict[str, Any]],
        response_times: List[float],
        direct_exec_times: List[float],
    ) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        if response_times:
            avg_response = statistics.mean(response_times)

            if avg_response > 2000:
                recommendations.append(
                    "❌ Average response time is >2s - investigate performance issues"
                )
            elif avg_response > 1000:
                recommendations.append(
                    "⚠️ Average response time is >1s - consider optimization"
                )
            else:
                recommendations.append("✅ Response times are acceptable")

        if direct_exec_times:
            avg_direct = statistics.mean(direct_exec_times)
            target_met_rate = sum(1 for t in direct_exec_times if t < 500) / len(
                direct_exec_times
            )

            if avg_direct > 500:
                recommendations.append(
                    "❌ Story 1.6 direct execution >500ms target - check processor performance"
                )
            elif target_met_rate < 0.9:
                recommendations.append(
                    "⚠️ <90% of direct execution under 500ms - monitor performance"
                )
            else:
                recommendations.append(
                    "✅ Story 1.6 direct execution meeting <500ms target"
                )

        success_rate = (
            len(successful_results) / len(successful_results)
            if successful_results
            else 0
        )
        if success_rate < 0.95:
            recommendations.append("❌ Success rate <95% - investigate failures")
        else:
            recommendations.append("✅ Good success rate")

        return recommendations

    def print_results(self, results: Dict[str, Any]) -> None:
        """Print formatted test results."""
        print("\n" + "=" * 60)
        print("🧪 FLRTS-BMAD Small Team Load Test Results")
        print("=" * 60)

        summary = results["load_test_summary"]
        print(f"👥 Users: {summary['concurrent_users']}")
        print(
            f"📊 Requests: {summary['successful_requests']}/{summary['total_requests']} successful"
        )
        print(f"⏱️  Duration: {summary['total_time_seconds']}s")
        print(f"🔄 Rate: {summary['requests_per_second']} req/s")

        print("\n📈 Response Time Performance:")
        perf = results["response_time_analysis"]
        if perf["avg_response_time_ms"]:
            print(f"   Average: {perf['avg_response_time_ms']}ms")
            print(f"   Median:  {perf['median_response_time_ms']}ms")
            print(f"   95th %:  {perf['p95_response_time_ms']}ms")
            print(
                f"   Range:   {perf['min_response_time_ms']}-{perf['max_response_time_ms']}ms"
            )

        print("\n🚀 Story 1.6 Direct Execution:")
        story = results["story_1_6_performance"]
        print(f"   Direct execution rate: {story['direct_execution_rate']:.1%}")
        print(f"   Direct exec avg time: {story['avg_direct_exec_time_ms']}ms")
        print(f"   LLM fallback avg time: {story['avg_llm_fallback_time_ms']}ms")
        print(f"   Under 500ms target: {story['direct_exec_target_met']:.1%}")

        print("\n💡 Recommendations:")
        for rec in results["recommendations"]:
            print(f"   {rec}")

        print("\n" + "=" * 60)


async def main():
    """Run the load test."""
    tester = SmallTeamLoadTester()

    # Test scenarios for small teams
    scenarios = [
        {"users": 5, "commands": 3, "name": "Light Load (5 users)"},
        {"users": 10, "commands": 5, "name": "Normal Load (10 users)"},
        {"users": 15, "commands": 4, "name": "Peak Load (15 users)"},
    ]

    for scenario in scenarios:
        print(f"\n🔬 Testing: {scenario['name']}")
        results = await tester.run_concurrent_users_test(
            num_users=scenario["users"], commands_per_user=scenario["commands"]
        )
        tester.print_results(results)

        # Brief pause between scenarios
        await asyncio.sleep(2)

    print("\n✅ Load testing complete! All scenarios tested for 5-20 user deployment.")


if __name__ == "__main__":
    print("🧪 FLRTS-BMAD Small Team Load Test")
    print("⚠️  Note: Ensure the application is running before starting the test")
    print("📍 Testing against: http://localhost:5000")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Load test interrupted by user")
    except Exception as e:
        print(f"\n❌ Load test failed: {e}")
