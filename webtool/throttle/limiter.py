import asyncio
from abc import ABC, abstractmethod

from webtool.cache.client import RedisCache
from webtool.throttle.decorator import LimitRule
from webtool.utils.json import ORJSONDecoder, ORJSONEncoder


class BaseLimiter(ABC):
    @abstractmethod
    def is_deny(self, identifier: str, rules: list[LimitRule]) -> list[float]:
        """
        Checks if any rate limits are exceeded.

        :param identifier: User or session identifier
        :param rules: List of rate limit rules to check
        :return: List of waiting times until rate limits reset (empty if not exceeded)
        """

        raise NotImplementedError


class RedisLimiter(BaseLimiter):
    """
    Rate limiter implementation using Redis for distributed rate limiting.
    """

    _LUA_LIMITER_SCRIPT = """
    -- Retrieve arguments
    -- ruleset = {key: [limit, window_size], ...}
    -- return = {key: [limit, current], ...}
    local now = tonumber(ARGV[1])
    local ruleset = cjson.decode(ARGV[2])

    for i, key in ipairs(KEYS) do
        -- Step 1: Remove expired requests from the sorted set
        redis.call('ZREMRANGEBYSCORE', key, 0, now - ruleset[key][2])

        -- Step 2: Count the number of requests within the valid time window
        local amount = redis.call('ZCARD', key)

        -- Step 3: Add the current request timestamp to the sorted set
        if amount <= ruleset[key][1] then
            redis.call('ZADD', key, now, tostring(now))
            amount = amount + 1
        end

        -- Step 4: Set the TTL for the key
        redis.call("EXPIRE", key, ruleset[key][2])
        ruleset[key][2] = amount
        ruleset[key][3] = redis.call("ZRANGE", key, -1, -1)[1]
    end

    return cjson.encode(ruleset)
    """

    def __init__(self, redis_cache: RedisCache):
        """
        :param redis: Redis client instance
        """

        self._cache = redis_cache.cache
        self._redis_function = self._cache.register_script(RedisLimiter._LUA_LIMITER_SCRIPT)
        self._json_encoder = ORJSONEncoder()
        self._json_decoder = ORJSONDecoder()

    @staticmethod
    def _get_ruleset(identifier: str, rules: list[LimitRule]) -> dict[str, tuple[int, int]]:
        """
        Constructs a ruleset dictionary mapping keys to limits and intervals.

        :param identifier: User or session identifier
        :param rules: List of rate limit rules to apply
        :return: Dictionary of {key: (max_requests, interval)}
        """

        ruleset = {identifier + rule.throttle_key: (rule.max_requests, rule.interval) for rule in rules}

        return ruleset

    async def _get_limits(self, ruleset) -> dict[str, list[int, int]]:
        """
        Executes the rate limiting Lua script in Redis.

        :param ruleset: Dictionary of rate limit rules
        :return: Dictionary of updated counts and timestamps
        """

        now = asyncio.get_running_loop().time()

        result = await self._redis_function(keys=list(ruleset.keys()), args=[now, self._json_encoder.encode(ruleset)])
        result = self._json_decoder.decode(result)

        return result

    async def is_deny(self, identifier: str, rules: list[LimitRule]) -> list[float]:
        """
        Checks if any rate limits are exceeded.

        :param identifier: User or session identifier
        :param rules: List of rate limit rules to check
        :return: List of waiting times until rate limits reset (empty if not exceeded)
        """

        ruleset = self._get_ruleset(identifier, rules)

        result = await self._get_limits(ruleset)
        now = asyncio.get_running_loop().time()
        deny = [float(val[2]) + ruleset[key][1] - now for key, val in result.items() if val[0] < val[1]]

        return deny
