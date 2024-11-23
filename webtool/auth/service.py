import time
from abc import ABC, abstractmethod
from typing import Generic, Optional

from webtool.auth.manager import BaseJWTManager, JWTManager
from webtool.auth.models import PayloadFactory, PayloadType
from webtool.cache.client import BaseCache, RedisCache
from webtool.utils.json import ORJSONDecoder, ORJSONEncoder
from webtool.utils.key import load_key


class BaseJWTService(Generic[PayloadType], ABC):
    @abstractmethod
    async def create_token(self, data: dict) -> tuple[str, str]:
        """
        Create Access and Refresh Tokens.

        Parameters:
            data: must include 'sub' field.

        Returns:
            tuple: Access, Refresh Token.
        """
        raise NotImplementedError

    @abstractmethod
    async def validate_access_token(self, access_token: str, validate_exp: bool = True) -> Optional[PayloadType]:
        """
        Validate Access Token.

        Parameters:
            access_token: Access Token.
            validate_exp: Whether to validate expiration or not.

        Returns:
            PayloadType: Access Token Data
        """
        raise NotImplementedError

    @abstractmethod
    async def validate_refresh_token(self, refresh_token: str, validate_exp: bool = True) -> Optional[PayloadType]:
        """
        Validate Refresh Token.

        Parameters:
            refresh_token: Access Token.
            validate_exp: Whether to validate expiration or not.

        Returns:
            PayloadType: Refresh Token Data
        """
        raise NotImplementedError

    @abstractmethod
    async def invalidate_token(self, refresh_token: str) -> bool:
        """
        Invalidates the Refresh token and the Access token issued with it .

        Parameters:
            refresh_token: Access Token.

        Returns:
            bool: Returns `true` on success.
        """
        raise NotImplementedError

    @abstractmethod
    async def update_token(self, data: dict, refresh_token: str) -> tuple[str, str] | None:
        """
        Invalidates the Refresh token and the Access token issued with it and issue New Access and Refresh Tokens.

        Parameters:
            data: Token data.
            refresh_token: Access Token.

        Returns:
            tuple: Access, Refresh Token.
        """
        raise NotImplementedError


class JWTService(BaseJWTService[PayloadType], PayloadFactory, Generic[PayloadType]):
    """
    generate access token, refresh token

    Info:
        Most cases, the `algorithm` parameter is automatically determined based on the `secret_key`,
        so there is no need to specify the `algorithm`.
        If using an asymmetric encryption key, providing the `secret_key` will automatically use the correct public key.
        The `secret_key` can be generated using the `webtools.utils` package.
    """

    _CACHE_TOKEN_PREFIX = "jwt_"
    _CACHE_INVALIDATE_PREFIX = "jwt_invalidate_"

    def __init__(
        self,
        cache: "BaseCache",
        secret_key: str | bytes = "",
        access_token_expire_time: int = 3600,
        refresh_token_expire_time: int = 604800,
        jwt_manager: BaseJWTManager | None = None,
        algorithm: str | None = None,
    ):
        self._cache = cache
        self._secret_key = secret_key
        self._jwt_manager = jwt_manager or JWTManager()
        self._json_encoder = ORJSONEncoder()
        self._json_decoder = ORJSONDecoder()
        self.algorithm = algorithm
        self.access_token_expire_time = access_token_expire_time
        self.refresh_token_expire_time = refresh_token_expire_time

        self._private_key = None
        self._public_key = None

        key_object = load_key(secret_key)

        if len(key_object) == 3:
            self._private_key, self._public_key, key_algorithm = key_object
        else:
            key_algorithm = key_object[-1]

        self._verify_key_algorithm(key_algorithm)

    def __call__(self):
        """
        Make the instance callable and return itself.
        """
        return self

    def _verify_key_algorithm(self, key_algorithm: str) -> None:
        """
        Verify that the loaded key's algorithm matches the expected algorithm.
        Raises ValueError if there is a mismatch.
        """
        if self.algorithm:
            if key_algorithm != self.algorithm:
                raise ValueError(f"Expected algorithm {key_algorithm}, but got {self.algorithm}")
        else:
            self.algorithm = key_algorithm

    def _create_token(self, data: dict) -> str:
        if self._private_key:
            return self._jwt_manager.encode(data, self._private_key, self.algorithm)
        return self._jwt_manager.encode(data, self._secret_key, self.algorithm)

    def _decode_token(self, token: str, at_hash: str | None = None) -> Optional[PayloadType]:
        if self._public_key:
            return self._jwt_manager.decode(token, self._public_key, self.algorithm, at_hash)
        return self._jwt_manager.decode(token, self._secret_key, self.algorithm, at_hash)

    async def _save_refresh_data(self, access_data: PayloadType, refresh_data: PayloadType) -> None:
        access_jti = self._get_jti(access_data)

        key = self._get_key(JWTService._CACHE_TOKEN_PREFIX, refresh_data)
        val = self._get_extra(refresh_data)
        val["access_jti"] = access_jti
        val = self._json_encoder.encode(val)

        async with self._cache.lock(key, 100):
            await self._cache.set(key, val, ex=self.refresh_token_expire_time)

    async def _read_refresh_data(self, refresh_data: PayloadType) -> dict | None:
        key = self._get_key(JWTService._CACHE_TOKEN_PREFIX, refresh_data)

        async with self._cache.lock(key, 100):
            val = await self._cache.get(key)

        if val:
            val = self._json_decoder.decode(val)

        return val

    async def _invalidate_token_data(self, validated_refresh_data: PayloadType) -> None:
        key = self._get_key(JWTService._CACHE_TOKEN_PREFIX, validated_refresh_data)
        refresh_exp = self._get_exp(validated_refresh_data)
        refresh_extra = self._get_extra(validated_refresh_data)
        access_key = f"{JWTService._CACHE_INVALIDATE_PREFIX}{refresh_extra.get('access_jti')}"
        access_exp = refresh_exp - self.refresh_token_expire_time + self.access_token_expire_time

        now = time.time()
        if access_exp > now:
            await self._cache.set(access_key, 1, exat=int(access_exp) + 1, nx=True)

        await self._cache.delete(key)

    async def create_token(self, data: dict) -> tuple[str, str]:
        """
        Create Access and Refresh Tokens.

        Parameters:
            data: must include 'sub' field.

        Returns:
            tuple: Access, Refresh Token.
        """
        self._validate_sub(data)

        access_data = self._create_metadata(data, self.access_token_expire_time)
        refresh_data = self._create_metadata(data, self.refresh_token_expire_time)

        access_token = self._create_token(access_data)
        refresh_token = self._create_token(refresh_data)
        await self._save_refresh_data(access_data, refresh_data)

        return access_token, refresh_token

    async def validate_access_token(self, access_token: str, validate_exp: bool = True) -> Optional[PayloadType]:
        """
        Validate Access Token.

        Parameters:
            access_token: Access Token.
            validate_exp: Whether to validate expiration or not.

        Returns:
            Optional[PayloadType]: Access Token Data
        """
        access_data = self._decode_token(access_token)

        if not access_data:
            return None

        if validate_exp and not self._validate_exp(access_data):
            return None

        access_jti = self._get_jti(access_data)
        key = f"{JWTService._CACHE_INVALIDATE_PREFIX}{access_jti}"

        if await self._cache.get(key):
            return None

        return access_data

    async def validate_refresh_token(self, refresh_token: str, validate_exp: bool = True) -> Optional[PayloadType]:
        """
        Validate Refresh Token.

        Parameters:
            refresh_token: Access Token.
            validate_exp: Whether to validate expiration or not.

        Returns:
            Optional[PayloadType]: Refresh Token Data
        """
        refresh_data = self._decode_token(refresh_token)

        if not refresh_data:
            return None

        if validate_exp and not self._validate_exp(refresh_data):
            return None

        cached_refresh_data = await self._read_refresh_data(refresh_data)
        if not cached_refresh_data:
            return None

        refresh_data["extra"] |= cached_refresh_data
        return refresh_data

    async def invalidate_token(self, refresh_token: str) -> bool:
        """
        Invalidates the Refresh token and the Access token issued with it .

        Parameters:
            refresh_token: Access Token.

        Returns:
            bool: Returns `true` on success.
        """
        refresh_data = await self.validate_refresh_token(refresh_token)

        if not refresh_data:
            return False

        await self._invalidate_token_data(refresh_data)
        return True

    async def update_token(self, data: dict, refresh_token: str) -> tuple[str, str] | None:
        """
        Invalidates the Refresh token and the Access token issued with it and issue New Access and Refresh Tokens.

        Parameters:
            data: Token data.
            refresh_token: Access Token.

        Returns:
            tuple: Access, Refresh Token.
        """
        refresh_data = await self.invalidate_token(refresh_token)

        if not refresh_data:
            return None

        new_access_token, new_refresh_token = await self.create_token(data)

        return new_access_token, new_refresh_token


class RedisJWTService(JWTService, Generic[PayloadType]):
    """
    generate access token, refresh token

    Info:
        Most cases, the `algorithm` parameter is automatically determined based on the `secret_key`,
        so there is no need to specify the `algorithm`.
        If using an asymmetric encryption key, providing the `secret_key` will automatically use the correct public key.
        The `secret_key` can be generated using the `webtools.utils` package.
    """

    _LUA_SAVE_TOKEN_SCRIPT = """
    -- PARAMETERS
    local refresh_token = KEYS[1]
    local now = tonumber(ARGV[1])
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
    redis.call('ZADD', key, now, refresh_jti)
    redis.call('EXPIRE', key, refresh_token_expire_time)
    """

    _LUA_INVALIDATE_TOKEN_SCRIPT = """
    -- PARAMETERS
    local refresh_token = KEYS[1]
    local now = tonumber(ARGV[1])
    local access_token_expire_time = tonumber(ARGV[2])
    local refresh_token_expire_time = tonumber(ARGV[3])
    local refresh_jti_to_invalidate = ARGV[4]
    local access_jti
    local key
    local refresh_to_invalidate_issue_time
    
    -- REFRESH TOKEN DATA EXTRACTION
    refresh_token = cjson.decode(refresh_token)
    local refresh_sub = refresh_token['sub']
    local refresh_jti = refresh_token['jti']
    
    if #refresh_jti_to_invalidate ~= 0 then
    
        -- CHECK REFRESH TOKEN DATA FOR SEARCH
        key = "jwt_sub_" .. refresh_sub
        refresh_to_invalidate_issue_time = redis.call('ZSCORE', key, refresh_jti_to_invalidate)
        if not refresh_to_invalidate_issue_time then
            return 0
        end
        
        -- CHECK REFRESH TOKEN DATA FOR VALIDATION
        key = "jwt_" .. refresh_jti
        local refresh_data_to_invalidate = redis.call('GET', key)
        if not refresh_data_to_invalidate then
            redis.call('ZREM', refresh_sub, refresh_jti_to_invalidate)
            return 0
        end
        
        -- REFRESH TOKEN DATA EXTRACTION
        refresh_data_to_invalidate = cjson.decode(refresh_data_to_invalidate)
        access_jti = refresh_data_to_invalidate['access_jti']
        refresh_jti = refresh_jti_to_invalidate
    else
    
        -- INVALIDATE ORIGINAL ACCESS, REFRESH TOKEN
        access_jti = refresh_token['extra']['access_jti']
        refresh_to_invalidate_issue_time = refresh_token['exp'] - refresh_token_expire_time
    end

    -- MARK THE ACCESS TOKEN AS EXPIRED
    local access_exp = refresh_to_invalidate_issue_time + access_token_expire_time
    if access_exp > now then
        key = "jwt_invalidate_" .. access_jti
        redis.call('SET', key, 1, 'EXAT', math.ceil(access_exp))
    end
    
    -- DELETE REFRESH TOKEN DATA FOR VALIDATION
    local key = "jwt_" .. refresh_jti
    redis.call('DEL', key)
    
    -- DELETE REFRESH TOKEN DATA FOR SEARCH
    key = "jwt_sub_" .. refresh_sub
    redis.call('ZREM', key, refresh_jti)
    
    return 1
    """

    _LUA_SEARCH_TOKEN_SCRIPT = """
    -- PARAMETERS
    local refresh_token = KEYS[1]
    local now = tonumber(ARGV[1])
    local refresh_token_expire_time = tonumber(ARGV[2])
    local key
    
    -- REFRESH TOKEN DATA EXTRACTION
    refresh_token = cjson.decode(refresh_token)
    local refresh_sub = refresh_token['sub']

    -- DELETE EXPIRED REFRESH TOKEN DATA FOR SEARCH
    key = "jwt_sub_" .. refresh_sub
    redis.call('ZREMRANGEBYSCORE', key, 0, now - refresh_token_expire_time)
    
    -- RETURN REFRESH TOKENS OF SUB
    return redis.call('ZRANGE', key, 0, -1)
    """

    def __init__(
        self,
        cache: "RedisCache",
        secret_key: str | bytes = "",
        access_token_expire_time: int = 3600,
        refresh_token_expire_time: int = 604800,
        jwt_manager: BaseJWTManager | None = None,
        algorithm: str | None = None,
    ):
        super().__init__(cache, secret_key, access_token_expire_time, refresh_token_expire_time, jwt_manager, algorithm)
        self._save_script = self._cache.cache.register_script(RedisJWTService._LUA_SAVE_TOKEN_SCRIPT)
        self._invalidate_script = self._cache.cache.register_script(RedisJWTService._LUA_INVALIDATE_TOKEN_SCRIPT)
        self._search_script = self._cache.cache.register_script(RedisJWTService._LUA_SEARCH_TOKEN_SCRIPT)

    async def _save_refresh_data(self, access_data: PayloadType, refresh_data: PayloadType) -> None:
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

    async def _invalidate_token_data(
        self,
        validated_refresh_data: PayloadType,
        refresh_jti_to_invalidate: str | None = None,
    ) -> bool:
        refresh_json = self._json_encoder.encode(validated_refresh_data)

        return await self._invalidate_script(
            keys=[refresh_json],
            args=[
                time.time(),
                self.access_token_expire_time,
                self.refresh_token_expire_time,
                refresh_jti_to_invalidate or b"",
            ],
        )

    async def invalidate_token(
        self,
        refresh_token: str,
        refresh_jti_to_invalidate: str | bytes | None = None,
    ) -> bool:
        """
        Invalidates the Refresh token and the Access token issued with it .

        Parameters:
            refresh_token: Access Token.
            refresh_jti_to_invalidate: Refresh Token JTI to invalidate can be found using search_token.

        Returns:
            bool: Returns `true` on success.
        """
        refresh_data = await self.validate_refresh_token(refresh_token)

        if not refresh_data:
            return False

        return await self._invalidate_token_data(refresh_data, refresh_jti_to_invalidate)

    async def search_token(self, refresh_token: str) -> list[bytes]:
        """
        Returns the JTI of the refresh token issued with the token’s sub claim

        Parameters:
            refresh_token: Access Token.

        Returns:
            list[bytes]: Returns a list containing JTIs on success.
        """
        refresh_data = self._decode_token(refresh_token)
        refresh_json = self._json_encoder.encode(refresh_data)

        return await self._search_script(
            keys=[refresh_json],
            args=[
                time.time(),
                self.refresh_token_expire_time,
            ],
        )


class KeyclockService:
    pass
