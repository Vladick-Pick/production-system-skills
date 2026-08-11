#!/usr/bin/env python3
"""Проверить чистую и повторную атомарную установку самодостаточного пакета."""

from __future__ import annotations

import json
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
                "references/METHODOLOGY-COMPATIBILITY.md",
                "references/TEMPLATE-SCHEMA-v0.2.json",
                "references/TEMPLATE-SCHEMA-v0.3.json",
                "references/MIGRATION-v0.1-to-v0.2.md",
                "references/MIGRATION-v0.2-to-v0.3.md",
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
                "scripts/build_template_v0_3.py",
                "scripts/migrate_template_v0_2_to_v0_3.py",
            ):
                if not (target / name / relative).is_file():
                    raise AssertionError(f"{name}: нет {relative}")
            installed = target / name
            built = subprocess.run(
                [sys.executable, "scripts/build_template_v0_3.py", "--summary"],
                cwd=installed,
                text=True,
                capture_output=True,
                check=False,
            )
            if built.returncode != 0:
                raise AssertionError(f"{name}: установленный builder не запускается\n{built.stdout}\n{built.stderr}")
            summary = json.loads(built.stdout)
            if summary.get("schema_version") != "0.3" or len(summary.get("sheet_ids", {})) != 32:
                raise AssertionError(f"{name}: установленный builder собрал не v0.3/32 листа")

            migrated = subprocess.run(
                [
                    sys.executable,
                    "scripts/migrate_template_v0_2_to_v0_3.py",
                    str(ROOT / "evals" / "fixtures" / "migration-v0.2-to-v0.3" / "source.json"),
                    "--build-package",
                ],
                cwd=installed,
                text=True,
                capture_output=True,
                check=False,
            )
            if migrated.returncode != 0:
                raise AssertionError(f"{name}: установленная миграция не запускается\n{migrated.stdout}\n{migrated.stderr}")
            migration_result = json.loads(migrated.stdout)
            if migration_result.get("status") != "PASS" or not migration_result.get("settings_restored"):
                raise AssertionError(f"{name}: установленная миграция не собрала исполнимый пакет")

    print("[OK] Installer: чистая установка, stop без --force, удаление stale, сохранение посторонних skills")
    print("[OK] Самодостаточные builder/migration выполнены из каждой установленной runtime-папки")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
