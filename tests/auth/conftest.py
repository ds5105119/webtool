import pytest_asyncio

from webtool.auth import JWTService, RedisJWTService
from webtool.cache import InMemoryCache, RedisCache
from webtool.utils import key


@pytest_asyncio.fixture(scope="session")
async def in_memory_jwt_service():
    client = InMemoryCache()
    service = JWTService(client)

    try:
        yield service
    finally:
        await client.aclose()


@pytest_asyncio.fixture(scope="session")
async def jwt_service():
    client = RedisCache("redis://127.0.0.1:6379/0")
    private_key = key.make_ed_key()
    service = RedisJWTService(client, secret_key=private_key)

    try:
        yield service
    finally:
        await client.aclose()
