import asyncio
import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, Union

from redis.asyncio.client import Redis
from redis.asyncio.connection import ConnectionPool
from redis.asyncio.retry import Retry
from redis.backoff import default_backoff
from redis.exceptions import BusyLoadingError, ConnectionError, RedisError

from webtool.cache.lock import AsyncInMemoryLock, AsyncRedisLock, BaseLock

DEFAULT_CAP = 0.512
DEFAULT_BASE = 0.008


class BaseCache(ABC):
    """
    Abstract base class for Redis client implementations.
    Defines the interface for performing safe Redis operations.
    """

    cache: Any

    @abstractmethod
    async def lock(
        self,
        key: Union[bytes, str, memoryview],
        ttl_ms: Union[int, timedelta, None] = 100,
        blocking: bool = True,
        blocking_timeout: float = DEFAULT_CAP,
        blocking_sleep: float = DEFAULT_BASE,
    ) -> BaseLock:
        """
        Sets a key-value pair in a lock mechanism.

        Parameters:
            key: The key to be locked.
            ttl_ms: The time-to-live for the lock in milliseconds.
            blocking: If True, the method will block until the lock is acquired.
            blocking_timeout: The maximum time in seconds to block while waiting for the lock to be acquired.
            blocking_sleep: The time in seconds to wait between attempts to acquire the lock when blocking.

        Returns:
            BaseLock: The Lock object representing the acquired lock.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    async def set(
        self,
        key: Union[bytes, str, memoryview],
        value: Union[bytes, memoryview, str, int, float],
        ex: Union[int, timedelta, None] = None,
        exat: Union[int, datetime, None] = None,
        nx: bool = False,
    ) -> Any:
        """
        Sets a key-value pair.

        Parameters:
            key: The key for the data to be set.
            value: The value associated with the key.
            ex: Expiration time for the key, in seconds or as a timedelta.
            exat: Expiration time as an absolute timestamp.
            nx: if set to True, set the value at key to value only if it does not exist.

        Returns:
            Any: return of set.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    async def get(
        self,
        key: Union[bytes, str, memoryview],
    ) -> Any:
        """
        Gets a key-value pair.

        Parameters:
            key: The key for the data to be set.
        Returns:
            Any: return of get.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        key: Union[bytes, str, memoryview],
    ) -> Any:
        """
        Deletes a key-value pair.

        Parameters:
            key: The key for the data to be set.
        Returns:
            None

        Raises:
             NotImplementedError: If the method is not implemented in a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    async def aclose(self) -> None:
        """
        Closes Cache Client.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """

        raise NotImplementedError


class InMemoryCache(BaseCache):
    """
    Implementation of a InMemory client.
    DO NOT USE IN PRODUCTION.
    """

    def __init__(self):
        self.cache: dict = {}

    async def _expire(self) -> None:
        now = asyncio.get_event_loop().time()
        self.cache = {k: v for k, v in self.cache.items() if v[1] > now}

    def lock(
        self,
        key: Union[bytes, str, memoryview],
        ttl_ms: Union[int, timedelta, None] = 100,
        blocking: bool = True,
        blocking_timeout: float = DEFAULT_CAP,
        blocking_sleep: float = DEFAULT_BASE,
    ) -> AsyncInMemoryLock:
        """
        Sets a key-value pair in a lock mechanism.

        Parameters:
            key: The key to be locked.
            ttl_ms: The time-to-live for the lock in milliseconds.
            blocking: If True, the method will block until the lock is acquired.
            blocking_timeout: The maximum time in seconds to block while waiting for the lock to be acquired.
            blocking_sleep: The time in seconds to wait between attempts to acquire the lock when blocking.

        Returns:
            AsyncInMemoryLock: The Lock object representing the acquired lock.
        """
        return AsyncInMemoryLock(self, key, ttl_ms, blocking, blocking_timeout, blocking_sleep)

    async def set(
        self,
        key: Union[bytes, str, memoryview],
        value: Union[bytes, memoryview, str, int, float],
        ex: Union[int, timedelta, None] = None,
        exat: Union[int, datetime, None] = None,
        nx: bool = False,
    ) -> Any:
        """
        Sets a key-value pair.

        Parameters:
            key: The key for the data to be set.
            value: The value associated with the key.
            ex: Expiration time for the key, in seconds or as a timedelta.
            exat: Expiration time as an absolute timestamp.
            nx: if set to True, set the value at key to value only if it does not exist.

        Returns:
            Any: return of set.
        """

        await self._expire()
        if nx and self.cache.get(key):
            return None

        if ex:
            now = asyncio.get_running_loop().time()
            if isinstance(ex, (float, int)):
                exp = now + ex
            else:
                exp = now + ex.total_seconds()
        else:
            if isinstance(exat, int):
                exp = exat
            elif isinstance(exat, datetime):
                exp = exat.timestamp()
            else:
                exp = float("inf")

        self.cache[key] = (value, exp)
        return self.cache[key]

    async def get(
        self,
        key: Union[bytes, str, memoryview],
    ) -> Any:
        """
        Gets a key-value pair.

        Parameters:
            key: The key for the data to be set.
        Returns:
            Any: return of get.
        """

        await self._expire()

        val = self.cache.get(key)
        if val:
            return val[0]
        return None

    async def delete(
        self,
        key: Union[bytes, str, memoryview],
    ) -> Any:
        """
        Deletes a key-value pair.

        Parameters:
            key: The key for the data to be set.
        Returns:
            None
        """

        await self._expire()

        return self.cache.pop(key)

    async def aclose(self) -> None:
        """
        Closes the Cache client.
        """

        self.cache.clear()


@dataclass(frozen=True)
class RedisConfig:
    """
    Configuration settings for establishing a connection with a Redis server.

    Parameters:
        username (Optional[str]): username
        password (Optional[str]): password
        health_check_interval (int): Interval in seconds for performing health checks.
        socket_timeout (float): Timeout in seconds for socket operations, including reads and writes.
        socket_connect_timeout (float): Timeout in seconds for establishing a new connection to Redis.
        socket_keepalive (bool): Whether to enable TCP keepalive for the connection. Default is True.
        retry (Optional[Retry]): Retry policy for handling transient failures.
        retry_on_error (Optional[list[type[Exception]]]): A list of exception types that should trigger a retry.
        retry_on_timeout (bool): Whether to retry operations when a timeout occurs.
        ssl (bool): Specifies if SSL should be used for the Redis connection.
        protocol (Optional[int]): Redis protocol version to be used. Default is RESP3.

    Methods:
        to_dict() -> dict[str, Any]: Converts the configuration fields to a dictionary.
    """

    username: Optional[str] = None
    password: Optional[str] = None
    health_check_interval: int = 0
    socket_timeout: float = 0.5
    socket_connect_timeout: float = 2.0
    socket_keepalive: bool = True
    retry: Optional[Retry] = Retry(default_backoff(), retries=3)
    retry_on_error: Optional[list[type[Exception]]] = field(
        default_factory=lambda: [BusyLoadingError, ConnectionError, RedisError, OSError]
    )
    retry_on_timeout: bool = True
    ssl: bool = False
    max_connections: Optional[int] = None
    protocol: Optional[int] = 3

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v}


class RedisCache(BaseCache):
    """
    Implementation of a Redis client with failover capabilities.
    """

    def __init__(
        self,
        redis_url: str = None,
        connection_pool: Optional[ConnectionPool] = None,
        logger: logging.Logger = None,
        config: RedisConfig | None = None,
    ):
        """
        Initializes the Redis client.

        Parameters:
            redis_url: Redis data source name for connection.
            connection_pool: An existing connection pool to use.
        """

        self.logger = logger or logging.getLogger(__name__)
        self.config = config or RedisConfig()

        if connection_pool:
            self.connection_pool = connection_pool
        elif redis_url:
            kwargs = self.config.to_dict()
            kwargs.update(
                {
                    "retry": deepcopy(self.config.retry),
                }
            )
            self.connection_pool = ConnectionPool.from_url(redis_url, **kwargs)
        else:
            raise TypeError("RedisClient must be provided with either redis_dsn or connection_pool")

        self.cache: Redis = Redis.from_pool(self.connection_pool)

    def lock(
        self,
        key: Union[bytes, str, memoryview],
        ttl_ms: Union[int, timedelta, None] = 100,
        blocking: bool = True,
        blocking_timeout: float = DEFAULT_CAP,
        blocking_sleep: float = DEFAULT_BASE,
    ) -> AsyncRedisLock:
        """
        Sets a key-value pair in a lock mechanism.

        Parameters:
            key: The key to be locked.
            ttl_ms: The time-to-live for the lock in milliseconds.
            blocking: If True, the method will block until the lock is acquired.
            blocking_timeout: The maximum time in seconds to block while waiting for the lock to be acquired.
            blocking_sleep: The time in seconds to wait between attempts to acquire the lock when blocking.

        Returns:
            AsyncRedisLock: The Lock object representing the acquired lock.
        """
        return AsyncRedisLock(self, key, ttl_ms, blocking, blocking_timeout, blocking_sleep)

    async def set(
        self,
        key: Union[bytes, str, memoryview],
        value: Union[bytes, memoryview, str, int, float],
        ex: Union[int, timedelta, None] = None,
        exat: Union[int, datetime, None] = None,
        nx: bool = False,
    ) -> Any:
        """
        Sets a key-value pair.

        Parameters:
            key: The key for the data to be set.
            value: The value associated with the key.
            ex: Expiration time for the key, in seconds or as a timedelta.
            exat: Expiration time as an absolute timestamp.
            nx: if set to True, set the value at key to value only if it does not exist.

        Returns:
            Any: return of set.
        """

        return await self.cache.set(key, value, ex=ex, exat=exat, nx=nx)

    async def get(
        self,
        key: Union[bytes, str, memoryview],
    ) -> Any:
        """
        Gets a key-value pair.

        Parameters:
            key: The key for the data to be set.
        Returns:
            Any: return of get.
        """

        return await self.cache.get(key)

    async def delete(
        self,
        key: Union[bytes, str, memoryview],
    ) -> Any:
        """
        Deletes a key-value pair.

        Parameters:
            key: The key for the data to be set.
        Returns:
            None
        """

        return await self.cache.delete(key)

    async def aclose(self) -> None:
        """
        Closes the Redis client connection and connection pool.
        """

        self.logger.info(f"Closing Redis client connection (id: {id(self)})")

        try:
            await self.cache.aclose()
        except AttributeError as e:
            self.logger.warning(f"Failed to close Redis connection: {e}")

        try:
            await self.connection_pool.aclose()
            await self.connection_pool.disconnect()
        except AttributeError as e:
            self.logger.warning(f"Failed to close connection pool: {e}")
