#!/usr/bin/env python3
"""Check current webhook configuration for the bot."""

import os
import sys

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get bot token
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN not found in environment")
    print("\nPlease set it in your .env file or export it:")
    print("export TELEGRAM_BOT_TOKEN='your-bot-token-here'")
    sys.exit(1)

# Check webhook info
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"

try:
    response = requests.get(url)
    data = response.json()

    if data.get("ok"):
        info = data["result"]
        print("📡 Webhook Status:")
        print("-" * 50)

        webhook_url = info.get("url", "")
        if webhook_url:
            print(f"✅ URL: {webhook_url}")
            print(f"   Pending updates: {info.get('pending_update_count', 0)}")

            if "onrender.com" in webhook_url:
                print("   ✓ Using Render deployment")

            last_error = info.get("last_error_message")
            if last_error:
                print(f"   ⚠️  Last error: {last_error}")
                print(f"   Error date: {info.get('last_error_date')}")
        else:
            print("❌ No webhook URL set!")
            print("\nTo set webhook, run:")
            print(
                "python scripts/deployment/setup_webhook.py https://your-bot.onrender.com/webhook"
            )
    else:
        print(f"❌ API Error: {data.get('description', 'Unknown error')}")

except Exception as e:
    print(f"❌ Request failed: {e}")
