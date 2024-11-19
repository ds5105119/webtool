import asyncio
import random
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Union

from webtool.utils.hash import sha256


class BaseLock(ABC):
    __slots__ = (
        "_client",
        "_key",
        "_ttl",
        "_blocking",
        "_blocking_timeout",
        "_blocking_sleep",
    )

    def __init__(
        self,
        client,
        key: Union[bytes, str, memoryview],
        ttl_ms: Union[int, timedelta, None],
        blocking: bool,
        blocking_timeout: float,
        blocking_sleep: float,
    ):
        self._client = client
        self._key = key
        self._ttl = ttl_ms
        self._blocking = blocking
        self._blocking_timeout = blocking_timeout
        self._blocking_sleep = blocking_sleep / 2

    @abstractmethod
    async def acquire(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def release(self) -> None:
        raise NotImplementedError

    async def __aenter__(self):
        if await self.acquire():
            return self
        raise TimeoutError

    async def __aexit__(self, exc_type, exc, tb):
        await self.release()


class AsyncInMemoryLock(BaseLock):
    async def acquire(self) -> bool:
        """
        if blocking is enabled, retry with Equal Jitter Backoff strategy

        Returns:
            bool: True when acquired lock, else False
        """
        self._key = sha256(self._key)
        start_time = asyncio.get_running_loop().time()

        while True:
            lock_acquired = await self._client.set(self._key, 1, ex=self._ttl / 1000, nx=True)
            if lock_acquired:
                return True

            if not self._blocking:
                return False

            failed_time = asyncio.get_running_loop().time()
            if failed_time - start_time > self._blocking_timeout:
                return False

            delay = (1 + random.random()) * self._blocking_sleep
            await asyncio.sleep(delay)

    async def release(self):
        await self._client.delete(self._key)


class AsyncRedisLock(BaseLock):
    async def acquire(self) -> bool:
        """
        if blocking is enabled, retry with Equal Jitter Backoff strategy

        Returns:
            bool: True when acquired lock, else False
        """
        self._key = sha256(self._key)
        start_time = asyncio.get_running_loop().time()

        while True:
            lock_acquired = await self._client.cache.set(self._key, 1, px=self._ttl, nx=True)
            if lock_acquired:
                return True

            if not self._blocking:
                return False

            failed_time = asyncio.get_running_loop().time()
            if failed_time - start_time > self._blocking_timeout:
                return False

            delay = (1 + random.random()) * self._blocking_sleep
            await asyncio.sleep(delay)

    async def release(self):
        await self._client.cache.delete(self._key)
