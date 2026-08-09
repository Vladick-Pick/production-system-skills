#!/usr/bin/env python3
"""Синхронизировать общие контракты в четыре самодостаточные папки скиллов."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "resolve-model-element",
    "model-production-system",
    "maintain-production-system",
    "audit-production-system",
)
REFERENCES = (
    "LANGUAGE.md",
    "METAONTOLOGY.md",
    "INTERVIEW-CONTRACT.md",
    "TEMPLATE-CONTRACT.md",
    "PROJECTION-CONTRACT.md",
)
EXTRA_BUNDLED_FILES = (
    (ROOT / "templates" / "template-schema-v0.2.json", "TEMPLATE-SCHEMA-v0.2.json"),
)


def main() -> int:
    for skill in SKILLS:
        target = ROOT / "skills" / skill / "references"
        target.mkdir(parents=True, exist_ok=True)
        for name in REFERENCES:
            source = ROOT / "references" / name
            destination = target / name
            shutil.copy2(source, destination)
        for source, name in EXTRA_BUNDLED_FILES:
            shutil.copy2(source, target / name)
        count = len(REFERENCES) + len(EXTRA_BUNDLED_FILES)
        print(f"[OK] {skill}: синхронизировано {count} reference-файлов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
