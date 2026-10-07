"""The app-factory feature: request field, selector and listing route behind one name."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import KW_ONLY, dataclass

from fastapi import APIRouter
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models import KnownModelName, Model, infer_model
from pydantic_ai_app_factory import AppDeps, AuthProvider, Feature, UserContext

from pydantic_ai_model_selection._capability import ModelSelectionCapability, model_extras_type
from pydantic_ai_model_selection._routes import build_model_selection_router


@dataclass(frozen=True)
class ModelOption:
    """One selectable model."""

    model: Model | KnownModelName | str
    """A pydantic-ai model or model string. `KnownModelName` gives editor completion; any string works."""
    _: KW_ONLY
    label: str | None = None
    """Display text for the dropdown; the model's name when `None`."""


class ModelSelection(Feature):
    """Lets a request pick its model from the configured options.

    An unknown key is a 422 at the boundary; a key `allow` denies is a 403 in the run, because only
    the run has the user and the key together.
    """

    name = 'model-selection'

    def __init__(
        self,
        *,
        options: Mapping[str, ModelOption],
        allow: Callable[[UserContext, str], bool | Awaitable[bool]] | None = None,
    ) -> None:
        if not options:
            raise ValueError('options must not be empty')
        # Resolving here makes a missing provider key fail startup, not the first request.
        self._models: dict[str, Model] = {}
        self._labels: dict[str, str] = {}
        for key, option in options.items():
            model = option.model if isinstance(option.model, Model) else infer_model(option.model)
            self._models[key] = model
            self._labels[key] = option.label if option.label is not None else model.model_name
        self._allow = allow
        self.extras_type = model_extras_type(options)

    def capabilities(self) -> list[AbstractCapability[AppDeps]]:
        return [ModelSelectionCapability[AppDeps](models=self._models, allow=self._allow)]

    def routers(self, *, auth: AuthProvider) -> list[APIRouter]:
        return [build_model_selection_router(labels=self._labels, allow=self._allow, auth=auth)]
