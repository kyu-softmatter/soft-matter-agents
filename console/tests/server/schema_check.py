"""A small JSON Schema checker for the question_request schema.

The console's environment has no jsonschema (its lock is resolved offline), and a test must read
the schema from the repository (`contracts/schemas/question_request.schema.json`) and not a copy.
So this reads the keywords that schema uses -- `type`, `const`, `enum`, `pattern`, `minLength`,
`maxLength`, `format: date-time`, `required`, `properties`, `additionalProperties: false`, `items`,
`uniqueItems` -- and raises on any other keyword rather than skipping it, so a schema that grows a
rule this checker cannot judge fails loudly. `test_question_requests.py` runs it against the
repository's own example and rejected fixtures, so the checker itself is watched to accept and to reject.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sma_console.agents.sma_files import repository_root

SCHEMA_PATH = repository_root() / "contracts" / "schemas" / "question_request.schema.json"
KNOWN = {
    "$schema", "$id", "title", "description", "type", "const", "enum", "pattern", "minLength", "maxLength",
    "format", "required", "properties", "additionalProperties", "items", "uniqueItems",
}


def schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))


def problems(value: Any, spec: dict[str, Any] | None = None, path: str = "$") -> list[str]:
    """Every way `value` fails `spec` (default: the repository's question_request schema)."""
    spec = schema() if spec is None else spec
    unknown = set(spec) - KNOWN
    if unknown:
        raise AssertionError(f"{path}: this checker does not know {sorted(unknown)}")
    out: list[str] = []
    kind = spec.get("type")
    py = {"object": dict, "string": str, "boolean": bool, "array": list}
    if kind is not None and (not isinstance(value, py[kind]) or (kind != "boolean" and isinstance(value, bool))):
        return [f"{path}: not a {kind}"]
    if "const" in spec and value != spec["const"]:
        out.append(f"{path}: not {spec['const']!r}")
    if "enum" in spec and value not in spec["enum"]:
        out.append(f"{path}: not one of {spec['enum']}")
    if isinstance(value, str):
        if "minLength" in spec and len(value) < spec["minLength"]:
            out.append(f"{path}: shorter than {spec['minLength']}")
        if "maxLength" in spec and len(value) > spec["maxLength"]:
            out.append(f"{path}: longer than {spec['maxLength']}")
        if "pattern" in spec and re.search(spec["pattern"], value) is None:
            out.append(f"{path}: does not match {spec['pattern']}")
        if spec.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                if not value.endswith("Z") and not re.search(r"[+-]\d\d:\d\d$", value):
                    out.append(f"{path}: a date-time carries a zone")
            except ValueError:
                out.append(f"{path}: not a date-time")
    if isinstance(value, dict):
        for key in spec.get("required", []):
            if key not in value:
                out.append(f"{path}: missing {key}")
        props = spec.get("properties", {})
        if spec.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    out.append(f"{path}: key {key!r} is not in the schema")
        for key, sub in props.items():
            if key in value:
                out += problems(value[key], sub, f"{path}.{key}")
    if isinstance(value, list):
        if spec.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            out.append(f"{path}: items repeat")
        if "items" in spec:
            for i, item in enumerate(value):
                out += problems(item, spec["items"], f"{path}[{i}]")
    return out


def conforms(value: Any) -> bool:
    return not problems(value)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))
