# LLM JSON Guard

A tiny Python package by **Aarnav Saboo** for a common AI-app problem: asking for JSON and receiving something that is almost JSON.

It extracts JSON from plain text or fenced responses and lets application code validate required keys before using the result.

```python
from llm_json_guard import extract_json, require_keys

raw = """Sure — here is the result:
```json
{"title": "Hello", "score": 0.91}
```
"""

data = extract_json(raw)
require_keys(data, ["title", "score"])
```

## Why

Structured model output is useful, but deterministic validation still belongs in application code. Parse it, validate it, then use it.

Built by **Aarnav Saboo**.

https://aarnavsaboo.github.io
