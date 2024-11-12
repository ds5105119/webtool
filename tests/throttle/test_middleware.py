import asyncio
import random
import time
from uuid import uuid4

import pytest
from httpx import AsyncClient

from .conftest import app


@pytest.mark.asyncio(scope="session")
async def test_anno_throttle_1():
    async with AsyncClient(app=app, base_url="http://test") as ac:

        async def worker_1():
            first_response = await ac.get("/2/", follow_redirects=False)
            cookies = dict(first_response.cookies)

            responses = [first_response]
            for _ in range(5):
                resp = await ac.get("/2/", cookies=cookies)
                responses.append(resp)
            return responses

        t = time.time()
        results = await asyncio.gather(*[worker_1() for _ in range(100)])

    now = time.time()
    delta = now - t
    assert delta < 5

    for response_set in results:
        assert len(response_set) == 6
        assert response_set[0].status_code == 307
        assert response_set[1].status_code == 200
        assert response_set[2].status_code == 200
        assert response_set[3].status_code == 200
        assert response_set[4].status_code == 200
        assert response_set[5].status_code == 429


@pytest.mark.asyncio(scope="session")
async def test_anno_throttle_2():
    async with AsyncClient(app=app, base_url="http://test") as ac:

        async def worker_1():
            first_response = await ac.get("/3/", follow_redirects=False)
            cookies = dict(first_response.cookies)

            responses = [first_response]
            for _ in range(3):
                resp = await ac.get("/3/", cookies=cookies)
                responses.append(resp)
            return responses

        t = time.time()
        results = await asyncio.gather(*[worker_1() for _ in range(100)])

    now = time.time()
    delta = now - t
    assert delta < 5

    for response_set in results:
        assert len(response_set) == 4
        assert response_set[0].status_code == 307
        assert response_set[1].status_code == 200
        assert response_set[2].status_code == 200
        assert response_set[3].status_code == 429


@pytest.mark.asyncio(scope="session")
async def test_auth_throttle_3(jwt_service):
    async with AsyncClient(app=app, base_url="http://test") as ac:

        async def worker_1():
            token_data = {"sub": uuid4().hex}
            access_token = jwt_service.create_access_token(token_data)

            responses = []
            for _ in range(5):
                resp = await ac.get("/3/", headers={"Authorization": f"Bearer {access_token}"})
                responses.append(resp)
            return responses

        t = time.time()
        results = await asyncio.gather(*[worker_1() for _ in range(100)])

    now = time.time()
    delta = now - t
    assert delta < 5

    for response_set in results:
        assert len(response_set) == 5
        assert response_set[0].status_code == 200
        assert response_set[1].status_code == 200
        assert response_set[2].status_code == 200
        assert response_set[3].status_code == 200
        assert response_set[4].status_code == 429


@pytest.mark.asyncio(scope="session")
async def test_auth_throttle_4(jwt_service):
    async with AsyncClient(app=app, base_url="http://test") as ac:

        async def worker_1():
            token_data = {"sub": uuid4().hex, "scope": ["write"]}
            access_token = jwt_service.create_access_token(token_data)

            responses = []
            for _ in range(5):
                resp = await ac.get("/4/", headers={"Authorization": f"Bearer {access_token}"})
                responses.append(resp)
            return responses

        async def worker_2():
            token_data = {"sub": uuid4().hex, "scope": ["read"]}
            access_token = jwt_service.create_access_token(token_data)

            responses = []
            for _ in range(5):
                resp = await ac.get("/4/", headers={"Authorization": f"Bearer {access_token}"})
                responses.append(resp)
            return responses

        async def worker_3():
            first_response = await ac.get("/4/", follow_redirects=False)
            cookies = dict(first_response.cookies)

            responses = [first_response]
            for _ in range(3):
                resp = await ac.get("/4/", cookies=cookies)
                responses.append(resp)
            return responses

        t = time.time()
        tasks = [random.randint(0, 2) for _ in range(100)]
        results = await asyncio.gather(
            *[worker_1() if task == 0 else worker_2() if task == 1 else worker_3() for task in tasks]
        )

    now = time.time()
    delta = now - t
    assert delta < 5

    for i, response_set in enumerate(results):
        if tasks[i] == 0:
            assert len(response_set) == 5
            assert all([response.status_code == 200 for response in response_set[:-1]])
            assert response_set[-1].status_code == 429
        elif tasks[i] == 1:
            assert len(response_set) == 5
            assert all([response.status_code == 200 for response in response_set])
        elif tasks[i] == 2:
            assert len(response_set) == 4
            assert response_set[0].status_code == 307
            assert all([response.status_code == 200 for response in response_set[1:-1]])
            assert response_set[-1].status_code == 429
