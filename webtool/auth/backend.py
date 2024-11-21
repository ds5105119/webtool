from abc import ABC, abstractmethod
from typing import Any, Callable, Literal, Optional
from uuid import uuid4

from dns.dnssec import validate

from webtool.auth.models import AuthData
from webtool.auth.service import BaseJWTService


def _get_header_value(header, name: str) -> str | None:
    """
    Extracts a specific header value from HTTP headers.

    :param header: HTTP header dictionary
    :param name: Name of the header to find
    :return: Header value or None
    """

    header = {key.decode("utf-8").lower(): val for key, val in header}
    val = header.get(name)

    if val is None:
        return val

    return val.decode("utf-8")


def _get_cookie_value(cookie: str, name: str) -> str | None:
    """
    Extracts a specific cookie value from a cookie string.

    :param cookie: Cookie string (e.g., "name1=value1; name2=value2")
    :param name: Name of the cookie to find
    :return: Cookie value or None
    """

    cookie = dict(c.split("=") for c in cookie.split("; "))
    val = cookie.get(name)

    return val


class BaseBackend(ABC):
    """
    Abstract base class for authentication backends.
    All authentication backends must inherit from this class.
    """

    @abstractmethod
    async def authenticate(self, scope) -> AuthData | None:
        """
        Performs authentication using the request scope.

        :param scope: ASGI request scope
        :return: Authentication data or None
        """

        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def _callback():
        """
        Callback method called when authentication fails
        """

        raise NotImplementedError


class BaseAnnoBackend(BaseBackend):
    """
    Base backend class for handling anonymous users
    """

    @abstractmethod
    def verify_identity(self, *args, **kwargs) -> Any:
        """
        Method to verify the identity of anonymous users
        """

        raise NotImplementedError


class IPBackend(BaseBackend):
    """
    Authentication backend based on IP address
    """

    async def authenticate(self, scope) -> AuthData | None:
        """
        Performs authentication using the client's IP address.

        :param scope: ASGI request scope
        :return: IP address or None
        """

        client = scope.get("client")
        if client is None:
            return self._callback()

        auth = AuthData(identifier=client[0])

        return auth

    @staticmethod
    def _callback():
        """
        Returns None when IP authentication fails.
        """

        return None


class SessionBackend(BaseBackend):
    """
    Session-based authentication backend
    """

    def __init__(self, session_name: str):
        """
        :param session_name: Name of the session cookie
        """

        self.session_name = session_name

    def get_session(self, scope):
        """
        Extracts session information from request scope.

        :param scope: ASGI request scope
        :return: Session value or None
        """

        headers = scope.get("headers")
        if headers is None:
            return None

        cookie = _get_header_value(headers, "cookie")
        if cookie is None:
            return None

        session = _get_cookie_value(cookie, self.session_name)
        if session is None:
            return None

        return session

    async def authenticate(self, scope) -> AuthData | None:
        """
        Performs authentication using session information.

        :param scope: ASGI request scope
        :return: Session information or None
        """

        session = self.get_session(scope)
        if not session:
            return self._callback()

        auth = AuthData(identifier=session)

        return auth

    @staticmethod
    def _callback():
        """
        Returns None when session authentication fails.
        """

        return None


class AnnoSessionBackend(SessionBackend, BaseAnnoBackend):
    """
    Session backend for anonymous users.
    Automatically creates and assigns new sessions.
    """

    def __init__(
        self,
        session_name,
        max_age: int = 1209600,
        secure: bool = True,
        same_site: Literal["lax", "strict", "none"] | None = "lax",
        session_factory: Optional[Callable] = uuid4,
    ):
        """
        :param session_name: Name of the session cookie
        :param max_age: Session expiration time (seconds)
        :param secure: HTTPS only flag
        :param same_site: SameSite cookie policy
        :param session_factory: Session ID generation function
        """

        super().__init__(session_name)

        self.session_factory = session_factory
        self.security_flags = f"path=/; httponly; samesite={same_site}; Max-Age={max_age};"
        if secure:
            self.security_flags += " secure;"

    async def verify_identity(self, scope, send):
        """
        Assigns new session to anonymous users and redirects.

        :param scope: ASGI request scope
        :param send: ASGI send function
        """

        await send(
            {
                "type": "http.response.start",
                "status": 307,
                "headers": [
                    (b"location", scope["path"].encode()),
                    (
                        b"Set-Cookie",
                        f"{self.session_name}={self.session_factory().hex}; path=/; {self.security_flags}".encode(),
                    ),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b""})


class JWTBackend(BaseBackend):
    """
    JWT (JSON Web Token) based authentication backend
    """

    def __init__(self, jwt_service: "BaseJWTService"):
        """
        :param jwt_service: Service object for JWT processing
        """

        self.jwt_service = jwt_service

    @staticmethod
    def _get_authorization_scheme_param(
        authorization_header_value: Optional[str],
    ) -> tuple[str, str]:
        """
        Separates scheme and token from Authorization header.

        :param authorization_header_value: Authorization header value
        :return: (scheme, token) tuple
        """

        if not authorization_header_value:
            return "", ""
        scheme, _, param = authorization_header_value.partition(" ")

        return scheme, param

    def get_token(self, scope):
        """
        Extracts JWT from request scope.

        :param scope: ASGI request scope
        :return: (scheme, token) tuple or None
        """

        headers = scope.get("headers")
        if headers is None:
            return None

        authorization_value = _get_header_value(headers, "authorization")
        if authorization_value is None:
            return None

        scheme, param = self._get_authorization_scheme_param(authorization_value)
        if scheme.lower() != "bearer" or not param:
            return None

        return scheme, param

    async def validate_token(self, token):
        """
        Validates JWT.

        :param token: JWT string
        :return: Validated token data or None
        """

        validated_token = await self.jwt_service.validate_access_token(token)

        if validated_token is None:
            return None

        if validated_token.get("sub") is None:
            return None

        return validated_token

    async def authenticate(self, scope) -> AuthData | None:
        """
        Performs authentication using JWT.

        :param scope: ASGI request scope
        :return: Validated token data or None
        """

        token_data = self.get_token(scope)
        if token_data is None:
            return self._callback()

        validated_token = await self.validate_token(token_data[1])
        if validated_token is None:
            return self._callback()

        validated_data = dict(validated_token)

        auth = AuthData(
            identifier=validated_data.pop("sub"),
            scope=validated_data.get("scope", None),
            extra=validated_data,
        )

        return auth

    @staticmethod
    def _callback():
        """
        Returns None when JWT authentication fails.
        """

        return None
