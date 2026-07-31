#!/usr/bin/env python3
"""Статические поведенческие fixtures; не заменяют живой forward-тест агента."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FIXTURES = {
    "resolve-model-element": {
        "required": [
            "карту противоречий",
            "опровергнуть свою гипотезу",
            "предложить готовое определение",
            "задать один вопрос",
            "оставить нерешённым",
        ],
    },
    "model-production-system": {
        "required": [
            "от продукта назад",
            "пройти исполнение вперёд",
            "один основной объект",
            "проиграть сценарии",
            "проекцию draw.io",
        ],
    },
    "maintain-production-system": {
        "required": [
            "классифицировать изменение",
            "карту влияния",
            "активных экземпляров",
            "принятая версия неизменяема",
            "синхронизировать представления",
        ],
    },
    "audit-production-system": {
        "required": [
            "read-only",
            "не исправлять найденное",
            "проиграть исполнение",
            "слепых зон",
            "не перерисовывать схему",
        ],
    },
}


def main() -> int:
    failures: list[str] = []
    for name, fixture in FIXTURES.items():
        path = ROOT / "skills" / name / "SKILL.md"
        text = path.read_text(encoding="utf-8").lower()
        for phrase in fixture["required"]:
            if phrase.lower() not in text:
                failures.append(f"{name}: отсутствует поведенческий маркер {phrase!r}")

    if failures:
        print("[FAIL] Контрактные fixtures:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("[OK] Четыре поведенческих контракта содержат обязательные предохранители")
    print("[INFO] Это статическая проверка; живой forward-тест выполняется в отдельной сессии")
    return 0


if __name__ == "__main__":
    sys.exit(main())
