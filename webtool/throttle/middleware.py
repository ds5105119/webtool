from collections.abc import Iterable
from typing import Callable, Optional

from starlette.routing import BaseRoute, Match

from webtool.auth.backend import AnnoSessionBackend, BaseAnnoBackend, BaseBackend
from webtool.throttle.decorator import (
    THROTTLE_RULE_ATTR_NAME,
    LimitRule,
    LimitRuleManager,
    _find_closure_rules_function,
)
from webtool.throttle.limiter import RedisLimiter


def _find_route_handler(routes: Iterable[BaseRoute], scope) -> Optional[Callable]:
    """
    Finds and returns the route handler function for the given scope.

    :param routes: Iterable of BaseRoute objects
    :param scope: ASGI request scope

    :return: Route handler function or None if not found
    """

    for route in routes:
        match, _ = route.matches(scope)
        if match == Match.FULL and hasattr(route, "endpoint"):
            return route.endpoint
    return None


async def _default_callback(scope, send, expire: int):
    """
    Default callback function for rate limit exceeded response.
    Returns a 429 status code with Retry-After header.

    :param scope: ASGI request scope
    :param send: ASGI send function
    :param expire: Time until rate limit reset (in seconds)
    """

    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"location", scope["path"].encode()),
                (b"Retry-After", str(expire).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": ""})


class LimitMiddleware:
    """
    Middleware for implementing rate limiting in ASGI applications.

    This middleware supports both authenticated and anonymous users,
    applying rate limits based on user identifiers or session IDs.
    """

    def __init__(
        self,
        app,
        cache,
        auth_backend: "BaseBackend",
        anno_backend: "BaseAnnoBackend" = None,
    ) -> None:
        """
        :param app: ASGI application
        :param cache: Cache client instance for storing rate limit data
        :param auth_backend: Authentication backend for identifying users
        :param anno_backend: Backend for handling anonymous users (defaults to AnnoSessionBackend)
        """

        self.app = app
        self.limiter = RedisLimiter(cache)
        self.auth_backend = auth_backend
        self.anno_backend = anno_backend or AnnoSessionBackend("th-session")

    async def __call__(self, scope, receive, send):
        """
        Main middleware handler that processes each request.

        :param scope: ASGI request scope
        :param receive: ASGI receive function
        :param send: ASGI send function
        """

        # http check
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # find handler
        routes = scope["app"].routes
        handler = _find_route_handler(routes, scope)
        if handler is None:
            return await self.app(scope, receive, send)

        is_user = False

        try:
            auth_data = await self.auth_backend.authenticate(scope)
            scope["auth"] = auth_data.data
            is_user = True
        except ValueError:
            try:
                auth_data = await self.anno_backend.authenticate(scope)
            except ValueError:
                send = await self.anno_backend.verify_identity(scope, send)
                return await self.app(scope, receive, send)

        # find limit rule manager
        handler = _find_closure_rules_function(handler)
        if handler is None:
            return await self.app(scope, receive, send)

        # Apply limit rules
        manager: LimitRuleManager = getattr(handler, THROTTLE_RULE_ATTR_NAME)
        if manager is None:
            return await self.app(scope, receive, send)

        rules = manager.should_limit(scope, is_user=is_user, auth_data=auth_data)
        return await self.apply(scope, receive, send, auth_data.identifier, rules)

    async def apply(self, scope, receive, send, identifier: str, rules: list["LimitRule"]):
        """
        Applies rate limiting rules and handles the request.

        :param scope: ASGI request scope
        :param receive: ASGI receive function
        :param send: ASGI send function
        :param identifier: ASGI identifier string
        :param rules: List of rate limit rules

        :return: Response from app or rate limit exceeded response
        """

        if rules:
            deny = await self.limiter.is_deny(identifier, rules)
            if deny:
                return await _default_callback(scope, send, int(max(deny)))

        return await self.app(scope, receive, send)
