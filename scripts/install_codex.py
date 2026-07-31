#!/usr/bin/env python3
"""Установить четыре скилла в локальный каталог Codex без скрытого удаления."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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
    for name in SKILLS:
        source = ROOT / "skills" / name
        destination = target / name
        shutil.copytree(source, destination, dirs_exist_ok=args.force)
        print(f"[OK] {name} -> {destination}")

    print("[OK] Установлено 4 скилла. Старый business-ontology не изменён и не входит в пакет.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
