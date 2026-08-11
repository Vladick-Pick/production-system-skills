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
V2_SCHEMA_CANDIDATES = (
    ROOT / "templates" / "template-schema-v0.2.json",
    ROOT / "references" / "TEMPLATE-SCHEMA-v0.2.json",
)
V2_SCHEMA_PATH = next((path for path in V2_SCHEMA_CANDIDATES if path.is_file()), V2_SCHEMA_CANDIDATES[0])
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


def scalar_value(value: Any) -> Any:
    """Прочитать примитив из inventory, не теряя поддерживаемую typed-форму."""
    if not isinstance(value, dict):
        return value
    if set(value) == {"userEnteredValue"} and isinstance(value["userEnteredValue"], dict):
        return scalar_value(value["userEnteredValue"])
    for key in ("stringValue", "numberValue", "boolValue", "formulaValue"):
        if set(value) == {key}:
            return value[key]
    raise MigrationError("SOURCE_CELL_VALUE_INVALID", "не удалось прочитать typed value")


def replace_scalar(value: Any, replacement: Any) -> Any:
    """Заменить строковое значение, сохранив форму inventory."""
    if not isinstance(value, dict):
        return replacement
    if set(value) == {"userEnteredValue"} and isinstance(value["userEnteredValue"], dict):
        return {"userEnteredValue": replace_scalar(value["userEnteredValue"], replacement)}
    if set(value) == {"stringValue"}:
        return {"stringValue": replacement}
    raise MigrationError("SEMANTIC_VALUE_SHAPE_INVALID", "семантическое преобразование поддерживает строковое значение")


def transformed_preserved_rows(
    source: dict[str, Any],
    v2: dict[str, Any],
    v3: dict[str, Any],
) -> tuple[dict[str, list[Any]], list[dict[str, Any]]]:
    """Применить только явно объявленные семантические миграции v0.3."""
    preserved_names = [name for name in v2["sheet_order"] if name not in REGENERATED_SHEETS]
    preserved = {name: copy.deepcopy(source["sheets"][name]) for name in preserved_names}
    transformations: list[dict[str, Any]] = []
    rules = v3.get("semantic_migrations", {})
    knowledge_map = rules.get("knowledge_status", {})
    for sheet_name, rows in preserved.items():
        for row_index, item in enumerate(rows):
            if not isinstance(item, dict) or "knowledge_status" not in item:
                continue
            old = scalar_value(item["knowledge_status"])
            if old not in knowledge_map:
                continue
            new = knowledge_map[old]
            item["knowledge_status"] = replace_scalar(item["knowledge_status"], new)
            transformations.append(
                {
                    "kind": "controlled_vocabulary_rename",
                    "sheet": sheet_name,
                    "row_index": row_index,
                    "stable_id": scalar_value(item.get(v3["sheets"][sheet_name]["columns"][0])),
                    "field": "knowledge_status",
                    "from": old,
                    "to": new,
                }
            )

    object_rule = rules.get("object_type", {})
    legacy_types = set(object_rule.get("requires_resolution", []))
    allowed_targets = set(object_rule.get("allowed_targets", []))
    resolutions = source.get("semantic_resolutions", {}).get("object_type", {})
    if not isinstance(resolutions, dict):
        raise MigrationError("SEMANTIC_RESOLUTIONS_INVALID", "semantic_resolutions.object_type должен быть объектом")
    unresolved: list[str] = []
    for row_index, item in enumerate(preserved.get("Объекты", [])):
        if not isinstance(item, dict) or "object_type" not in item:
            continue
        old = scalar_value(item["object_type"])
        if old not in legacy_types:
            continue
        object_id = scalar_value(item.get("object_id"))
        resolution = resolutions.get(object_id)
        if not isinstance(resolution, dict):
            unresolved.append(f"{object_id or f'row-{row_index + 1}'}:{old}")
            continue
        target = resolution.get("target")
        decision_id = resolution.get("decision_id")
        if target not in allowed_targets or not isinstance(decision_id, str) or not decision_id:
            raise MigrationError(
                "SEMANTIC_OBJECT_TYPE_RESOLUTION_INVALID",
                f"{object_id}: нужны target из {sorted(allowed_targets)} и непустой decision_id",
            )
        item["object_type"] = replace_scalar(item["object_type"], target)
        transformations.append(
            {
                "kind": "context_role_to_intrinsic_type",
                "sheet": "Объекты",
                "row_index": row_index,
                "stable_id": object_id,
                "field": "object_type",
                "from": old,
                "to": target,
                "decision_id": decision_id,
            }
        )
    if unresolved:
        raise MigrationError(
            "SEMANTIC_OBJECT_TYPE_RESOLUTION_REQUIRED",
            "контекстные роли вход/выход требуют явной классификации: " + ", ".join(unresolved),
        )
    return preserved, transformations


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


def validate_settings(source: dict[str, Any]) -> dict[str, Any]:
    settings = source.get("settings")
    if not isinstance(settings, dict) or not settings.get("model_id"):
        raise MigrationError("SOURCE_SETTINGS_MISSING", "inventory должен сохранять настройки Система, включая model_id")
    for prefix in ("working_version", "current_version"):
        id_key = f"{prefix}_id"
        selector_key = f"{prefix}_selector"
        if id_key not in settings or selector_key not in settings:
            raise MigrationError("SOURCE_SETTINGS_MISSING", f"inventory должен содержать {id_key} и {selector_key}")
        if bool(scalar_value(settings[id_key])) != bool(scalar_value(settings[selector_key])):
            raise MigrationError("SOURCE_VERSION_POINTER_INCOMPLETE", f"{id_key} и {selector_key} должны быть заполнены или пусты вместе")
    return settings


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
    validate_settings(source)
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
    return sheet_ids, named_range_ids


def plan_migration(source: dict[str, Any]) -> dict[str, Any]:
    v2, v3 = validate_source(source)
    preserved_names = [name for name in v2["sheet_order"] if name not in REGENERATED_SHEETS]
    source_preserved = {name: copy.deepcopy(source["sheets"][name]) for name in preserved_names}
    preserved, semantic_transformations = transformed_preserved_rows(source, v2, v3)
    source_counts = {name: len(source["sheets"][name]) for name in v2["sheet_order"]}
    preserved_counts = {name: len(rows) for name, rows in preserved.items()}
    source_value_fingerprint = canonical_hash(source_preserved)

    target_sheets: dict[str, list[Any] | dict[str, str]] = {}
    for sheet_name in v3["sheet_order"]:
        if sheet_name in NEW_REGISTRIES:
            target_sheets[sheet_name] = []
        elif sheet_name in REGENERATED_SHEETS:
            target_sheets[sheet_name] = {"state": "regenerate_with_builder_v0.3"}
        else:
            target_sheets[sheet_name] = copy.deepcopy(preserved[sheet_name])

    target_preserved = {
        name: target_sheets[name]
        for name in preserved_names
    }
    target_value_fingerprint = canonical_hash(target_preserved)

    plan_core = {
        "source_spreadsheet_id": source["spreadsheet_id"],
        "source_schema_version": "0.2",
        "source_build_fingerprint": source["build_fingerprint"],
        "source_sheet_order": v2["sheet_order"],
        "source_counts": source_counts,
        "source_value_fingerprint": source_value_fingerprint,
        "source_settings_fingerprint": canonical_hash(source["settings"]),
        "target_schema_version": "0.3",
        "target_sheet_order": v3["sheet_order"],
        "target_builder": "scripts/build_template_v0_3.py",
        "preserved_sheets": preserved_names,
        "preserved_counts": preserved_counts,
        "target_preserved_value_fingerprint": target_value_fingerprint,
        "exact_value_preservation": not semantic_transformations,
        "semantic_transformations": semantic_transformations,
        "semantic_policy": "stable IDs и референты сохраняются; только объявленные словарные преобразования изменяют значения",
        "new_empty_registries": list(NEW_REGISTRIES),
        "regenerated_sheets": list(REGENERATED_SHEETS),
        "source_copy_required": True,
        "source_must_remain_unchanged": True,
        "rollback": "Продолжить работу в исходной неизменённой книге v0.2",
        "inference_policy": "Не создавать исторические отклонения, гипотезы или эксперименты и не угадывать внутренний тип входа/выхода",
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
        source_rows = plan["target_sheets"][sheet_name]
        if any(not isinstance(item, dict) for item in source_rows):
            raise MigrationError("SOURCE_ROW_SHAPE_INVALID", f"{sheet_name}: для исполнения каждая строка должна быть объектом field→value")
        unknown = sorted({field for item in source_rows for field in item if field not in columns})
        if unknown:
            raise MigrationError("SOURCE_FIELD_DRIFT", f"{sheet_name}: неизвестные поля {unknown}")
        if source_rows:
            data_start = int(target_sheet.get("data_start_row", v3["default_table"]["data_start_row"])) - 1
            # Записывать только реально присутствующие значения. Разворачивание
            # sparse inventory до полной строки очистило бы формулы builder в
            # отсутствующих computed/selector ячейках.
            for column_index, field in enumerate(columns):
                positioned = [(index, item[field]) for index, item in enumerate(source_rows) if field in item]
                start = 0
                while start < len(positioned):
                    end = start + 1
                    while end < len(positioned) and positioned[end][0] == positioned[end - 1][0] + 1:
                        end += 1
                    segment = positioned[start:end]
                    restore_requests.append(
                        base_builder.update_block(
                            payload["sheet_ids"][sheet_name],
                            data_start + segment[0][0],
                            column_index,
                            [base_builder.row([restore_cell(value)]) for _, value in segment],
                        )
                    )
                    start = end
        restored_counts[sheet_name] = len(source_rows)

    settings = source["settings"]
    system_id = payload["sheet_ids"]["Система"]
    restore_requests.append(base_builder.update_block(system_id, 2, 1, [base_builder.row([restore_cell(settings["model_id"])])]))
    # B4/B5 — вычисляемые version IDs builder. Восстанавливаем только видимые
    # selectors C4/C5, чтобы не заменить lookup-формулы статическим текстом.
    restore_requests.append(
        base_builder.update_block(
            system_id,
            3,
            2,
            [
                base_builder.row([restore_cell(settings["working_version_selector"])]),
                base_builder.row([restore_cell(settings["current_version_selector"])]),
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
        "source_settings_fingerprint": plan["source_settings_fingerprint"],
        "target_preserved_value_fingerprint": plan["target_preserved_value_fingerprint"],
        "semantic_transformations": plan["semantic_transformations"],
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
        if target_sheets[name] != plan["target_sheets"][name]:
            raise MigrationError("TARGET_VALUE_DRIFT", f"значения листа {name} не совпадают с объявленной семантической миграцией")
    for name in NEW_REGISTRIES:
        if target_sheets[name] not in ([], None):
            raise MigrationError("TARGET_NEW_REGISTRY_NOT_EMPTY", f"лист {name} должен быть пустым")
    target_settings = target.get("settings")
    if not isinstance(target_settings, dict):
        raise MigrationError("TARGET_SETTINGS_MISSING", "целевая inventory должна содержать настройки Система")
    for field in ("model_id", "working_version_id", "working_version_selector", "current_version_id", "current_version_selector"):
        if scalar_value(target_settings.get(field)) != scalar_value(source["settings"].get(field)):
            raise MigrationError("TARGET_SETTINGS_DRIFT", f"настройка {field} не совпадает после вычисления builder")
    preserved = {name: target_sheets[name] for name in plan["preserved_sheets"]}
    return {
        "status": "PASS",
        "migration_id": plan["migration_id"],
        "source_value_fingerprint": plan["source_value_fingerprint"],
        "source_settings_fingerprint": plan["source_settings_fingerprint"],
        "target_value_fingerprint": canonical_hash(preserved),
        "semantic_transformations": plan["semantic_transformations"],
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
