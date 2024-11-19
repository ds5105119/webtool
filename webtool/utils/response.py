from typing import Any

from starlette.responses import JSONResponse as JSONResponse

try:
    import msgspec
except ImportError:  # pragma: nocover
    msgspec = None  # type: ignore


class MsgSpecJSONResponse(JSONResponse):
    """
    JSON response using the high-performance(5x) msgspec library to serialize data to JSON.
    """

    def render(self, content: Any) -> bytes:
        assert msgspec is not None, "msgspec must be installed to use MsgSpecJSONResponse"
        return msgspec.json.encode(content)
