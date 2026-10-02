# LLM JSON Guard

**Schema-driven output validation and feedback loops for language-model pipelines.**

Parsing JSON is not the same as getting usable data. This package separates extraction, JSON Schema validation, task-specific checks and bounded regeneration. It is useful for structured NLP tasks such as entity extraction, classification and document metadata extraction.

Maintained by **Aarnav Saboo**. Python 3.10+, MIT.

## Install and run

```bash
python -m pip install -e .
python examples/extraction.py
python -m unittest discover -s tests -v
```

The example uses deterministic model responses. It validates entity offsets against a source sentence, feeds back the failing span check, and accepts the corrected result. No model account or API key is needed.

## Validate a response

```python
from llm_json_guard import OutputGuard

guard = OutputGuard({
    "type": "object",
    "properties": {"label": {"enum": ["positive", "negative", "neutral"]}},
    "required": ["label"],
    "additionalProperties": False,
})
result = guard.validate('{"label":"positive"}')
print(result.valid, result.data, result.issues)
```

Validation uses JSON Schema Draft 2020-12 through `jsonschema`, rather than a home-grown partial schema implementation. Errors contain JSON Pointer paths and failed keywords. There is no string-to-number coercion or automatic JSON repair.

## Connect a model

```python
from llm_json_guard import generate_validated

# Supply your own function: generate(prompt: str) -> str.
# It owns provider configuration, transport timeouts and billing limits.
result = generate_validated(generate, "Classify this text: ...", guard, max_attempts=3)
print(result.data)
print(len(result.attempts))
```

`agenerate_validated` supports async model functions. Validation failures produce bounded feedback; provider exceptions propagate immediately instead of silently retrying. The callback must return plain model text. The attempt limit is 1–10.

## Add task-specific checks

```python
from llm_json_guard import OutputGuard, validate_entity_spans

guard = OutputGuard(entity_schema, post_validate=lambda data:
    validate_entity_spans(data, source_text))
```

The included entity-span checker confirms that `text == source[start:end]`. Offsets use Python string indices. It does not judge whether an entity label is correct, whether every entity was found, or whether a response is factually true.

## Batch evaluation

```bash
llm-json-guard validate response.txt --schema examples/entities.schema.json
llm-json-guard batch responses.jsonl --schema examples/entities.schema.json
```

Batch input is one `{"id":"sample-1","output":"...model text..."}` record per line. Output includes per-record validation results and a schema pass rate. Exit codes: 0 for all valid, 1 for invalid outputs, 2 for configuration/file errors. Malformed records count as failures rather than stopping the entire batch.

## Parsing policies

By default, accept a complete JSON document or exactly one fenced JSON block. Set `allow_prose=True` to scan surrounding prose for a single decodable object/array. Multiple candidates are rejected as ambiguous. Prose extraction is heuristic: use the default policy for well-defined model interfaces.

Duplicate keys and non-JSON numeric constants are rejected. External schema references are not fetched; local `#/$defs/...` references are supported. Format checks are opt-in with `check_formats=True`; available formats follow your installed `jsonschema` dependencies.

## What this does not do

This is not a hallucination detector, a model server or a general NLP model. A passing schema checks structure, not truth. It does not execute tools, fix values, persist conversations or contact a provider on its own. Attempt records contain parsed data and validation messages; treat them as application data when logging.

See [the pipeline design](docs/design.md) and [the entity extraction example](examples/extraction.py).
