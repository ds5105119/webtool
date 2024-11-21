from json import JSONDecoder, JSONEncoder
from typing import cast

import orjson


class ORJSONEncoder:
    """
    ORJSON Encoder Class
    """

    @staticmethod
    def encode(o):
        return orjson.dumps(o)


class _PyORJSONEncoder:
    __slots__ = ()

    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def default(o):
        raise TypeError(f"Object of type {o.__class__.__name__} " f"is not JSON serializable")

    @staticmethod
    def encode(o):
        return orjson.dumps(o).decode("utf-8")

    @staticmethod
    def iterencode(o, _one_shot=False):
        return orjson.dumps(o).decode("utf-8")


class ORJSONDecoder:
    """
    ORJSON Decoder Class
    """

    @staticmethod
    def decode(s, *args):
        return orjson.loads(s)


class _PyORJSONDecoder:
    __slots__ = ()

    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def decode(s, *args):
        return orjson.loads(s)

    @staticmethod
    def raw_decode(s, *args):
        return orjson.loads(s)


PyORJSONDecoder = cast(type[JSONDecoder], _PyORJSONDecoder)
"""Compatible with Python's `json.JSONDecoder`. The `typing.cast` function Cast to a `json.JSONDecoder`.
"""

PyORJSONEncoder = cast(type[JSONEncoder], _PyORJSONEncoder)
"""Compatible with Python's `json.JSONEncoder`. The `typing.cast` function Cast to a `json.JSONEncoder`.
"""
