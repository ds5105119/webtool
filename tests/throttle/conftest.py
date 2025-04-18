from typing import Any

import httpx
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from fastapi.security import HTTPBearer
from starlette.middleware import Middleware

from webtool.auth import JWTBackend, JWTService, RedisJWTService
from webtool.cache import RedisCache
from webtool.throttle import LimitMiddleware, RedisLimiter, limiter


@pytest_asyncio.fixture(scope="session")
async def redis():
    cache = RedisCache("redis://127.0.0.1:6379/0")

    try:
        yield cache
    finally:
        await cache.aclose()


@pytest_asyncio.fixture(scope="session")
def jwt_service(redis):
    service = RedisJWTService(redis, secret_key="test")

    return service


@pytest_asyncio.fixture(scope="session")
def limit(redis):
    limit = RedisLimiter(redis.redis)

    return limit


@pytest_asyncio.fixture(scope="session")
def backend(jwt_service):
    backend = JWTBackend(jwt_service)
    return backend


class ExtendHTTPBearer(HTTPBearer):
    async def __call__(self, request: Request) -> Any | None:
        print(request.scope)
        auth = request.scope.get("auth")
        return auth


global_cache = RedisCache("redis://127.0.0.1:6379/0")
global_service = JWTService(global_cache, secret_key="test")
global_backend = JWTBackend(global_service)
bearer_scheme = ExtendHTTPBearer()

app = FastAPI(
    middleware=[
        Middleware(
            LimitMiddleware,  # type: ignore
            cache=global_cache,
            auth_backend=global_backend,
        ),
    ],
    default_response_class=ORJSONResponse,
)


@app.get("/1/")
async def api_1():
    return {"msg": "Hello World"}


@app.get("/2/")
@limiter(4, 10)
async def api_2():
    return {"msg": "Hello World"}


@app.get("/3/")
@limiter(4, 10, scopes=["user"])
@limiter(2, 10, scopes=["anno"])
async def api_3():
    return {"msg": "Hello World"}


@app.get("/4/")
@limiter(4, 10, method=["GET"], scopes=["user", "write"])
@limiter(2, 10, scopes=["anno"])
async def api_4():
    return {"msg": "Hello World"}


transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 8000))
