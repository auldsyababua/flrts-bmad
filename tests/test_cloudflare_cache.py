"""
Integration tests for Cloudflare Workers KV cache implementation.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.storage.cloudflare_cache import CloudflareCache, CloudflareRedis


@pytest.fixture
def mock_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-account-123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token-xyz")
    monkeypatch.setenv("CLOUDFLARE_KV_NAMESPACE_ID", "test-namespace")
    monkeypatch.setenv("CACHE_DEFAULT_TTL", "300")


@pytest.fixture
async def cache(mock_env):
    """Create a CloudflareCache instance for testing."""
    return CloudflareCache()


@pytest.fixture
async def redis_cache(mock_env):
    """Create a CloudflareRedis instance for testing."""
    return CloudflareRedis()


class TestCloudflareCache:
    """Test suite for Cloudflare KV cache operations."""

    @pytest.mark.asyncio
    async def test_get_and_set(self, cache):
        """Test basic get and set operations."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value

            # Test set
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_instance.put = AsyncMock(return_value=mock_response)

            result = await cache.set("test-key", "test-value")
            assert result is True

            # Test get
            mock_response.status_code = 200
            mock_response.text = "test-value"
            mock_instance.get = AsyncMock(return_value=mock_response)

            value = await cache.get("test-key")
            assert value == "test-value"

    @pytest.mark.asyncio
    async def test_json_serialization(self, cache):
        """Test JSON serialization for complex types."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value

            # Test set with dict
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_instance.put = AsyncMock(return_value=mock_response)

            test_dict = {"name": "test", "value": 123}
            result = await cache.set("json-key", test_dict)
            assert result is True

            # Verify JSON was sent
            call_args = mock_instance.put.call_args
            assert json.loads(call_args[1]["content"]) == test_dict

            # Test get with JSON response
            mock_response.status_code = 200
            mock_response.text = json.dumps(test_dict)
            mock_instance.get = AsyncMock(return_value=mock_response)

            value = await cache.get("json-key")
            assert value == test_dict

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """Test delete operation."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.delete = AsyncMock(return_value=mock_response)

            result = await cache.delete("test-key")
            assert result is True
            mock_instance.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists(self, cache):
        """Test exists check."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value

            # Key exists
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "value"
            mock_response.raise_for_status = Mock()
            mock_instance.get = AsyncMock(return_value=mock_response)

            result = await cache.exists("existing-key")
            assert result is True

            # Key doesn't exist
            mock_response.status_code = 404
            mock_instance.get = AsyncMock(return_value=mock_response)

            result = await cache.exists("missing-key")
            assert result is False

    @pytest.mark.asyncio
    async def test_keys_listing(self, cache):
        """Test listing keys with patterns."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {
                "result": [
                    {"name": "cache:key1"},
                    {"name": "cache:key2"},
                    {"name": "other:key3"},
                ]
            }
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(return_value=mock_response)

            keys = await cache.keys("cache:*")
            assert len(keys) == 3  # Returns all in this mock
            assert "cache:key1" in keys

    @pytest.mark.asyncio
    async def test_hash_operations(self, cache):
        """Test hash operations (Redis compatibility)."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value

            # Setup mock responses
            mock_get_response = Mock()
            mock_get_response.status_code = 404  # Initially empty
            mock_get_response.raise_for_status = Mock()

            mock_put_response = Mock()
            mock_put_response.raise_for_status = Mock()

            mock_instance.get = AsyncMock(return_value=mock_get_response)
            mock_instance.put = AsyncMock(return_value=mock_put_response)

            # Test hset
            result = await cache.hset("myhash", "field1", "value1")
            assert result is True

            # Test hget (mock existing hash)
            mock_get_response.status_code = 200
            mock_get_response.text = json.dumps(
                {"field1": "value1", "field2": "value2"}
            )

            value = await cache.hget("myhash", "field1")
            assert value == "value1"

            # Test hgetall
            all_fields = await cache.hgetall("myhash")
            assert all_fields == {"field1": "value1", "field2": "value2"}

    @pytest.mark.asyncio
    async def test_list_operations(self, cache):
        """Test list operations (Redis compatibility)."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value

            # Setup mock responses
            mock_get_response = Mock()
            mock_get_response.status_code = 404  # Initially empty
            mock_get_response.raise_for_status = Mock()

            mock_put_response = Mock()
            mock_put_response.raise_for_status = Mock()

            mock_instance.get = AsyncMock(return_value=mock_get_response)
            mock_instance.put = AsyncMock(return_value=mock_put_response)

            # Test lpush
            length = await cache.lpush("mylist", "item1", "item2")
            assert length == 2

            # Test lrange (mock existing list)
            mock_get_response.status_code = 200
            mock_get_response.text = json.dumps(["item2", "item1", "item0"])

            items = await cache.lrange("mylist", 0, -1)
            assert items == ["item2", "item1", "item0"]

            # Test llen
            length = await cache.llen("mylist")
            assert length == 3

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache):
        """Test TTL and expiration functionality."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.put = AsyncMock(return_value=mock_response)

            # Test setex
            result = await cache.setex("temp-key", 60, "temp-value")
            assert result is True

            # Verify expiration was set
            call_args = mock_instance.put.call_args
            assert "expiration" in call_args[1]["params"]

            # Test expire on existing key
            mock_get_response = Mock()
            mock_get_response.status_code = 200
            mock_get_response.text = "existing-value"
            mock_instance.get = AsyncMock(return_value=mock_get_response)

            result = await cache.expire("existing-key", 120)
            assert result is True

    @pytest.mark.asyncio
    async def test_error_handling(self, cache):
        """Test error handling in various operations."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value

            # Simulate API error
            mock_instance.get = AsyncMock(side_effect=Exception("API Error"))
            mock_instance.put = AsyncMock(side_effect=Exception("API Error"))
            mock_instance.delete = AsyncMock(side_effect=Exception("API Error"))

            # All operations should handle errors gracefully
            result = await cache.get("key")
            assert result is None

            result = await cache.set("key", "value")
            assert result is False

            result = await cache.delete("key")
            assert result is False

    @pytest.mark.asyncio
    async def test_ping(self, cache):
        """Test connection ping."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(return_value=mock_response)

            result = await cache.ping()
            assert result is True

            # Test failed ping
            mock_instance.get = AsyncMock(side_effect=Exception("Connection failed"))
            result = await cache.ping()
            assert result is False


class TestCloudflareRedis:
    """Test Redis compatibility wrapper."""

    @pytest.mark.asyncio
    async def test_redis_compatibility(self, redis_cache):
        """Test Redis-compatible interface."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value

            # Setup mock responses
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.status_code = 200
            mock_response.text = "test-value"

            mock_instance.put = AsyncMock(return_value=mock_response)
            mock_instance.get = AsyncMock(return_value=mock_response)

            # Test Redis-style set with expiration
            result = await redis_cache.set("key", "value", ex=60)
            assert result is True

            # Test Redis-style get
            value = await redis_cache.get("key")
            assert value == "test-value"

    @pytest.mark.asyncio
    async def test_from_env_factory(self, redis_cache):
        """Test factory method for compatibility."""
        client = redis_cache.from_env()
        assert client is not None
        assert hasattr(client, "get")
        assert hasattr(client, "set")
