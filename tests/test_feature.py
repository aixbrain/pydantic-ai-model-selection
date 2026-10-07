"""The feature through `create_agent_app`: boundary validation, selection, the route."""

import json
from typing import Annotated, Any

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient
from pydantic_ai import Agent
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.test import TestModel
from pydantic_ai_app_factory import AppDeps, UserContext, create_agent_app

from pydantic_ai_model_selection import ModelOption, ModelSelection

OPTIONS = {
    'fast': ModelOption(TestModel(custom_output_text='FAST'), label='Fast'),
    'slow': ModelOption(TestModel(custom_output_text='SLOW')),
}


def _auth(x_scopes: Annotated[str | None, Header()] = None) -> UserContext:
    if x_scopes is None:
        raise HTTPException(status_code=401)
    return UserContext(user_id='u1', scopes=frozenset(x_scopes.split(',')) - {''})


def _client(**kwargs: Any) -> TestClient:
    selection = ModelSelection(options=OPTIONS, **kwargs)
    agent = Agent(TestModel(custom_output_text='AGENT'), deps_type=AppDeps)
    return TestClient(create_agent_app(agent, auth=_auth, features=[selection]))


def _fast_or_premium(user: UserContext, key: str) -> bool:
    return key == 'fast' or 'premium' in user.scopes


def _fast_only(user: UserContext, key: str) -> bool:
    return key == 'fast'


AUTH = {'X-Scopes': ''}
PREMIUM = {'X-Scopes': 'premium'}


def _chat(model: str | None = None) -> dict[str, Any]:
    message = {'id': 'm1', 'role': 'user', 'parts': [{'type': 'text', 'text': 'hi'}]}
    body: dict[str, Any] = {'trigger': 'submit-message', 'id': 'c1', 'messages': [message]}
    if model is not None:
        body['model'] = model
    return body


def _chat_text(body: str) -> str:
    chunks = [json.loads(line[6:]) for line in body.splitlines() if line.startswith('data: {')]
    return ''.join(c['delta'] for c in chunks if c['type'] == 'text-delta')


def _chat_error(body: str) -> dict[str, Any]:
    chunks = [json.loads(line[6:]) for line in body.splitlines() if line.startswith('data: {')]
    return next(c['data'] for c in chunks if c['type'] == 'data-error')


def test_options_must_not_be_empty() -> None:
    with pytest.raises(ValueError, match='empty'):
        ModelSelection(options={})


async def _async_fast_or_premium(user: UserContext, key: str) -> bool:
    return key == 'fast' or 'premium' in user.scopes


def test_allow_may_be_async() -> None:
    client = _client(allow=_async_fast_or_premium)

    body = {'prompt': 'hi', 'extras': {'model': 'slow'}}
    assert client.post('/run', json=body, headers=AUTH).status_code == 403
    assert client.post('/run', json=body, headers=PREMIUM).json()['output'] == 'SLOW'
    assert [m['key'] for m in client.get('/model-selection/models', headers=AUTH).json()] == ['fast']


def test_a_model_string_is_resolved_when_the_feature_is_built() -> None:
    selection = ModelSelection(options={'t': ModelOption('test', label='Test')})
    agent = Agent(TestModel(custom_output_text='AGENT'), deps_type=AppDeps)
    client = TestClient(create_agent_app(agent, auth=_auth, features=[selection]))

    response = client.post('/run', json={'prompt': 'hi', 'extras': {'model': 't'}}, headers=AUTH)

    assert response.status_code == 200
    assert response.json()['output'] != 'AGENT'


def test_a_missing_provider_key_fails_startup_not_the_first_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)

    with pytest.raises(UserError):
        ModelSelection(options={'gpt': ModelOption('openai:gpt-5-mini', label='GPT')})


def test_the_feature_is_named_and_exposes_its_keys_on_config() -> None:
    config = _client().get('/config').json()

    assert 'model-selection' in config['features']
    assert config['extras_schema']['properties']['model'] == {
        'anyOf': [{'enum': ['fast', 'slow'], 'type': 'string'}, {'type': 'null'}],
        'default': None,
        'title': 'Model',
    }


def test_run_without_the_field_keeps_the_agent_model() -> None:
    assert _client().post('/run', json={'prompt': 'hi'}, headers=AUTH).json()['output'] == 'AGENT'


def test_run_with_the_field_uses_that_model() -> None:
    body = {'prompt': 'hi', 'extras': {'model': 'slow'}}

    assert _client().post('/run', json=body, headers=AUTH).json()['output'] == 'SLOW'


def test_run_rejects_an_unknown_key_at_the_boundary() -> None:
    response = _client().post('/run', json={'prompt': 'hi', 'extras': {'model': 'other'}}, headers=AUTH)

    assert response.status_code == 422
    assert response.json()['detail'][0]['loc'] == ['body', 'extras', 'model']


def test_chat_with_the_field_uses_that_model() -> None:
    response = _client().post('/chat', json=_chat('slow'), headers=AUTH)

    assert response.status_code == 200
    assert _chat_text(response.text) == 'SLOW'


def test_chat_without_the_field_keeps_the_agent_model() -> None:
    response = _client().post('/chat', json=_chat(), headers=AUTH)

    assert response.status_code == 200
    assert _chat_text(response.text) == 'AGENT'


def test_chat_rejects_an_unknown_key_at_the_boundary() -> None:
    response = _client().post('/chat', json=_chat('other'), headers=AUTH)

    assert response.status_code == 422
    assert response.json()['detail'][0]['loc'] == ['body', 'model']


def test_a_forbidden_key_is_a_403_on_run() -> None:
    client = _client(allow=_fast_or_premium)

    response = client.post('/run', json={'prompt': 'hi', 'extras': {'model': 'slow'}}, headers=AUTH)

    assert response.status_code == 403
    assert response.json()['code'] == 'model-selection/forbidden'
    premium = client.post('/run', json={'prompt': 'hi', 'extras': {'model': 'slow'}}, headers=PREMIUM)
    assert premium.status_code == 200
    assert premium.json()['output'] == 'SLOW'


def test_a_forbidden_key_is_an_error_chunk_on_chat() -> None:
    client = _client(allow=_fast_only)

    response = client.post('/chat', json=_chat('slow'), headers=AUTH)

    assert response.status_code == 200  # the stream has started; the error travels in it
    assert _chat_error(response.text)['code'] == 'model-selection/forbidden'


def test_the_listing_sits_behind_the_app_auth_and_is_filtered() -> None:
    client = _client(allow=_fast_or_premium)

    assert client.get('/model-selection/models').status_code == 401
    assert client.get('/model-selection/models', headers=AUTH).json() == [{'key': 'fast', 'label': 'Fast'}]
    assert client.get('/model-selection/models', headers=PREMIUM).json() == [
        {'key': 'fast', 'label': 'Fast'},
        {'key': 'slow', 'label': 'test'},  # no label configured, so the model's name stands in
    ]
