import pytest_asyncio

from webtool.auth import JWTService
from webtool.cache import RedisCache


@pytest_asyncio.fixture(scope="session")
async def jwt_service():
    client = RedisCache("redis://127.0.0.1:6379/0")
    service = JWTService(client, secret_key="test")

    try:
        yield service
    finally:
        await client.aclose()
