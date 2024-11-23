from abc import ABC, abstractmethod
from typing import Any, Callable, Literal, Optional
from uuid import uuid4

from webtool.auth.models import AuthData, Payload
from webtool.auth.service import BaseJWTService


def _get_header_value(header: dict, name: str) -> str | None:
    """
    Extracts a specific header value from HTTP headers.

    Parameters:
        header: HTTP header dictionary
        name: Name of the header to find
        Header value or None
    """

    header = {key.decode("utf-8").lower(): val for key, val in header}
    val = header.get(name)

    if val is None:
        return val

    return val.decode("utf-8")


def _get_cookie_value(cookie: str, name: str) -> str | None:
    """
    Extracts a specific cookie value from a cookie string.

    Parameters:
        cookie: Cookie string (e.g., "name1=value1; name2=value2")
        name: Name of the cookie to find
        Cookie value or None
    """

    cookie = dict(c.split("=") for c in cookie.split("; "))
    val = cookie.get(name)

    return val


def _get_authorization_scheme_param(authorization_header_value: Optional[str]) -> tuple[str, str]:
    """
    Separates scheme and token from Authorization header.

    Parameters:
        authorization_header_value: Authorization header value

    Return:
        tuple: scheme and token
    """

    if not authorization_header_value:
        return "", ""
    scheme, _, param = authorization_header_value.partition(" ")

    return scheme, param


def _get_access_token(scope: dict):
    """
    Extracts JWT from request scope.

    Parameters:
        scope: ASGI request scope

    Returns:
        (scheme, token) tuple or None
    """

    headers = scope.get("headers")
    if headers is None:
        return None

    authorization_value = _get_header_value(headers, "authorization")
    if authorization_value is None:
        return None

    scheme, param = _get_authorization_scheme_param(authorization_value)
    if scheme.lower() != "bearer" or not param:
        return None

    return scheme, param


class BaseBackend(ABC):
    """
    Abstract base class for authentication backends.
    All authentication backends must inherit from this class.
    """

    @abstractmethod
    async def authenticate(self, scope: dict) -> AuthData | None:
        """
        Performs authentication using the request scope.

        Parameters:
            scope: ASGI request scope

        Returns:
            AuthData: Authentication data or None
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
    The implementation of BaseAnnoBackend should include a function to identify unauthenticated users
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

    async def authenticate(self, scope: dict) -> AuthData | None:
        """
        Performs authentication using the client's IP address.

        Parameters:
            scope: ASGI request scope

        Returns:
            AuthData: IP address or None
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
        Parameters:
            session_name: Name of the session cookie
        """

        self.session_name = session_name

    def get_session(self, scope: dict) -> str | None:
        """
        Extracts session information from request scope.

        Parameters:
            scope: ASGI request scope

        Returns:
            Session string or None
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

    async def authenticate(self, scope: dict) -> AuthData | None:
        """
        Performs authentication using session information.

        Parameters:
            scope: ASGI request scope

        Returns:
            AuthData: IP address or None
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
        session_name: str,
        max_age: int = 1209600,
        secure: bool = True,
        same_site: Literal["lax", "strict", "none"] | None = "lax",
        session_factory: Optional[Callable] = uuid4,
    ):
        """
        Parameters:
            session_name: Name of the session cookie
            max_age: Session expiration time (seconds)
            secure: HTTPS only flag
            same_site: SameSite cookie policy: lax, strict, none
            session_factory: Session ID generation function
        """

        super().__init__(session_name)

        self.session_factory = session_factory
        self.security_flags = f"path=/; httponly; samesite={same_site}; Max-Age={max_age};"
        if secure:
            self.security_flags += " secure;"

    async def verify_identity(self, scope: dict, send: Callable) -> None:
        """
        Assigns new session to anonymous users and redirects.

        Parameters:
            scope: ASGI request scope
            send: ASGI send function
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
        Parameters:
            jwt_service: Service object for JWT processing
        """

        self.jwt_service = jwt_service

    async def validate_token(self, token: str) -> Payload | None:
        """
        Validates JWT.

        Parameters:
            token: JWT string

        Returns:
            Validated token data or None
        """

        validated_token = await self.jwt_service.validate_access_token(token)

        if validated_token is None:
            return None

        if validated_token.get("sub") is None:
            return None

        return validated_token

    async def authenticate(self, scope: dict) -> AuthData | None:
        """
        Performs authentication using JWT.

        Parameters:
            scope: ASGI request scope

        Returns:
            Validated token data or None
        """

        token_data = _get_access_token(scope)
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
