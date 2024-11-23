from webtool.throttle.decorator import (
    THROTTLE_RULE_ATTR_NAME,
    _find_closure_rules_function,
    limiter,
)


def test_decorator():
    foo = 0

    def decorator(func):
        bar = foo

        def wrapper(*args, **kwargs):
            print(bar)
            return func(*args, **kwargs)

        return wrapper

    @decorator
    @limiter(1, 2, "a")
    @decorator
    @limiter(3, 4, "b")
    @decorator
    @decorator
    @limiter(5, 6, "c")
    @decorator
    @decorator
    @decorator
    def func():
        pass

    rules = list(getattr(_find_closure_rules_function(func), THROTTLE_RULE_ATTR_NAME).rules)

    assert len(rules) == 3
