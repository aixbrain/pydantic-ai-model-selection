"""The request field and the selector that reads it."""

# `ModelSelector` is a string alias in pydantic-ai and cannot be subscripted at runtime.
from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Optional, Protocol, TypeAlias, TypeVar

from pydantic import BaseModel, create_model
from pydantic_ai import ModelSelectionContext
from pydantic_ai.capabilities import AbstractCapability, ModelSelector
from pydantic_ai.models import Model
from pydantic_ai_app_factory import AgentError


class SupportsModelSelectionDeps(Protocol):
    """What the capability reads from a run's deps; read-only, so frozen dataclasses satisfy it."""

    @property
    def user(self) -> object: ...

    @property
    def extras(self) -> Mapping[str, Any]: ...


DepsT = TypeVar('DepsT', bound=SupportsModelSelectionDeps)

AllowFunc: TypeAlias = Callable[[Any, str], bool | Awaitable[bool]]
"""`(user, key) -> bool`, sync or async; the user is whatever the deps carry."""


async def is_allowed(allow: AllowFunc | None, user: Any, key: str) -> bool:
    if allow is None:
        return True
    verdict = allow(user, key)
    if inspect.isawaitable(verdict):
        verdict = await verdict
    return verdict


def model_extras_type(keys: Iterable[str]) -> type[BaseModel]:
    """A request model with one optional field, `model`, one of `keys`.

    A `Literal`, so an unknown key is a 422 at the boundary and the keys appear in the schema.
    """
    keys = tuple(keys)
    if not keys:
        raise ValueError('keys must not be empty')
    # pyright rejects `| None` on a `Literal` built at runtime.
    return create_model('ModelSelectionExtras', model=(Optional[Literal[keys]], None))  # noqa: UP045


@dataclass
class ModelSelectionCapability(AbstractCapability[DepsT]):
    """Selects the run's model from the `model` key on `deps.extras`.

    Without a key the run keeps the model ranked below this capability, usually the agent's own, and
    `allow` is not asked. `agent.run(model=...)` and `agent.override(model=...)` bypass the selector.
    """

    models: Mapping[str, Model]
    allow: AllowFunc | None = None
    """Called before every model request step, so keep it cheap."""

    @classmethod
    def get_serialization_name(cls) -> str | None:
        # `Model` objects and a callable cannot be rebuilt from serialized data.
        return None

    def get_model(self) -> ModelSelector[DepsT]:
        return self._select

    async def _select(self, ctx: ModelSelectionContext[DepsT]) -> Model:
        # Selection runs before `before_run`, so refusing here builds nothing for a forbidden model.
        key = ctx.deps.extras.get('model')
        if key is None:
            if ctx.model is None:
                raise ValueError('The request picked no model and the agent has none; give the agent a model.')
            return ctx.model
        if not await is_allowed(self.allow, ctx.deps.user, key):
            raise AgentError('model-selection/forbidden', 'This model is not available to you.', http_status=403)
        return self.models[key]
