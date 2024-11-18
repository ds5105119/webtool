# Auth - Service

## JWTService

The JWTService class provides an abstraction for managing JSON Web Tokens (JWT), including creation, validation, and invalidation of both access and refresh tokens. Designed for flexibility, it supports multiple caching backends via the BaseCache interface and enables extensibility for custom JWT handling with BaseJWTManager.

### Parameters

The class accepts the following configuration during initialization:
- `cache`: An instance of BaseCache, used for managing token-related data storage. 
- `jwt_manager` (optional): An instance of BaseJWTManager (or its subclass). Defaults to JWTManager. 
- `secret_key`: A secret key for signing JWT tokens. 
- `algorithm`: The signing algorithm. Defaults to HS384. 
- `access_token_expire_time`: Expiration time for access tokens in seconds. Default: 3600 seconds (1 hour). 
- `refresh_token_expire_time`: Expiration time for refresh tokens in seconds. Default: 604800 seconds (1 week).

### Features

- Access Token Management: Create and validate short-lived access tokens. 
- Refresh Token Management: Generate refresh tokens, store metadata in a cache, and validate them. 
- Token Invalidation: Support for securely invalidating tokens to prevent further use. 
- Token Updates: Enable **Refresh Token Rotation**(RTR).
- Customizability: Use the BaseJWTService interface to create tailored implementations for unique requirements.

### Usage Example

```python
from webtool.auth import JWTService
from webtool.cache import RedisCache

cache = RedisCache("redis://localhost:6379/0")
jwt_service = JWTService(cache, secret_key="your_secret_key")

async def create_tokens():
    user_data = {"sub": "user123"}
    access, refresh = await jwt_service.create_token(user_data)
    return access, refresh
```

## RedisJWTService

RedisJWTService extends JWTService with Redis-specific optimizations, leveraging Lua scripting for atomic operations. It is ideal for high-performance environments requiring efficient token storage and management.

### Additional Features

- Optimized Token Storage: Uses Redis’s native commands and Lua scripts for efficient token management. 
- Atomic Invalidation: Ensures secure and consistent token invalidation using Lua scripts. 
- Search Capability: Provides functionality to retrieve all active refresh tokens for a user (sub), supporting session-based authentication management.

### Lua Scripts

- Save Token Script: Atomically stores refresh tokens and associates them with access tokens. 
- Invalidate Token Script: Invalidates access and refresh tokens while cleaning up associated metadata. 
- Search Token Script: Fetches refresh tokens for a specific user and removes expired tokens.

### Usage Example

```python
import asyncio
from webtool.auth import RedisJWTService
from webtool.cache import RedisCache

cache = RedisCache("redis://localhost:6379/0")
redis_jwt_service = RedisJWTService(cache, secret_key="your_secret_key")

async def manage_tokens():
    user_data = {"sub": "user123"}
    access, refresh = await redis_jwt_service.create_token(user_data)
    print("Access Token:", access)
    print("Refresh Token:", refresh)
    
    # Validate tokens
    access_data = await redis_jwt_service.validate_access_token(access)
    print("Access Token Data:", access_data)
    
    refresh_data = await redis_jwt_service.validate_refresh_token(access, refresh)
    print("Refresh Token Data:", refresh_data)
    
    # Rotate tokens
    new_access, new_refresh = await redis_jwt_service.update_token(user_data, access, refresh)
    print("New Access Token:", new_access)
    print("New Refresh Token:", new_refresh)
    
    # Search active tokens
    active_tokens = await redis_jwt_service.search_token(new_access, new_refresh)
    print("Active Refresh Tokens:", active_tokens)

# Example usage
asyncio.run(manage_tokens())
```

