#!/usr/bin/env python3
"""Проверить schema, builder, связанную панель и проверки шаблона v0.4."""

from __future__ import annotations

import json
import re
import sys

import build_template_v0_2 as base
from build_template_v0_4 import NEW_SHEETS, configure_copy, load_schema


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
    if schema["schema_version"] != "0.4" or len(schema["sheet_order"]) != 37:
        raise AssertionError("итоговая schema v0.4 должна содержать 37 листов")
    anchor = schema["sheet_order"].index("Элементы модели") + 1
    if tuple(schema["sheet_order"][anchor : anchor + len(NEW_SHEETS)]) != NEW_SHEETS:
        raise AssertionError("пять новых реестров стоят не после общего каталога элементов")
    if {"показатель", "норматив"} & set(schema["enums"]["element_type"]):
        raise AssertionError("показатели и нормативы не должны оставаться новыми типами общего каталога")
    if {"owner_position_id", "owner_position_selector"} & set(schema["sheets"]["Показатели"]["columns"]):
        raise AssertionError("ответственность показателя должна наследоваться от владельца системы, а не дублироваться")

    for sheet_name in NEW_SHEETS:
        sheet = schema["sheets"][sheet_name]
        if sheet.get("kind") != "versioned_authoring":
            raise AssertionError(f"{sheet_name}: реестр карты должен быть versioned_authoring")
        columns = sheet["columns"]
        if columns[1:3] != ["version_id", "version_operation"]:
            raise AssertionError(f"{sheet_name}: стабильный ID должен предшествовать редакции")
        if len(columns) != len(set(columns)):
            raise AssertionError(f"{sheet_name}: повторяющиеся колонки")
        for field, selector in sheet.get("selectors", {}).items():
            if columns.index(selector) != columns.index(field) + 1:
                raise AssertionError(f"{sheet_name}: {selector} должен стоять рядом с {field}")

    condition_columns = schema["sheets"]["Условия назначений"]["columns"]
    for field in ("compensation_scheme_rule_version_id", "allocation_rule_version_id"):
        if field not in condition_columns:
            raise AssertionError(f"Условия назначений должны фиксировать конкретную редакцию: {field}")

    if schema["sheets"]["Гипотезы"]["foreign_keys"]["primary_metric_id"] != "Показатели.indicator_id":
        raise AssertionError("гипотезы должны ссылаться на самостоятельный показатель")
    if schema["sheets"]["Эксперименты"]["foreign_keys"]["primary_metric_id"] != "Показатели.indicator_id":
        raise AssertionError("эксперименты должны ссылаться на самостоятельный показатель")
    if schema["sheets"]["Отклонения"]["foreign_keys"]["norm_requirement_id"] != "Требования показателей.requirement_id":
        raise AssertionError("отклонение должно ссылаться на действующий норматив-требование")
    for sheet_name in ("Отклонения", "Гипотезы", "Эксперименты"):
        scope_targets = schema["sheets"][sheet_name]["polymorphic_foreign_keys"]["scope_element_id"]["targets"]
        if scope_targets.get("показатель") != "Показатели.indicator_id":
            raise AssertionError(f"{sheet_name}: область развития типа показатель должна ссылаться на новый реестр Показатели")
    if "observed_value" in json.dumps(schema, ensure_ascii=False) or "financial_fact" in json.dumps(schema, ensure_ascii=False):
        raise AssertionError("schema карты не должна хранить наблюдения или финансовые факты")

    payload = base.build(schema, existing_ids=[11, 12], existing_named_range_ids=["nr-old"], title="v0.4 fixture")
    base.validate_batch(payload)
    if tuple(payload["sheet_ids"]) != tuple(schema["sheet_order"]):
        raise AssertionError("builder нарушил порядок 37 листов")
    requests = payload["requests"]
    serialized = json.dumps(requests, ensure_ascii=False)
    created = [request["addSheet"]["properties"] for request in requests if "addSheet" in request]
    public = [properties for properties in created if not properties["title"].startswith("__v02_")]
    if len(public) != 37 or not all(item["gridProperties"].get("hideGridlines") for item in public):
        raise AssertionError("builder должен создавать 37 публичных листов со скрытой сеткой")
    dashboard = next(item for item in public if item["title"] == "Рабочая панель")
    if dashboard["gridProperties"]["rowCount"] < 1005 or dashboard["gridProperties"]["columnCount"] < 44:
        raise AssertionError("рабочей панели недостаточно места для независимых секций")

    instruction_id = payload["sheet_ids"]["Инструкция"]
    instruction_merges = {
        (
            item["mergeCells"]["range"]["startRowIndex"],
            item["mergeCells"]["range"]["endRowIndex"],
            item["mergeCells"]["range"]["startColumnIndex"],
            item["mergeCells"]["range"]["endColumnIndex"],
        )
        for item in requests
        if "mergeCells" in item and item["mergeCells"]["range"]["sheetId"] == instruction_id
    }
    for expected in ((11, 12, 2, 8), (12, 13, 2, 8), (14, 15, 0, 8), (19, 20, 1, 8)):
        if expected not in instruction_merges:
            raise AssertionError(f"Инструкция v0.4 не адаптирована к двум новым строкам: {expected}")

    formulas = formula_values(requests)
    dashboard_formulas = [formula for formula in formulas if "$E$5" in formula or "$E$4" in formula or "$E$3" in formula]
    joined = "\n".join(dashboard_formulas)
    for token in ("Показатели", "Экономические правила", "Привязки показателей", "Требования показателей"):
        if token not in serialized:
            raise AssertionError(f"builder не материализует v0.4 поверхность {token}")
    if "Показатели" not in joined or "Экономические правила" not in joined:
        raise AssertionError("рабочая панель не показывает определения измеримости и экономики выбранного процесса")
    if "Наблюдения" in joined or "Финансовые факты" in joined:
        raise AssertionError("панель карты не должна превращаться в хранилище территории")
    if any(re.search(r"\$?[A-Z]{1,3}:\$?[A-Z]{1,3}", formula) for formula in dashboard_formulas):
        raise AssertionError("формулы панели не должны использовать полные столбцы")
    if "Нет связанных записей" not in joined:
        raise AssertionError("пустые секции должны иметь понятное состояние")

    required_check_ids = (
        "CHK-INDICATOR-CONTRACT",
        "CHK-FINANCIAL-INDICATOR",
        "CHK-INDICATOR-BINDING",
        "CHK-REQUIREMENT-VALUE",
        "CHK-REQUIREMENT-PERIOD",
        "CHK-ECONOMIC-RULE-CORE",
        "CHK-EXPENSE-AXES",
        "CHK-ECONOMIC-ALLOCATION",
        "CHK-ASSIGNMENT-CONDITION",
        "CHK-ASSIGNMENT-RULE-REVISION",
        "CHK-LEGACY-MEASUREMENT-ELEMENT",
    )
    missing_checks = [check_id for check_id in required_check_ids if check_id not in serialized]
    if missing_checks:
        raise AssertionError(f"builder не материализует v0.4 проверки: {missing_checks}")
    for enum_name in (
        "indicator_kind",
        "measurement_scope_type",
        "requirement_type",
        "economic_rule_kind",
        "calculation_method",
        "expense_attribution",
        "expense_behavior",
        "financial_result_position",
    ):
        if f"enum_{enum_name}" not in serialized:
            raise AssertionError(f"builder не создаёт named range enum_{enum_name}")
    if "selector_empty_v03" not in serialized:
        raise AssertionError("полиморфные selectors не имеют безопасного пустого диапазона")

    conditional = [request for request in requests if "addConditionalFormatRule" in request]
    if len(conditional) != 1:
        raise AssertionError("красная подсветка разрешена только для ERROR на листе Проверки")
    condition = conditional[0]["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
    if '="ERROR"' not in condition:
        raise AssertionError("WARN не должен окрашиваться как критическая ошибка")

    json.loads(json.dumps(payload, ensure_ascii=False))
    print(
        f"[OK] v0.4 builder: {payload['request_count']} requests, "
        f"{len(dashboard_formulas)} dashboard formulas, {len(schema['sheet_order'])} sheets"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
