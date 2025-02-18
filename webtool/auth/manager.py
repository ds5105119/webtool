from abc import ABC, abstractmethod
from typing import Optional

import jwt as pyjwt


class BaseJWTManager(ABC):
    """
    Abstract base class for managing JSON Web Tokens (JWT).
    This class defines the interface for encoding and decoding JWT (RFC7519).

    Info:
        대부분의 경우 해당 클래스의 하위 구현체를 직접 사용할 필요는 거의 없습니다.
    """

    @abstractmethod
    def encode(
        self,
        claims: dict,
        secret_key: str | bytes,
        algorithm: str,
    ) -> str:
        """
        Encodes the specified claims into a JSON Web Token (JWT).

        Parameters:
            claims: A dictionary containing the claims to be included in the JWT.
            secret_key: The secret key used to sign the JWT.
            algorithm: The signing algorithm to be used for the JWT.

        Returns:
            str: A string representation of the encoded JWT.

        Raises:
             NotImplementedError: If this method is not implemented in a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    def decode(
        self,
        token: str,
        secret_key: str | bytes,
        algorithm: str,
        at_hash: Optional[str] = None,
    ) -> dict | None:
        """
        Decodes a JSON Web Token (JWT) and validates its claims.

        Parameters:
            token: The JWT string to be decoded.
            secret_key: The secret key used to validate the JWT signature.
            algorithm: The signing algorithm used to verify the JWT,
            at_hash: Optional parameter for additional handling of access tokens.

        Returns:
            dicy: A dictionary containing the claims if the token is valid, or None if the token is invalid or expired.

        Raises:
             NotImplementedError: If this method is not implemented in a subclass.
        """

        raise NotImplementedError


class JWTManager(BaseJWTManager):
    """
    JWT manager for encoding and decoding JSON Web Tokens.
    """

    def __init__(self, options: dict[str, bool | list[str]] | None = None):
        self.jwt = pyjwt.PyJWT(options or self._get_default_options())

    @staticmethod
    def _get_default_options() -> dict[str, bool | list[str]]:
        return {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
            "verify_aud": True,
            "verify_iss": True,
            "verify_sub": True,
            "verify_jti": True,
            "require": [],
        }

    def encode(
        self,
        claims: dict,
        secret_key: str | bytes,
        algorithm: str,
    ) -> str:
        """
        Encodes the specified claims into a JSON Web Token (JWT) with a specified expiration time.

        Parameters:
            claims: A dictionary containing the claims to be included in the JWT.
            secret_key: The secret key used to sign the JWT.
            algorithm: The signing algorithm to use for the JWT, defaults to 'ES384'.

        Returns:
            str: Json Web Token (JWT).
        """

        return self.jwt.encode(claims, secret_key, algorithm)

    def decode(
        self,
        token: str,
        secret_key: str | bytes,
        algorithm: str,
        at_hash: Optional[str] = None,
        raise_error: bool = False,
        options: dict[str, bool | list[str]] | None = None,
    ) -> dict | None:
        """
        Decodes a JSON Web Token (JWT) and returns the claims if valid.

        Parameters:
            token: The JWT string to be decoded.
            secret_key: The secret key used to validate the JWT signature.
            algorithm: The signing algorithm used for verification JWT, defaults to 'ES384'.
            at_hash: Optional parameter for additional handling of access tokens.
            raise_error: Optional parameter for additional handling of error messages.
            options: Optional parameters for additional handling of additional errors.

        Returns:
            dict: A dictionary containing the claims if the token is valid, or None if the token is invalid or expired.
        """

        try:
            res = self.jwt.decode(token, secret_key, algorithms=[algorithm], options=options)

            if at_hash and res.get("at_hash") != at_hash:
                raise ValueError("Invalid token")

            return res

        except pyjwt.InvalidTokenError as e:
            if raise_error:
                raise e
            else:
                return None
        except ValueError as e:
            if raise_error:
                raise e
            else:
                return None
