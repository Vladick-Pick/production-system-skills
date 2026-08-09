#!/usr/bin/env python3
"""Проверить чистую и повторную атомарную установку самодостаточного пакета."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_codex.py"
SKILLS = (
    "resolve-model-element",
    "model-production-system",
    "maintain-production-system",
    "audit-production-system",
)
RUNTIME_SKILLS = SKILLS[1:]


def run(target: Path, force: bool = False, expected: int = 0) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(INSTALLER), "--target", str(target)]
    if force:
        command.append("--force")
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != expected:
        raise AssertionError(f"installer rc={result.returncode}, expected={expected}\n{result.stdout}\n{result.stderr}")
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="production-system-install-test-") as temp:
        target = Path(temp) / "skills"
        run(target)
        run(target, expected=2)

        stale = target / "model-production-system" / "STALE.txt"
        stale.write_text("old", encoding="utf-8")
        unrelated = target / "unrelated-skill"
        unrelated.mkdir()
        (unrelated / "KEEP.txt").write_text("keep", encoding="utf-8")

        run(target, force=True)
        if stale.exists():
            raise AssertionError("--force оставил устаревший файл")
        if not (unrelated / "KEEP.txt").is_file():
            raise AssertionError("installer изменил посторонний скилл")

        for name in SKILLS:
            skill = target / name
            for relative in (
                "SKILL.md",
                "references/LANGUAGE.md",
                "references/TEMPLATE-SCHEMA-v0.2.json",
                "references/MIGRATION-v0.1-to-v0.2.md",
            ):
                if not (skill / relative).is_file():
                    raise AssertionError(f"{name}: нет {relative}")
        for name in RUNTIME_SKILLS:
            for relative in (
                "scripts/versioning/resolve.py",
                "scripts/bpmn/common.py",
                "scripts/bpmn/generate.py",
                "scripts/bpmn/validate.py",
                "scripts/build_template_v0_2.py",
            ):
                if not (target / name / relative).is_file():
                    raise AssertionError(f"{name}: нет {relative}")

    print("[OK] Installer: чистая установка, stop без --force, удаление stale, сохранение посторонних skills")
    print("[OK] Самодостаточные migration, versioning, BPMN и template runtime-файлы присутствуют")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
