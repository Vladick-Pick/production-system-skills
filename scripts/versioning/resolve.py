#!/usr/bin/env python3
"""Собрать materialized snapshot из разреженной линейной цепочки версий."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ALLOWED_STATUSES = {"черновик", "принято", "действует", "закрыто"}
ALLOWED_OPERATIONS = {"применить", "исключить"}


class ResolutionError(Exception):
    """Ожидаемая детерминированная ошибка resolver."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def resolve(case: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    versions: dict[str, dict[str, Any]] = {}
    for version in case["versions"]:
        version_id = version["version_id"]
        if version_id in versions:
            raise ResolutionError("DUPLICATE_VERSION")
        if version["status"] not in ALLOWED_STATUSES:
            raise ResolutionError("UNKNOWN_STATUS")
        versions[version_id] = version

    if sum(version["status"] == "черновик" for version in versions.values()) > 1:
        raise ResolutionError("MULTIPLE_DRAFTS")

    target = case["target_version_id"]
    if target not in versions:
        raise ResolutionError("MISSING_TARGET")

    chain: list[str] = []
    seen: set[str] = set()
    cursor: str | None = target
    while cursor is not None:
        if cursor in seen:
            raise ResolutionError("PREDECESSOR_CYCLE")
        if cursor not in versions:
            raise ResolutionError("MISSING_PREDECESSOR")
        seen.add(cursor)
        chain.append(cursor)
        cursor = versions[cursor].get("predecessor_version_id")

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    stable_ids: set[str] = set()
    for row in case["rows"]:
        version_id = row["version_id"]
        operation = row["version_operation"]
        stable_id = row["stable_id"]
        if version_id not in versions:
            raise ResolutionError("ROW_VERSION_MISSING")
        if operation not in ALLOWED_OPERATIONS:
            raise ResolutionError("UNKNOWN_OPERATION")
        key = (version_id, stable_id)
        if key in by_key:
            raise ResolutionError("DUPLICATE_REVISION")
        by_key[key] = row
        stable_ids.add(stable_id)

    snapshot: list[dict[str, Any]] = []
    for stable_id in sorted(stable_ids):
        for version_id in chain:
            row = by_key.get((version_id, stable_id))
            if row is None:
                continue
            if row["version_operation"] == "применить":
                snapshot.append(
                    {
                        "stable_id": stable_id,
                        "source_version_id": version_id,
                        "value": row.get("value"),
                    }
                )
            break

    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return snapshot, fingerprint


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON object с versions, rows и target_version_id")
    parser.add_argument("--output", type=Path, help="Необязательный JSON-файл результата")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    try:
        snapshot, fingerprint = resolve(payload)
    except ResolutionError as exc:
        print(json.dumps({"status": "FAIL", "error_code": exc.code}, ensure_ascii=False, indent=2))
        return 1

    result = {"status": "PASS", "snapshot": snapshot, "snapshot_fingerprint": fingerprint}
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
