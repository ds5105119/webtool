import time
from abc import ABC, abstractmethod
from typing import Optional
from uuid import uuid4

from jose.constants import ALGORITHMS

from webtool.auth.manager import BaseJWTManager, JWTManager, TokenData
from webtool.cache.client import BaseCache


class BaseJWTService(ABC):
    @abstractmethod
    def check_access_token_expired(self, access_token: str) -> TokenData | None:
        raise NotImplementedError

    @abstractmethod
    def create_access_token(self, data: dict) -> str:
        raise NotImplementedError

    @abstractmethod
    async def create_refresh_token(self, data: dict, access_token: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def update_token(self, data: dict, access_token: str, refresh_token: str) -> tuple[str, str]:
        raise NotImplementedError


class JWTService(BaseJWTService):
    """
    generate access token, refresh token
    """

    def __init__(
        self,
        cache: "BaseCache",
        jwt_manager: "BaseJWTManager" = JWTManager(),
        algorithm: str = ALGORITHMS.HS384,
        secret_key: str = None,
        access_token_expire_time: int = 3600,
        refresh_token_expire_time: int = 604800,
    ):
        self._cache = cache
        self._jwt_manager = jwt_manager
        self._secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_time = access_token_expire_time
        self.refresh_token_expire_time = refresh_token_expire_time

    @staticmethod
    def _create_jti() -> str:
        """
        Generates a unique identifier (JWT ID) for the token.

        :return: JWT ID (jti),
        """

        return uuid4().hex

    def _create_token_metadata(self, data: dict, ttl: float) -> TokenData:
        now = time.time()
        token_data = data.copy()

        token_data.setdefault("exp", now + ttl)
        token_data.setdefault("iat", now)
        token_data.setdefault("jti", self._create_jti())

        return token_data

    @staticmethod
    def _get_identifier(validated_data: TokenData) -> str:
        return validated_data.get("sub")

    @staticmethod
    def _get_metadata(validated_data: TokenData) -> str:
        jti = validated_data.get("jti")
        exp = validated_data.get("exp")

        if not jti:
            raise ValueError("Missing JWT ID")
        if not exp:
            raise ValueError("Missing expiration time")

        return f"{jti},{exp}"

    async def _get_db_data(self, validated_data: TokenData) -> str:
        key = self._get_identifier(validated_data)
        refresh_token = await self._cache.safe_get(key)

        return refresh_token.decode("utf-8")

    async def _save_db_data(self, refresh_data: TokenData) -> None:
        key = self._get_identifier(refresh_data)
        val = self._get_metadata(refresh_data)

        await self._cache.safe_set(key, val, ex=self.refresh_token_expire_time)

    def _create_token(self, data: dict, access_token: Optional[str] = None) -> str:
        return self._jwt_manager.encode(data, self._secret_key, self.algorithm, access_token)

    def _check_refresh_token_expired(self, refresh_token: str, access_token: str) -> TokenData | None:
        now = time.time()

        refresh_data = self._jwt_manager.decode(refresh_token, self._secret_key, self.algorithm, access_token)
        exp = float(refresh_data.get("exp"))

        if exp > now:
            return refresh_data

        return None

    def check_access_token_expired(self, access_token: str) -> TokenData | None:
        now = time.time()

        access_data = self._jwt_manager.decode(access_token, self._secret_key, self.algorithm)
        if access_data is None:
            return None

        exp = access_data.get("exp")
        if exp is None:
            return None

        if float(exp) > now:
            return access_data

        return None

    def create_access_token(self, data: dict) -> str:
        data = self._create_token_metadata(data, self.access_token_expire_time)
        token = self._create_token(data)

        return token

    async def create_refresh_token(self, data: dict, access_token: str) -> str:
        data = self._create_token_metadata(data, self.refresh_token_expire_time)
        token = self._create_token(data, access_token)
        await self._save_db_data(data)

        return token

    async def update_token(self, data: dict, access_token: str, refresh_token: str) -> tuple[str, str]:
        access_data = self._jwt_manager.decode(access_token, self._secret_key, self.algorithm)
        refresh_data = self._jwt_manager.decode(refresh_token, self._secret_key, self.algorithm, access_token)

        metadata_refresh = self._get_metadata(refresh_data)
        metadata_db = await self._get_db_data(access_data)

        if metadata_refresh != metadata_db:
            raise ValueError("refresh token is invalid")

        if self._check_refresh_token_expired(refresh_token, access_token) is None:
            raise ValueError("refresh token is expired")

        new_access_token = self.create_access_token(data)
        new_refresh_token = await self.create_refresh_token(data, new_access_token)

        return new_access_token, new_refresh_token
