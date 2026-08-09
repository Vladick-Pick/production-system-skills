#!/usr/bin/env python3
"""Детерминированные fixtures разреженного resolver версий v0.2."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from versioning.resolve import ResolutionError, resolve


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals" / "fixtures" / "versioning" / "cases.json"
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
