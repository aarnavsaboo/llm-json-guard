"""Bounded generation/validation loops using caller-owned model functions."""
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
import json
from .validation import OutputGuard, ValidationResult


@dataclass(frozen=True)
class GenerationResult:
    data: Any
    attempts: list[ValidationResult]


class GenerationFailed(ValueError):
    def __init__(self, attempts: list[ValidationResult]):
        super().__init__(f"No valid output after {len(attempts)} attempts")
        self.attempts = attempts


def _check_attempts(max_attempts: int):
    if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
        raise ValueError("max_attempts must be an integer from 1 to 10")


def _next_prompt(prompt: str, guard: OutputGuard, previous: ValidationResult | None) -> str:
    instruction = prompt + "\n\nReturn JSON matching this schema:\n" + json.dumps(guard.schema)
    if previous:
        feedback = [{"path": i.path, "keyword": i.keyword, "message": i.message}
                    for i in previous.issues[:10]]
        instruction += "\nThe last response failed validation. Correct these issues:\n" + json.dumps(feedback)[:4000]
    return instruction


def generate_validated(generate: Callable[[str], str], prompt: str, guard: OutputGuard,
                       max_attempts: int = 3) -> GenerationResult:
    _check_attempts(max_attempts)
    attempts = []
    for _ in range(max_attempts):
        text = generate(_next_prompt(prompt, guard, attempts[-1] if attempts else None))
        result = guard.validate(text)
        attempts.append(result)
        if result.valid:
            return GenerationResult(result.data, attempts)
    raise GenerationFailed(attempts)


async def agenerate_validated(generate: Callable[[str], Awaitable[str]], prompt: str,
                              guard: OutputGuard, max_attempts: int = 3) -> GenerationResult:
    _check_attempts(max_attempts)
    attempts = []
    for _ in range(max_attempts):
        text = await generate(_next_prompt(prompt, guard, attempts[-1] if attempts else None))
        result = guard.validate(text)
        attempts.append(result)
        if result.valid:
            return GenerationResult(result.data, attempts)
    raise GenerationFailed(attempts)
