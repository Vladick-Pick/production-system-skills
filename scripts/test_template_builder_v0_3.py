#!/usr/bin/env python3
"""Проверить additive schema, реестры развития и панель шаблона v0.3."""

from __future__ import annotations

import json
import re
import sys

import build_template_v0_2 as base
from build_template_v0_3 import configure_copy, load_schema


EXPECTED_NEW_SHEETS = ("Отклонения", "Гипотезы", "Эксперименты")


def formula_values(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if isinstance(value.get("formulaValue"), str):
            found.append(value["formulaValue"])
        for nested in value.values():
            found.extend(formula_values(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(formula_values(nested))
    return found


def main() -> int:
    configure_copy()
    schema = load_schema()
    if schema["schema_version"] != "0.3" or len(schema["sheet_order"]) != 32:
        raise AssertionError("итоговая schema v0.3 должна содержать 32 листа")
    anchor = schema["sheet_order"].index("Изменения модели") + 1
    if tuple(schema["sheet_order"][anchor : anchor + 3]) != EXPECTED_NEW_SHEETS:
        raise AssertionError("три реестра развития стоят не после истории модели")
    if schema["sheet_order"][:anchor] != base.load_schema()["sheet_order"][:anchor]:
        raise AssertionError("overlay v0.3 изменяет порядок базовых листов до точки вставки")

    for sheet_name in EXPECTED_NEW_SHEETS:
        sheet = schema["sheets"][sheet_name]
        if sheet.get("kind") != "development_registry":
            raise AssertionError(f"{sheet_name}: неверный storage class")
        if sheet.get("freeze_columns") != 3:
            raise AssertionError(f"{sheet_name}: первые ID, название и статус должны оставаться видимыми")
        columns = sheet["columns"]
        if len(columns) != len(set(columns)):
            raise AssertionError(f"{sheet_name}: повторяющиеся колонки")
        selectors = sheet.get("selectors", {})
        for field, selector in selectors.items():
            if field not in columns or selector not in columns:
                raise AssertionError(f"{sheet_name}: нарушена соседняя ID/selector пара")
            if columns.index(selector) != columns.index(field) + 1:
                raise AssertionError(f"{sheet_name}: selector {selector} должен стоять рядом с {field}")

    experiment = schema["sheets"]["Эксперименты"]
    if experiment.get("computed") != ["basis_type"]:
        raise AssertionError("basis_type должен вычисляться, а не вводиться человеком")
    if "exactly_one_basis" not in experiment.get("constraints", []):
        raise AssertionError("schema не объявляет инвариант ровно одного основания")
    if "base_version_id" not in schema["sheets"]["Гипотезы"]["columns"]:
        raise AssertionError("гипотеза должна быть привязана к базовой версии")
    expected_scope_types = {"действие", "процесс", "производственная система", "объект", "состояние", "продукт", "материал", "показатель"}
    if set(schema["enums"]["development_scope_type"]) != expected_scope_types:
        raise AssertionError("словарь областей развития неполон")

    payload = base.build(schema, existing_ids=[11, 12], existing_named_range_ids=["nr-old"], title="v0.3 fixture")
    base.validate_batch(payload)
    if tuple(payload["sheet_ids"]) != tuple(schema["sheet_order"]):
        raise AssertionError("builder нарушил порядок 32 листов")
    requests = payload["requests"]
    created = [request["addSheet"]["properties"] for request in requests if "addSheet" in request]
    public = [properties for properties in created if not properties["title"].startswith("__v02_")]
    if len(public) != 32 or not all(item["gridProperties"].get("hideGridlines") for item in public):
        raise AssertionError("builder должен создавать 32 публичных листа со скрытой сеткой")
    dashboard = next(item for item in public if item["title"] == "Рабочая панель")
    if dashboard["gridProperties"]["rowCount"] < 1005 or dashboard["gridProperties"]["columnCount"] < 44:
        raise AssertionError("рабочей панели недостаточно места для независимых секций")

    formulas = formula_values(requests)
    basis_formulas = [formula for formula in formulas if "отклонение" in formula and "гипотеза" in formula and "$E" in formula and "$G" in formula]
    if len(basis_formulas) != 1:
        raise AssertionError("builder должен создавать одну вычисляемую формулу basis_type")
    dashboard_formulas = [
        formula
        for formula in formulas
        if "$E$5" in formula or "$E$4" in formula or "$E$3" in formula
    ]
    required_tokens = (
        "Действия",
        "Связи действий",
        "Переходы",
        "Состояния",
        "Материалы",
        "Позиции контрактов",
        "Контракты",
        "Интерфейсы передачи",
        "Отклонения",
        "Гипотезы",
        "Эксперименты",
        "Диаграммы",
    )
    joined = "\n".join(dashboard_formulas)
    missing = [token for token in required_tokens if token not in joined]
    if missing:
        raise AssertionError(f"рабочая панель не содержит формулы секций: {missing}")
    if any(re.search(r"\$?[A-Z]{1,3}:\$?[A-Z]{1,3}", formula) for formula in dashboard_formulas):
        raise AssertionError("формулы панели не должны использовать полные столбцы")
    if "Нет связанных записей" not in joined:
        raise AssertionError("пустые секции должны иметь понятное состояние")
    for token in ("dashboard_system_labels_v03", "dashboard_process_labels_v03"):
        if token not in json.dumps(requests, ensure_ascii=False):
            raise AssertionError(f"панель не содержит зависимый selector {token}")
    if 'resolution_status' not in schema["sheets"]["Срез модели"]["columns"] or '"разрешено"' not in joined:
        raise AssertionError("зависимые selectors и панель должны использовать только разрешённый срез")
    if "selector_empty_v03" not in json.dumps(requests, ensure_ascii=False):
        raise AssertionError("полиморфный selector не имеет безопасного пустого диапазона")
    for scope_token in ('"объект"', '"состояние"', '"материал"', '"показатель"'):
        if scope_token not in joined:
            raise AssertionError(f"контур развития процесса не учитывает {scope_token}")

    conditional = [request for request in requests if "addConditionalFormatRule" in request]
    if len(conditional) != 1:
        raise AssertionError("красная подсветка разрешена только для ERROR на листе Проверки")
    condition = conditional[0]["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
    if '="ERROR"' not in condition:
        raise AssertionError("WARN не должен окрашиваться как критическая ошибка")

    json.loads(json.dumps(payload, ensure_ascii=False))
    print(
        f"[OK] v0.3 builder: {payload['request_count']} requests, "
        f"{len(dashboard_formulas)} dashboard formulas, {len(schema['sheet_order'])} sheets"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
