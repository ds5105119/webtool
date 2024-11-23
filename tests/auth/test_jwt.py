import asyncio
import time
from uuid import uuid4

import pytest


@pytest.mark.asyncio(scope="session")
async def test_create_token(jwt_service):
    token_data = {"sub": "user123"}
    tokens = await jwt_service.create_token(token_data)
    assert tokens


@pytest.mark.asyncio(scope="session")
async def test_update_token(jwt_service):
    token_data = {"sub": uuid4().hex}

    access_token, refresh_token = await jwt_service.create_token(token_data)
    new_access_token, new_refresh_token = await jwt_service.update_token(token_data, refresh_token)
    time.sleep(1)

    async def create_worker():
        data = {"sub": uuid4().hex}
        access, refresh = await jwt_service.create_token(token_data)
        return data, access, refresh

    async def update_worker(data, access, refresh):
        return await jwt_service.update_token(data, refresh)

    t = time.time()
    tokens = await asyncio.gather(*[create_worker() for _ in range(100)])
    d = time.time() - t
    assert d < 5
    print(f"\n리프레시 토큰 발급 소요 시간: {d}sec")

    t = time.time()
    tokens = await asyncio.gather(*[update_worker(*args) for args in tokens])
    d = time.time() - t
    assert d < 5
    print(f"\n토큰 업데이트 소요 시간: {d}sec")

    try:
        _ = await jwt_service.update_token(token_data, refresh_token)
    except ValueError:
        pass
    else:
        assert True, "유효하지 않은 토큰으로 리프레시 성공"
