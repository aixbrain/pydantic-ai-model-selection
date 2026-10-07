"""The package re-exports its contract; private modules stay private."""

import pydantic_ai_model_selection as pkg


def test_public_names() -> None:
    assert set(pkg.__all__) == {
        'AllowFunc',
        'ModelOption',
        'ModelOut',
        'ModelSelection',
        'ModelSelectionCapability',
        'SupportsModelSelectionDeps',
        'UserDependency',
        'build_model_selection_router',
        'model_extras_type',
    }
    for name in pkg.__all__:
        assert getattr(pkg, name) is not None
