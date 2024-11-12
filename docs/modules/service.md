# Auth - service

## JWTService

The `JWTService` class is responsible for generating and managing access tokens and refresh tokens using JSON Web Tokens (JWT). It provides an abstraction layer over the `BaseJWTManager` implementation, which is responsible for encoding and decoding the JWT tokens.

### Parameters

The `JWTService` class can be instantiated with the following parameters:

- `cache`: An instance of `BaseCache` that will be used to store the refresh tokens.
- `jwt_manager`: An instance of `BaseJWTManager` (or its subclass `JWTManager`) that will be used for token encoding and decoding.
- `secret_key`: The secret key used to sign the JWT tokens.
- `algorithm`: The signing algorithm to use for the JWT tokens, defaults to 'HS384'.
- `access_token_expire_time`: The expiration time for access tokens in seconds, defaults to 3600 (1 hour).
- `refresh_token_expire_time`: The expiration time for refresh tokens in seconds, defaults to 604800 (1 week).


### Features

- **Access Token Generation**: The `JWTService` can create access tokens with a configurable expiration time.
- **Refresh Token Generation**: The service can create refresh tokens with a configurable expiration time and store them in a cache.
- **Token Validation**: The service can validate the access tokens and refresh tokens, checking for expiration and other token metadata.
- **Token Refresh**: The service can update the access token and refresh token when the refresh token is still valid.

### Usage

```python
from webtool.auth import JWTService
from webtool.cache import RedisCache

cache = RedisCache("redis://localhost:6379/0")
jwt_service = JWTService(cache, secret_key="your_secret_key")


async def get_token(data):
    access_token = jwt_service.create_access_token(data)
    refresh_token = await jwt_service.create_refresh_token(data, access_token)
    return access_token, refresh_token

access, refresh = get_token({"sub": "user123", "scope": ["write"]})
```
