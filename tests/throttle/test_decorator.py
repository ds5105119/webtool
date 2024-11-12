from webtool.throttle.decorator import THROTTLE_RULE_ATTR_NAME, find_closure_rules_function, limiter


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

    rules = list(getattr(find_closure_rules_function(func), THROTTLE_RULE_ATTR_NAME).rules)

    assert "1 per 2 a set() set()" in rules.__repr__()
    assert "3 per 4 b set() set()" in rules.__repr__()
    assert "5 per 6 c set() set()" in rules.__repr__()
