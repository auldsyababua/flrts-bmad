"""
Unified cache interface using Cloudflare KV.
"""

from dotenv import load_dotenv

from .cloudflare_cache import CloudflareRedis
from .cloudflare_cache import cloudflare_cache as cache_client

# Load environment variables
load_dotenv()

# Create Redis-compatible client
Redis = CloudflareRedis

# Export the cache client
__all__ = ["cache_client", "Redis"]
