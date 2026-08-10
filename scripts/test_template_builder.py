#!/usr/bin/env python3
"""Проверить полноту и безопасную повторяемость физического builder v0.2."""

from __future__ import annotations

import json
import sys

from build_template_v0_2 import (
    DESCRIPTION_BY_KIND,
    DESCRIPTION_BY_SHEET,
    HELP_BY_KIND,
    HELP_BY_SHEET,
    build,
    id_formula,
    load_schema,
    validate_batch,
    version_id_formula,
)


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
    conditional_rules = [request for request in requests if "addConditionalFormatRule" in request]
    if len(conditional_rules) != 1:
        raise AssertionError("красная conditional formatting разрешена только на листе Проверки")
    checks_id = payload["sheet_ids"]["Проверки"]
    if conditional_rules[0]["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] != checks_id:
        raise AssertionError("условное форматирование не должно красить авторские строки")
    expected_id_formula = '=IF(C5="","",XLOOKUP(C5,selector_05,selector_05_ids,""))'
    if id_formula(2, 5, "selector_05", "selector_05_ids") != expected_id_formula:
        raise AssertionError("ID formula должна использовать точный lookup по парным каталогам")
    declared_id_formula = (
        schema["physical_contract"]["selector_id_formula"]
        .replace("<selector>", "C5")
        .replace("<labels_range>", "selector_05")
        .replace("<ids_range>", "selector_05_ids")
    )
    if declared_id_formula != expected_id_formula:
        raise AssertionError("JSON physical contract расходится с исполняемой selector ID formula")
    if version_id_formula(5) != '=IF($A5="","",\'Система\'!$B$4)':
        raise AssertionError("version_id должен оставаться пустым до появления stable ID строки")
    if tuple(DESCRIPTION_BY_SHEET) != tuple(schema["sheet_order"]):
        raise AssertionError("каждый лист должен иметь отдельное человеко-читаемое описание")
    visible_copy = " ".join(
        [*DESCRIPTION_BY_KIND.values(), *DESCRIPTION_BY_SHEET.values(), *HELP_BY_KIND.values(), *HELP_BY_SHEET.values()]
    ).lower()
    for internal_term in ("разреженн", "selector", "authoring row"):
        if internal_term in visible_copy:
            raise AssertionError(f"пользовательская подсказка содержит внутренний термин: {internal_term}")
    product_copy = f'{DESCRIPTION_BY_SHEET["Продукты"]} {HELP_BY_SHEET["Продукты"]}'.lower()
    if not all(term in product_copy for term in ("внутренн", "внешн", "поставщик", "производит")):
        raise AssertionError("лист Продукты не объясняет внутреннее производство и внешнюю поставку")

    formulas = [formula for request in requests for formula in _formula_values(request)]
    selector_formulas = [formula for formula in formulas if "XLOOKUP" in formula]
    if not selector_formulas or any(token in formula for formula in formulas for token in ("REGEXEXTRACT", "MID(")):
        raise AssertionError("builder должен получать ID lookup-формулой, а не извлекать его из видимого текста")
    if any('" [id="' in formula for formula in formulas):
        raise AssertionError("builder не должен встраивать ID в человеко-читаемую подпись")
    if "[id=" in visible_copy:
        raise AssertionError("пользовательские подсказки не должны показывать технический ID внутри названия")

    selector_label_names = [name for name in named if name.startswith("selector_") and not name.endswith("_ids")]
    selector_id_names = [name for name in named if name.startswith("selector_") and name.endswith("_ids")]
    if len(selector_label_names) != len(selector_id_names) or not selector_label_names:
        raise AssertionError("каждый selector должен иметь парный скрытый диапазон ID")

    number_formats = [
        request["repeatCell"]["cell"]["userEnteredFormat"]["numberFormat"]
        for request in requests
        if request.get("repeatCell", {}).get("cell", {}).get("userEnteredFormat", {}).get("numberFormat")
    ]
    patterns = {item["pattern"] for item in number_formats}
    if not {"dd.mm.yyyy", "dd.mm.yyyy hh:mm"}.issubset(patterns):
        raise AssertionError("builder должен форматировать date и datetime как читаемые даты")
    version_formulas = [formula for formula in formulas if "'Система'!$B$4" in formula and formula.startswith("=IF($A")]
    expected_versioned_sheets = sum(
        1
        for sheet in schema["sheets"].values()
        if sheet.get("kind") in {"versioned_authoring", "versioned_authoring_with_settings"}
        and "version_id" in sheet.get("columns", [])
    )
    if len(version_formulas) != expected_versioned_sheets or "='Система'!$B$4" in formulas:
        raise AssertionError("builder должен скрывать version_id на пустых capacity-строках")

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
