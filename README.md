# WebTool

Well-Architected FastAPI/Starlette library for authentication, throttling, caching, logging, and utilities.

## Requirements

- Python 3.10+

## Installation

```shell
pip install webkit
```

```shell
poetry add webkit
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
    access_token = jwt_service.create_access_token({"sub": 123, "scope": ["write"]})
    refresh_token = await jwt_service.create_refresh_token({"sub": 123}, access_token)
    return access_token, refresh_token
```

### Throttling
Rate limiting system for FastAPI/Starlette applications.

```python
from webtool.throttle import limiter
from fastapi import FastAPI

app = FastAPI()


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