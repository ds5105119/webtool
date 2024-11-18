from abc import ABC, abstractmethod
from typing import Optional

from jose import JWTError, jwt


class BaseJWTManager(ABC):
    """
    Abstract base class for managing JSON Web Tokens (JWT).
    This class defines the interface for encoding and decoding JWT (RFC7519).
    """

    @abstractmethod
    def encode(
        self,
        claims: dict,
        secret_key: str,
        algorithm: str,
        access_token: Optional[str] = None,
    ) -> str:
        """
        Encodes the specified claims into a JSON Web Token (JWT).

        :param claims: A dictionary containing the claims to be included in the JWT.
        :param secret_key: The secret key used to sign the JWT.
        :param algorithm: The signing algorithm to be used for the JWT.
        :param access_token: Optional parameter for additional handling of access tokens.

        :return: A string representation of the encoded JWT.

        :raises NotImplementedError: If this method is not implemented in a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    def decode(
        self,
        token: str,
        secret_key: str,
        algorithm: str,
        access_token: Optional[str] = None,
    ) -> dict | None:
        """
        Decodes a JSON Web Token (JWT) and validates its claims.

        :param token: The JWT string to be decoded.
        :param secret_key: The secret key used to validate the JWT signature.
        :param algorithm: The signing algorithm used to verify the JWT,
        :param access_token: Optional parameter for additional handling of access tokens.

        :return: A dictionary containing the claims if the token is valid,
                 or None if the token is invalid or expired.

        :raises NotImplementedError: If this method is not implemented in a subclass.
        """

        raise NotImplementedError


class JWTManager(BaseJWTManager):
    """
    JWT manager for encoding and decoding JSON Web Tokens.
    """

    def encode(
        self,
        claims: dict,
        secret_key: str,
        algorithm: str,
        access_token: Optional[str] = None,
    ) -> str:
        """
        Encodes the specified claims into a JSON Web Token (JWT) with a specified expiration time.
        :param claims: A dictionary containing the claims to be included in the JWT.
        :param secret_key: The secret key used to sign the JWT.
        :param algorithm: The signing algorithm to use for the JWT, defaults to 'ES384'.
        :param access_token: Optional parameter for additional handling of access tokens.

        :return: JWT
        """

        return jwt.encode(claims, secret_key, algorithm=algorithm, access_token=access_token)

    def decode(
        self,
        token: str,
        secret_key: str,
        algorithm: str,
        access_token: Optional[str] = None,
    ) -> dict | None:
        """
        Decodes a JSON Web Token (JWT) and returns the claims if valid.

        :param token: The JWT string to be decoded.
        :param secret_key: The secret key used to validate the JWT signature.
        :param algorithm: The signing algorithm used for verification JWT, defaults to 'ES384'.
        :param access_token: Optional parameter for additional handling of access tokens.

        :return: A dictionary containing the claims if the token is valid,
                 or None if the token is invalid or expired.
        """

        try:
            options = {
                "verify_signature": True,
                "verify_aud": False,
                "verify_iat": True,
                "verify_exp": False,
                "verify_nbf": True,
                "verify_iss": True,
                "verify_sub": True,
                "verify_jti": True,
                "verify_at_hash": True,
                "require_aud": False,
                "require_iat": False,
                "require_exp": False,
                "require_nbf": False,
                "require_iss": False,
                "require_sub": False,
                "require_jti": False,
                "require_at_hash": False,
                "leeway": 0,
            }

            return jwt.decode(
                token,
                secret_key,
                algorithms=[algorithm],
                options=options,
                access_token=access_token,
            )
        except JWTError:
            return None
