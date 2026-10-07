"""The request field and the selector, without `create_agent_app`."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai_app_factory import AgentError

from pydantic_ai_model_selection import ModelSelectionCapability, model_extras_type


@dataclass(frozen=True)
class User:
    user_id: str
    premium: bool = False


@dataclass
class Deps:
    user: User
    extras: Mapping[str, Any] = field(default_factory=dict)


MODELS = {'fast': TestModel(custom_output_text='FAST'), 'slow': TestModel(custom_output_text='SLOW')}


def _agent(allow: Callable[[Any, str], bool] | None = None) -> Agent[Deps, str]:
    capability = ModelSelectionCapability[Deps](models=MODELS, allow=allow)
    return Agent(TestModel(custom_output_text='AGENT'), deps_type=Deps, capabilities=[capability])


def _fast_or_premium(user: User, key: str) -> bool:
    return key == 'fast' or user.premium


def test_the_request_field_accepts_only_the_configured_keys() -> None:
    extras = model_extras_type(['fast', 'slow'])

    assert extras.model_validate({'model': 'slow'}).model_dump() == {'model': 'slow'}
    assert extras.model_validate({}).model_dump() == {'model': None}
    with pytest.raises(ValidationError):
        extras.model_validate({'model': 'other'})


def test_the_request_field_needs_keys() -> None:
    with pytest.raises(ValueError, match='empty'):
        model_extras_type([])


def test_the_capability_opts_out_of_serialization() -> None:
    assert ModelSelectionCapability.get_serialization_name() is None


def test_the_request_field_lists_the_keys_in_its_schema() -> None:
    schema = model_extras_type(['fast', 'slow']).model_json_schema()

    assert schema['properties']['model'] == {
        'anyOf': [{'enum': ['fast', 'slow'], 'type': 'string'}, {'type': 'null'}],
        'default': None,
        'title': 'Model',
    }


@pytest.mark.anyio
async def test_the_chosen_key_selects_the_model() -> None:
    result = await _agent().run('hi', deps=Deps(User('u'), {'model': 'slow'}))

    assert result.output == 'SLOW'


@pytest.mark.anyio
async def test_a_missing_key_keeps_the_agent_model() -> None:
    result = await _agent().run('hi', deps=Deps(User('u')))

    assert result.output == 'AGENT'


def _nothing(user: User, key: str) -> bool:
    return False


@pytest.mark.anyio
async def test_allow_is_not_consulted_for_the_agent_model() -> None:
    result = await _agent(allow=_nothing).run('hi', deps=Deps(User('u')))

    assert result.output == 'AGENT'


@pytest.mark.anyio
async def test_a_missing_key_fails_when_the_agent_has_no_model() -> None:
    agent = Agent(deps_type=Deps, capabilities=[ModelSelectionCapability[Deps](models=MODELS)])

    with pytest.raises(ValueError, match='agent has none'):
        await agent.run('hi', deps=Deps(User('u')))


@pytest.mark.anyio
async def test_allow_denies_with_a_403_code() -> None:
    agent = _agent(allow=_fast_or_premium)

    with pytest.raises(AgentError) as info:
        await agent.run('hi', deps=Deps(User('u'), {'model': 'slow'}))

    assert info.value.code == 'model-selection/forbidden'
    assert info.value.http_status == 403


@pytest.mark.anyio
async def test_allow_sees_the_user_on_deps() -> None:
    agent = _agent(allow=_fast_or_premium)

    result = await agent.run('hi', deps=Deps(User('u', premium=True), {'model': 'slow'}))

    assert result.output == 'SLOW'
