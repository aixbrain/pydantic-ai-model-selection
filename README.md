# Per-Request Model Selection for Pydantic AI Apps

`pydantic-ai-model-selection` is a feature for
[pydantic-ai-app-factory](https://github.com/aixbrain/pydantic-ai-app-factory) that lets a client pick
the model for one run from a list the operator fixes at startup. It validates the choice at the
boundary, can restrict options per user, and serves the list a frontend dropdown reads.

> [!NOTE]
> This package is in early development, the API might still change before v1.0.

## Quick Start

Install the package:

```bash
pip install pydantic-ai-model-selection "pydantic-ai-slim[openai]"
```

Create a file `main.py` with:

```python
from pydantic_ai_app_factory import UserContext, create_agent, create_agent_app
from pydantic_ai_model_selection import ModelOption, ModelSelection


def auth() -> UserContext:
    return UserContext(user_id='demo')


selection = ModelSelection(
    options={
        'fast': ModelOption('openai:gpt-5-mini', label='Fast'),
        'thorough': ModelOption('openai:gpt-5'),
    },
)
agent = create_agent('openai:gpt-5-mini', instructions='You are a helpful assistant.')
app = create_agent_app(agent, auth=auth, features=[selection])
```

A request that names no model runs on the agent's own model. Set `OPENAI_API_KEY` in the
environment; a missing provider key fails startup.

Launch it like any other FastAPI app:

```bash
pip install "fastapi[standard]"
fastapi dev
```

A request names its model as a top-level field on `/chat`, or under `extras` on `/run`:

```bash
curl -N http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"id": "test-1", "trigger": "submit-message", "model": "thorough", "messages": [{"id": "m1", "role": "user", "parts": [{"type": "text", "text": "Hello"}]}]}'
```

`GET /model-selection/models` returns the options this caller may pick, with their labels.

## Documentation

[Model selection](https://github.com/aixbrain/pydantic-ai-model-selection/blob/main/docs/model-selection.md)
covers the options, per-user restrictions, the listing route, use without `create_agent_app`, and the
reference. It builds on the factory's
[Features](https://github.com/aixbrain/pydantic-ai-app-factory/blob/main/docs/features.md).

## Motivation

Pydantic AI can already pick a model per run through a capability's
[`get_model()`](https://pydantic.dev/docs/ai/capabilities/custom/#selecting-the-model), and its models
share one interface across providers. So the options can mix OpenAI, Google and a self-hosted
gateway, and this package only wraps the hook as an app-factory feature.

## Contributing

Contributions under Apache-2.0 are welcome; please open an issue first. `make install` sets up the
environment and `make all` must pass before a commit. Conventions are in
[AGENTS.md](https://github.com/aixbrain/pydantic-ai-model-selection/blob/main/AGENTS.md).

## License

[Apache-2.0](https://github.com/aixbrain/pydantic-ai-model-selection/blob/main/LICENSE)
