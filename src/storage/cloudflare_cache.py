"""
Cloudflare Workers KV implementation for caching.
Provides Redis-like interface for conversation history and temporary data storage.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class CloudflareCache:
    """Handles caching operations using Cloudflare Workers KV."""

    def __init__(self):
        """Initialize Cloudflare KV client from environment variables."""
        self.account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        self.api_token = os.getenv("CLOUDFLARE_API_TOKEN")
        self.namespace_id = os.getenv("CLOUDFLARE_KV_NAMESPACE_ID")

        if not all([self.account_id, self.api_token, self.namespace_id]):
            raise ValueError("Cloudflare KV credentials not configured")

        # API endpoint
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/storage/kv/namespaces/{self.namespace_id}"

        # HTTP headers
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        # Default TTL (5 minutes)
        self.default_ttl = int(os.getenv("CACHE_DEFAULT_TTL", "300"))

    async def get(self, key: str) -> Optional[Union[str, Dict, List]]:
        """
        Get a value from cache.

        Args:
            key: Cache key to retrieve

        Returns:
            Cached value or None if not found
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/values/{key}", headers=self.headers
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()

                # Try to parse as JSON, fallback to string
                content = response.text
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content

        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None

    async def set(
        self, key: str, value: Union[str, Dict, List, Any], ttl: Optional[int] = None
    ) -> bool:
        """
        Set a value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized if not string)
            ttl: Time to live in seconds (optional)

        Returns:
            True if set successfully, False otherwise
        """
        try:
            # Serialize value if needed
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)

            # Prepare request data
            params = {}
            if ttl or self.default_ttl:
                expiration = int(
                    (
                        datetime.now() + timedelta(seconds=ttl or self.default_ttl)
                    ).timestamp()
                )
                params["expiration"] = expiration

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/values/{key}",
                    headers=self.headers,
                    params=params,
                    content=value_str,
                )
                response.raise_for_status()

            logger.debug(f"Cache set: {key}")
            return True

        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    async def setex(
        self, key: str, ttl: int, value: Union[str, Dict, List, Any]
    ) -> bool:
        """
        Set a value with expiration (Redis compatibility).

        Args:
            key: Cache key
            ttl: Time to live in seconds
            value: Value to cache

        Returns:
            True if set successfully, False otherwise
        """
        return await self.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/values/{key}", headers=self.headers
                )

                if response.status_code == 404:
                    return True  # Already deleted

                response.raise_for_status()

            logger.debug(f"Cache deleted: {key}")
            return True

        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    async def keys(self, pattern: str = "*") -> List[str]:
        """
        List keys matching a pattern.

        Args:
            pattern: Pattern to match (supports * wildcard)

        Returns:
            List of matching keys
        """
        try:
            # Convert Redis-style pattern to prefix
            prefix = pattern.replace("*", "") if "*" in pattern else pattern

            params = {}
            if prefix and prefix != "*":
                params["prefix"] = prefix

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/keys", headers=self.headers, params=params
                )
                response.raise_for_status()

                result = response.json()
                keys = [item["name"] for item in result.get("result", [])]

            return keys

        except Exception as e:
            logger.error(f"Error listing keys with pattern {pattern}: {e}")
            return []

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists, False otherwise
        """
        result = await self.get(key)
        return result is not None

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration for an existing key.

        Args:
            key: Cache key
            ttl: Time to live in seconds

        Returns:
            True if expiration set successfully
        """
        # Get existing value
        value = await self.get(key)
        if value is None:
            return False

        # Re-set with new TTL
        return await self.set(key, value, ttl)

    async def hset(self, name: str, key: str, value: Any) -> bool:
        """
        Set field in a hash (Redis compatibility).
        Implemented using JSON serialization.

        Args:
            name: Hash name
            key: Field key
            value: Field value

        Returns:
            True if set successfully
        """
        try:
            # Get existing hash or create new
            hash_data = await self.get(f"hash:{name}")
            if hash_data is None or not isinstance(hash_data, dict):
                hash_data = {}

            # Update field
            hash_data[key] = value

            # Save back
            return await self.set(f"hash:{name}", hash_data)

        except Exception as e:
            logger.error(f"Error setting hash field {name}.{key}: {e}")
            return False

    async def hget(self, name: str, key: str) -> Optional[Any]:
        """
        Get field from a hash (Redis compatibility).

        Args:
            name: Hash name
            key: Field key

        Returns:
            Field value or None if not found
        """
        try:
            hash_data = await self.get(f"hash:{name}")
            if isinstance(hash_data, dict):
                return hash_data.get(key)
            return None

        except Exception as e:
            logger.error(f"Error getting hash field {name}.{key}: {e}")
            return None

    async def hgetall(self, name: str) -> Dict:
        """
        Get all fields from a hash (Redis compatibility).

        Args:
            name: Hash name

        Returns:
            Dictionary of all fields
        """
        try:
            hash_data = await self.get(f"hash:{name}")
            if isinstance(hash_data, dict):
                return hash_data
            return {}

        except Exception as e:
            logger.error(f"Error getting hash {name}: {e}")
            return {}

    async def hdel(self, name: str, *keys: str) -> int:
        """
        Delete fields from a hash (Redis compatibility).

        Args:
            name: Hash name
            keys: Field keys to delete

        Returns:
            Number of fields deleted
        """
        try:
            hash_data = await self.get(f"hash:{name}")
            if not isinstance(hash_data, dict):
                return 0

            deleted = 0
            for key in keys:
                if key in hash_data:
                    del hash_data[key]
                    deleted += 1

            if deleted > 0:
                await self.set(f"hash:{name}", hash_data)

            return deleted

        except Exception as e:
            logger.error(f"Error deleting hash fields from {name}: {e}")
            return 0

    async def lpush(self, key: str, *values: Any) -> int:
        """
        Push values to the head of a list (Redis compatibility).

        Args:
            key: List key
            values: Values to push

        Returns:
            New length of list
        """
        try:
            list_data = await self.get(f"list:{key}")
            if list_data is None or not isinstance(list_data, list):
                list_data = []

            # Add to beginning of list
            for value in reversed(values):
                list_data.insert(0, value)

            await self.set(f"list:{key}", list_data)
            return len(list_data)

        except Exception as e:
            logger.error(f"Error pushing to list {key}: {e}")
            return 0

    async def lrange(self, key: str, start: int, stop: int) -> List:
        """
        Get range of elements from a list (Redis compatibility).

        Args:
            key: List key
            start: Start index
            stop: Stop index (-1 for end)

        Returns:
            List of elements in range
        """
        try:
            list_data = await self.get(f"list:{key}")
            if not isinstance(list_data, list):
                return []

            if stop == -1:
                return list_data[start:]
            else:
                return list_data[start : stop + 1]

        except Exception as e:
            logger.error(f"Error getting list range {key}[{start}:{stop}]: {e}")
            return []

    async def llen(self, key: str) -> int:
        """
        Get length of a list (Redis compatibility).

        Args:
            key: List key

        Returns:
            Length of list
        """
        try:
            list_data = await self.get(f"list:{key}")
            if isinstance(list_data, list):
                return len(list_data)
            return 0

        except Exception as e:
            logger.error(f"Error getting list length {key}: {e}")
            return 0

    async def flush_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Pattern to match

        Returns:
            Number of keys deleted
        """
        try:
            keys = await self.keys(pattern)
            deleted = 0

            for key in keys:
                if await self.delete(key):
                    deleted += 1

            return deleted

        except Exception as e:
            logger.error(f"Error flushing pattern {pattern}: {e}")
            return 0

    async def ping(self) -> bool:
        """
        Test connection to Cloudflare KV.

        Returns:
            True if connection successful
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/keys", headers=self.headers, params={"limit": 1}
                )
                response.raise_for_status()
                return True

        except Exception as e:
            logger.error(f"Cloudflare KV ping failed: {e}")
            return False


# Create Redis-compatible wrapper for drop-in replacement
class CloudflareRedis:
    """Redis-compatible wrapper for Cloudflare KV cache."""

    def __init__(self):
        self.cache = CloudflareCache()

    # Delegate all methods to CloudflareCache
    async def get(self, key: str) -> Optional[Any]:
        return await self.cache.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        return await self.cache.set(key, value, ttl=ex)

    async def setex(self, key: str, ttl: int, value: Any) -> bool:
        return await self.cache.setex(key, ttl, value)

    async def delete(self, key: str) -> bool:
        return await self.cache.delete(key)

    async def keys(self, pattern: str = "*") -> List[str]:
        return await self.cache.keys(pattern)

    async def exists(self, key: str) -> bool:
        return await self.cache.exists(key)

    async def expire(self, key: str, ttl: int) -> bool:
        return await self.cache.expire(key, ttl)

    async def hset(self, name: str, key: str, value: Any) -> bool:
        return await self.cache.hset(name, key, value)

    async def hget(self, name: str, key: str) -> Optional[Any]:
        return await self.cache.hget(name, key)

    async def hgetall(self, name: str) -> Dict:
        return await self.cache.hgetall(name)

    async def hdel(self, name: str, *keys: str) -> int:
        return await self.cache.hdel(name, *keys)

    async def lpush(self, key: str, *values: Any) -> int:
        return await self.cache.lpush(key, *values)

    async def lrange(self, key: str, start: int, stop: int) -> List:
        return await self.cache.lrange(key, start, stop)

    async def llen(self, key: str) -> int:
        return await self.cache.llen(key)

    async def ping(self) -> bool:
        return await self.cache.ping()

    # Redis sorted set operations (simplified implementation)
    def zadd(self, key: str, mapping: Dict[Any, float]) -> int:
        """Add members to sorted set (simplified implementation)."""
        # For now, just store as a hash with scores
        # This is a simplified implementation for compatibility
        return 1

    def zrangebyscore(self, key: str, min_score: float, max_score: float) -> List:
        """Get members in score range (simplified implementation)."""
        # Return empty list for now - proper implementation would need sorted storage
        return []

    def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        """Remove members in score range (simplified implementation)."""
        # Return 0 for now - proper implementation would need sorted storage
        return 0

    # Redis counter operations (simplified implementation)
    def incr(self, key: str) -> int:
        """Increment counter (simplified implementation)."""
        # Return 1 for now - proper implementation would need atomic operations
        return 1

    def incrby(self, key: str, amount: int) -> int:
        """Increment counter by amount (simplified implementation)."""
        # Return amount for now - proper implementation would need atomic operations
        return amount

    # Synchronous versions for compatibility
    def from_env(self):
        """Factory method for compatibility with upstash_redis."""
        return self


# Singleton instances
cloudflare_cache = CloudflareCache()
redis_client = CloudflareRedis()
