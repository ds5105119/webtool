from collections import deque
from typing import Any, Callable, Optional, Union

from webtool.utils.hash import sha256

THROTTLE_RULE_ATTR_NAME = "_throttle_rules"


def _find_closure_rules_function(func):
    """
    Recursively finds a function with throttle rules in closure tree.
    Traverses through function closures using BFS.

    Parameters:
        func: Function to search from

    Returns:
        func: Function with throttle rules or None if not found
    """

    queue = deque([func])
    visited = set()

    while queue:
        current_func = queue.popleft()
        if current_func in visited:
            continue
        visited.add(current_func)

        if hasattr(current_func, THROTTLE_RULE_ATTR_NAME):
            return current_func

        if hasattr(current_func, "__closure__") and current_func.__closure__:
            for cell in current_func.__closure__:
                cell_content = cell.cell_contents
                if callable(cell_content):
                    queue.append(cell_content)

    return None


def limiter(
    max_requests: Union[int, Callable[..., int]],
    interval: int = 3600,
    throttle_key: Optional[str] = None,
    method: Optional[list[str]] = None,
    scopes: Optional[list[str]] = None,
) -> Callable:
    """
    Decorator for implementing rate limiting on functions.

    Parameters:
        max_requests: Maximum number of requests allowed in the interval
        interval: Time interval in seconds (default: 3600)
        throttle_key: Custom key for the rate limit (default: function path)
        method: List of HTTP methods to apply limit to (optional)
        scopes: List of user scopes to apply limit to (optional)

    Returns:
        Callable: Decorated function with rate limiting rules
    """

    def decorator(func):
        exist_func = _find_closure_rules_function(func)

        key = throttle_key
        if exist_func:
            key = key or sha256(f"{exist_func.__module__}{exist_func.__name__}{interval}{method}{scopes}").hex()
            if not hasattr(func, THROTTLE_RULE_ATTR_NAME):
                exist_rules = getattr(exist_func, THROTTLE_RULE_ATTR_NAME)
                setattr(func, THROTTLE_RULE_ATTR_NAME, exist_rules)
        else:
            key = key or sha256(f"{func.__module__}{func.__name__}{interval}{method}{scopes}").hex()
            setattr(func, THROTTLE_RULE_ATTR_NAME, LimitRuleManager())

        new_rule = LimitRule(
            max_requests=max_requests,
            interval=interval,
            throttle_key=key,
            method=[m.upper() for m in method] if method else [],
            scopes=scopes or [],
        )

        getattr(func, THROTTLE_RULE_ATTR_NAME).add_rules(new_rule)

        return func

    return decorator


class LimitRule:
    """
    Represents a single rate limiting rule.

    Contains the conditions and parameters for a rate limit:
    - Maximum requests allowed
    - Time interval
    - Unique identifier
    - HTTP methods (optional)
    - User scopes (optional)
    """

    __slots__ = (
        "throttle_key",
        "max_requests",
        "interval",
        "method",
        "scopes",
        "for_user",
        "for_anno",
    )

    def __init__(
        self,
        max_requests: int,
        interval: int,
        throttle_key: str,
        method: Optional[list[str]],
        scopes: Optional[list[str]],
    ):
        """
        Parameters:
            max_requests: Maximum number of requests allowed
            interval: Time interval in seconds
            throttle_key: Unique identifier for this rule
            method: List of HTTP methods this rule applies to
            scopes: List of user scopes this rule applies to
        """

        self.max_requests: int = max_requests
        self.interval: int = interval
        self.throttle_key: str = throttle_key
        self.method: Optional[set[str]] = set(method)
        self.scopes: Optional[set[str]] = set(scopes)
        self.for_user: bool = "user" in scopes or ("user" in scopes) == ("anno" in scopes)
        self.for_anno: bool = "anno" in scopes or ("user" in scopes) == ("anno" in scopes)

        self.scopes.discard("user")
        self.scopes.discard("anno")

    def __repr__(self):
        """
        String representation of the rule showing its configuration
        """

        return (
            f"{self.max_requests} / {self.interval} "
            f"{self.throttle_key:.20s}... {self.method} {self.scopes} "
            f"for {'user' if self.for_user else 'anno' if self.for_anno else ''}"
        )

    def is_enabled(
        self,
        scope: dict,
        anno_identifier: Any | None = None,
        user_identifier: Any | None = None,
        auth_scope: list[str] | None = None,
    ) -> bool:
        """
        Checks if this rule should be applied based on request context.

        Parameters:
            scope: ASGI request scope
            anno_identifier: Anonymous user identifier
            user_identifier: Authenticated user identifier (optional)
            auth_scope: List of user scopes this rule applies to

        Returns:
            bool: indicating if rule should be applied
        """

        if self.method and scope.get("method") not in self.method:
            return False

        if not self.scopes or (auth_scope and set(auth_scope) & self.scopes):
            if user_identifier and self.for_user:
                return True
            elif anno_identifier and self.for_anno:
                return True

        return False


class LimitRuleManager:
    """
    Container class for managing multiple rate limit rules.
    Allows adding and checking rules for specific requests.
    """

    __slots__ = ("rules",)

    def __init__(self):
        self.rules: set[LimitRule] = set()

    def should_limit(
        self,
        scope: dict,
        anno_identifier: Any | None = None,
        user_identifier: Any | None = None,
        auth_scope: list[str] | None = None,
    ) -> list[LimitRule]:
        """
        Determines which rules should be applied for a given request.

        Parameters:
            scope: ASGI request scope
            anno_identifier: Anonymous user identifier (optional)
            user_identifier: Authenticated user identifier (optional)
            auth_scope: List of user scopes this rule applies to

        Returns:
            List of applicable rules
        """

        rules = [rule for rule in self.rules if rule.is_enabled(scope, anno_identifier, user_identifier, auth_scope)]

        return rules

    def add_rules(self, rule: LimitRule) -> None:
        """
        Adds a new rate limit rule to the collection.

        Parameters:
            rule: LimitRule instance to add
        """

        self.rules.add(rule)
