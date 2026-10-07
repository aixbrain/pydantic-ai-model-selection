"""Per-request model selection for pydantic-ai-app-factory; import from here, not the private modules."""

from pydantic_ai_model_selection._capability import (
    AllowFunc,
    ModelSelectionCapability,
    SupportsModelSelectionDeps,
    model_extras_type,
)
from pydantic_ai_model_selection._routes import ModelOut, UserDependency, build_model_selection_router
from pydantic_ai_model_selection.feature import ModelOption, ModelSelection

__all__ = [
    'AllowFunc',
    'ModelOption',
    'ModelOut',
    'ModelSelection',
    'ModelSelectionCapability',
    'SupportsModelSelectionDeps',
    'UserDependency',
    'build_model_selection_router',
    'model_extras_type',
]
