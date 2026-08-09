#!/usr/bin/env python3
"""Проверить IR, BPMN/SVG lineage, hashes и readiness без deployment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from common import (
    BPMNDI_NS,
    BPMN_NS,
    MODELER_NS,
    all_nodes,
    canonical_node_id,
    model_fingerprint,
    read_ir,
    readiness_from_issues,
    sha256_bytes,
    validate_ir,
)


def q(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def properties(element: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for prop in element.findall(f"./{q(BPMN_NS, 'extensionElements')}/{q(MODELER_NS, 'properties')}/{q(MODELER_NS, 'property')}"):
        name = prop.get("name")
        value = prop.get("value")
        if name is not None and value is not None:
            result[name] = value
    return result


def collect_trace(root: ET.Element) -> dict[str, dict[str, str]]:
    trace: dict[str, dict[str, str]] = {
        "process": {},
        "system": {},
        "position": {},
        "action": {},
        "event": {},
        "gateway": {},
        "edge": {},
    }
    keys = {
        "canonicalProcessId": "process",
        "canonicalSystemId": "system",
        "canonicalPositionId": "position",
        "canonicalActionId": "action",
        "canonicalEventId": "event",
        "canonicalGatewayId": "gateway",
        "canonicalEdgeId": "edge",
    }
    for element in root.iter():
        props = properties(element)
        for prop_name, kind in keys.items():
            value = props.get(prop_name)
            if value:
                trace[kind][value] = element.get("id", "")
    return trace


def validate_artifacts(
    ir: dict[str, Any],
    bpmn_path: Path,
    svg_path: Path,
    manifest_path: Path,
    expected_version_id: str | None,
) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    ir_issues = validate_ir(ir, expected_version_id)
    if any(issue.blocks_view for issue in ir_issues):
        failures.extend({"code": issue.code, "message": issue.message} for issue in ir_issues if issue.blocks_view)
        return failures

    try:
        bpmn_bytes = bpmn_path.read_bytes()
        root = ET.fromstring(bpmn_bytes)
    except (OSError, ET.ParseError) as exc:
        return [{"code": "BPMN_XML", "message": str(exc)}]
    try:
        svg_bytes = svg_path.read_bytes()
        svg_root = ET.fromstring(svg_bytes)
    except (OSError, ET.ParseError) as exc:
        return [{"code": "SVG_XML", "message": str(exc)}]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [{"code": "MANIFEST_JSON", "message": str(exc)}]

    if root.tag != q(BPMN_NS, "definitions"):
        failures.append({"code": "BPMN_ROOT", "message": "root не bpmn:definitions"})
    if svg_root.tag != "{http://www.w3.org/2000/svg}svg":
        failures.append({"code": "SVG_ROOT", "message": "root не svg"})

    all_ids: list[str] = [element.get("id") for element in root.iter() if element.get("id")]
    if len(all_ids) != len(set(all_ids)):
        failures.append({"code": "BPMN_DUPLICATE_ID", "message": "BPMN XML содержит повторяющиеся id"})
    id_set = set(all_ids)
    for element in root.iter():
        for attribute in ("sourceRef", "targetRef", "processRef", "bpmnElement", "attachedToRef", "default"):
            ref = element.get(attribute)
            if ref and ref not in id_set:
                failures.append({"code": "BPMN_BROKEN_REF", "message": f"{attribute}={ref} не разрешается"})

    fingerprint = model_fingerprint(ir)
    if manifest.get("model_fingerprint") != fingerprint:
        failures.append({"code": "MANIFEST_FINGERPRINT", "message": "manifest fingerprint не совпадает с IR"})
    if svg_root.get("data-model-fingerprint") != fingerprint:
        failures.append({"code": "SVG_FINGERPRINT", "message": "SVG fingerprint не совпадает с IR"})
    process_elements = root.findall(f".//{q(BPMN_NS, 'process')}")
    if len(process_elements) != 1 or properties(process_elements[0]).get("modelFingerprint") != fingerprint:
        failures.append({"code": "BPMN_FINGERPRINT", "message": "BPMN process fingerprint не совпадает с IR"})

    if manifest.get("bpmn_sha256") != sha256_bytes(bpmn_bytes):
        failures.append({"code": "BPMN_HASH", "message": "bpmn_sha256 не совпадает"})
    if manifest.get("svg_sha256") != sha256_bytes(svg_bytes):
        failures.append({"code": "SVG_HASH", "message": "svg_sha256 не совпадает"})
    if manifest.get("process_id") != ir["process"].get("process_id"):
        failures.append({"code": "MANIFEST_PROCESS", "message": "manifest process_id не совпадает"})
    if manifest.get("version_id") != ir["process"].get("version_id"):
        failures.append({"code": "MANIFEST_VERSION", "message": "manifest version_id не совпадает"})

    expected_readiness = readiness_from_issues(ir_issues)
    if manifest.get("readiness_status") != expected_readiness:
        failures.append({"code": "READINESS", "message": "manifest readiness не следует из IR issues"})

    trace = collect_trace(root)
    expected = {
        "process": {str(ir["process"]["process_id"])},
        "system": {str(ir["process"]["system_id"])},
        "position": {str(lane["position_id"]) for lane in ir.get("lanes", [])},
        "action": {str(action["action_id"]) for action in ir.get("actions", [])},
        "event": {str(event["event_id"]) for event in ir.get("events", [])},
        "gateway": {str(gateway["gateway_id"]) for gateway in ir.get("gateways", [])},
        "edge": {str(flow["edge_id"]) for flow in ir.get("flows", [])},
    }
    for kind, expected_ids in expected.items():
        actual_ids = set(trace[kind])
        if actual_ids != expected_ids:
            failures.append(
                {
                    "code": "TRACE_MISMATCH",
                    "message": f"{kind}: expected={sorted(expected_ids)}, actual={sorted(actual_ids)}",
                }
            )

    manifest_ids = set(manifest.get("included_stable_ids", []))
    expected_manifest_ids = set().union(*expected.values())
    if manifest_ids != expected_manifest_ids:
        failures.append(
            {
                "code": "MANIFEST_TRACE",
                "message": f"included_stable_ids расходятся: missing={sorted(expected_manifest_ids-manifest_ids)}, extra={sorted(manifest_ids-expected_manifest_ids)}",
            }
        )

    bpmn_shapes = root.findall(f".//{q(BPMNDI_NS, 'BPMNShape')}")
    bpmn_edges = root.findall(f".//{q(BPMNDI_NS, 'BPMNEdge')}")
    if not bpmn_shapes or len(bpmn_edges) != len(ir.get("flows", [])):
        failures.append({"code": "BPMN_DI", "message": "BPMN DI не покрывает shapes/flows"})

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ir", type=Path)
    parser.add_argument("--bpmn", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-version-id")
    args = parser.parse_args()

    ir = read_ir(args.ir)
    failures = validate_artifacts(ir, args.bpmn, args.svg, args.manifest, args.expected_version_id)
    if failures:
        print(json.dumps({"status": "FAIL", "failures": failures}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "PASS", "process_id": ir["process"]["process_id"], "version_id": ir["process"]["version_id"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
