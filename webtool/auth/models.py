import time
from typing import Any, Generic, NotRequired, Required, TypedDict, TypeVar
from uuid import uuid4


class Payload(TypedDict):
    sub: Required[str]
    exp: NotRequired[float]
    iat: NotRequired[float]
    jti: NotRequired[str]
    scope: NotRequired[list[str]]
    extra: NotRequired[dict[str, Any]]


class AuthData:
    __slots__ = ["identifier", "scope", "extra"]

    def __init__(self, identifier: str | None, scope: list[str] | None = None, extra: dict | None = None):
        self.identifier = identifier
        self.scope = scope
        self.extra = extra


PayloadType = TypeVar("PayloadType", bound=Payload)


class PayloadFactory(Generic[PayloadType]):
    @staticmethod
    def _get_jti(validated_data: PayloadType) -> str:
        return validated_data.get("jti")

    @staticmethod
    def _get_exp(validated_data: PayloadType) -> float:
        return validated_data.get("exp")

    @staticmethod
    def _get_extra(validated_data: PayloadType) -> dict[str, Any]:
        return validated_data.get("extra")

    @staticmethod
    def _get_key(prefix: str, validated_data: PayloadType) -> str:
        return f"{prefix}{validated_data.get('jti')}"

    @staticmethod
    def _validate_sub(token_data: PayloadType) -> bool:
        if token_data.get("sub"):
            return True
        else:
            raise ValueError("The sub claim must be provided.")

    @staticmethod
    def _validate_exp(token_data: PayloadType) -> bool:
        exp = token_data.get("exp")
        now = time.time()

        return float(exp) > now

    @staticmethod
    def _create_metadata(data: dict, ttl: float) -> PayloadType:
        now = time.time()
        data = data.copy()

        data["exp"] = now + ttl
        data["iat"] = now
        data["jti"] = uuid4().hex
        data.setdefault("extra", {})

        return data
