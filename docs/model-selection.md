# Model Selection

This guide shows you how to let clients choose the model for a run: configuring
the options, what a request sends, the listing for a dropdown, restricting
options per user, and using the pieces outside `create_agent_app`.

Prerequisites: an app assembled as in the factory's
[Building an app](https://github.com/aixbrain/pydantic-ai-app-factory/blob/main/docs/building-an-app.md).
Every name below imports from `pydantic_ai_model_selection`.

## Configuring options

Each option is a model under the key a request sends, with an optional label:

```python
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

selection = ModelSelection(
    options={
        'fast': ModelOption('openai:gpt-5-mini'),
        'gemini': ModelOption('google:gemini-3.5-flash'),
        'gateway-llama': ModelOption(
            OpenAIChatModel('llama-4', provider=OpenAIProvider(base_url=GATEWAY_URL, api_key=GATEWAY_KEY)),
            label='Llama (gateway)',
        ),
    },
)
app = create_agent_app(agent, auth=auth, features=[selection])
```

Options may come from different providers; each needs its `pydantic-ai-slim`
extra and key. Model strings are resolved when the feature is built, so a
missing provider key fails startup. The name is not checked against pydantic-ai's `KnownModelName`
list, which only gives editor completion; a newer model or one behind a gateway
works. For a second endpoint or credential at one provider, pass a `Model` with
its own provider, as for the gateway above.

A request that picks no model runs on the agent's own model, as it would
without the feature. A capability listed after this feature that also
implements `get_model()` overrides it. `agent.run(model=...)` and
`agent.override(model=...)` bypass the feature and `allow`; in tests, put test
models into `options` instead of using `override`.

## What clients send

The field is `model`: top level on `/chat`, inside `extras` on `/run`:

```json
{"prompt": "Summarize this.", "extras": {"model": "gateway-llama"}}
```

A key that is not an option is rejected with 422 before the run starts. The
keys appear as an enum in the extras schema on `GET /config`.

## Listing models

`GET /model-selection/models` sits behind the app's auth and returns the
options this caller may pick:

```json
[
  {"key": "fast", "label": "gpt-5-mini"},
  {"key": "gemini", "label": "gemini-3.5-flash"},
  {"key": "gateway-llama", "label": "Llama (gateway)"}
]
```

An option without a label shows its model's name. A frontend with its own
translations keys them on `key`.

## Restricting by user

`allow` takes the factory's `UserContext` and a key and returns whether that
user may use it. It may be sync or async. It filters the listing and runs
before every model request step, so keep it cheap:

```python
selection = ModelSelection(
    options=options,
    allow=lambda user, key: key == 'fast' or 'premium' in user.scopes,
)
```

A denied key answers 403 with code `model-selection/forbidden`; on `/chat` it
arrives as a `data-error` chunk, because the stream has started. A request
without `model` runs on the agent's model and is not checked, so the agent's
model is open to every user.

Two things reach callers regardless of `allow`:

- **Every key.** `GET /config` is unauthenticated and its schema lists all
  keys. Name them accordingly.
- **The provider URL.** The messages in a `/run` response name the model and
  its provider URL, so a gateway URL reaches every `/run` caller.

## Use without create_agent_app

The capability and the router work with any `Agent` and FastAPI app;
`pydantic-ai-app-factory` stays installed because the capability raises its
`AgentError`. The deps object needs readable `user` and `extras` attributes:

```python
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI
from pydantic_ai import Agent
from pydantic_ai.models import infer_model

from pydantic_ai_model_selection import ModelSelectionCapability, build_model_selection_router, model_extras_type


@dataclass(frozen=True)
class MyUser:
    user_id: str


@dataclass
class MyDeps:
    user: MyUser
    extras: Mapping[str, Any] = field(default_factory=dict)


models = {'fast': infer_model('openai:gpt-5-mini'), 'thorough': infer_model('openai:gpt-5')}
agent = Agent('openai:gpt-5-mini', deps_type=MyDeps, capabilities=[ModelSelectionCapability[MyDeps](models=models)])
# inside an async function
result = await agent.run('Summarize this.', deps=MyDeps(user=MyUser('u1'), extras={'model': 'thorough'}))

RequestExtras = model_extras_type(models)  # validate request bodies with this

app = FastAPI()
app.include_router(
    build_model_selection_router(labels={'fast': 'Fast', 'thorough': 'Thorough'}, allow=None, auth=my_auth)
)
```

Validate request bodies with `model_extras_type`; an unvalidated unknown key
raises a `KeyError` in the run. Without the factory's error handler, a denied
key is a plain 500.

pydantic-ai cannot resume a suspended background response under a model
selector; that resume raises a `UserError`, reported by the factory as
`internal`.

## Reference

```python
ModelOption(model: Model | KnownModelName | str, *, label: str | None = None)

ModelSelection(*, options: Mapping[str, ModelOption],
               allow: Callable[[UserContext, str], bool | Awaitable[bool]] | None = None)
# name = 'model-selection'; ValueError for empty options

ModelSelectionCapability[DepsT](models: Mapping[str, Model], allow: AllowFunc | None = None)
# AllowFunc = Callable[[Any, str], bool | Awaitable[bool]]
# DepsT is bound to SupportsModelSelectionDeps (read-only `user` and `extras`)

model_extras_type(keys: Iterable[str]) -> type[BaseModel]
# one field: model: Literal[*keys] | None = None

build_model_selection_router(*, labels: Mapping[str, str], allow: AllowFunc | None,
                             auth: UserDependency) -> APIRouter
# GET /model-selection/models -> list[ModelOut(key, label)]
```

| Code | HTTP status | When |
|---|---|---|
| (validation) | 422 | `model` is not a configured key |
| `model-selection/forbidden` | 403 | `allow(user, key)` is false |

For tests, follow the factory's
[Testing](https://github.com/aixbrain/pydantic-ai-app-factory/blob/main/docs/testing.md)
guide; a `TestModel(custom_output_text=...)` per option shows which one ran.
