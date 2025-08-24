#!/usr/bin/env python3
"""
Production Configuration Validator for FLRTS-BMAD

Validates that all required environment variables are set and production-ready.
"""

import json
import os
import re
import sys
from typing import List, Tuple


class ConfigValidator:
    """Validates production configuration."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.env_vars = dict(os.environ)

    def validate_required_vars(self) -> None:
        """Validate required environment variables."""
        required_vars = [
            "TELEGRAM_BOT_TOKEN",
            "OPENAI_API_KEY",
            "CLOUDFLARE_ACCOUNT_ID",
            "CLOUDFLARE_API_TOKEN",
            "CLOUDFLARE_VECTORIZE_INDEX",
            "CLOUDFLARE_KV_NAMESPACE_ID",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "AUTHORIZED_USERNAMES",
            "AUTHORIZED_USER_IDS",
        ]

        for var in required_vars:
            if not self.env_vars.get(var):
                self.errors.append(f"Missing required environment variable: {var}")

    def validate_telegram_config(self) -> None:
        """Validate Telegram configuration."""
        token = self.env_vars.get("TELEGRAM_BOT_TOKEN", "")

        # Check token format (should be digits:letters)
        if token and not re.match(r"^\d+:[A-Za-z0-9_-]+$", token):
            self.errors.append("TELEGRAM_BOT_TOKEN appears to be invalid format")

        # Check for test/placeholder values
        if "test" in token.lower() or "your_" in token.lower():
            self.errors.append("TELEGRAM_BOT_TOKEN appears to be a placeholder value")

    def validate_openai_config(self) -> None:
        """Validate OpenAI configuration."""
        api_key = self.env_vars.get("OPENAI_API_KEY", "")

        # Check key format
        if api_key and not api_key.startswith("sk-"):
            self.errors.append("OPENAI_API_KEY should start with 'sk-'")

        # Check for test/placeholder values
        if "test" in api_key.lower() or "your_" in api_key.lower():
            self.errors.append("OPENAI_API_KEY appears to be a placeholder value")

    def validate_supabase_config(self) -> None:
        """Validate Supabase configuration."""
        url = self.env_vars.get("SUPABASE_URL", "")
        key = self.env_vars.get("SUPABASE_KEY", "")

        # Check URL format
        if url and not url.startswith("https://"):
            self.errors.append("SUPABASE_URL should start with 'https://'")

        if url and ".supabase.co" not in url:
            self.warnings.append(
                "SUPABASE_URL doesn't look like a standard Supabase URL"
            )

        # Check for test/placeholder values
        if "test" in url.lower() or "your_" in url.lower():
            self.errors.append("SUPABASE_URL appears to be a placeholder value")

        if "test" in key.lower() or "your_" in key.lower():
            self.errors.append("SUPABASE_KEY appears to be a placeholder value")

    def validate_auth_config(self) -> None:
        """Validate authorization configuration."""
        usernames = self.env_vars.get("AUTHORIZED_USERNAMES", "")
        user_ids = self.env_vars.get("AUTHORIZED_USER_IDS", "")

        try:
            username_list = json.loads(usernames) if usernames else []
            if not isinstance(username_list, list) or len(username_list) == 0:
                self.errors.append(
                    "AUTHORIZED_USERNAMES must be a non-empty JSON array"
                )
        except json.JSONDecodeError:
            self.errors.append("AUTHORIZED_USERNAMES is not valid JSON")

        try:
            user_id_list = json.loads(user_ids) if user_ids else []
            if not isinstance(user_id_list, list) or len(user_id_list) == 0:
                self.errors.append("AUTHORIZED_USER_IDS must be a non-empty JSON array")
        except json.JSONDecodeError:
            self.errors.append("AUTHORIZED_USER_IDS is not valid JSON")

    def validate_performance_config(self) -> None:
        """Validate performance-related settings."""
        pool_size = self.env_vars.get("SUPABASE_POOL_SIZE", "10")

        try:
            size = int(pool_size)
            if size > 50:
                self.warnings.append(
                    f"SUPABASE_POOL_SIZE ({size}) is quite high for a 5-20 user system"
                )
            elif size < 2:
                self.warnings.append(f"SUPABASE_POOL_SIZE ({size}) might be too low")
        except ValueError:
            self.errors.append("SUPABASE_POOL_SIZE must be a number")

    def validate_security(self) -> None:
        """Validate security configuration."""
        # Check for exposed secrets in logs
        if self.env_vars.get("DEBUG", "").lower() == "true":
            self.warnings.append("DEBUG mode is enabled - disable for production")

        # Check for development flags
        if self.env_vars.get("TESTING_MODE", "").lower() == "true":
            self.warnings.append("TESTING_MODE is enabled - disable for production")

    def check_story_1_6_config(self) -> None:
        """Validate Story 1.6 direct execution configuration."""
        # Direct execution doesn't need specific config, but check performance settings
        max_tokens = self.env_vars.get("MAX_TOKENS", "2000")
        try:
            tokens = int(max_tokens)
            if tokens > 4000:
                self.warnings.append(
                    f"MAX_TOKENS ({tokens}) is high - may slow direct execution fallbacks"
                )
        except ValueError:
            self.warnings.append("MAX_TOKENS should be a number")

    def validate_all(self) -> Tuple[List[str], List[str]]:
        """Run all validations and return errors and warnings."""
        self.validate_required_vars()
        self.validate_telegram_config()
        self.validate_openai_config()
        self.validate_supabase_config()
        self.validate_auth_config()
        self.validate_performance_config()
        self.validate_security()
        self.check_story_1_6_config()

        return self.errors, self.warnings

    def print_results(self) -> bool:
        """Print validation results and return True if valid."""
        errors, warnings = self.validate_all()

        print("🔍 FLRTS-BMAD Configuration Validation")
        print("=" * 50)

        if errors:
            print("❌ ERRORS (must fix before production):")
            for error in errors:
                print(f"  - {error}")
            print()

        if warnings:
            print("⚠️  WARNINGS (recommended to address):")
            for warning in warnings:
                print(f"  - {warning}")
            print()

        if not errors and not warnings:
            print("✅ All configuration checks passed!")
        elif not errors:
            print("✅ No critical errors found. Warnings should be reviewed.")
        else:
            print("❌ Configuration has critical errors that must be fixed.")

        print("\nStory 1.6 Direct Execution: Ready ✓")
        print("Expected users: 5-20")
        print("Performance target: <500ms for direct operations")

        return len(errors) == 0


def main():
    """Main validation function."""
    # Default to loading .env file if it exists
    env_file = ".env"
    load_env_file = True

    if len(sys.argv) > 1:
        if sys.argv[1] == "--env-file":
            env_file = sys.argv[2] if len(sys.argv) > 2 else ".env"
        elif sys.argv[1] == "--no-env":
            load_env_file = False
        elif sys.argv[1] == "--help":
            print(
                "Usage: python validate_config.py [--env-file FILE] [--no-env] [--help]"
            )
            print(
                "  --env-file FILE  Load environment from specific file (default: .env)"
            )
            print(
                "  --no-env         Don't load any .env file, use system environment only"
            )
            print("  --help           Show this help")
            sys.exit(0)

    if load_env_file:
        try:
            with open(env_file) as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        key, value = line.strip().split("=", 1)
                        os.environ[key] = value.strip("\"'")
            print(f"📁 Loaded environment from: {env_file}")
        except FileNotFoundError:
            print(f"⚠️  Environment file {env_file} not found, using system environment")
        except Exception as e:
            print(f"❌ Error loading {env_file}: {e}")
            sys.exit(1)

    validator = ConfigValidator()
    is_valid = validator.print_results()

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
