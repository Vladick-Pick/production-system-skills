#!/usr/bin/env python3
"""Построить детерминированный Google Sheets batchUpdate для шаблона v0.4."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import build_template_v0_2 as base
import build_template_v0_3 as v3


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
OVERLAY_SCHEMA_CANDIDATES = (
    ROOT / "templates" / "template-schema-v0.4.json",
    ROOT / "references" / "TEMPLATE-SCHEMA-v0.4.json",
    HERE.parents[1] / "references" / "TEMPLATE-SCHEMA-v0.4.json",
)
OVERLAY_SCHEMA_PATH = next((path for path in OVERLAY_SCHEMA_CANDIDATES if path.is_file()), OVERLAY_SCHEMA_CANDIDATES[0])
NEW_SHEETS = (
    "Показатели",
    "Привязки показателей",
    "Требования показателей",
    "Экономические правила",
    "Условия назначений",
)


def load_schema() -> dict[str, Any]:
    """Разрешить v0.3 и версионный overlay v0.4 в одну физическую схему."""
    base_schema = v3.load_schema()
    overlay = json.loads(OVERLAY_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema = copy.deepcopy(base_schema)
    expected_base = Path(v3.OVERLAY_SCHEMA_PATH).name
    declared_base = str(overlay.get("base_schema", ""))
    if declared_base.casefold() not in {"template-schema-v0.3.json", expected_base.casefold()}:
        raise ValueError("overlay v0.4 ссылается на неожиданную базовую схему")

    additions = list(overlay.get("sheet_order_additions", []))
    insert_after = overlay.get("insert_after")
    if insert_after not in schema["sheet_order"]:
        raise ValueError(f"не найден лист для вставки overlay: {insert_after!r}")
    if tuple(additions) != NEW_SHEETS or set(additions) != set(overlay.get("sheets", {})):
        raise ValueError("overlay v0.4 должен объявлять пять принятых реестров в точном порядке")
    if any(name in schema["sheets"] for name in additions):
        raise ValueError("overlay v0.4 пытается заменить существующий лист v0.3")

    insertion = schema["sheet_order"].index(insert_after) + 1
    schema["sheet_order"][insertion:insertion] = additions
    schema["sheets"].update(copy.deepcopy(overlay["sheets"]))
    for sheet_name, changes in overlay.get("sheet_overrides", {}).items():
        if sheet_name not in schema["sheets"]:
            raise ValueError(f"overlay v0.4 меняет неизвестный лист: {sheet_name}")
        schema["sheets"][sheet_name].update(copy.deepcopy(changes))
    for enum_name, values in overlay.get("enums", {}).items():
        if enum_name in schema["enums"]:
            raise ValueError(f"overlay v0.4 пытается заменить enum v0.3: {enum_name}")
        schema["enums"][enum_name] = list(values)
    for enum_name, values in overlay.get("enum_overrides", {}).items():
        if enum_name not in base_schema["enums"]:
            raise ValueError(f"overlay v0.4 заменяет неизвестный enum v0.3: {enum_name}")
        if not isinstance(values, list) or not values or len(values) != len(set(values)):
            raise ValueError(f"overlay v0.4 задаёт некорректный enum override: {enum_name}")
        schema["enums"][enum_name] = list(values)

    schema["schema_version"] = overlay["schema_version"]
    schema["sheet_count"] = overlay["sheet_count"]
    schema["base_schema_version"] = base_schema["schema_version"]
    schema["overlay_schema"] = OVERLAY_SCHEMA_PATH.name
    schema["semantic_migrations_v0_4"] = copy.deepcopy(overlay.get("semantic_migrations", {}))
    validate_schema(schema)
    return schema


def validate_schema(schema: dict[str, Any]) -> None:
    order = schema.get("sheet_order", [])
    sheets = schema.get("sheets", {})
    if schema.get("schema_version") != "0.4":
        raise ValueError("итоговая схема должна иметь schema_version=0.4")
    if len(order) != 37 or schema.get("sheet_count") != 37:
        raise ValueError("v0.4 должна содержать ровно 37 листов")
    if len(order) != len(set(order)) or set(order) != set(sheets):
        raise ValueError("порядок и набор листов v0.4 расходятся")
    anchor = order.index("Элементы модели") + 1
    if tuple(order[anchor : anchor + len(NEW_SHEETS)]) != NEW_SHEETS:
        raise ValueError("пять реестров измеримости и экономики стоят не в принятом порядке")
    forbidden_legacy = {"показатель", "норматив"}
    if forbidden_legacy & set(schema["enums"]["element_type"]):
        raise ValueError("новые показатели и нормативы не должны создаваться в Элементы модели")

    for sheet_name, sheet in sheets.items():
        columns = sheet.get("columns", [])
        if len(columns) != len(set(columns)):
            raise ValueError(f"{sheet_name}: повторяющиеся колонки")
        for required in sheet.get("required", []):
            if required not in columns:
                raise ValueError(f"{sheet_name}: required {required!r} отсутствует в columns")
        selectors = sheet.get("selectors", {})
        selectors = selectors if isinstance(selectors, dict) else {}
        for field, selector in selectors.items():
            if field in sheet.get("settings", {}):
                continue
            if field not in columns or selector not in columns:
                raise ValueError(f"{sheet_name}: нарушена пара ID/selector {field!r}/{selector!r}")
            if columns.index(selector) != columns.index(field) + 1:
                raise ValueError(f"{sheet_name}: selector {selector!r} должен стоять рядом с {field!r}")
        for field, enum_name in sheet.get("enums", {}).items():
            if field not in columns or enum_name not in schema["enums"]:
                raise ValueError(f"{sheet_name}: неизвестный enum {field!r}/{enum_name!r}")
        for field, target in sheet.get("foreign_keys", {}).items():
            if field not in columns:
                raise ValueError(f"{sheet_name}: FK {field!r} отсутствует в columns")
            target_sheet, target_field = target.split(".", 1)
            if target_sheet not in sheets or target_field not in sheets[target_sheet].get("columns", []):
                raise ValueError(f"{sheet_name}: неизвестная цель FK {target!r}")
        for field, specification in sheet.get("polymorphic_foreign_keys", {}).items():
            if field not in columns:
                raise ValueError(f"{sheet_name}: полиморфная связь {field!r} отсутствует в columns")
            if not isinstance(specification, dict):
                continue
            type_field = specification.get("type_field")
            targets = specification.get("targets")
            if type_field not in columns or not isinstance(targets, dict) or not targets:
                raise ValueError(f"{sheet_name}: полиморфная связь {field!r} не задаёт type_field/targets")
            enum_name = sheet.get("enums", {}).get(type_field)
            if enum_name and set(targets) != set(schema["enums"][enum_name]):
                raise ValueError(f"{sheet_name}: targets {field!r} не совпадают со словарём {enum_name}")
            for target in targets.values():
                target_sheet, target_field = target.split(".", 1)
                if target_sheet not in sheets or target_field not in sheets[target_sheet].get("columns", []):
                    raise ValueError(f"{sheet_name}: неизвестная цель полиморфной связи {target!r}")


def configure_copy() -> None:
    """Дополнить нейтральный builder человеко-читаемыми текстами v0.4."""
    v3.configure_copy()
    base.DESCRIPTION_BY_SHEET.update(
        {
            "Показатели": "Определения измеримых характеристик системы: что, для чего и по какому правилу считается.",
            "Привязки показателей": "Контракты получения фактов из систем-владельцев без копирования самих фактов в модель.",
            "Требования показателей": "Нормативы, цели и планы для показателей, областей и периодов.",
            "Экономические правила": "Ставки, формулы, схемы и правила управленческого расчёта и распределения.",
            "Условия назначений": "Применение схем компенсации к назначениям и подтверждённые индивидуальные отличия по периодам.",
            "Элементы модели": "Регламенты, правила, данные, источники истины, информационные системы, интерфейсы исполнения, SLA и автоматизации.",
        }
    )
    base.HELP_BY_SHEET.update(
        {
            "Показатели": "Начните с управленческого вопроса. Не создавайте новый показатель только из-за смены источника или дашборда; наблюдения и временные ряды остаются в системе исполнения.",
            "Привязки показателей": "fact_source — система-владелец фактов; source — доказательство принятого определения binding. Укажите точный locator/query и правило покрытия.",
            "Требования показателей": "Одна строка = один норматив, цель или план для конкретной области и периода. Более частное требование не отменяет общее молча.",
            "Экономические правила": "Цена, ставка и формула являются правилами карты. Фактическое использование, начисление и платёж здесь не хранятся. Не смешивайте три оси расхода.",
            "Условия назначений": "Ссылайтесь на схему позиции и фиксируйте только применение или индивидуальное отличие. Общий компонент не копируйте по назначениям.",
        }
    )
    base.DISPLAY_FIELD_OVERRIDES.update(
        {
            "Показатели": "indicator_name",
            "Привязки показателей": "binding_id",
            "Требования показателей": "requirement_name",
            "Экономические правила": "rule_name",
            "Условия назначений": "condition_name",
        }
    )
    base.HEADER_NOTES.update(
        {
            "fact_source_id": "Стабильный ID системы-владельца фактов. Не путать с source_id, который доказывает принятое определение строки.",
            "period_start": "Начало периода применимости требования. Для норматива — начало действия, для плана — начало планового периода.",
            "period_end": "Конец периода или срок достижения. Для цели и плана обязателен.",
            "valid_from": "Дата начала применения правила или условия к территории; не заменяет version_id редакции карты.",
            "storage_mode": "В модели хранится значение либо только проверяемая ссылка на закрытый источник.",
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-sheet-ids", default="", help="Список текущих numeric sheetId через запятую")
    parser.add_argument(
        "--existing-named-range-ids",
        default="",
        help="Список текущих namedRangeId через запятую; обязателен для повторной точной сборки",
    )
    parser.add_argument("--title", default="Шаблон канонической модели бизнеса — v0.4")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary", action="store_true", help="Не выводить requests, только параметры сборки")
    parser.add_argument("--request-start", type=int, default=0, help="Первый request для частичного применения")
    parser.add_argument("--request-limit", type=int, help="Число requests для частичного применения")
    parser.add_argument("--only-formulas", action="store_true", help="Вывести только requests, содержащие formulaValue")
    args = parser.parse_args()

    configure_copy()
    schema = load_schema()
    existing_ids = [int(value) for value in args.existing_sheet_ids.split(",") if value.strip()]
    named_ids = [value.strip() for value in args.existing_named_range_ids.split(",") if value.strip()]
    payload = base.build(schema, existing_ids, named_ids, args.title)
    base.validate_batch(payload)

    if args.only_formulas:
        payload = {
            **{key: value for key, value in payload.items() if key != "requests"},
            "requests": [request for request in payload["requests"] if "formulaValue" in json.dumps(request, ensure_ascii=False)],
        }
    start = max(0, args.request_start)
    end = None if args.request_limit is None else start + max(0, args.request_limit)
    if start or end is not None:
        payload = {
            **{key: value for key, value in payload.items() if key != "requests"},
            "requests": payload["requests"][start:end],
        }
    if args.summary:
        payload = {key: value for key, value in payload.items() if key != "requests"}

    output = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
