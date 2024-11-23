# Getting Started

Webtool is designed to provide authentication, authorization, throttling, DB management, and cache management.

## Caching

Authentication, authorization, and throttling are dependent on caching. Create a cache as follows:

### RedisCache

```python
from webtool.cache import RedisCache

redis = RedisCache("redis://127.0.0.1:6379/0")
```

### InMemoryCache

```python
from webtool.cache import InMemoryCache

cache = InMemoryCache()
```

!!! Warning
    Do not use `InMemoryCache` in production environments.

## JWT

### Creating a JWTService

You can create a JWT service using the cache:

```python
from webtool.cache import RedisCache
from webtool.auth import JWTService

redis = RedisCache("redis://127.0.0.1:6379/0")
jwt_service = JWTService(redis, secret_key="1234")
```

The JWT authentication algorithm is automatically determined based on the `secret_key`.

You can also easily generate a `secret_key` using the `webtool.utils` module:

```python
from webtool.utils import make_ed_key
from webtool.cache import RedisCache
from webtool.auth import JWTService

redis = RedisCache("redis://127.0.0.1:6379/0")
jwt_service = JWTService(redis, secret_key=make_ed_key(save=True))
```

### Using JWTService

The completed JWT service can be used for token generation, validation, invalidation, and updating. 
Using RedisJWTService creates a Redis-optimized JWTService object that utilizes Redis Lua scripting.

```python
import asyncio

from webtool.utils import make_ed_key
from webtool.cache import RedisCache
from webtool.auth import RedisJWTService

redis = RedisCache("redis://127.0.0.1:6379/0")
jwt_service = RedisJWTService(redis, secret_key=make_ed_key(save=True))

async def main():
    user_claim = {"sub": "123"}
    
    access, refresh = await jwt_service.create_token(user_claim)
    new_access, new_refresh = await jwt_service.update_token(user_claim, refresh)

    print(await jwt_service.validate_access_token(access))  # None
    print(await jwt_service.validate_access_token(new_access))  # {'sub': '123', ...}

if __name__ == "__main__":
    asyncio.run(main())
```

!!! Note
    Tokens are of `TypedDict` type and must include a `sub` claim of type `str`.

## Throttling

To use middleware-level throttle in Starlette/FastAPI, use the `webtool.throttle` module:

```python
from fastapi import FastAPI
from starlette.middleware import Middleware

from webtool.utils import make_ed_key
from webtool.cache import RedisCache
from webtool.auth import RedisJWTService, JWTBackend
from webtool.throttle import LimitMiddleware, limiter


redis = RedisCache("redis://127.0.0.1:6379/0")
jwt_service = RedisJWTService(redis, secret_key=make_ed_key(save=True))
jwt_backend = JWTBackend(jwt_service)

app = FastAPI(
    middleware=[
        Middleware(
            LimitMiddleware,
            cache=redis,
            auth_backend=jwt_backend,
        )
    ]
)

@app.get('api/1/')
@limiter(max_requests=10, interval=10)
async def get_resource():
    return {"status": "success"}

@app.get('api/2/')
@limiter(max_requests=10, interval=10, scopes=["anno"])
async def get_resource():
    return {"status": "success"}

@app.get('api/3/')
@limiter(max_requests=10, interval=10, scopes=["user"])
async def get_resource():
    return {"status": "success"}
```

!!! Info
    `LimitMiddleware` uses `cache` for limiting. Currently, only `RedisCache` is available.

!!! Info
    `LimitMiddleware` uses `auth_backend` (for authenticated users) and `anno_backend` (for unauthenticated users).
    Currently, only `webtool.auth.backend.AnnoSessionBackend` is available for use as `anno_backend`.

### FastAPI Integration

Thanks to FastAPI, integration is very straightforward. 
Inherit from OAuth2PasswordBearer or OAuth2AuthorizationCodeBearer and modify the `__call__` method as follows:

```python
from typing import Optional

from fastapi import Depends, FastAPI, Request, status
from fastapi.security import OAuth2AuthorizationCodeBearer, OAuth2PasswordBearer
from starlette.middleware import Middleware

from webtool.auth import JWTBackend, RedisJWTService
from webtool.cache import RedisCache
from webtool.throttle import LimitMiddleware
from webtool.utils import make_ed_key


class ExtendOAuth2PasswordBearer(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        auth = request.scope.get("auth")
        return auth


class ExtendOAuth2AuthorizationCodeBearer(OAuth2AuthorizationCodeBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        auth = request.scope.get("auth")
        return auth


redis = RedisCache("redis://127.0.0.1:6379/0")
jwt_service = RedisJWTService(redis, secret_key=make_ed_key(save=True))
jwt_backend = JWTBackend(jwt_service)

app = FastAPI(
    middleware=[
        Middleware(
            LimitMiddleware,
            cache=redis,
            auth_backend=jwt_backend,
        )
    ]
)

oauth_password_schema = ExtendOAuth2PasswordBearer(tokenUrl="token")


@app.get("/token/", status_code=status.HTTP_200_OK)
async def get_token():
    tokens = await jwt_service.create_token({"sub": "123"})
    return tokens


@app.get("/get_user/", status_code=status.HTTP_200_OK)
async def auth_info(auth=Depends(oauth_password_schema)):
    return auth


if __name__ == "__main__":
    import os
    import uvicorn

    current_file = os.path.basename(__file__).replace(".py", "")
    uvicorn.run(f"{current_file}:app", host="127.0.0.1", port=8000)
```

Now, if you send a GET request to http://127.0.0.1:8000/token/, you will receive a response like this:

```json
[
    "eyJhbGciOiJIUEHi78mA3KUSB2...",
    "eyJhbGciOiJFZERTQSIsInR5cC..."
]
```

If you send a GET request to http://127.0.0.1:8000/get_user/ using the first string (Access Token) in the response with Authorization header, 
you will receive the following response:

```json
{
    "identifier": "123",
    "scope": null,
    "extra": {
        "exp": 1732390689.2838972,
        "iat": 1732387089.2838972,
        "jti": "1ab6ee829b984cb28ec9ffd535cdadx2",
        "extra": {}
    }
}
```