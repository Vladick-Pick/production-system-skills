#!/usr/bin/env python3
"""Построить и проверить логический migration package шаблона v0.2 → v0.3.

Скрипт не меняет Google Sheet и не создаёт копию сам. Он принимает read-only
inventory исходной книги, доказывает точную v0.2-структуру и возвращает
детерминированный target plan: сохранённые данные, пустые новые реестры и
перечень служебных поверхностей для пересборки builder v0.3.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from build_template_v0_3 import load_schema as load_v3_schema


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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    try:
        result = (
            verify_target(source, json.loads(args.target.read_text(encoding="utf-8")))
            if args.target
            else plan_migration(source)
        )
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
