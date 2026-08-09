#!/usr/bin/env python3
"""Детерминированные fixtures разреженного resolver версий v0.2."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals" / "fixtures" / "versioning" / "cases.json"
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
    payload = json.loads(FIXTURES.read_text(encoding="utf-8"))
    failures: list[str] = []

    for case in payload["cases"]:
        case_id = case["case_id"]
        expected_error = case.get("expected_error")
        try:
            snapshot, fingerprint = resolve(case)
        except ResolutionError as exc:
            if exc.code != expected_error:
                failures.append(
                    f"{case_id}: ошибка {exc.code}, ожидалась {expected_error or 'успешная сборка'}"
                )
            else:
                print(f"[OK] {case_id}: {exc.code}")
            continue

        if expected_error:
            failures.append(f"{case_id}: ожидалась ошибка {expected_error}, но срез собран")
            continue

        expected = sorted(case["expected_snapshot"], key=lambda row: row["stable_id"])
        if snapshot != expected:
            failures.append(
                f"{case_id}: срез не совпал; ожидалось {expected!r}, получено {snapshot!r}"
            )
        else:
            print(f"[OK] {case_id}: {len(snapshot)} элементов, sha256={fingerprint[:12]}")

    if failures:
        print("[FAIL] Versioning fixtures:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"[OK] Versioning resolver: {len(payload['cases'])} fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
