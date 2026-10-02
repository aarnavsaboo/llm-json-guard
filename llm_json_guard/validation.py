"""JSON Schema validation with machine-readable paths and semantic hooks."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable
from jsonschema import Draft202012Validator, FormatChecker
from .parsing import OutputParseError, extract_json


@dataclass(frozen=True)
class Issue:
    path: str
    keyword: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    data: Any
    issues: list[Issue]

    def as_dict(self) -> dict:
        return asdict(self)


def _pointer(parts) -> str:
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts) if parts else ""


def _local_refs_only(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef"} and isinstance(child, str) and not child.startswith("#"):
                raise ValueError("Only local schema references are supported")
            _local_refs_only(child)
    elif isinstance(value, list):
        for child in value:
            _local_refs_only(child)


class OutputGuard:
    def __init__(self, schema: dict | bool, *, allow_prose: bool = False,
                 max_chars: int = 1_000_000, check_formats: bool = False,
                 post_validate: Callable[[Any], Iterable[Issue]] | None = None):
        if max_chars < 1:
            raise ValueError("max_chars must be positive")
        schema = deepcopy(schema)
        Draft202012Validator.check_schema(schema)
        _local_refs_only(schema)
        self.schema = schema
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker() if check_formats else None)
        self.allow_prose, self.max_chars = allow_prose, max_chars
        self.post_validate = post_validate

    def validate(self, text: str) -> ValidationResult:
        try:
            value = extract_json(text, allow_prose=self.allow_prose, max_chars=self.max_chars)
        except (OutputParseError, TypeError) as exc:
            return ValidationResult(False, None, [Issue("", "parse", str(exc))])
        issues = [Issue(_pointer(error.absolute_path), str(error.validator), error.message)
                  for error in self.validator.iter_errors(value)]
        issues.sort(key=lambda issue: (issue.path, issue.keyword, issue.message))
        if not issues and self.post_validate:
            issues.extend(self.post_validate(value))
        return ValidationResult(not issues, value, issues)


def validate_entity_spans(data: Any, source: str) -> list[Issue]:
    """Check extracted surface forms against Python string offsets.

    Expected shape: {"entities": [{"text": ..., "start": ..., "end": ...}]}.
    This checks span consistency, not completeness or label correctness.
    """
    issues = []
    if not isinstance(data, dict) or not isinstance(data.get("entities"), list):
        return [Issue("/entities", "span", "Expected an entities list")]
    for i, entity in enumerate(data["entities"]):
        path = f"/entities/{i}"
        if not isinstance(entity, dict):
            issues.append(Issue(path, "span", "Expected an entity object"))
            continue
        start, end = entity.get("start"), entity.get("end")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source):
            issues.append(Issue(path, "span", "Invalid source offsets"))
        elif entity.get("text") != source[start:end]:
            issues.append(Issue(path + "/text", "span", "Text does not match the source span"))
    return issues
