# pydantic-ai-model-selection

## Module layout

Public modules are the API: `feature.py` (the `Feature` products compose in) and `__init__.py`
(the supported import surface, re-exporting the capability, the router builder and the wire
models from their private modules). Every other module is a private implementation detail and
underscore-prefixed; nothing outside this package may import one.

- `pydantic_ai_model_selection/_capability.py` -- the request field (`model_extras_type`) and the
  selector that reads it (`ModelSelectionCapability`); they share one key, so they share a module
- `pydantic_ai_model_selection/_routes.py` -- `GET /model-selection/models` and its wire models
- `pydantic_ai_model_selection/feature.py` -- `ModelOption`, `ModelSelection`

## Design rules

- Validation is split along one line: whether a key is a configured option is checked by the
  request model at the boundary (422); whether this user may use it is checked by the capability
  in the run (403), because only the run has the user and the key together.
- Everything is fixed at startup. Model strings are resolved in the constructor so a missing
  provider key fails startup, not the first request that picks that option. The package adds no
  credential check of its own: pydantic-ai raises for a missing key.
- The route returns keys and labels only, never a model, provider, URL or credential.
- Capability and router work outside `create_agent_app`; `feature.py` is the only module that
  imports the `Feature` base class.

## Coding standards

- Python 3.11+
- pyright strict; avoid `Any` in public signatures where practical
- ruff: line-length 120, single quotes, max-complexity 15
- 100% branch coverage, enforced by `make testcov`
- docstrings use single backticks (markdown), not RST double backticks
- no em-dashes in prose, docstrings, comments, or commit messages; use `--`
- document the why and the non-obvious; don't restate what the code says

## Commands

```bash
make install      # uv sync
make format       # ruff format (rewrites files)
make format-check # ruff format --check
make lint         # ruff check
make typecheck    # pyright strict
make test         # pytest
make testcov      # pytest with 100% branch coverage
make all          # lint + format-check + typecheck + testcov
```

Run `make all` before every commit.

## Testing patterns

- No real model calls: `ALLOW_MODEL_REQUESTS = False` in `tests/conftest.py`
- Standalone test functions, not test classes
- Options under test are `TestModel(custom_output_text=...)` instances, so a test can tell which
  one answered; `infer_model('test')` covers the string-option path without a provider key
- Tests import from the package root only; mark genuinely unreachable branches `# pragma: no cover`
