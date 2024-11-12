from typing import Any

import msgspec
from starlette.responses import JSONResponse as JSONResponse


class MsgSpecJSONResponse(JSONResponse):
    """
    JSON response using the high-performance(5x) msgspec library to serialize data to JSON.
    """

    def render(self, content: Any) -> bytes:
        return msgspec.json.encode(content)
