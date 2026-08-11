#!/usr/bin/env python3
"""Локальный контур contracts, artifact fixtures и behavioral grader."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FIXTURES = {
    "resolve-model-element": {
        "required": [
            "semantic-resolution package",
            "семь тестов",
            "одновременно активен ровно один вопрос",
            "package_hash",
            "существующая модель не изменена этим скиллом",
            "причина отклонения",
            "подтверждённое отклонение",
            "норма наблюдаемости",
            "maintain-production-system",
            "METHODOLOGY-COMPATIBILITY.md",
        ],
    },
    "model-production-system": {
        "required": [
            "систему от продукта назад",
            "пройти исполнение вперёд",
            "одну ответственную позицию",
            "одной идемпотентной transaction",
            "bpmn, svg и manifest",
            "не создавать строки `отклонения`",
            "пробел модели",
            "нормы наблюдаемости",
            "минимальный допуск",
        ],
    },
    "maintain-production-system": {
        "required": [
            "классифицировать изменение",
            "карта влияния",
            "миграцию живых экземпляров",
            "разреженную редакцию",
            "принятие и ввод в действие",
            "migration-assessment",
            "migration dossier",
            "исходная v0.1-книга остаётся неизменной",
            "успешный отдельный пакет не равен успешной миграции",
            "что осталось неизвестным или не перенесённым",
            "режим миграции v0.2 → v0.3",
            "контур развития системы",
            "ровно одно основание",
            "гипотеза развития",
            "базовую версию",
            "--build-package",
            "подтверждение лёгкой карточки",
            "полный mutation package",
            "semantic_compatibility_checked",
        ],
    },
    "audit-production-system": {
        "required": [
            "read-only audit report",
            "evidence ledger",
            "разреженные версии",
            "проиграть минимум",
            "bpmn/svg lineage",
            "проверить контур развития",
            "лёгкую карточку кандидата",
            "базовую версию",
            "нормы наблюдаемости",
        ],
    },
}


def check_skill_contracts() -> list[str]:
    failures: list[str] = []
    for name, fixture in FIXTURES.items():
        path = ROOT / "skills" / name / "SKILL.md"
        text = path.read_text(encoding="utf-8").lower()
        for phrase in fixture["required"]:
            if phrase.lower() not in text:
                failures.append(f"{name}: отсутствует contract marker {phrase!r}")
    return failures


def run_fixture(script: str) -> int:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script)],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


def main() -> int:
    failures = check_skill_contracts()
    if failures:
        print("[FAIL] Контракты скиллов:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("[OK] Routing и критические предохранители четырёх скиллов присутствуют")

    failed_scripts = [
        script
        for script in (
            "run_versioning_fixtures.py",
            "run_bpmn_fixtures.py",
            "test_template_builder.py",
            "test_template_builder_v0_3.py",
            "test_migration_v0_2_to_v0_3.py",
            "test_install_codex.py",
        )
        if run_fixture(script) != 0
    ]
    if failed_scripts:
        print(f"[FAIL] Не прошли artifact fixtures: {', '.join(failed_scripts)}")
        return 1

    behavioral = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_behavioral_evals.py"), "--self-test"],
        cwd=ROOT,
        check=False,
    )
    if behavioral.returncode != 0:
        print("[FAIL] Behavioral transcript/outcome grader не прошёл самопроверку")
        return 1

    print("[OK] Versioning, BPMN и behavioral grader fixtures прошли")
    print("[INFO] Recorded fixtures не являются fresh-agent evidence; release gate требует отдельные 3/3 trials")
    return 0


if __name__ == "__main__":
    sys.exit(main())
