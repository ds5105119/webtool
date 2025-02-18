from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import uuid4

Payload = dict[str, Any]
PayloadT = TypeVar("PayloadT", bound=Payload)


class AuthData:
    __slots__ = ["identifier", "scope", "data"]

    def __init__(self, identifier: Any | None, data: dict | None = None):
        self.identifier = identifier
        self.data = data


class PayloadFactory[PayloadT]:
    @staticmethod
    def _get_jti(validated_data: PayloadT) -> str:
        return validated_data.get("jti")

    @staticmethod
    def _get_exp(validated_data: PayloadT) -> float:
        return validated_data.get("exp")

    @staticmethod
    def _get_key(prefix: str, validated_data: PayloadT) -> str:
        return f"{prefix}{validated_data.get('jti')}"

    @staticmethod
    def _validate_sub(token_data: PayloadT) -> bool:
        if token_data.get("sub"):
            return True
        else:
            raise ValueError("The sub claim must be provided.")

    @staticmethod
    def _create_metadata(data: dict, ttl: float) -> PayloadT:
        now = int(datetime.now(tz=timezone.utc).timestamp())
        data = data.copy()

        data["exp"] = now + ttl
        data["iat"] = now
        data["jti"] = uuid4().hex

        return data
