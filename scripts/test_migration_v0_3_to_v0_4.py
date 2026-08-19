#!/usr/bin/env python3
"""Регрессия миграции v0.3 → v0.4: preserve, interview gate, map boundary."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from migrate_template_v0_3_to_v0_4 import (
    MigrationError,
    build_migration_package,
    plan_migration,
    verify_target,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals" / "fixtures" / "migration-v0.3-to-v0.4" / "source.json"


def expect_error(source: dict, code: str, *, build: bool = False) -> None:
    try:
        if build:
            build_migration_package(source)
        else:
            plan_migration(source)
    except MigrationError as exc:
        if exc.code != code:
            raise AssertionError(f"ожидалась ошибка {code}, получена {exc.code}") from exc
    else:
        raise AssertionError(f"ожидалась ошибка {code}")


def main() -> int:
    source = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source_before = copy.deepcopy(source)
    first = plan_migration(source)
    second = plan_migration(source)
    if source != source_before:
        raise AssertionError("migration planner изменил исходную inventory")
    if first != second:
        raise AssertionError("одинаковый source должен давать один migration plan")
    if first["status"] != "PASS" or first["questions"]:
        raise AssertionError("полный fixture должен проходить без дополнительных вопросов")
    if len(first["source_sheet_order"]) != 32 or len(first["target_sheet_order"]) != 37:
        raise AssertionError("миграция должна менять 32 листа на 37")
    if first["new_empty_economic_registries"] != ["Экономические правила", "Условия назначений"]:
        raise AssertionError("миграция не должна выдумывать экономику")
    if first["target_sheets"]["Экономические правила"] or first["target_sheets"]["Условия назначений"]:
        raise AssertionError("новые экономические реестры должны быть пустыми")

    remaining_element_ids = {row["element_id"] for row in first["target_sheets"]["Элементы модели"]}
    if remaining_element_ids != {"el-sla"}:
        raise AssertionError("SLA должен остаться, а показатель и норматив — перейти в самостоятельные реестры")
    indicators = first["target_sheets"]["Показатели"]
    requirements = first["target_sheets"]["Требования показателей"]
    bindings = first["target_sheets"]["Привязки показателей"]
    if [row["indicator_id"] for row in indicators] != ["el-conversion"]:
        raise AssertionError("stable ID показателя не сохранён")
    if [row["requirement_id"] for row in requirements] != ["el-conversion-norm"]:
        raise AssertionError("stable ID норматива не сохранён")
    if bindings[0]["indicator_id"] != "el-conversion" or bindings[0]["fact_source_id"] != "src-crm":
        raise AssertionError("binding показателя не связывает карту с источником фактов")
    if first["target_sheets"]["Гипотезы"][0]["primary_metric_id"] != "el-conversion":
        raise AssertionError("ссылка гипотезы на stable ID показателя потеряна")
    deviation = first["target_sheets"]["Отклонения"][0]
    if deviation.get("norm_requirement_id") != "el-conversion-norm" or "norm_element_id" in deviation:
        raise AssertionError("ссылка отклонения не переименована в требование показателя")

    package = build_migration_package(source, target_title="Тестовая миграция v0.4")
    repeated = build_migration_package(source, target_title="Тестовая миграция v0.4")
    if source != source_before:
        raise AssertionError("migration package изменил исходную inventory")
    if package["batch_update"]["batch_fingerprint"] != repeated["batch_update"]["batch_fingerprint"]:
        raise AssertionError("один source должен давать детерминированный batch")
    batch = package["batch_update"]
    created = [item for item in batch["requests"] if "addSheet" in item and not item["addSheet"]["properties"]["title"].startswith("__")]
    if len(created) != 37:
        raise AssertionError("migration package должен создать точные 37 листов")
    deleted_source_ids = {
        item["deleteSheet"]["sheetId"]
        for item in batch["requests"]
        if "deleteSheet" in item and item["deleteSheet"]["sheetId"] in set(source["sheet_ids"].values())
    }
    if deleted_source_ids != set(source["sheet_ids"].values()):
        raise AssertionError("пакет должен пересобирать только отдельную копию со всеми 32 исходными sheetId")
    indicator_sheet_id = batch["sheet_ids"]["Показатели"]
    restored_indicator = [
        request
        for request in batch["requests"]
        if request.get("updateCells", {}).get("range", {}).get("sheetId") == indicator_sheet_id
        and request.get("updateCells", {}).get("range", {}).get("startRowIndex") == 4
        and any(
            cell.get("userEnteredValue", {}).get("stringValue") == "el-conversion"
            for row in request.get("updateCells", {}).get("rows", [])
            for cell in row.get("values", [])
        )
    ]
    if len(restored_indicator) != 1:
        raise AssertionError("batchUpdate не восстанавливает перенесённый показатель")
    if package["restored_counts"]["Показатели"] != 1 or package["restored_counts"]["Требования показателей"] != 1:
        raise AssertionError("migration report не отражает семантические преобразования")

    system_id = batch["sheet_ids"]["Система"]
    overwritten_pointer_ids = [
        request
        for request in batch["requests"]
        if request.get("updateCells", {}).get("range", {}).get("sheetId") == system_id
        and request.get("updateCells", {}).get("range", {}).get("startRowIndex") in (3, 4)
        and request.get("updateCells", {}).get("range", {}).get("startColumnIndex") == 1
        and any(
            cell.get("userEnteredValue", {}).get("stringValue") == "ver-v03"
            for row in request.get("updateCells", {}).get("rows", [])
            for cell in row.get("values", [])
        )
    ]
    if overwritten_pointer_ids:
        raise AssertionError("migration package заменил вычисляемые version ID статическим текстом")

    unresolved = copy.deepcopy(source)
    unresolved["semantic_resolutions"]["v0.4"]["indicators"] = {}
    unresolved["semantic_resolutions"]["v0.4"]["requirements"] = {}
    unresolved_plan = plan_migration(unresolved)
    if unresolved_plan["status"] != "REQUIRES_INPUT":
        raise AssertionError("неразрешённые legacy элементы должны запускать интервью, а не молчаливый перенос")
    question_kinds = {item["kind"] for item in unresolved_plan["questions"]}
    if not {"indicator_resolution", "requirement_resolution", "deviation_norm_resolution"} <= question_kinds:
        raise AssertionError(f"migration plan не объясняет все смысловые вопросы: {question_kinds}")
    expect_error(unresolved, "SEMANTIC_RESOLUTION_REQUIRED", build=True)

    bad_financial = copy.deepcopy(source)
    financial = bad_financial["semantic_resolutions"]["v0.4"]["indicators"]["el-conversion"]
    financial["indicator_kind"] = "финансовый"
    expect_error(bad_financial, "FINANCIAL_INDICATOR_RESOLUTION_INVALID")
    bad_value = copy.deepcopy(source)
    bad_value["semantic_resolutions"]["v0.4"]["requirements"]["el-conversion-norm"]["lower_bound"] = 0.1
    expect_error(bad_value, "REQUIREMENT_VALUE_SHAPE_INVALID")

    target = {
        "schema_version": "0.4",
        "sheet_order": first["target_sheet_order"],
        "sheets": {
            name: ([] if name in first["regenerated_sheets"] else copy.deepcopy(first["target_sheets"][name]))
            for name in first["target_sheet_order"]
        },
        "settings": copy.deepcopy(source["settings"]),
    }
    verified = verify_target(source, target)
    if verified["status"] != "PASS" or verified["target_authoring_fingerprint"] != first["target_authoring_fingerprint"]:
        raise AssertionError("target verification не доказал точное применение transformation package")

    drift = copy.deepcopy(source)
    drift["sheet_order"] = drift["sheet_order"][:-1]
    expect_error(drift, "SOURCE_SHEET_ORDER_DRIFT")
    missing = copy.deepcopy(source)
    del missing["sheets"]["Отклонения"]
    expect_error(missing, "SOURCE_SHEET_SET_DRIFT")
    wrong = copy.deepcopy(source)
    wrong["schema_version"] = "0.2"
    expect_error(wrong, "SOURCE_SCHEMA_MISMATCH")

    bad_target = copy.deepcopy(target)
    bad_target["sheets"]["Экономические правила"] = [{"economic_rule_id": "invented"}]
    try:
        verify_target(source, bad_target)
    except MigrationError as exc:
        if exc.code != "TARGET_VALUE_DRIFT":
            raise
    else:
        raise AssertionError("verify_target принял выдуманную экономику")

    print(
        "[OK] Migration v0.3→v0.4: 32→37 sheets, stable IDs preserved, "
        "semantic interview required, economics not invented, sparse batch verified"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
