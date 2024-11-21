from typing import Optional

from starlette.requests import Request

from webtool.auth.models import AuthData


def get_auth(request: Request) -> Optional[AuthData]:
    user = getattr(request.state, "auth", None)
    return user
