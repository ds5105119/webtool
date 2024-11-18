# WebTool(Alpha)

Webtool은 FastAPI/Starlette를 위한 JWT인증 및 스로틀링, 캐싱, 로깅 등을 위한 라이브러리입니다.

## 요구 사항

- Python 3.11+

## 설치

```shell
pip install webtool
```

```shell
poetry add webtool
```

## 기능

### JWT 인증
Redis 또는 InMemory Cache 백엔드를 사용한 RTR구조의 
JWT token management system with Redis-backed refresh tokens.

```python
from webtool.auth import JWTService
from webtool.cache import RedisCache

cache_client = RedisCache("redis://localhost:6379/0")
jwt_service = JWTService(cache_client)


async def get_token():
    access_token = jwt_service.create_access_token({"sub": 123, "scope": ["write"]})
    refresh_token = await jwt_service.create_refresh_token({"sub": 123}, access_token)
    return access_token, refresh_token
```

### Throttling
Rate limiting system for FastAPI/Starlette applications.

```python
from fastapi import FastAPI
from starlette.middleware import Middleware
from webtool.auth import JWTService
from webtool.cache import RedisCache
from webtool.throttle import limiter, LimitMiddleware, JWTBackend

cache = RedisCache("redis://127.0.0.1:6379/0")
jwt_backend = JWTBackend(JWTService(cache, secret_key="test"))

app = FastAPI(
    middleware=[
        Middleware(
            LimitMiddleware,
            cache=cache,
            auth_backend=jwt_backend,
        ),
    ],
)


@app.get("/api/resource")
@limiter(max_requests=50, interval=3600, scope=["user"])
@limiter(max_requests=10, interval=3600, scope=["anno"])
async def get_resource():
    return {"status": "success"}
```

### MsgPack Response
MessagePack-based response.

```python
from webtool.utils import MsgSpecJSONResponse
from fastapi import FastAPI

app = FastAPI(
    default_response_class=MsgSpecJSONResponse,
)


@app.get("/api/resource")
async def get_resource():
    return {"status": "success"}
```

## License

This project is licensed under the Apache-2.0 License.
