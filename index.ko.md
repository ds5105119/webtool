# WebTool(Alpha)

WebTool은 FastAPI/Starlette에서 JWT인증 및 스로틀링, 캐싱, 로깅 등을 사용하기 위한 라이브러리입니다. 

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
Redis 또는 InMemory Cache 백엔드를 사용하여 RTR전략으로 access token과 refresh token을 관리할 수 있습니다.

```python
from webtool.auth import JWTService
from webtool.cache import RedisCache

cache_client = RedisCache("redis://localhost:6379/0")
jwt_service = JWTService(cache_client)


async def get_token():
    access, refresh = jwt_service.create_token({"sub": 123, "scopes": ["write"]})
    return access, refresh
```

### 스로틀링
FastAPI/Starlette 어플리케이션에서 스로틀링을 적용할 수 있습니다.

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
@limiter(max_requests=50, interval=3600, scopes=["user"])
@limiter(max_requests=10, interval=3600, scopes=["anno"])
async def get_resource():
    return {"status": "success"}
```

### MsgPack 응답
MessagePack-based 응답.

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

## 라이선스

This project is licensed under the Apache-2.0 License.
