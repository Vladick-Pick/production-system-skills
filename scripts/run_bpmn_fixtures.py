#!/usr/bin/env python3
"""Прогнать BPMN/SVG fixtures, lineage, readiness и воспроизводимость."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "bpmn" / "generate.py"
VALIDATOR = ROOT / "scripts" / "bpmn" / "validate.py"
FIXTURES = ROOT / "evals" / "fixtures" / "bpmn"
BUILT_AT = "2026-08-09T00:00:00Z"


def run(command: list[str], expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if expect_success and result.returncode != 0:
        raise AssertionError(f"команда упала: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"команда должна была упасть: {' '.join(command)}")
    return result


def paths(output: Path, process_id: str, version_id: str) -> tuple[Path, Path, Path]:
    base = output / f"{process_id}--{version_id}"
    return base.with_suffix(".bpmn"), base.with_suffix(".svg"), output / f"{process_id}--{version_id}.manifest.json"


def build_and_validate(fixture: Path, output: Path, process_id: str, version_id: str) -> dict[str, object]:
    run(
        [
            sys.executable,
            str(GENERATOR),
            str(fixture),
            "--output-dir",
            str(output),
            "--expected-version-id",
            version_id,
            "--built-at",
            BUILT_AT,
        ]
    )
    bpmn, svg, manifest_path = paths(output, process_id, version_id)
    run(
        [
            sys.executable,
            str(VALIDATOR),
            str(fixture),
            "--bpmn",
            str(bpmn),
            "--svg",
            str(svg),
            "--manifest",
            str(manifest_path),
            "--expected-version-id",
            version_id,
        ]
    )
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="production-system-bpmn-") as temp:
        root = Path(temp)
        normal_a = root / "normal-a"
        normal_b = root / "normal-b"
        complex_out = root / "complex"
        unknown_out = root / "unknown"

        normal_manifest = build_and_validate(
            FIXTURES / "normal-path.json", normal_a, "proc-lead-capture", "v2"
        )
        build_and_validate(
            FIXTURES / "normal-path.json", normal_b, "proc-lead-capture", "v2"
        )
        complex_manifest = build_and_validate(
            FIXTURES / "complex-flow.json", complex_out, "proc-qualify-lead", "v2"
        )
        unknown_manifest = build_and_validate(
            FIXTURES / "unknown-connector.json",
            unknown_out,
            "proc-unknown-connector",
            "v2",
        )

        if normal_manifest["readiness_status"] != "готова к просмотру":
            raise AssertionError("normal path не должен обходить внешний Modeler gate")
        if complex_manifest["readiness_status"] != "готова к просмотру":
            raise AssertionError("complex flow не должен обходить внешний Modeler gate")
        unknown_codes = {item["code"] for item in unknown_manifest["deployment_blockers"]}
        if "JOB_TYPE_MISSING" not in unknown_codes:
            raise AssertionError("unknown connector не заблокировал deployment")
        if "MODELER_VALIDATION_MISSING" not in unknown_codes:
            raise AssertionError("нет внешнего Modeler blocker")

        for suffix in (".bpmn", ".svg", ".manifest.json"):
            first = normal_a / f"proc-lead-capture--v2{suffix}"
            second = normal_b / f"proc-lead-capture--v2{suffix}"
            if first.read_bytes() != second.read_bytes():
                raise AssertionError(f"повторная сборка изменила bytes {suffix}")

        complex_bpmn = (complex_out / "proc-qualify-lead--v2.bpmn").read_text(encoding="utf-8")
        for marker in (
            "mat-qualification-script",
            "is-crm",
            "cp-club",
            "proc-compliance-check",
            "PT30M",
            "edge-quality-rejected",
        ):
            if marker not in complex_bpmn:
                raise AssertionError(f"BPMN не содержит trace marker {marker}")

        stale = run(
            [
                sys.executable,
                str(GENERATOR),
                str(FIXTURES / "normal-path.json"),
                "--output-dir",
                str(root / "stale"),
                "--expected-version-id",
                "v3",
                "--built-at",
                BUILT_AT,
            ],
            expect_success=False,
        )
        if "STALE_VERSION" not in stale.stdout:
            raise AssertionError("stale version не обнаружена")

        schema = json.loads((ROOT / "templates" / "template-schema-v0.2.json").read_text(encoding="utf-8"))
        if "Проекция draw.io" in schema["sheet_order"]:
            raise AssertionError("draw.io попал в финальный v0.2")

    print("[OK] BPMN/SVG: normal, decision, exclusive, parallel, timer, return, subprocess, automation")
    print("[OK] Lineage, materials/IS properties, stale version, unknown connector, repeat bytes")
    print("[INFO] Camunda Desktop Modeler gate не симулируется и остаётся deployment blocker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
