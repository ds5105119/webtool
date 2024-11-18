import pytest_asyncio

from webtool.auth import JWTService, RedisJWTService
from webtool.cache import InMemoryCache, RedisCache


@pytest_asyncio.fixture(scope="session")
async def inmemory_jwt_service():
    client = InMemoryCache()
    service = JWTService(client)

    try:
        yield service
    finally:
        await client.aclose()


@pytest_asyncio.fixture(scope="session")
async def jwt_service():
    client = RedisCache("redis://127.0.0.1:6379/0")
    service = RedisJWTService(client, secret_key="test")

    try:
        yield service
    finally:
        await client.aclose()
