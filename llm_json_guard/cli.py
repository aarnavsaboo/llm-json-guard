import argparse
import json
import sys
from pathlib import Path
from jsonschema.exceptions import SchemaError
from .validation import OutputGuard


def main():
    parser = argparse.ArgumentParser(description="Validate structured model output against JSON Schema")
    parser.add_argument("mode", choices=["validate", "batch"])
    parser.add_argument("input")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--allow-prose", action="store_true")
    args = parser.parse_args()
    try:
        guard = OutputGuard(json.loads(Path(args.schema).read_text(encoding="utf-8")), allow_prose=args.allow_prose)
        if args.mode == "validate":
            result = guard.validate(Path(args.input).read_text(encoding="utf-8"))
            print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, allow_nan=False))
            return 0 if result.valid else 1
        rows = []
        for line_no, line in enumerate(Path(args.input).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                result = guard.validate(item["output"])
                rows.append({"line": line_no, "id": item.get("id"), **result.as_dict()})
            except (ValueError, TypeError, KeyError) as exc:
                rows.append({"line": line_no, "valid": False, "error": str(exc)})
        passed = sum(row["valid"] for row in rows)
        print(json.dumps({"total": len(rows), "passed": passed,
                          "pass_rate": passed / len(rows) if rows else None,
                          "results": rows}, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if passed == len(rows) else 1
    except (OSError, ValueError, TypeError, SchemaError) as exc:
        print(f"llm-json-guard: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
