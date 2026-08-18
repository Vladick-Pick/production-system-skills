#!/usr/bin/env python3
"""Спланировать, собрать и проверить миграцию канонической книги v0.3 → v0.4.

Скрипт работает только с read-only inventory. Он не создаёт Google Sheet и не
применяет batchUpdate сам. Старые показатели и нормативы переносятся лишь после
явного семантического разрешения; отсутствующая экономика не выдумывается.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import build_template_v0_2 as base_builder
from build_template_v0_3 import load_schema as load_v3_schema
from build_template_v0_4 import configure_copy, load_schema as load_v4_schema


REGENERATED_SHEETS = (
    "Инструкция",
    "Схема шаблона",
    "Срез модели",
    "Проверки",
    "Реестр процессов",
    "Рабочая панель",
)
NEW_ECONOMIC_SHEETS = ("Экономические правила", "Условия назначений")
NEW_MEASUREMENT_SHEETS = ("Показатели", "Привязки показателей", "Требования показателей")


class MigrationError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def scalar_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    if set(value) == {"userEnteredValue"} and isinstance(value["userEnteredValue"], dict):
        return scalar_value(value["userEnteredValue"])
    for key in ("stringValue", "numberValue", "boolValue", "formulaValue"):
        if set(value) == {key}:
            return value[key]
    raise MigrationError("SOURCE_CELL_VALUE_INVALID", "не удалось прочитать typed value")


def restore_cell(value: Any) -> dict[str, Any]:
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
    v3 = load_v3_schema()
    v4 = load_v4_schema()
    if source.get("schema_version") != "0.3":
        raise MigrationError("SOURCE_SCHEMA_MISMATCH", "ожидалась schema_version 0.3")
    if not source.get("spreadsheet_id"):
        raise MigrationError("SOURCE_ID_MISSING", "не указан spreadsheet_id исходной книги")
    if not source.get("build_fingerprint"):
        raise MigrationError("SOURCE_FINGERPRINT_MISSING", "не указан build_fingerprint v0.3")
    if source.get("sheet_order") != v3["sheet_order"]:
        raise MigrationError("SOURCE_SHEET_ORDER_DRIFT", "состав или порядок 32 листов отличается от v0.3")
    sheets = source.get("sheets")
    if not isinstance(sheets, dict) or set(sheets) != set(v3["sheet_order"]):
        raise MigrationError("SOURCE_SHEET_SET_DRIFT", "inventory должен содержать каждый лист v0.3 ровно один раз")
    for sheet_name, rows in sheets.items():
        if not isinstance(rows, list):
            raise MigrationError("SOURCE_ROWS_INVALID", f"{sheet_name}: rows должны быть JSON-массивом")
    validate_settings(source)
    return v3, v4


def validate_execution_inventory(source: dict[str, Any], v3: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    sheet_ids = source.get("sheet_ids")
    if not isinstance(sheet_ids, dict) or set(sheet_ids) != set(v3["sheet_order"]):
        raise MigrationError("SOURCE_SHEET_IDS_MISSING", "для исполнимого пакета нужны numeric sheetId всех 32 листов")
    if any(not isinstance(value, int) for value in sheet_ids.values()) or len(set(sheet_ids.values())) != len(sheet_ids):
        raise MigrationError("SOURCE_SHEET_IDS_INVALID", "sheetId должны быть уникальными целыми числами")
    named_range_ids = source.get("named_range_ids")
    if not isinstance(named_range_ids, list) or any(not isinstance(value, str) or not value for value in named_range_ids):
        raise MigrationError("SOURCE_NAMED_RANGE_IDS_MISSING", "нужен список namedRangeId целевой копии")
    return sheet_ids, named_range_ids


def value_of(row: dict[str, Any], field: str, default: Any = "") -> Any:
    return scalar_value(row[field]) if field in row else default


def copy_if_present(source: dict[str, Any], target: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        if field in source:
            target[field] = copy.deepcopy(source[field])


def resolution_root(source: dict[str, Any]) -> dict[str, Any]:
    resolutions = source.get("semantic_resolutions", {})
    if not isinstance(resolutions, dict):
        raise MigrationError("SEMANTIC_RESOLUTIONS_INVALID", "semantic_resolutions должен быть JSON-объектом")
    root = resolutions.get("v0.4", {})
    if not isinstance(root, dict):
        raise MigrationError("SEMANTIC_RESOLUTIONS_INVALID", "semantic_resolutions.v0.4 должен быть JSON-объектом")
    return root


def missing_fields(value: Any, required: tuple[str, ...]) -> list[str]:
    if not isinstance(value, dict):
        return list(required)
    return [field for field in required if value.get(field) in (None, "")]


def validate_value_shape(resolution: dict[str, Any], stable_id: str) -> None:
    operator = resolution.get("comparison_operator")
    target = resolution.get("target_value") not in (None, "")
    lower = resolution.get("lower_bound") not in (None, "")
    upper = resolution.get("upper_bound") not in (None, "")
    expression = resolution.get("value_expression") not in (None, "")
    if operator in {"равно", "не менее", "не более"} and not (target and not lower and not upper and not expression):
        raise MigrationError("REQUIREMENT_VALUE_SHAPE_INVALID", f"{stable_id}: оператор {operator} требует только target_value")
    if operator == "диапазон" and not (lower and upper and not target and not expression):
        raise MigrationError("REQUIREMENT_VALUE_SHAPE_INVALID", f"{stable_id}: диапазон требует lower_bound и upper_bound")
    if operator == "формула" and not (expression and not target and not lower and not upper):
        raise MigrationError("REQUIREMENT_VALUE_SHAPE_INVALID", f"{stable_id}: формула требует только value_expression")


def transform_model(
    source: dict[str, Any],
    v3: dict[str, Any],
    v4: dict[str, Any],
) -> tuple[dict[str, list[Any] | dict[str, str]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Вернуть целевые строки, transformations и вопросы без изменения source."""
    target: dict[str, list[Any] | dict[str, str]] = {}
    for sheet_name in v4["sheet_order"]:
        if sheet_name in REGENERATED_SHEETS:
            target[sheet_name] = {"state": "regenerate_with_builder_v0.4"}
        elif sheet_name in v3["sheets"]:
            target[sheet_name] = copy.deepcopy(source["sheets"][sheet_name])
        else:
            target[sheet_name] = []

    transformations: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    root = resolution_root(source)
    indicator_resolutions = root.get("indicators", {})
    requirement_resolutions = root.get("requirements", {})
    if not isinstance(indicator_resolutions, dict) or not isinstance(requirement_resolutions, dict):
        raise MigrationError("SEMANTIC_RESOLUTIONS_INVALID", "indicators и requirements должны быть объектами stable_id→resolution")

    remaining_elements: list[dict[str, Any]] = []
    indicator_rows: list[dict[str, Any]] = []
    binding_rows: list[dict[str, Any]] = []
    requirement_rows: list[dict[str, Any]] = []
    migrated_indicator_ids: set[str] = set()
    migrated_requirement_ids: set[str] = set()

    indicator_required = (
        "decision_id",
        "indicator_kind",
        "management_question",
        "measured_characteristic",
        "observation_unit_type",
        "observation_unit_id",
        "single_unit_rule",
        "unit_of_measure",
        "time_attribution_rule",
        "required_facts",
        "coverage_rule",
    )
    binding_required = (
        "binding_id",
        "binding_role",
        "fact_source_id",
        "fact_locator_contract",
        "required_fact_description",
        "coverage_rule",
    )
    requirement_required = (
        "decision_id",
        "indicator_id",
        "requirement_name",
        "scope_type",
        "scope_element_id",
        "comparison_operator",
        "period_start",
    )

    for row_index, item in enumerate(source["sheets"]["Элементы модели"]):
        if not isinstance(item, dict):
            raise MigrationError("SOURCE_ROW_SHAPE_INVALID", "Элементы модели: каждая строка должна быть объектом field→value")
        element_type = value_of(item, "element_type")
        stable_id = str(value_of(item, "element_id", f"row-{row_index + 1}"))
        if element_type not in {"показатель", "норматив"}:
            remaining_elements.append(copy.deepcopy(item))
            continue

        if element_type == "показатель":
            resolution = indicator_resolutions.get(stable_id)
            missing = missing_fields(resolution, indicator_required)
            if missing:
                questions.append(
                    {
                        "kind": "indicator_resolution",
                        "stable_id": stable_id,
                        "element_name": value_of(item, "element_name"),
                        "missing_fields": missing,
                        "legacy_definition": value_of(item, "definition"),
                        "legacy_formula_or_rule": value_of(item, "formula_or_rule"),
                        "legacy_unit_or_format": value_of(item, "unit_or_format"),
                        "question": "Уточнить управленческий вопрос, измеряемый смысл, единицу наблюдения, правило одной единицы, время, требуемые факты и покрытие; подтвердить, что это тот же показатель.",
                    }
                )
                continue
            assert isinstance(resolution, dict)
            knowledge_status = value_of(item, "knowledge_status")
            binding = resolution.get("fact_binding")
            binding_missing = missing_fields(binding, binding_required) if knowledge_status == "принято" else []
            if binding_missing:
                questions.append(
                    {
                        "kind": "indicator_binding_resolution",
                        "stable_id": stable_id,
                        "element_name": value_of(item, "element_name"),
                        "missing_fields": binding_missing,
                        "question": "Для принятого показателя определить основной источник фактов, точный locator/query и правило покрытия.",
                    }
                )
                continue
            indicator = {
                "indicator_id": copy.deepcopy(item.get("element_id", stable_id)),
                "version_id": copy.deepcopy(item.get("version_id", "")),
                "version_operation": copy.deepcopy(item.get("version_operation", "")),
                "system_id": copy.deepcopy(item.get("system_id", "")),
                "indicator_name": copy.deepcopy(item.get("element_name", "")),
                "indicator_kind": resolution["indicator_kind"],
                "management_question": resolution["management_question"],
                "measured_characteristic": resolution["measured_characteristic"],
                "observation_unit_type": resolution["observation_unit_type"],
                "observation_unit_id": resolution["observation_unit_id"],
                "single_unit_rule": resolution["single_unit_rule"],
                "aggregation_rule": resolution.get("aggregation_rule", ""),
                "unit_of_measure": resolution["unit_of_measure"],
                "time_attribution_rule": resolution["time_attribution_rule"],
                "grouping_or_window_rule": resolution.get("grouping_or_window_rule", ""),
                "allowed_dimensions": resolution.get("allowed_dimensions", ""),
                "required_facts": resolution["required_facts"],
                "coverage_rule": resolution["coverage_rule"],
                "freshness_requirement": resolution.get("freshness_requirement", ""),
                "currency": resolution.get("currency", ""),
                "recognition_basis": resolution.get("recognition_basis", ""),
                "composition_boundary": resolution.get("composition_boundary", ""),
                "reconciliation_rule": resolution.get("reconciliation_rule", ""),
                "knowledge_status": copy.deepcopy(item.get("knowledge_status", "")),
                "source_id": copy.deepcopy(item.get("source_id", "")),
            }
            copy_if_present(
                item,
                indicator,
                (
                    "system_selector",
                    "source_selector",
                    "source_locator",
                    "last_reviewed",
                    "notes",
                ),
            )
            if resolution["indicator_kind"] == "финансовый":
                missing_financial = missing_fields(
                    resolution,
                    ("currency", "recognition_basis", "composition_boundary", "reconciliation_rule"),
                )
                if missing_financial:
                    raise MigrationError(
                        "FINANCIAL_INDICATOR_RESOLUTION_INVALID",
                        f"{stable_id}: не заполнены {missing_financial}",
                    )
            indicator_rows.append(indicator)
            migrated_indicator_ids.add(stable_id)
            transformations.append(
                {
                    "kind": "extract_indicator",
                    "stable_id": stable_id,
                    "from": "Элементы модели",
                    "to": "Показатели",
                    "decision_id": resolution["decision_id"],
                    "legacy_owner_position_id": value_of(item, "owner_position_id"),
                    "target_owner_rule": "ответственность наследуется от владельца производственной системы через system_id (D-12)",
                }
            )
            if isinstance(binding, dict):
                binding_row = {
                    "binding_id": binding["binding_id"],
                    "version_id": copy.deepcopy(item.get("version_id", "")),
                    "version_operation": copy.deepcopy(item.get("version_operation", "")),
                    "indicator_id": copy.deepcopy(item.get("element_id", stable_id)),
                    "binding_role": binding["binding_role"],
                    "fact_source_id": binding["fact_source_id"],
                    "fact_locator_contract": binding["fact_locator_contract"],
                    "source_event_or_field": binding.get("source_event_or_field", ""),
                    "required_fact_description": binding["required_fact_description"],
                    "coverage_rule": binding["coverage_rule"],
                    "freshness_requirement": binding.get("freshness_requirement", ""),
                    "valid_from": binding.get("valid_from", ""),
                    "valid_to": binding.get("valid_to", ""),
                    "knowledge_status": copy.deepcopy(item.get("knowledge_status", "")),
                    "source_id": binding.get("source_id", copy.deepcopy(item.get("source_id", ""))),
                    "source_locator": binding.get("source_locator", copy.deepcopy(item.get("source_locator", ""))),
                    "notes": binding.get("notes", ""),
                }
                binding_rows.append(binding_row)
                transformations.append(
                    {
                        "kind": "create_indicator_binding",
                        "stable_id": str(binding["binding_id"]),
                        "indicator_id": stable_id,
                        "decision_id": binding.get("decision_id", resolution["decision_id"]),
                    }
                )
            continue

        resolution = requirement_resolutions.get(stable_id)
        missing = missing_fields(resolution, requirement_required)
        if missing:
            questions.append(
                {
                    "kind": "requirement_resolution",
                    "stable_id": stable_id,
                    "element_name": value_of(item, "element_name"),
                    "missing_fields": missing,
                    "legacy_definition": value_of(item, "definition"),
                    "legacy_target_or_threshold": value_of(item, "target_or_threshold"),
                    "question": "Связать норматив с показателем, областью, оператором, значением и периодом; подтвердить сохранение stable ID.",
                }
            )
            continue
        assert isinstance(resolution, dict)
        validate_value_shape(resolution, stable_id)
        requirement = {
            "requirement_id": copy.deepcopy(item.get("element_id", stable_id)),
            "version_id": copy.deepcopy(item.get("version_id", "")),
            "version_operation": copy.deepcopy(item.get("version_operation", "")),
            "indicator_id": resolution["indicator_id"],
            "requirement_type": "норматив",
            "requirement_name": resolution["requirement_name"],
            "scope_type": resolution["scope_type"],
            "scope_element_id": resolution["scope_element_id"],
            "comparison_operator": resolution["comparison_operator"],
            "target_value": resolution.get("target_value", ""),
            "lower_bound": resolution.get("lower_bound", ""),
            "upper_bound": resolution.get("upper_bound", ""),
            "value_expression": resolution.get("value_expression", ""),
            "period_start": resolution["period_start"],
            "period_end": resolution.get("period_end", ""),
            "replaces_requirement_id": resolution.get("replaces_requirement_id", ""),
            "knowledge_status": copy.deepcopy(item.get("knowledge_status", "")),
            "source_id": copy.deepcopy(item.get("source_id", "")),
        }
        copy_if_present(item, requirement, ("source_selector", "source_locator", "last_reviewed", "notes"))
        requirement_rows.append(requirement)
        migrated_requirement_ids.add(stable_id)
        transformations.append(
            {
                "kind": "extract_requirement",
                "stable_id": stable_id,
                "from": "Элементы модели",
                "to": "Требования показателей",
                "indicator_id": resolution["indicator_id"],
                "decision_id": resolution["decision_id"],
            }
        )

    resolved_indicator_ids = migrated_indicator_ids
    for row in requirement_rows:
        indicator_id = str(scalar_value(row["indicator_id"]))
        if indicator_id not in resolved_indicator_ids:
            raise MigrationError(
                "REQUIREMENT_INDICATOR_MISSING",
                f"{scalar_value(row['requirement_id'])}: показатель {indicator_id} не перенесён",
            )

    target["Элементы модели"] = remaining_elements
    target["Показатели"] = indicator_rows
    target["Привязки показателей"] = binding_rows
    target["Требования показателей"] = requirement_rows
    target["Экономические правила"] = []
    target["Условия назначений"] = []

    deviations: list[dict[str, Any]] = []
    for item in source["sheets"]["Отклонения"]:
        if not isinstance(item, dict):
            raise MigrationError("SOURCE_ROW_SHAPE_INVALID", "Отклонения: каждая строка должна быть объектом field→value")
        migrated = copy.deepcopy(item)
        if "norm_element_id" in migrated:
            migrated["norm_requirement_id"] = migrated.pop("norm_element_id")
        if "norm_element_selector" in migrated:
            migrated["norm_requirement_selector"] = migrated.pop("norm_element_selector")
        norm_id = str(value_of(migrated, "norm_requirement_id"))
        if norm_id and norm_id not in migrated_requirement_ids:
            questions.append(
                {
                    "kind": "deviation_norm_resolution",
                    "stable_id": str(value_of(migrated, "deviation_id")),
                    "norm_requirement_id": norm_id,
                    "question": "Отклонение ссылается на норматив, который ещё не разрешён как Требование показателя.",
                }
            )
        deviations.append(migrated)
    target["Отклонения"] = deviations

    unknown_indicator_resolutions = sorted(set(indicator_resolutions) - migrated_indicator_ids)
    unknown_requirement_resolutions = sorted(set(requirement_resolutions) - migrated_requirement_ids)
    if unknown_indicator_resolutions or unknown_requirement_resolutions:
        raise MigrationError(
            "SEMANTIC_RESOLUTION_TARGET_MISSING",
            f"решения ссылаются на отсутствующие legacy IDs: indicators={unknown_indicator_resolutions}, requirements={unknown_requirement_resolutions}",
        )
    return target, transformations, questions


def plan_migration(source: dict[str, Any]) -> dict[str, Any]:
    v3, v4 = validate_source(source)
    target_sheets, transformations, questions = transform_model(source, v3, v4)
    source_counts = {name: len(source["sheets"][name]) for name in v3["sheet_order"]}
    target_counts = {
        name: len(rows)
        for name, rows in target_sheets.items()
        if isinstance(rows, list)
    }
    source_authoring = {
        name: source["sheets"][name]
        for name in v3["sheet_order"]
        if name not in REGENERATED_SHEETS
    }
    target_authoring = {
        name: rows
        for name, rows in target_sheets.items()
        if name not in REGENERATED_SHEETS
    }
    status = "REQUIRES_INPUT" if questions else "PASS"
    plan_core = {
        "source_spreadsheet_id": source["spreadsheet_id"],
        "source_schema_version": "0.3",
        "source_build_fingerprint": source["build_fingerprint"],
        "source_sheet_order": v3["sheet_order"],
        "source_counts": source_counts,
        "source_authoring_fingerprint": canonical_hash(source_authoring),
        "source_settings_fingerprint": canonical_hash(source["settings"]),
        "target_schema_version": "0.4",
        "target_sheet_order": v4["sheet_order"],
        "target_builder": "scripts/build_template_v0_4.py",
        "target_counts": target_counts,
        "target_authoring_fingerprint": canonical_hash(target_authoring),
        "semantic_transformations": transformations,
        "questions": questions,
        "new_empty_economic_registries": list(NEW_ECONOMIC_SHEETS),
        "regenerated_sheets": list(REGENERATED_SHEETS),
        "source_copy_required": True,
        "source_must_remain_unchanged": True,
        "rollback": "Продолжить работу в исходной неизменённой книге v0.3",
        "inference_policy": "Не выдумывать управленческий вопрос, единицу наблюдения, binding, область норматива, показатель или экономику",
        "target_sheets": target_sheets,
    }
    migration_id = "mig-v03-v04-" + canonical_hash(plan_core)[:16]
    return {
        "status": status,
        "migration_id": migration_id,
        "migration_plan_fingerprint": canonical_hash(plan_core),
        **plan_core,
    }


def build_migration_package(source: dict[str, Any], *, target_title: str | None = None) -> dict[str, Any]:
    v3, v4 = validate_source(source)
    sheet_ids, named_range_ids = validate_execution_inventory(source, v3)
    plan = plan_migration(source)
    if plan["status"] != "PASS":
        unresolved = ", ".join(str(item.get("stable_id")) for item in plan["questions"])
        raise MigrationError("SEMANTIC_RESOLUTION_REQUIRED", f"нужны ответы по элементам: {unresolved}")
    configure_copy()
    title = target_title or f"{source.get('spreadsheet_title', 'Модель бизнеса')} — шаблон v0.4"
    payload = base_builder.build(v4, list(sheet_ids.values()), named_range_ids, title)

    restore_requests: list[dict[str, Any]] = []
    restored_counts: dict[str, int] = {}
    for sheet_name, source_rows in plan["target_sheets"].items():
        if sheet_name in REGENERATED_SHEETS:
            continue
        target_sheet = v4["sheets"][sheet_name]
        columns = target_sheet.get("columns", [])
        if any(not isinstance(item, dict) for item in source_rows):
            raise MigrationError("SOURCE_ROW_SHAPE_INVALID", f"{sheet_name}: каждая строка должна быть объектом field→value")
        unknown = sorted({field for item in source_rows for field in item if field not in columns})
        if unknown:
            raise MigrationError("SOURCE_FIELD_DRIFT", f"{sheet_name}: неизвестные поля {unknown}")
        if source_rows:
            data_start = int(target_sheet.get("data_start_row", v4["default_table"]["data_start_row"])) - 1
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
        "apply_to": "отдельная копия исходной книги v0.3 с sheetId/namedRangeId из inventory",
        "source_authoring_fingerprint": plan["source_authoring_fingerprint"],
        "source_settings_fingerprint": plan["source_settings_fingerprint"],
        "target_authoring_fingerprint": plan["target_authoring_fingerprint"],
        "semantic_transformations": plan["semantic_transformations"],
        "restored_counts": restored_counts,
        "settings_restored": True,
        "batch_update": payload,
    }


def verify_target(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    plan = plan_migration(source)
    if plan["status"] != "PASS":
        raise MigrationError("SEMANTIC_RESOLUTION_REQUIRED", "нельзя проверять target до разрешения всех вопросов")
    if target.get("schema_version") != "0.4":
        raise MigrationError("TARGET_SCHEMA_MISMATCH", "целевая inventory не объявляет v0.4")
    if target.get("sheet_order") != plan["target_sheet_order"]:
        raise MigrationError("TARGET_SHEET_ORDER_MISMATCH", "целевая книга не содержит точные 37 листов")
    target_sheets = target.get("sheets")
    if not isinstance(target_sheets, dict) or set(target_sheets) != set(plan["target_sheet_order"]):
        raise MigrationError("TARGET_SHEET_SET_MISMATCH", "целевая inventory неполна")
    for name, expected in plan["target_sheets"].items():
        if name in REGENERATED_SHEETS:
            continue
        if target_sheets[name] != expected:
            raise MigrationError("TARGET_VALUE_DRIFT", f"значения листа {name} не совпадают с принятым migration package")
    target_settings = target.get("settings")
    if not isinstance(target_settings, dict):
        raise MigrationError("TARGET_SETTINGS_MISSING", "целевая inventory должна содержать настройки Система")
    for field in ("model_id", "working_version_id", "working_version_selector", "current_version_id", "current_version_selector"):
        if scalar_value(target_settings.get(field)) != scalar_value(source["settings"].get(field)):
            raise MigrationError("TARGET_SETTINGS_DRIFT", f"настройка {field} не совпадает после вычисления builder")
    target_authoring = {
        name: target_sheets[name]
        for name in plan["target_sheet_order"]
        if name not in REGENERATED_SHEETS
    }
    return {
        "status": "PASS",
        "migration_id": plan["migration_id"],
        "source_authoring_fingerprint": plan["source_authoring_fingerprint"],
        "source_settings_fingerprint": plan["source_settings_fingerprint"],
        "target_authoring_fingerprint": canonical_hash(target_authoring),
        "semantic_transformations": plan["semantic_transformations"],
        "target_counts": {name: len(target_sheets[name]) for name in target_authoring},
        "source_unchanged": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="read-only inventory JSON книги v0.3")
    parser.add_argument("--target", type=Path, help="необязательная inventory JSON собранной книги v0.4")
    parser.add_argument("--build-package", action="store_true", help="сформировать batchUpdate для отдельной копии")
    parser.add_argument("--target-title", help="название целевой копии v0.4")
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
