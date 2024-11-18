# Auth - manager

This module provides functionality for handling **JSON Web Tokens (JWT)** for authentication and authorization. It defines the structure and methods required to encode and decode JWTs, as well as manage the claims associated with the tokens.

## TokenData Class

The `TokenData` class represents the claims embedded in a JWT. It is a typed dictionary (`TypedDict`) that ensures type safety when working with JWTs.

```python
class TokenData(TypedDict):
    sub: str
    exp: float
    iat: float
    jti: str
    scope: NotRequired[list[str]]
```

Field Descriptions:

- `sub`: Unique identifier for the subject.
- `exp`: Expiration time (defaults if not provided).
- `iat`: Issued at time (defaults if not provided).
- `jti`: JWT ID (defaults if not provided).
- `scope`: Optional list of scopes for fine-grained access control.

## BaseJWTManager Class

Abstract base class for managing JWTs, defining the interface for encoding and decoding JWTs.

Methods:

- `encode(claims, secret_key, algorithm, access_token) -> str`
Encodes claims into a JWT.

- `decode(token, secret_key, algorithm, access_token) -> str`
Decodes and validates a JWT.

## JWTManager Class

JWTManager is an implementation of 'BaseJWTManager' using python-jose. responsible for encoding and decoding JSON Web Tokens (JWT). The JWTManager class follows the Apache Software Foundation (ASF) coding style guidelines, providing clear and concise documentation for its methods and parameters.

- `encode(claims, secret_key, algorithm, access_token) -> str`
This method takes the JWT claims, secret key, signing algorithm, and an optional access token parameter, and returns the encoded JWT string.

- `decode(token, secret_key, algorithm, access_token) -> str`:
This method takes the JWT token string, secret key, signing algorithm, and an optional access token parameter, and returns the decoded claims if the token is valid, or None if the token is invalid or expired.

### Usage

In most cases, JWTManager is not used directly

```python
from webtool.auth import JWTManager

manager = JWTManager()

access_token = manager.encode({
    "sub": "1", 
    "exp": 1, 
    "iat": 123, 
    "jti": "abc",
    "scope": ["user"]
}, secret_key="your_secret_key", algorithm='HS256')
```