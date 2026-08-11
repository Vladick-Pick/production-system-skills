#!/usr/bin/env python3
"""Регрессия миграции v0.2 → v0.3: preserve, empty registries, drift stop."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from migrate_template_v0_2_to_v0_3 import MigrationError, plan_migration, verify_target


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals" / "fixtures" / "migration-v0.2-to-v0.3" / "source.json"


def expect_error(source: dict, code: str) -> None:
    try:
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
    if len(first["source_sheet_order"]) != 29 or len(first["target_sheet_order"]) != 32:
        raise AssertionError("миграция должна менять 29 листов на 32")
    if first["new_empty_registries"] != ["Отклонения", "Гипотезы", "Эксперименты"]:
        raise AssertionError("миграция добавляет не те реестры")
    if any(first["target_sheets"][name] for name in first["new_empty_registries"]):
        raise AssertionError("новые реестры должны быть пустыми")
    if first["source_value_fingerprint"] != first["target_preserved_value_fingerprint"]:
        raise AssertionError("fingerprint сохраняемых значений изменился")
    if first["target_sheets"]["Процессы"] != source["sheets"]["Процессы"]:
        raise AssertionError("авторские значения процессов не сохранены")
    if first["target_sheets"]["Решения"] != source["sheets"]["Решения"]:
        raise AssertionError("история решений не сохранена")

    target = {
        "schema_version": "0.3",
        "sheet_order": first["target_sheet_order"],
        "sheets": first["target_sheets"],
    }
    verified = verify_target(source, target)
    if verified["status"] != "PASS" or verified["source_value_fingerprint"] != verified["target_value_fingerprint"]:
        raise AssertionError("target verification не доказал сохранность")

    drift = copy.deepcopy(source)
    drift["sheet_order"] = drift["sheet_order"][:-1]
    expect_error(drift, "SOURCE_SHEET_ORDER_DRIFT")
    missing = copy.deepcopy(source)
    del missing["sheets"]["Объекты"]
    expect_error(missing, "SOURCE_SHEET_SET_DRIFT")
    wrong = copy.deepcopy(source)
    wrong["schema_version"] = "0.1"
    expect_error(wrong, "SOURCE_SCHEMA_MISMATCH")

    bad_target = copy.deepcopy(target)
    bad_target["sheets"]["Отклонения"] = [{"deviation_id": "invented-history"}]
    try:
        verify_target(source, bad_target)
    except MigrationError as exc:
        if exc.code != "TARGET_NEW_REGISTRY_NOT_EMPTY":
            raise
    else:
        raise AssertionError("verify_target принял выдуманную историю развития")

    print(
        "[OK] Migration v0.2→v0.3: 29→32 sheets, values preserved, "
        "new registries empty, drift and invented history rejected"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
