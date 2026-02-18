"""Redis-backed token bucket rate limiter."""

import time

import redis.asyncio as redis


class RateLimitExceeded(Exception):
    """Raised when the rate limit is exceeded."""

    def __init__(self, name: str, retry_after: float):
        self.name = name
        self.retry_after = retry_after
        super().__init__(f"Rate limit '{name}' exceeded. Retry after {retry_after:.1f}s")


class RateLimiter:
    """Token bucket rate limiter backed by Redis.

    Args:
        redis_client: Async Redis client instance.
        name: Unique identifier for this limiter (e.g. 'hubspot').
        max_tokens: Maximum tokens in the bucket.
        refill_seconds: Time window in seconds to refill to max_tokens.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        name: str,
        max_tokens: int,
        refill_seconds: float,
    ):
        self._redis = redis_client
        self._key = f"ratelimit:{name}"
        self._max_tokens = max_tokens
        self._refill_rate = max_tokens / refill_seconds

    async def acquire(self, tokens: int = 1) -> bool:
        """Attempt to acquire tokens. Returns True if allowed, raises on limit."""
        now = time.time()
        pipe = self._redis.pipeline()

        # Atomic token bucket via Lua script
        script = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local requested = tonumber(ARGV[4])

        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1])
        local last_refill = tonumber(bucket[2])

        if tokens == nil then
            tokens = max_tokens
            last_refill = now
        end

        local elapsed = now - last_refill
        tokens = math.min(max_tokens, tokens + elapsed * refill_rate)

        if tokens >= requested then
            tokens = tokens - requested
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, math.ceil(max_tokens / refill_rate) + 10)
            return 1
        else
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, math.ceil(max_tokens / refill_rate) + 10)
            return 0
        end
        """
        result = await self._redis.eval(  # type: ignore[union-attr]
            script, 1, self._key, self._max_tokens, self._refill_rate, now, tokens
        )

        if result == 0:
            wait = (tokens - 0) / self._refill_rate if self._refill_rate > 0 else 1.0
            raise RateLimitExceeded(self._key, wait)

        return True
