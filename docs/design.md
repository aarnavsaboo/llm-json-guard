# Structured extraction design

The pipeline has four explicit boundaries:

1. **Parse** one model response using a declared extraction policy.
2. **Validate** data against a checked JSON Schema.
3. **Check task constraints** with an optional caller-supplied validator.
4. **Regenerate** with bounded, machine-readable feedback when validation fails.

A malformed schema is a configuration error, not a failed model response. It raises during guard construction. A malformed model response becomes a `ValidationResult` with a parse issue. A provider exception is not swallowed by the feedback loop: provider retries belong in the integration layer.

## Feedback and attempts

The next prompt retains the original request and schema and includes at most ten issues, capped to 4,000 feedback characters. It does not automatically echo the entire previous response. Attempts retain validation results for inspection. The default is three attempts and the hard configurable ceiling is ten. This is a validation-attempt budget, not a time, token or monetary budget.

## Extraction is not repair

A fenced response can be parsed without changing its contents. Malformed commas, single-quoted dictionaries and mismatched types are not rewritten. In optional prose mode, the decoder scans for decodable containers and requires exactly one candidate. That policy cannot determine a model's intended answer; avoid it where ambiguity matters.

## Entity spans as a semantic hook

Schema validation can establish that an extraction has strings and integer offsets. A post-validator can additionally compare each span with the original source. This still cannot establish the correctness of entity categories or detect missing entities. Keep completeness and task accuracy evaluation separate from schema pass rate.

Reference: [jsonschema validation API](https://python-jsonschema.readthedocs.io/en/stable/validate/).
