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
    (ROOT / "templates" / "migrations" / "v0.1-to-v0.2.md", "MIGRATION-v0.1-to-v0.2.md"),
)
RUNTIME_SKILLS = {
    "model-production-system",
    "maintain-production-system",
    "audit-production-system",
}
RUNTIME_FILES = (
    (ROOT / "scripts" / "bpmn" / "common.py", Path("bpmn/common.py")),
    (ROOT / "scripts" / "bpmn" / "generate.py", Path("bpmn/generate.py")),
    (ROOT / "scripts" / "bpmn" / "validate.py", Path("bpmn/validate.py")),
    (ROOT / "scripts" / "versioning" / "resolve.py", Path("versioning/resolve.py")),
    (ROOT / "scripts" / "build_template_v0_2.py", Path("build_template_v0_2.py")),
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
        runtime_count = 0
        if skill in RUNTIME_SKILLS:
            scripts = ROOT / "skills" / skill / "scripts"
            shutil.rmtree(scripts, ignore_errors=True)
            for source, relative in RUNTIME_FILES:
                destination = scripts / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                runtime_count += 1
        count = len(REFERENCES) + len(EXTRA_BUNDLED_FILES)
        print(f"[OK] {skill}: синхронизировано {count} reference-файлов и {runtime_count} runtime-файлов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
