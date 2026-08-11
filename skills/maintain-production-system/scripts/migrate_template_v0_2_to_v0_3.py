#!/usr/bin/env python3
"""Построить применимый migration package шаблона v0.2 → v0.3.

Скрипт не получает доступ к Drive и не создаёт копию сам. Он принимает
read-only inventory исходной книги, проверяет точную v0.2-структуру и может
вернуть либо логический план, либо детерминированный Google Sheets batchUpdate
для уже созданной отдельной копии. Пакет пересобирает физический шаблон v0.3,
после чего восстанавливает исходные настройки и авторские строки без догадок.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import build_template_v0_2 as base_builder
from build_template_v0_3 import configure_copy, load_schema as load_v3_schema


ROOT = Path(__file__).resolve().parents[1]
V2_SCHEMA_PATH = ROOT / "templates" / "template-schema-v0.2.json"
NEW_REGISTRIES = ("Отклонения", "Гипотезы", "Эксперименты")
REGENERATED_SHEETS = (
    "Инструкция",
    "Схема шаблона",
    "Срез модели",
    "Проверки",
    "Реестр процессов",
    "Рабочая панель",
)


class MigrationError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_v2_schema() -> dict[str, Any]:
    return json.loads(V2_SCHEMA_PATH.read_text(encoding="utf-8"))


def restore_cell(value: Any) -> dict[str, Any]:
    """Сохранить точное userEnteredValue, включая формулы исходной книги."""
    if isinstance(value, dict):
        if set(value) == {"userEnteredValue"} and isinstance(value["userEnteredValue"], dict):
            return copy.deepcopy(value)
        value_kinds = {"stringValue", "numberValue", "boolValue", "formulaValue"}
        if len(value) == 1 and next(iter(value), None) in value_kinds:
            return {"userEnteredValue": copy.deepcopy(value)}
        raise MigrationError(
            "SOURCE_CELL_VALUE_INVALID",
            "значение ячейки должно быть примитивом, userEnteredValue или одним typed value",
        )
    return base_builder.cell(value)


def validate_source(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    v2 = load_v2_schema()
    v3 = load_v3_schema()
    if source.get("schema_version") != "0.2":
        raise MigrationError("SOURCE_SCHEMA_MISMATCH", "ожидалась schema_version 0.2")
    if not source.get("spreadsheet_id"):
        raise MigrationError("SOURCE_ID_MISSING", "не указан spreadsheet_id исходной книги")
    if not source.get("build_fingerprint"):
        raise MigrationError("SOURCE_FINGERPRINT_MISSING", "не указан build_fingerprint v0.2")
    if source.get("sheet_order") != v2["sheet_order"]:
        raise MigrationError("SOURCE_SHEET_ORDER_DRIFT", "состав или порядок 29 листов отличается от v0.2")
    sheets = source.get("sheets")
    if not isinstance(sheets, dict) or set(sheets) != set(v2["sheet_order"]):
        raise MigrationError("SOURCE_SHEET_SET_DRIFT", "inventory должен содержать каждый лист v0.2 ровно один раз")
    for sheet_name, rows in sheets.items():
        if not isinstance(rows, list):
            raise MigrationError("SOURCE_ROWS_INVALID", f"{sheet_name}: rows должны быть JSON-массивом")
    return v2, v3


def validate_execution_inventory(source: dict[str, Any], v2: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    sheet_ids = source.get("sheet_ids")
    if not isinstance(sheet_ids, dict) or set(sheet_ids) != set(v2["sheet_order"]):
        raise MigrationError("SOURCE_SHEET_IDS_MISSING", "для исполнимого пакета нужны numeric sheetId всех 29 листов")
    if any(not isinstance(value, int) for value in sheet_ids.values()) or len(set(sheet_ids.values())) != len(sheet_ids):
        raise MigrationError("SOURCE_SHEET_IDS_INVALID", "sheetId должны быть уникальными целыми числами")
    named_range_ids = source.get("named_range_ids")
    if not isinstance(named_range_ids, list) or any(not isinstance(value, str) or not value for value in named_range_ids):
        raise MigrationError("SOURCE_NAMED_RANGE_IDS_MISSING", "нужен список namedRangeId целевой копии")
    settings = source.get("settings")
    if not isinstance(settings, dict) or not settings.get("model_id"):
        raise MigrationError("SOURCE_SETTINGS_MISSING", "inventory должен сохранять настройки Система, включая model_id")
    return sheet_ids, named_range_ids


def plan_migration(source: dict[str, Any]) -> dict[str, Any]:
    v2, v3 = validate_source(source)
    preserved_names = [name for name in v2["sheet_order"] if name not in REGENERATED_SHEETS]
    preserved = {name: copy.deepcopy(source["sheets"][name]) for name in preserved_names}
    source_counts = {name: len(source["sheets"][name]) for name in v2["sheet_order"]}
    preserved_counts = {name: len(rows) for name, rows in preserved.items()}
    source_value_fingerprint = canonical_hash(preserved)

    target_sheets: dict[str, list[Any] | dict[str, str]] = {}
    for sheet_name in v3["sheet_order"]:
        if sheet_name in NEW_REGISTRIES:
            target_sheets[sheet_name] = []
        elif sheet_name in REGENERATED_SHEETS:
            target_sheets[sheet_name] = {"state": "regenerate_with_builder_v0.3"}
        else:
            target_sheets[sheet_name] = copy.deepcopy(source["sheets"][sheet_name])

    target_preserved = {
        name: target_sheets[name]
        for name in preserved_names
    }
    target_value_fingerprint = canonical_hash(target_preserved)
    if target_value_fingerprint != source_value_fingerprint:
        raise MigrationError("PRESERVATION_MISMATCH", "план изменил сохраняемые значения")

    plan_core = {
        "source_spreadsheet_id": source["spreadsheet_id"],
        "source_schema_version": "0.2",
        "source_build_fingerprint": source["build_fingerprint"],
        "source_sheet_order": v2["sheet_order"],
        "source_counts": source_counts,
        "source_value_fingerprint": source_value_fingerprint,
        "target_schema_version": "0.3",
        "target_sheet_order": v3["sheet_order"],
        "target_builder": "scripts/build_template_v0_3.py",
        "preserved_sheets": preserved_names,
        "preserved_counts": preserved_counts,
        "target_preserved_value_fingerprint": target_value_fingerprint,
        "new_empty_registries": list(NEW_REGISTRIES),
        "regenerated_sheets": list(REGENERATED_SHEETS),
        "source_copy_required": True,
        "source_must_remain_unchanged": True,
        "rollback": "Продолжить работу в исходной неизменённой книге v0.2",
        "inference_policy": "Не создавать исторические отклонения, гипотезы или эксперименты",
        "target_sheets": target_sheets,
    }
    migration_id = "mig-v02-v03-" + canonical_hash(plan_core)[:16]
    return {
        "status": "PASS",
        "migration_id": migration_id,
        "migration_plan_fingerprint": canonical_hash(plan_core),
        **plan_core,
    }


def build_migration_package(source: dict[str, Any], *, target_title: str | None = None) -> dict[str, Any]:
    """Собрать один batchUpdate для применения к заранее созданной копии v0.2."""
    v2, v3 = validate_source(source)
    sheet_ids, named_range_ids = validate_execution_inventory(source, v2)
    plan = plan_migration(source)
    configure_copy()
    title = target_title or f"{source.get('spreadsheet_title', 'Модель бизнеса')} — шаблон v0.3"
    payload = base_builder.build(v3, list(sheet_ids.values()), named_range_ids, title)

    restore_requests: list[dict[str, Any]] = []
    restored_counts: dict[str, int] = {}
    for sheet_name in plan["preserved_sheets"]:
        target_sheet = v3["sheets"][sheet_name]
        columns = target_sheet.get("columns", [])
        source_rows = source["sheets"][sheet_name]
        if any(not isinstance(item, dict) for item in source_rows):
            raise MigrationError("SOURCE_ROW_SHAPE_INVALID", f"{sheet_name}: для исполнения каждая строка должна быть объектом field→value")
        unknown = sorted({field for item in source_rows for field in item if field not in columns})
        if unknown:
            raise MigrationError("SOURCE_FIELD_DRIFT", f"{sheet_name}: неизвестные поля {unknown}")
        if source_rows:
            rows = [
                base_builder.row([restore_cell(item.get(field)) for field in columns])
                for item in source_rows
            ]
            restore_requests.append(
                base_builder.update_block(
                    payload["sheet_ids"][sheet_name],
                    int(target_sheet.get("data_start_row", v3["default_table"]["data_start_row"])) - 1,
                    0,
                    rows,
                )
            )
        restored_counts[sheet_name] = len(source_rows)

    settings = source["settings"]
    system_id = payload["sheet_ids"]["Система"]
    restore_requests.append(
        base_builder.update_block(
            system_id,
            2,
            1,
            [
                base_builder.row([restore_cell(settings.get("model_id"))]),
                base_builder.row(
                    [
                        restore_cell(settings.get("working_version_id")),
                        restore_cell(settings.get("working_version_selector")),
                    ]
                ),
                base_builder.row(
                    [
                        restore_cell(settings.get("current_version_id")),
                        restore_cell(settings.get("current_version_selector")),
                    ]
                ),
            ],
        )
    )
    payload["requests"].extend(restore_requests)
    payload["request_count"] = len(payload["requests"])
    payload["batch_fingerprint"] = canonical_hash(payload["requests"])
    return {
        "status": "PASS",
        "migration_id": plan["migration_id"],
        "source_spreadsheet_id": source["spreadsheet_id"],
        "target_copy_required": True,
        "apply_to": "отдельная копия исходной книги v0.2 с теми же sheetId/namedRangeId из inventory",
        "source_value_fingerprint": plan["source_value_fingerprint"],
        "restored_counts": restored_counts,
        "settings_restored": True,
        "batch_update": payload,
    }


def verify_target(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    plan = plan_migration(source)
    if target.get("schema_version") != "0.3":
        raise MigrationError("TARGET_SCHEMA_MISMATCH", "целевая inventory не объявляет v0.3")
    if target.get("sheet_order") != plan["target_sheet_order"]:
        raise MigrationError("TARGET_SHEET_ORDER_MISMATCH", "целевая книга не содержит точные 32 листа")
    target_sheets = target.get("sheets")
    if not isinstance(target_sheets, dict) or set(target_sheets) != set(plan["target_sheet_order"]):
        raise MigrationError("TARGET_SHEET_SET_MISMATCH", "целевая inventory неполна")
    for name in plan["preserved_sheets"]:
        if target_sheets[name] != source["sheets"][name]:
            raise MigrationError("TARGET_VALUE_DRIFT", f"изменены существующие значения листа {name}")
    for name in NEW_REGISTRIES:
        if target_sheets[name] not in ([], None):
            raise MigrationError("TARGET_NEW_REGISTRY_NOT_EMPTY", f"лист {name} должен быть пустым")
    preserved = {name: target_sheets[name] for name in plan["preserved_sheets"]}
    return {
        "status": "PASS",
        "migration_id": plan["migration_id"],
        "source_value_fingerprint": plan["source_value_fingerprint"],
        "target_value_fingerprint": canonical_hash(preserved),
        "preserved_counts": {name: len(target_sheets[name]) for name in plan["preserved_sheets"]},
        "new_empty_registries": list(NEW_REGISTRIES),
        "source_unchanged": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="read-only inventory JSON книги v0.2")
    parser.add_argument("--target", type=Path, help="необязательная inventory JSON собранной книги v0.3")
    parser.add_argument("--build-package", action="store_true", help="сформировать применимый batchUpdate для отдельной копии")
    parser.add_argument("--target-title", help="название целевой копии v0.3")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    try:
        if args.target and args.build_package:
            raise MigrationError("CLI_MODE_CONFLICT", "--target и --build-package нельзя использовать одновременно")
        if args.target:
            result = verify_target(source, json.loads(args.target.read_text(encoding="utf-8")))
        elif args.build_package:
            result = build_migration_package(source, target_title=args.target_title)
        else:
            result = plan_migration(source)
        exit_code = 0
    except MigrationError as exc:
        result = {"status": "FAIL", "error_code": exc.code, "detail": exc.detail}
        exit_code = 1
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
