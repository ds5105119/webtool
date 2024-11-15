from collections import deque
from typing import Any, Callable, Optional, Union

THROTTLE_RULE_ATTR_NAME = "_throttle_rules"


def find_closure_rules_function(func):
    """
    Recursively finds a function with throttle rules in closure tree.
    Traverses through function closures using BFS.

    :param func: Function to search from
    :return: Function with throttle rules or None if not found
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
    scope: Optional[list[str]] = None,
):
    """
    Decorator for implementing rate limiting on functions.

    :param max_requests: Maximum number of requests allowed in the interval
    :param interval: Time interval in seconds (default: 3600)
    :param throttle_key: Custom key for the rate limit (default: function path)
    :param method: List of HTTP methods to apply limit to (optional)
    :param scope: List of user scopes to apply limit to (optional)
    :return: Decorated function with rate limiting rules
    """

    def decorator(func):
        exist_func = find_closure_rules_function(func)

        if exist_func:
            key = throttle_key or f"{exist_func.__module__}.{exist_func.__name__}"
            if not hasattr(func, THROTTLE_RULE_ATTR_NAME):
                exist_rules = getattr(exist_func, THROTTLE_RULE_ATTR_NAME)
                setattr(func, THROTTLE_RULE_ATTR_NAME, exist_rules)
        else:
            key = throttle_key or f"{func.__module__}.{func.__name__}"
            setattr(func, THROTTLE_RULE_ATTR_NAME, LimitRuleManager())

        new_rule = LimitRule(
            max_requests=max_requests,
            interval=interval,
            throttle_key=key,
            method=[m.upper() for m in method] if method else [],
            scope=scope or [],
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
        "scope",
        "for_user",
        "for_anno",
    )

    def __init__(
        self,
        max_requests: int,
        interval: int,
        throttle_key: str,
        method: Optional[list[str]],
        scope: Optional[list[str]],
    ):
        """
        :param max_requests: Maximum number of requests allowed
        :param interval: Time interval in seconds
        :param throttle_key: Unique identifier for this rule
        :param method: List of HTTP methods this rule applies to
        :param scope: List of user scopes this rule applies to
        """

        self.max_requests: int = max_requests
        self.interval: int = interval
        self.throttle_key: str = throttle_key
        self.method: Optional[set[str]] = set(method)
        self.scope: Optional[set[str]] = set(scope)
        self.for_user: bool = "user" in scope or ("user" in scope) == ("anno" in scope)
        self.for_anno: bool = "anno" in scope or ("user" in scope) == ("anno" in scope)

        self.scope.discard("user")
        self.scope.discard("anno")

    def __repr__(self):
        """
        String representation of the rule showing its configuration
        """

        return f"{self.max_requests} per {self.interval} {self.throttle_key} {self.method} {self.scope}"

    def is_enabled(
        self,
        scope,
        anno_identifier: Any | None = None,
        user_identifier: Any | None = None,
        auth_scope: list[str] | None = None,
    ):
        """
        Checks if this rule should be applied based on request context.

        :param scope: ASGI request scope
        :param anno_identifier: Anonymous user identifier
        :param user_identifier: Authenticated user identifier (optional)
        :param auth_scope: List of user scopes this rule applies to
        :return: Boolean indicating if rule should be applied
        """

        if self.method and scope.get("method") not in self.method:
            return False

        if not self.scope or (auth_scope and set(auth_scope) & self.scope):
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
        scope,
        anno_identifier: Any | None = None,
        user_identifier: Any | None = None,
        auth_scope: list[str] | None = None,
    ) -> list[LimitRule]:
        """
        Determines which rules should be applied for a given request.

        :param scope: ASGI request scope
        :param anno_identifier: Anonymous user identifier (optional)
        :param user_identifier: Authenticated user identifier (optional)
        :param auth_scope: List of user scopes this rule applies to
        :return: List of applicable rules
        """

        rules = [rule for rule in self.rules if rule.is_enabled(scope, anno_identifier, user_identifier, auth_scope)]

        return rules

    def add_rules(self, rule: LimitRule) -> None:
        """
        Adds a new rate limit rule to the collection.

        :param rule: LimitRule instance to add
        """

        self.rules.add(rule)
