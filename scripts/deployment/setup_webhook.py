#!/usr/bin/env python3
"""
Setup webhook for production deployment.
Run this after deploying to Render to configure the webhook.
"""

import argparse
import os
import sys

import requests

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

from core.config import TELEGRAM_BOT_TOKEN  # noqa: E402


def setup_webhook(webhook_url):
    """Set webhook URL for Telegram bot"""
    print(f"Setting webhook to: {webhook_url}")

    # Delete any existing webhook first
    delete_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
    delete_response = requests.post(delete_url)
    print(f"Deleted existing webhook: {delete_response.json()}")

    # Set new webhook
    set_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    data = {"url": webhook_url, "allowed_updates": ["message", "callback_query"]}

    response = requests.post(set_url, json=data)
    result = response.json()

    if result.get("ok"):
        print("✅ Webhook set successfully!")

        # Get webhook info
        info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
        info_response = requests.get(info_url)
        info = info_response.json()

        if info.get("ok"):
            webhook_info = info["result"]
            print("\nWebhook info:")
            print(f"  URL: {webhook_info.get('url')}")
            print(
                f"  Has custom certificate: {webhook_info.get('has_custom_certificate')}"
            )
            print(f"  Pending update count: {webhook_info.get('pending_update_count')}")
            if webhook_info.get("last_error_message"):
                print(f"  ⚠️  Last error: {webhook_info.get('last_error_message')}")
    else:
        print(f"❌ Failed to set webhook: {result}")
        return False

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup Telegram webhook")
    parser.add_argument(
        "webhook_url",
        help="Full webhook URL (e.g., https://your-bot.onrender.com/webhook)",
    )

    args = parser.parse_args()

    if not args.webhook_url.startswith("https://"):
        print("Error: Webhook URL must use HTTPS")
        sys.exit(1)

    if setup_webhook(args.webhook_url):
        print("\n🎉 Webhook setup complete! Your bot is ready to receive messages.")
    else:
        print("\n❌ Webhook setup failed. Please check your configuration.")
        sys.exit(1)
