#!/usr/bin/env python3
"""
Database Migration Script for FLRTS-BMAD

Simple migration system for small team deployments.
Since Supabase handles most migrations automatically, this primarily
validates the database schema and ensures Story 1.6 requirements are met.
"""

import asyncio
import os
import sys
from typing import Any, Dict


class DatabaseMigrator:
    """Simple database migration and validation for FLRTS-BMAD."""

    def __init__(self):
        self.required_tables = [
            "tasks",
            "lists",
            "list_items",
            "field_reports",
            "personnel",
            "sites",
        ]

        self.story_1_6_requirements = {
            "tasks": ["id", "title", "status", "assigned_to", "created_by"],
            "lists": ["id", "name", "type", "created_by"],
            "list_items": ["id", "list_id", "content", "is_completed"],
        }

    async def validate_database_schema(self, supabase_client) -> Dict[str, Any]:
        """Validate that required tables and columns exist."""
        validation_results = {
            "schema_valid": True,
            "missing_tables": [],
            "missing_columns": {},
            "story_1_6_ready": True,
            "issues": [],
        }

        try:
            # Check each required table
            for table in self.required_tables:
                try:
                    # Simple query to check if table exists
                    response = (
                        await supabase_client.table(table)
                        .select("*")
                        .limit(1)
                        .execute()
                    )
                    print(f"✅ Table '{table}' exists")

                except Exception as e:
                    validation_results["missing_tables"].append(table)
                    validation_results["schema_valid"] = False
                    validation_results["issues"].append(f"Missing table: {table}")
                    print(f"❌ Table '{table}' missing or inaccessible: {e}")

            # Check Story 1.6 specific requirements
            for table, required_columns in self.story_1_6_requirements.items():
                if table not in validation_results["missing_tables"]:
                    try:
                        # Try to select required columns
                        columns_str = ", ".join(required_columns)
                        response = (
                            await supabase_client.table(table)
                            .select(columns_str)
                            .limit(1)
                            .execute()
                        )
                        print(f"✅ Story 1.6 columns in '{table}' are accessible")

                    except Exception as e:
                        validation_results["missing_columns"][table] = str(e)
                        validation_results["story_1_6_ready"] = False
                        validation_results["issues"].append(
                            f"Story 1.6 schema issue in {table}: {e}"
                        )
                        print(f"⚠️  Story 1.6 column issue in '{table}': {e}")

            return validation_results

        except Exception as e:
            return {
                "schema_valid": False,
                "error": str(e),
                "story_1_6_ready": False,
                "issues": [f"Database connection failed: {e}"],
            }

    async def run_basic_migrations(self, supabase_client) -> Dict[str, Any]:
        """Run any basic data migrations needed."""
        migration_results = {"migrations_run": [], "success": True, "issues": []}

        # For now, just validate the schema
        # In a real migration system, you'd have actual migration files here
        print("📋 Running basic database validation...")

        schema_validation = await self.validate_database_schema(supabase_client)

        if not schema_validation["schema_valid"]:
            migration_results["success"] = False
            migration_results["issues"].extend(schema_validation["issues"])

        if not schema_validation["story_1_6_ready"]:
            migration_results["success"] = False
            migration_results["issues"].append(
                "Database not ready for Story 1.6 direct execution"
            )

        migration_results["schema_validation"] = schema_validation

        return migration_results

    def print_migration_results(self, results: Dict[str, Any]) -> None:
        """Print migration results."""
        print("\n" + "=" * 50)
        print("🗄️  FLRTS-BMAD Database Migration Results")
        print("=" * 50)

        if results["success"]:
            print("✅ Database migration successful!")
            print("✅ Story 1.6 direct execution ready")
        else:
            print("❌ Database migration issues found:")
            for issue in results["issues"]:
                print(f"   - {issue}")

        schema = results.get("schema_validation", {})
        if schema:
            print("\n📊 Schema Status:")
            print(
                f"   Tables validated: {len(self.required_tables) - len(schema.get('missing_tables', []))}/{len(self.required_tables)}"
            )
            print(
                f"   Story 1.6 ready: {'✅' if schema.get('story_1_6_ready') else '❌'}"
            )

            if schema.get("missing_tables"):
                print(f"   Missing tables: {', '.join(schema['missing_tables'])}")

        print("=" * 50)


async def main():
    """Run database migrations."""
    print("🗄️  FLRTS-BMAD Database Migration Tool")
    print("=" * 50)

    # Load environment
    try:
        from src.core.database import get_supabase_client

        supabase_client = get_supabase_client()
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        print(
            "💡 Make sure your .env file is configured with SUPABASE_URL and SUPABASE_KEY"
        )
        sys.exit(1)

    # Run migrations
    migrator = DatabaseMigrator()
    results = await migrator.run_basic_migrations(supabase_client)
    migrator.print_migration_results(results)

    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


def validate_env():
    """Quick environment validation."""
    required_env_vars = ["SUPABASE_URL", "SUPABASE_KEY"]
    missing = [var for var in required_env_vars if not os.getenv(var)]

    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("💡 Make sure your .env file is configured properly")
        return False

    return True


if __name__ == "__main__":
    if not validate_env():
        sys.exit(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
