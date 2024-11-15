import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, NotRequired, Optional, TypedDict, override
from uuid import uuid4

import msgspec
from jose.constants import ALGORITHMS

from webtool.auth.manager import BaseJWTManager, JWTManager
from webtool.cache.client import BaseCache, RedisCache


class TokenData(TypedDict):
    sub: str
    exp: NotRequired[float]
    iat: NotRequired[float]
    jti: NotRequired[str]
    scope: NotRequired[list[str]]
    extra: NotRequired[dict[str, Any]]


class BaseJWTService(ABC):
    @abstractmethod
    async def create_token(self, data: dict) -> tuple[str, str]:
        raise NotImplementedError

    @abstractmethod
    async def validate_access_token(self, access_token: str, validate_exp=True) -> TokenData | None:
        raise NotImplementedError

    @abstractmethod
    async def validate_refresh_token(
        self, access_token: str, refresh_token: str, validate_exp=True
    ) -> TokenData | None:
        raise NotImplementedError

    @abstractmethod
    async def invalidate_token(self, access_token: str, refresh_token: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def update_token(self, data: dict, access_token: str, refresh_token: str) -> tuple[str, str] | None:
        raise NotImplementedError


class JWTService(BaseJWTService):
    """
    generate access token, refresh token
    """

    _CACHE_TOKEN_PREFIX = "jwt_"
    _CACHE_INVALIDATE_PREFIX = "jwt_invalidate_"

    def __init__(
        self,
        cache: "BaseCache",
        jwt_manager: BaseJWTManager | None = None,
        secret_key: str = "",
        algorithm: str = ALGORITHMS.HS384,
        access_token_expire_time: int = 3600,
        refresh_token_expire_time: int = 604800,
    ):
        self._cache = cache
        self._secret_key = secret_key
        self._jwt_manager = jwt_manager or JWTManager()
        self._json_encoder = msgspec.json.Encoder()
        self._json_decoder = msgspec.json.Decoder()
        self.algorithm = algorithm
        self.access_token_expire_time = access_token_expire_time
        self.refresh_token_expire_time = refresh_token_expire_time

    @staticmethod
    def _get_jti(validated_data: TokenData) -> str:
        return validated_data.get("jti")

    @staticmethod
    def _get_exp(validated_data: TokenData) -> float:
        return validated_data.get("exp")

    @staticmethod
    def _get_extra(validated_data: TokenData) -> dict[str, Any]:
        return validated_data.get("extra")

    @staticmethod
    def _validate_exp(token_data: TokenData) -> bool:
        exp = token_data.get("exp")
        now = time.time()

        return float(exp) > now

    @staticmethod
    def _get_key(validated_data: TokenData) -> str:
        return f"{JWTService._CACHE_TOKEN_PREFIX}{validated_data.get('jti')}"

    @staticmethod
    def _create_jti() -> str:
        """
        Generates a unique identifier (JWT ID) for the token.
        USE CRYPTOGRAPHICALLY SECURE PSEUDORANDOM STRING

        :return: JWT ID (jti),
        """

        jti = uuid4().hex
        return jti

    def _create_metadata(self, data: dict, ttl: float) -> TokenData:
        now = time.time()
        token_data = data.copy()

        token_data.setdefault("exp", now + ttl)
        token_data.setdefault("iat", now)
        token_data.setdefault("jti", self._create_jti())
        token_data.setdefault("extra", {})

        return token_data

    def _create_token(self, data: dict, access_token: Optional[str] = None) -> str:
        return self._jwt_manager.encode(data, self._secret_key, self.algorithm, access_token)

    def _decode_token(self, access_token: str, refresh_token: str | None = None):
        if refresh_token:
            return self._jwt_manager.decode(refresh_token, self._secret_key, self.algorithm, access_token)
        else:
            return self._jwt_manager.decode(access_token, self._secret_key, self.algorithm)

    async def _save_token_data(self, access_data: TokenData, refresh_data: TokenData) -> None:
        access_jti = self._get_jti(access_data)

        key = self._get_key(refresh_data)
        val = self._get_extra(refresh_data)
        val.setdefault("access_jti", access_jti)
        val = self._json_encoder.encode(val)

        async with self._cache.lock(key, 100):
            await self._cache.set(key, val, ex=self.refresh_token_expire_time)

    async def _read_token_data(self, refresh_data: TokenData) -> TokenData | None:
        key = self._get_key(refresh_data)

        async with self._cache.lock(key, 100):
            val = await self._cache.get(key)

        if val:
            val = self._json_decoder.decode(val)

        return val

    async def _invalidate_token_data(self, refresh_data: TokenData) -> None:
        refresh_exp = self._get_exp(refresh_data)
        refresh_db_data = await self._read_token_data(refresh_data)
        access_key = f"{JWTService._CACHE_INVALIDATE_PREFIX}{refresh_db_data.get("access_jti")}"
        access_exp = refresh_exp - self.refresh_token_expire_time + self.access_token_expire_time
        now = time.time()

        if access_exp > now:
            await self._cache.set(access_key, 1, exat=int(access_exp) + 1, nx=True)

        refresh_jti = self._get_key(refresh_data)
        await self._cache.delete(refresh_jti)

    async def create_token(self, data: dict) -> tuple[str, str]:
        access_data = self._create_metadata(data, self.access_token_expire_time)
        refresh_data = self._create_metadata(data, self.refresh_token_expire_time)

        access_token = self._create_token(access_data)
        refresh_token = self._create_token(refresh_data, access_token)
        await self._save_token_data(access_data, refresh_data)

        return access_token, refresh_token

    async def validate_access_token(self, access_token: str, validate_exp=True) -> TokenData | None:
        access_data = self._decode_token(access_token)

        if validate_exp and not self._validate_exp(access_data):
            return None

        access_jti = self._get_jti(access_data)
        key = f"{JWTService._CACHE_INVALIDATE_PREFIX}{access_jti}"

        if await self._cache.get(key):
            return None

        return access_data

    async def validate_refresh_token(
        self, access_token: str, refresh_token: str, validate_exp=True
    ) -> TokenData | None:
        refresh_data = self._decode_token(access_token, refresh_token)

        if validate_exp and not self._validate_exp(refresh_data):
            return None

        if not await self._read_token_data(refresh_data):
            return None

        return refresh_data

    async def invalidate_token(self, access_token: str, refresh_token: str) -> bool:
        refresh_data = await self.validate_refresh_token(access_token, refresh_token)

        if not refresh_data:
            return False

        await self._invalidate_token_data(refresh_data)
        return True

    async def update_token(self, data: dict, access_token: str, refresh_token: str) -> tuple[str, str] | None:
        refresh_data = await self.validate_refresh_token(access_token, refresh_token)

        if not refresh_data:
            return None

        await self._invalidate_token_data(refresh_data)

        refresh_jti = self._get_jti(refresh_data)
        async with self._cache.lock(refresh_jti, 100):
            new_access_token, new_refresh_token = await self.create_token(data)

        return new_access_token, new_refresh_token


class RedisJWTService(JWTService):
    _LUA_SAVE_TOKEN_SCRIPT = """
    -- PARAMETERS
    local refresh_token = KEYS[1]
    local now = ARGV[1]
    local access_jti = ARGV[2]
    local refresh_token_expire_time = ARGV[3]
        
    -- REFRESH TOKEN DATA EXTRACTION
    refresh_token = cjson.decode(refresh_token)
    local refresh_exp = refresh_token['exp']
    local refresh_sub = refresh_token['sub']
    local refresh_jti = refresh_token['jti']
    local refresh_val = refresh_token['extra']
        
    -- SAVE REFRESH TOKEN FOR VALIDATION
    local key = "jwt_" .. refresh_jti
    refresh_val['access_jti'] = access_jti
    refresh_val = cjson.encode(refresh_val)
    redis.call('SET', key, refresh_val, 'EXAT', math.floor(refresh_exp))
        
    -- SAVE REFRESH TOKEN FOR SEARCH
    key = "jwt_sub_" .. refresh_sub
    redis.call('ZADD', key, now, access_jti)
    redis.call("EXPIRE", key, refresh_token_expire_time)
    """

    _LUA_READ_TOKEN_SCRIPT = """
    -- PARAMETERS
    local sub = KEYS[1]
    local now = tonumber(ARGV[1])
    local jti = ARGV[2]

    redis.call('ZREMRANGEBYSCORE', sub, 0, now)
    local res = redis.call('ZSCORE', sub, jti)

    if res == nil then
        return "jti not found"
    else
        return cjson.encode(ruleset)
    end

    return cjson.encode(ruleset)
    """

    _LUA_INVALIDATE_TOKEN_SCRIPT = """
    -- PARAMETERS
    local refresh_token = KEYS[1]
    local now = tonumber(ARGV[1])
    local access_token_expire_time = tonumber(ARGV[2])
    local refresh_token_expire_time = tonumber(ARGV[3])
        
    -- REFRESH TOKEN DATA EXTRACTION
    refresh_token = cjson.decode(refresh_token)
    local refresh_jti = refresh_token['jti']
    local refresh_sub = refresh_token['sub']
    local refresh_exp = tonumber(refresh_token['exp'])
        
    -- VALIDATE REFRESH TOKEN
    local key = "jwt_" .. refresh_jti
    local refresh_val = redis.call('GET', key)
        
    if not refresh_val then
        return 0
    end
        
    -- READ REFRESH TOKEN DATA
    local decoded_val = cjson.decode(refresh_val)
    
    -- DELETE REFRESH TOKEN DATA FOR VALIDATION
    key = "jwt_" .. refresh_jti
    redis.call('DEL', key)
    
    -- DELETE REFRESH TOKEN DATA FOR SEARCH
    key = "jwt_sub_" .. refresh_sub
    local access_jti = decoded_val['access_jti']
    redis.call('ZREM', key, access_jti)
    
    -- MARK THE ACCESS TOKEN AS EXPIRED
    local access_exp = refresh_exp - refresh_token_expire_time + access_token_expire_time
    if access_exp > now then
        key = "jwt_invalidate_" .. access_jti
        redis.call('SET', key, 1, 'EX', math.ceil(access_exp))
    end
    
    return 1
    """

    _LUA_SEARCH_TOKEN_SCRIPT = """
    -- PARAMETERS
    local refresh_token = KEYS[1]
    local now = tonumber(ARGV[1])
    local refresh_token_expire_time = tonumber(ARGV[2])
    
    -- REFRESH TOKEN DATA EXTRACTION
    refresh_token = cjson.decode(refresh_token)
    local refresh_sub = refresh_token["sub"]

    -- DELETE EXPIRED REFRESH TOKEN DATA FOR SEARCH
    local key = "jwt_sub_" .. refresh_sub
    redis.call('ZREMRANGEBYSCORE', key, 0, now - refresh_token_expire_time)
    
    -- RETURN REFRESH TOKENS OF SUB
    return redis.call('ZRANGE', key, 0, -1)
    """

    def __init__(
        self,
        cache: "RedisCache",
        jwt_manager: BaseJWTManager | None = None,
        secret_key: str = "123",
        algorithm: str = ALGORITHMS.HS384,
        access_token_expire_time: int = 3600,
        refresh_token_expire_time: int = 604800,
    ):
        super().__init__(cache, jwt_manager, secret_key, algorithm, access_token_expire_time, refresh_token_expire_time)
        self._save_script = self._cache.cache.register_script(RedisJWTService._LUA_SAVE_TOKEN_SCRIPT)
        self._invalidate_script = self._cache.cache.register_script(RedisJWTService._LUA_INVALIDATE_TOKEN_SCRIPT)
        self._search_script = self._cache.cache.register_script(RedisJWTService._LUA_SEARCH_TOKEN_SCRIPT)

    @override
    async def _save_token_data(self, access_data: TokenData, refresh_data: TokenData) -> None:
        access_jti = self._get_jti(access_data)
        refresh_jti = self._get_jti(refresh_data)
        refresh_json = self._json_encoder.encode(refresh_data)

        async with self._cache.lock(refresh_jti, 100):
            await self._save_script(
                keys=[refresh_json],
                args=[
                    time.time(),
                    access_jti,
                    self.refresh_token_expire_time,
                ],
            )

    @override
    async def _invalidate_token_data(self, refresh_data: TokenData) -> bool:
        refresh_json = self._json_encoder.encode(refresh_data)

        return await self._invalidate_script(
            keys=[refresh_json],
            args=[
                time.time(),
                self.access_token_expire_time,
                self.refresh_token_expire_time,
            ],
        )

    async def search_token(self, access_token: str, refresh_token: str):
        refresh_data = self._decode_token(access_token, refresh_token)
        refresh_json = self._json_encoder.encode(refresh_data)

        return await self._search_script(
            keys=[refresh_json],
            args=[
                time.time(),
                self.refresh_token_expire_time,
            ],
        )


async def main():
    from webtool.cache.client import RedisCache

    redis_jwt = RedisJWTService(RedisCache("redis://localhost:6379/0"))

    user = {"sub": "100"}

    access, refresh = await redis_jwt.create_token(user)
    print(access, refresh)

    a_data = await redis_jwt.validate_access_token(access)
    print(a_data)

    r_data = await redis_jwt.validate_refresh_token(access, refresh)
    print(r_data)

    new_access, new_refresh = await redis_jwt.update_token(user, access, refresh)

    print(await redis_jwt.update_token(user, access, refresh))

    a_data = await redis_jwt.validate_access_token(access)
    print("만료된거", a_data)

    r_data = await redis_jwt.validate_refresh_token(access, refresh)
    print("만료된 리프레시", r_data)

    a_data = await redis_jwt.validate_access_token(new_access)
    print(a_data)

    r_data = await redis_jwt.validate_refresh_token(new_access, new_refresh)
    print(r_data)

    print(await redis_jwt.search_token(new_access, new_refresh))

    print(await redis_jwt.update_token(user, access, refresh))
    print(await redis_jwt.update_token(user, access, refresh))
    print(await redis_jwt.update_token(user, access, refresh))


if __name__ == "__main__":
    asyncio.run(main())
