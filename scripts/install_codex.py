#!/usr/bin/env python3
"""Установить четыре скилла в локальный каталог Codex без скрытого удаления."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "resolve-model-element",
    "model-production-system",
    "maintain-production-system",
    "audit-production-system",
)


def default_target() -> Path:
    codex_root = os.environ.get("CODEX_HOME")
    if codex_root:
        return Path(codex_root).expanduser() / "skills"
    return Path.home() / ".codex" / "skills"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=default_target(),
        help="Каталог skills локальной установки Codex",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Обновить существующие одноимённые папки без удаления посторонних скиллов",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validation = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_repository.py")],
        check=False,
    )
    if validation.returncode:
        return validation.returncode

    target = args.target.expanduser().resolve()
    existing = [name for name in SKILLS if (target / name).exists()]
    if existing and not args.force:
        print("[STOP] Одноимённые скиллы уже существуют:")
        for name in existing:
            print(f"  - {target / name}")
        print("Проверьте различия и повторите с --force, если обновление действительно нужно.")
        return 2

    target.mkdir(parents=True, exist_ok=True)
    transaction = Path(tempfile.mkdtemp(prefix=".production-system-skills-install-", dir=target))
    staged_root = transaction / "staged"
    backup_root = transaction / "backup"
    installed: list[str] = []
    backed_up: list[str] = []
    try:
        for name in SKILLS:
            source = ROOT / "skills" / name
            staged = staged_root / name
            shutil.copytree(source, staged)

        for name in SKILLS:
            destination = target / name
            staged = staged_root / name
            if destination.exists():
                backup_root.mkdir(parents=True, exist_ok=True)
                destination.replace(backup_root / name)
                backed_up.append(name)
            staged.replace(destination)
            installed.append(name)
            print(f"[OK] {name} -> {destination}")
    except Exception:
        for name in reversed(installed):
            destination = target / name
            if destination.exists():
                shutil.rmtree(destination)
        for name in reversed(backed_up):
            backup = backup_root / name
            if backup.exists():
                backup.replace(target / name)
        raise
    finally:
        shutil.rmtree(transaction, ignore_errors=True)

    print("[OK] Установлено 4 самодостаточных скилла атомарной заменой управляемых папок.")
    print("[OK] Устаревшие файлы внутри этих четырёх папок удалены; остальные скиллы не изменены.")
    print("[OK] Старый business-ontology не изменён и не входит в пакет.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
