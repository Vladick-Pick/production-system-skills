#!/usr/bin/env python3
"""Проверить полноту и безопасную повторяемость физического builder v0.2."""

from __future__ import annotations

import json
import sys

from build_template_v0_2 import build, id_formula, load_schema, validate_batch


def main() -> int:
    schema = load_schema()
    payload = build(
        schema,
        existing_ids=[101, 102],
        existing_named_range_ids=["nr-enum", "nr-selector"],
        title="Template builder fixture",
    )
    validate_batch(payload)
    requests = payload["requests"]
    request_types = [next(iter(request)) for request in requests]

    first_delete_named = request_types.index("deleteNamedRange")
    first_delete_sheet = request_types.index("deleteSheet")
    if first_delete_named >= first_delete_sheet:
        raise AssertionError("named ranges должны удаляться раньше исходных листов")
    if request_types.count("deleteNamedRange") != 2:
        raise AssertionError("builder не удаляет все переданные named ranges")
    if tuple(payload["sheet_ids"]) != tuple(schema["sheet_order"]):
        raise AssertionError("builder нарушил порядок 29 листов")

    named = [
        request["addNamedRange"]["namedRange"]["name"]
        for request in requests
        if "addNamedRange" in request
    ]
    if len(named) != len(set(named)):
        raise AssertionError("builder создаёт повторяющиеся имена named ranges")
    if not any("setDataValidation" in request for request in requests):
        raise AssertionError("builder не создаёт dropdown validations")
    if not any("addProtectedRange" in request for request in requests):
        raise AssertionError("builder не создаёт protected ranges")
    if not any("addConditionalFormatRule" in request for request in requests):
        raise AssertionError("builder не создаёт conditional formatting")
    if "[id=" not in id_formula(2, 5):
        raise AssertionError("ID formula не использует устойчивый ASCII selector marker")

    # JSON roundtrip доказывает, что payload можно передать raw batchUpdate без
    # нестандартных Python-типов.
    json.loads(json.dumps(payload, ensure_ascii=False))
    print(f"[OK] Physical builder: {payload['request_count']} requests, {len(named)} named ranges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
