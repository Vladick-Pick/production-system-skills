#!/usr/bin/env python3
"""Построить детерминированный Google Sheets batchUpdate для шаблона v0.3."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import build_template_v0_2 as base


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
BASE_SCHEMA_CANDIDATES = (
    ROOT / "templates" / "template-schema-v0.2.json",
    ROOT / "references" / "TEMPLATE-SCHEMA-v0.2.json",
    HERE.parents[1] / "references" / "TEMPLATE-SCHEMA-v0.2.json",
)
OVERLAY_SCHEMA_CANDIDATES = (
    ROOT / "templates" / "template-schema-v0.3.json",
    ROOT / "references" / "TEMPLATE-SCHEMA-v0.3.json",
    HERE.parents[1] / "references" / "TEMPLATE-SCHEMA-v0.3.json",
)
BASE_SCHEMA_PATH = next((path for path in BASE_SCHEMA_CANDIDATES if path.is_file()), BASE_SCHEMA_CANDIDATES[0])
OVERLAY_SCHEMA_PATH = next((path for path in OVERLAY_SCHEMA_CANDIDATES if path.is_file()), OVERLAY_SCHEMA_CANDIDATES[0])


def load_schema() -> dict[str, Any]:
    """Разрешить стабильную v0.2 и additive overlay v0.3 в одну схему."""
    base_schema = json.loads(BASE_SCHEMA_PATH.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema = copy.deepcopy(base_schema)
    if overlay.get("base_schema") != BASE_SCHEMA_PATH.name:
        raise ValueError("overlay v0.3 ссылается на неожиданную базовую схему")

    additions = list(overlay.get("sheet_order_additions", []))
    insert_after = overlay.get("insert_after")
    if insert_after not in schema["sheet_order"]:
        raise ValueError(f"не найден лист для вставки overlay: {insert_after!r}")
    if any(name in schema["sheets"] for name in additions):
        raise ValueError("overlay v0.3 пытается заменить существующий лист v0.2")
    if set(additions) != set(overlay.get("sheets", {})):
        raise ValueError("sheet_order_additions и sheets overlay расходятся")

    insertion = schema["sheet_order"].index(insert_after) + 1
    schema["sheet_order"][insertion:insertion] = additions
    schema["sheets"].update(copy.deepcopy(overlay["sheets"]))
    for sheet_name, changes in overlay.get("sheet_overrides", {}).items():
        if sheet_name not in schema["sheets"]:
            raise ValueError(f"overlay v0.3 меняет неизвестный лист: {sheet_name}")
        schema["sheets"][sheet_name].update(copy.deepcopy(changes))
    for enum_name, values in overlay.get("enums", {}).items():
        if enum_name in schema["enums"]:
            raise ValueError(f"overlay v0.3 пытается заменить enum v0.2: {enum_name}")
        schema["enums"][enum_name] = list(values)
    schema["schema_version"] = overlay["schema_version"]
    schema["sheet_count"] = overlay["sheet_count"]
    schema["base_schema_version"] = base_schema["schema_version"]
    schema["overlay_schema"] = OVERLAY_SCHEMA_PATH.name
    validate_schema(schema)
    return schema


def validate_schema(schema: dict[str, Any]) -> None:
    order = schema.get("sheet_order", [])
    sheets = schema.get("sheets", {})
    if schema.get("schema_version") != "0.3":
        raise ValueError("итоговая схема должна иметь schema_version=0.3")
    if len(order) != 32 or schema.get("sheet_count") != 32:
        raise ValueError("v0.3 должна содержать ровно 32 листа")
    if len(order) != len(set(order)) or set(order) != set(sheets):
        raise ValueError("порядок и набор листов v0.3 расходятся")
    expected_additions = ["Отклонения", "Гипотезы", "Эксперименты"]
    anchor = order.index("Изменения модели") + 1
    if order[anchor : anchor + 3] != expected_additions:
        raise ValueError("три реестра развития стоят не в принятом порядке")

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
        for field, enum_name in sheet.get("enums", {}).items():
            if field not in columns or enum_name not in schema["enums"]:
                raise ValueError(f"{sheet_name}: неизвестный enum {field!r}/{enum_name!r}")
        for field in sheet.get("computed_formulas", {}):
            if field not in columns:
                raise ValueError(f"{sheet_name}: вычисляемая колонка {field!r} отсутствует")
        for field, specification in sheet.get("polymorphic_foreign_keys", {}).items():
            if field not in columns:
                raise ValueError(f"{sheet_name}: полиморфная связь {field!r} отсутствует в columns")
            if not isinstance(specification, dict):
                # Унаследованные v0.2 связи сохраняют общий каталог Среза модели.
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
    base.DESCRIPTION_BY_KIND["development_registry"] = (
        "Рабочий реестр развития производственной системы с человеческими решениями."
    )
    base.DESCRIPTION_BY_SHEET.update(
        {
            "Отклонения": "Подтверждённые различия между действующей нормой и фактической работой системы.",
            "Гипотезы": "Новые внешние возможности, которые могут улучшить производительность или качество результата.",
            "Эксперименты": "Ограниченные проверки способов устранения отклонений или гипотез развития.",
        }
    )
    base.HELP_BY_KIND["development_registry"] = (
        "Начните с проверяемого источника и ближайшего следующего шага. "
        "Агент помогает классифицировать и проверить запись, а решения принимает человек."
    )
    base.HELP_BY_SHEET.update(
        {
            "Отклонения": "Не называйте проблемой разницу с будущей целью. Для подтверждения покажите действующую норму и наблюдаемый факт.",
            "Гипотезы": "Гипотеза начинается с внешнего изменения и его источника; предполагаемая причина отклонения остаётся в отклонении.",
            "Эксперименты": "Выберите ровно одно основание. Проверка проводится относительно действующей версии и не создаёт отдельную версию модели.",
        }
    )
    base.DISPLAY_FIELD_OVERRIDES.update(
        {
            "Отклонения": "deviation_title",
            "Гипотезы": "hypothesis_title",
            "Эксперименты": "experiment_title",
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
    parser.add_argument("--title", default="Шаблон канонической модели бизнеса — v0.3")
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
