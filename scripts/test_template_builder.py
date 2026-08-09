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
    expected_id_formula = '=IF(C5="","",IFERROR(REGEXEXTRACT(C5,"\\[id=([^\\]]+)\\]"),""))'
    if id_formula(2, 5) != expected_id_formula:
        raise AssertionError("ID formula должна использовать проверенный в Google Sheets REGEXEXTRACT-контракт")
    declared_id_formula = schema["physical_contract"]["selector_id_formula"].replace("<selector>", "C5")
    if declared_id_formula != expected_id_formula:
        raise AssertionError("JSON physical contract расходится с исполняемой selector ID formula")

    formulas = [formula for request in requests for formula in _formula_values(request)]
    selector_formulas = [formula for formula in formulas if "REGEXEXTRACT" in formula]
    if not selector_formulas or any("MID(" in formula for formula in formulas):
        raise AssertionError("builder вернул старую непарсящуюся MID/FIND selector-формулу")

    created_sheets = [request["addSheet"]["properties"] for request in requests if "addSheet" in request]
    public_sheets = [properties for properties in created_sheets if properties["title"] != "__v02_migration__"]
    if len(public_sheets) != 29 or not all(properties["gridProperties"].get("hideGridlines") for properties in public_sheets):
        raise AssertionError("все 29 публичных листов должны создаваться со скрытой сеткой")
    if request_types.count("mergeCells") < 80:
        raise AssertionError("builder не создаёт заголовочные и секционные объединения v0.2")
    if not any(
        request.get("repeatCell", {}).get("cell", {}).get("userEnteredFormat", {}).get("textFormat", {}).get("fontSize") == 16
        for request in requests
    ):
        raise AssertionError("builder не создаёт визуальную иерархию с заголовком 16 pt")

    # JSON roundtrip доказывает, что payload можно передать raw batchUpdate без
    # нестандартных Python-типов.
    json.loads(json.dumps(payload, ensure_ascii=False))
    print(f"[OK] Physical builder: {payload['request_count']} requests, {len(named)} named ranges")
    return 0


def _formula_values(value: object) -> list[str]:
    """Рекурсивно извлечь formulaValue без привязки к request type."""
    found: list[str] = []
    if isinstance(value, dict):
        if isinstance(value.get("formulaValue"), str):
            found.append(value["formulaValue"])
        for nested in value.values():
            found.extend(_formula_values(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_formula_values(nested))
    return found


if __name__ == "__main__":
    sys.exit(main())
