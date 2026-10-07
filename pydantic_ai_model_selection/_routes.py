"""The listing a frontend dropdown reads.

Mount it with the `auth` object the app guards with; FastAPI caches a dependency per object, so a
second, equivalent one would run auth twice.
"""

# No `from __future__ import annotations`: FastAPI must see `Depends(auth)` as a real object.

from collections.abc import Callable, Mapping
from typing import Annotated, Any, TypeAlias

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pydantic_ai_model_selection._capability import AllowFunc, is_allowed

UserDependency: TypeAlias = Callable[..., Any]
"""A FastAPI dependency returning the user `allow` receives; the factory's `AuthProvider` is one."""


class ModelOut(BaseModel):
    """One selectable model."""

    key: str
    """The value a request sends as `model`."""
    label: str


def build_model_selection_router(
    *,
    labels: Mapping[str, str],
    allow: AllowFunc | None,
    auth: UserDependency,
) -> APIRouter:
    """Builds `GET /model-selection/models`.

    It takes labels, not models, so no provider, URL or credential can reach the response.
    """
    router = APIRouter(prefix='/model-selection', tags=['model-selection'])

    @router.get('/models')
    async def list_models(user: Annotated[Any, Depends(auth)]) -> list[ModelOut]:
        """The options this caller may pick, in configuration order."""
        allowed = [key for key in labels if await is_allowed(allow, user, key)]
        return [ModelOut(key=key, label=labels[key]) for key in allowed]

    return router
