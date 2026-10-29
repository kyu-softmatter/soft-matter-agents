"""A small JSON Schema checker, for the contracts' own schemas (console card 012).

The console's environment has no `jsonschema` (its lock is resolved offline and nothing may be
installed), and two screens must check against the schemas **as the repository has them**: the idle
status file the runtime writes, and a plan draft before it is shown. So this reads the keywords those
schemas use and **raises on any keyword it cannot judge**, instead of passing over it: a schema that
grows a rule this checker does not know fails loudly, which is the safe direction.

Supported: `type`, `const`, `enum`, `pattern`, `minLength`, `maxLength`, `minimum`, `maximum`,
`exclusiveMinimum`, `exclusiveMaximum`, `format` (`date`, `date-time`; other formats are annotations),
`required`, `dependentRequired`, `properties`, `additionalProperties`, `unevaluatedProperties`,
`propertyNames`, `minProperties`, `maxProperties`, `items`, `prefixItems`, `minItems`, `maxItems`,
`uniqueItems`, `contains`, `allOf`, `anyOf`, `oneOf`, `not`,
`if`/`then`/`else`, and `$ref` to `#/...` or to a sibling schema file (`common.schema.json#/$defs/x`).
Annotations (`description`, `$comment`, `title`, `$id`, `$schema`, `$defs`, anything starting `x_`) are
ignored. It is run against the repository's own examples and its rejected fixtures in `tests/`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ANNOTATIONS = {"$schema", "$id", "$comment", "description", "title", "default", "examples", "$defs",
               "definitions", "deprecated", "readOnly"}
KNOWN = {
    "type", "const", "enum", "pattern", "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "format", "required", "properties", "additionalProperties", "unevaluatedProperties",
    "propertyNames", "minProperties", "maxProperties", "dependentRequired", "items", "prefixItems", "minItems",
    "maxItems", "uniqueItems", "contains", "allOf", "anyOf",
    "oneOf", "not", "if", "then", "else", "$ref",
}
_DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SchemaError(Exception):
    """The schema uses something this checker cannot judge, or names a schema that is not there."""


def _is(value: Any, kind: str) -> bool:
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "null":
        return value is None
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool) or (isinstance(value, float) and value.is_integer())
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    raise SchemaError(f"unknown type {kind!r}")


def _canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


class Schemas:
    """The schema files of one folder (`contracts/schemas/`), loaded when first named."""

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)
        self._docs: dict[str, Any] = {}

    def _doc(self, name: str) -> Any:
        if name not in self._docs:
            path = self.folder / name
            try:
                self._docs[name] = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as e:
                raise SchemaError(f"schema {name} cannot be read: {e}") from e
        return self._docs[name]

    def validate(self, instance: Any, name: str) -> list[str]:
        """Every way `instance` fails the schema file `name`; empty when it conforms."""
        errors, _ = self._eval(instance, self._doc(name), name, "$")
        return errors

    def validate_def(self, instance: Any, name: str, pointer: str) -> list[str]:
        """The same, against one definition inside the schema file `name` (`#/$defs/<x>`), so a part of a
        document can be judged by the schema's own words without the rest of it."""
        errors, _ = self._eval(instance, {"$ref": pointer}, name, "$")
        return errors

    def conforms(self, instance: Any, name: str) -> bool:
        return not self.validate(instance, name)

    # -- the walk -------------------------------------------------------------------------------

    def _resolve(self, ref: str, base: str) -> tuple[Any, str]:
        file, _, pointer = ref.partition("#")
        target = file or base
        node = self._doc(target)
        for part in [p for p in pointer.split("/") if p]:
            part = part.replace("~1", "/").replace("~0", "~")
            try:
                node = node[part]
            except (KeyError, TypeError) as e:
                raise SchemaError(f"{ref} does not resolve in {target}") from e
        return node, target

    def _eval(self, inst: Any, schema: Any, base: str, path: str) -> tuple[list[str], set[str]]:
        """(errors, names of the object's properties this schema evaluated)."""
        if schema is True:
            return [], set(inst) if isinstance(inst, dict) else set()
        if schema is False:
            return [f"{path}: nothing is allowed here"], set()
        if not isinstance(schema, dict):
            raise SchemaError(f"{path}: a schema is an object or a boolean")
        for key in schema:
            if key not in KNOWN and key not in ANNOTATIONS and not key.startswith("x_"):
                raise SchemaError(f"{base}: the keyword {key!r} is not one this checker can judge")
        errs: list[str] = []
        seen: set[str] = set()

        def sub(i: Any, s: Any, at: str, b: str = base) -> tuple[list[str], set[str]]:
            return self._eval(i, s, b, at)

        if "$ref" in schema:
            node, where = self._resolve(schema["$ref"], base)
            e, s = self._eval(inst, node, where, path)
            errs += e
            seen |= s
        if "type" in schema:
            kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_is(inst, k) for k in kinds):
                return errs + [f"{path}: not {' or '.join(kinds)}"], seen
        if "const" in schema and _canon(inst) != _canon(schema["const"]):
            errs.append(f"{path}: is not {schema['const']!r}")
        if "enum" in schema and not any(_canon(inst) == _canon(v) for v in schema["enum"]):
            errs.append(f"{path}: is not one of {schema['enum']}")
        if isinstance(inst, str):
            if "minLength" in schema and len(inst) < schema["minLength"]:
                errs.append(f"{path}: shorter than {schema['minLength']}")
            if "maxLength" in schema and len(inst) > schema["maxLength"]:
                errs.append(f"{path}: longer than {schema['maxLength']}")
            if "pattern" in schema and re.search(schema["pattern"], inst) is None:
                errs.append(f"{path}: does not match {schema['pattern']}")
            if schema.get("format") == "date-time" and not _DATE_TIME.match(inst):
                errs.append(f"{path}: not a date-time")
            if schema.get("format") == "date" and not _DATE.match(inst):
                errs.append(f"{path}: not a date")
        if isinstance(inst, (int, float)) and not isinstance(inst, bool):
            if "minimum" in schema and inst < schema["minimum"]:
                errs.append(f"{path}: below {schema['minimum']}")
            if "maximum" in schema and inst > schema["maximum"]:
                errs.append(f"{path}: above {schema['maximum']}")
            if "exclusiveMinimum" in schema and inst <= schema["exclusiveMinimum"]:
                errs.append(f"{path}: not above {schema['exclusiveMinimum']}")
            if "exclusiveMaximum" in schema and inst >= schema["exclusiveMaximum"]:
                errs.append(f"{path}: not below {schema['exclusiveMaximum']}")
        if isinstance(inst, dict):
            for r in schema.get("required", []):
                if r not in inst:
                    errs.append(f"{path}: {r} is required")
            props = schema.get("properties", {})
            for k, v in inst.items():
                if k in props:
                    e, _ = sub(v, props[k], f"{path}.{k}")
                    errs += e
                    seen.add(k)
            if "propertyNames" in schema:
                for k in inst:
                    e, _ = sub(k, schema["propertyNames"], f"{path}.<{k}>")
                    errs += e
            if "minProperties" in schema and len(inst) < schema["minProperties"]:
                errs.append(f"{path}: fewer than {schema['minProperties']} properties")
            if "maxProperties" in schema and len(inst) > schema["maxProperties"]:
                errs.append(f"{path}: more than {schema['maxProperties']} properties")
            for k, needs in schema.get("dependentRequired", {}).items():
                if k in inst:
                    errs += [f"{path}: {n} is required when {k} is present" for n in needs if n not in inst]
            if "additionalProperties" in schema:
                extra = schema["additionalProperties"]
                for k, v in inst.items():
                    if k not in props:
                        if extra is False:
                            errs.append(f"{path}: {k!r} is not allowed here")
                        elif extra is not True:
                            e, _ = sub(v, extra, f"{path}.{k}")
                            errs += e
                        seen.add(k)
        if isinstance(inst, list):
            if "minItems" in schema and len(inst) < schema["minItems"]:
                errs.append(f"{path}: fewer than {schema['minItems']} items")
            if "maxItems" in schema and len(inst) > schema["maxItems"]:
                errs.append(f"{path}: more than {schema['maxItems']} items")
            for i, s in enumerate(schema.get("prefixItems", [])):
                if i < len(inst):
                    e, _ = sub(inst[i], s, f"{path}[{i}]")
                    errs += e
            if schema.get("uniqueItems") and len({_canon(v) for v in inst}) != len(inst):
                errs.append(f"{path}: items repeat")
            if "items" in schema:
                for i, v in enumerate(inst):
                    if i >= len(schema.get("prefixItems", [])):
                        e, _ = sub(v, schema["items"], f"{path}[{i}]")
                        errs += e
            if "contains" in schema and not any(not sub(v, schema["contains"], f"{path}[{i}]")[0] for i, v in enumerate(inst)):
                errs.append(f"{path}: no item matches `contains`")
        for s in schema.get("allOf", []):
            e, k = sub(inst, s, path)
            errs += e
            seen |= k
        if "anyOf" in schema:
            results = [sub(inst, s, path) for s in schema["anyOf"]]
            ok = [r for r in results if not r[0]]
            if not ok:
                errs.append(f"{path}: matches none of the allowed shapes ({'; '.join(r[0][0] for r in results if r[0])[:240]})")
            for r in ok:
                seen |= r[1]
        if "oneOf" in schema:
            results = [sub(inst, s, path) for s in schema["oneOf"]]
            ok = [r for r in results if not r[0]]
            if len(ok) != 1:
                why = "none" if not ok else "more than one"
                errs.append(f"{path}: matches {why} of the allowed shapes ({'; '.join(r[0][0] for r in results if r[0])[:240]})")
            for r in ok[:1]:
                seen |= r[1]
        if "not" in schema and not sub(inst, schema["not"], path)[0]:
            errs.append(f"{path}: matches what is not allowed")
        if "if" in schema:
            matched = not sub(inst, schema["if"], path)[0]
            branch = schema.get("then") if matched else schema.get("else")
            if branch is not None:
                e, k = sub(inst, branch, path)
                errs += e
                seen |= k
        if "unevaluatedProperties" in schema and isinstance(inst, dict):
            extra = schema["unevaluatedProperties"]
            for k, v in inst.items():
                if k not in seen:
                    if extra is False:
                        errs.append(f"{path}: {k!r} is not allowed here")
                    elif extra is not True:
                        e, _ = sub(v, extra, f"{path}.{k}")
                        errs += e
                    seen.add(k)
        return errs, seen
