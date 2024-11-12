import asyncio
import random
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Union

from blake3 import blake3


class BaseLock(ABC):
    @abstractmethod
    async def acquire(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def release(self) -> None:
        raise NotImplementedError


class AsyncRedisLock(BaseLock):
    __slots__ = "_client", "_key", "_ttl", "_blocking", "_blocking_timeout", "_blocking_sleep"

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

    async def acquire(self):
        """
        if blocking is enabled, retry with Equal Jitter Backoff strategy

        :return: True when acquired lock, else False
        """
        if type(self._key) is str:
            self._key = self._key.encode()
        self._key = blake3(self._key).digest()

        start_time = asyncio.get_running_loop().time()

        while True:
            lock_acquired = await self._client.cache.set(self._key, b"locked", px=self._ttl, nx=True)
            if lock_acquired:
                return True

            if not self._blocking:
                return False

            failed_time = asyncio.get_running_loop().time()
            delay = (1 + random.random()) * self._blocking_sleep

            if failed_time - start_time > self._blocking_timeout:
                return False

            await asyncio.sleep(delay)

    async def release(self):
        await self._client.cache.delete(self._key)

    async def __aenter__(self):
        acquired = await self.acquire()
        if not acquired:
            raise TimeoutError
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.release()
