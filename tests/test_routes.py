"""The listing route on a bare FastAPI app."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from pydantic_ai_model_selection import AllowFunc, build_model_selection_router

LABELS = {'fast': 'Fast', 'slow': 'Thorough'}


@dataclass(frozen=True)
class User:
    user_id: str
    premium: bool = False


def _auth(x_user: Annotated[str | None, Header()] = None) -> User:
    if x_user is None:
        raise HTTPException(status_code=401)
    return User(x_user, premium=x_user == 'vip')


def _client(allow: AllowFunc | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(build_model_selection_router(labels=LABELS, allow=allow, auth=_auth))
    return TestClient(app)


def _fast_or_premium(user: User, key: str) -> bool:
    return key == 'fast' or user.premium


def test_the_route_requires_the_user_dependency() -> None:
    assert _client().get('/model-selection/models').status_code == 401


def test_every_option_is_listed_with_key_and_label_only() -> None:
    response = _client().get('/model-selection/models', headers={'X-User': 'u'})

    assert response.status_code == 200
    assert response.json() == [{'key': 'fast', 'label': 'Fast'}, {'key': 'slow', 'label': 'Thorough'}]


def _listed_keys(client: TestClient, user: str) -> list[str]:
    models = client.get('/model-selection/models', headers={'X-User': user}).json()
    return [m['key'] for m in models]


def test_allow_filters_the_listing_per_user() -> None:
    client = _client(allow=_fast_or_premium)

    assert _listed_keys(client, 'u') == ['fast']
    assert _listed_keys(client, 'vip') == ['fast', 'slow']


async def _async_fast_or_premium(user: User, key: str) -> bool:
    return key == 'fast' or user.premium


def test_allow_may_be_async() -> None:
    client = _client(allow=_async_fast_or_premium)

    assert _listed_keys(client, 'u') == ['fast']
    assert _listed_keys(client, 'vip') == ['fast', 'slow']
