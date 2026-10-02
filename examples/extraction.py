import json
from pathlib import Path
from llm_json_guard import OutputGuard, generate_validated, validate_entity_spans

source = "Ada works at Orion."
schema = json.loads((Path(__file__).parent / "entities.schema.json").read_text())
guard = OutputGuard(schema, post_validate=lambda data: validate_entity_spans(data, source))
responses = iter([
    '{"entities": [{"text":"Ada","label":"PERSON","start":1,"end":3}]}',
    '{"entities": [{"text":"Ada","label":"PERSON","start":0,"end":3}]}'
])
# Deterministic stand-in for a model call: this example makes no network requests.
result = generate_validated(lambda prompt: next(responses), "Extract entities: " + source, guard)
print(json.dumps(result.data, indent=2))
print(f"Accepted after {len(result.attempts)} attempts")
