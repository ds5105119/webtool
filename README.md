# WebTool(Alpha)
<img src="https://github.com/ds5105119/webtool/workflows/CI/badge.svg">

Well-Architected FastAPI/Starlette library for JWT authentication, throttling, caching, logging, and utilities.

## Requirements

- Python 3.11+

## Installation

```shell
pip install webtool
```

```shell
poetry add webtool
```

## Features

### Authentication
JWT token management system with Redis-backed refresh tokens.

```python
from webtool.auth import JWTService
from webtool.cache import RedisCache

cache_client = RedisCache("redis://localhost:6379/0")
jwt_service = JWTService(cache_client)


async def get_token():
    access, refresh = jwt_service.create_token({"sub": 123, "scope": ["write"]})
    return access, refresh
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
@limiter(max_requests=50, interval=3600, scopes=["user"])
@limiter(max_requests=10, interval=3600, scopes=["anno"])
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
