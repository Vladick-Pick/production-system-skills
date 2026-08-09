#!/usr/bin/env python3
"""Сгенерировать детерминированные BPMN, SVG и manifest из projection IR."""

from __future__ import annotations

import argparse
import html
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from common import (
    BPMNDI_NS,
    BPMN_NS,
    DC_NS,
    DI_NS,
    GENERATOR_VERSION,
    LAYOUT_VERSION,
    MODELER_NS,
    ProjectionIssue,
    XSI_NS,
    ZEEBE_NS,
    all_nodes,
    bpmn_node_id,
    canonical_json,
    canonical_node_id,
    layout,
    model_fingerprint,
    node_kind,
    read_ir,
    readiness_from_issues,
    safe_filename_component,
    sha256_bytes,
    validate_ir,
    write_bytes,
    xml_id,
)


for prefix, namespace in (
    ("bpmn", BPMN_NS),
    ("bpmndi", BPMNDI_NS),
    ("dc", DC_NS),
    ("di", DI_NS),
    ("xsi", XSI_NS),
    ("zeebe", ZEEBE_NS),
    ("modeler", MODELER_NS),
):
    ET.register_namespace(prefix, namespace)


def q(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def add_properties(parent: ET.Element, properties: dict[str, Any]) -> None:
    extension = ET.SubElement(parent, q(BPMN_NS, "extensionElements"))
    container = ET.SubElement(extension, q(MODELER_NS, "properties"))
    for name in sorted(properties):
        value = properties[name]
        if isinstance(value, (list, dict)):
            value = canonical_json(value)
        ET.SubElement(container, q(MODELER_NS, "property"), {"name": str(name), "value": str(value)})


def flow_waypoints(source: dict[str, float], target: dict[str, float]) -> list[tuple[float, float]]:
    source_center_y = source["y"] + source["height"] / 2
    target_center_y = target["y"] + target["height"] / 2
    if target["x"] >= source["x"]:
        start = (source["x"] + source["width"], source_center_y)
        end = (target["x"], target_center_y)
        middle_x = (start[0] + end[0]) / 2
    else:
        start = (source["x"], source_center_y)
        end = (target["x"] + target["width"], target_center_y)
        middle_x = min(start[0], end[0]) - 55
    if abs(start[1] - end[1]) < 1:
        return [start, end]
    return [start, (middle_x, start[1]), (middle_x, end[1]), end]


def svg_text_lines(label: str, max_chars: int) -> list[str]:
    return textwrap.wrap(label, width=max_chars, break_long_words=False, break_on_hyphens=False) or [""]


def svg_text_block(label: str, x: float, y: float, max_chars: int, css_class: str = "label") -> str:
    lines = svg_text_lines(label, max_chars)
    first_y = y - (len(lines) - 1) * 8
    tspans = "".join(
        f'<tspan x="{x}" y="{first_y + index * 16}">{html.escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return f'<text class="{css_class}" text-anchor="middle">{tspans}</text>'


def bpmn_bytes(ir: dict[str, Any], fingerprint: str, geometry: dict[str, Any]) -> bytes:
    process_data = ir["process"]
    process_xml_id = xml_id("Process", str(process_data["process_id"]))
    participant_xml_id = xml_id("Participant", str(process_data["system_id"]))
    collaboration_xml_id = xml_id("Collaboration", str(process_data["process_id"]))

    definitions = ET.Element(
        q(BPMN_NS, "definitions"),
        {
            "id": xml_id("Definitions", f"{process_data['process_id']}::{process_data['version_id']}"),
            "targetNamespace": "https://github.com/Vladick-Pick/production-system-skills",
            "exporter": "production-system-skills",
            "exporterVersion": GENERATOR_VERSION,
        },
    )
    collaboration = ET.SubElement(definitions, q(BPMN_NS, "collaboration"), {"id": collaboration_xml_id})
    participant = ET.SubElement(
        collaboration,
        q(BPMN_NS, "participant"),
        {
            "id": participant_xml_id,
            "name": str(process_data.get("system_name") or process_data["system_id"]),
            "processRef": process_xml_id,
        },
    )
    add_properties(
        participant,
        {
            "canonicalSystemId": process_data["system_id"],
            "versionId": process_data["version_id"],
            "modelFingerprint": fingerprint,
        },
    )
    process = ET.SubElement(
        definitions,
        q(BPMN_NS, "process"),
        {
            "id": process_xml_id,
            "name": str(process_data["name"]),
            "isExecutable": "true" if process_data.get("is_executable") else "false",
        },
    )
    add_properties(
        process,
        {
            "canonicalProcessId": process_data["process_id"],
            "canonicalSystemId": process_data["system_id"],
            "versionId": process_data["version_id"],
            "modelFingerprint": fingerprint,
            "targetCamundaVersion": process_data.get("target_camunda_version", ""),
        },
    )

    node_map = {canonical_node_id(node): bpmn_node_id(node) for node in all_nodes(ir)}
    incoming: dict[str, list[str]] = {node_id: [] for node_id in node_map}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_map}
    for flow in ir.get("flows", []):
        flow_xml_id = xml_id("Flow", str(flow["edge_id"]))
        outgoing[str(flow["source_id"])].append(flow_xml_id)
        incoming[str(flow["target_id"])].append(flow_xml_id)

    lane_set = ET.SubElement(process, q(BPMN_NS, "laneSet"), {"id": xml_id("LaneSet", process_data["process_id"])})
    for lane in ir.get("lanes", []):
        lane_element = ET.SubElement(
            lane_set,
            q(BPMN_NS, "lane"),
            {
                "id": xml_id("Lane", str(lane["position_id"])),
                "name": str(lane.get("name") or lane["position_id"]),
            },
        )
        add_properties(
            lane_element,
            {
                "canonicalPositionId": lane["position_id"],
                "canonicalLaneKind": lane.get("kind", "position"),
                "versionId": process_data["version_id"],
                "modelFingerprint": fingerprint,
            },
        )
        for node in all_nodes(ir):
            if node.get("position_id") == lane["position_id"]:
                ET.SubElement(lane_element, q(BPMN_NS, "flowNodeRef")).text = node_map[canonical_node_id(node)]

    default_edges = {
        str(flow["source_id"]): xml_id("Flow", str(flow["edge_id"]))
        for flow in ir.get("flows", [])
        if flow.get("is_default") is True
    }

    xml_element_by_canonical: dict[str, ET.Element] = {}
    for event in ir.get("events", []):
        event_id = str(event["event_id"])
        event_kind = event["event_kind"]
        attributes = {"id": node_map[event_id], "name": str(event.get("name") or "")}
        if event_kind == "start":
            element = ET.SubElement(process, q(BPMN_NS, "startEvent"), attributes)
        elif event_kind == "end":
            element = ET.SubElement(process, q(BPMN_NS, "endEvent"), attributes)
        else:
            attributes["attachedToRef"] = node_map[str(event["attached_to_action_id"])]
            attributes["cancelActivity"] = "true" if event.get("interrupting", True) else "false"
            element = ET.SubElement(process, q(BPMN_NS, "boundaryEvent"), attributes)
            timer = ET.SubElement(element, q(BPMN_NS, "timerEventDefinition"))
            timer_type = event.get("timer_type", "timeDuration")
            ET.SubElement(timer, q(BPMN_NS, timer_type)).text = str(event["timer_definition"])
        xml_element_by_canonical[event_id] = element
        add_properties(
            element,
            {
                "canonicalEventId": event_id,
                "canonicalEventKind": event_kind,
                "versionId": process_data["version_id"],
                "modelFingerprint": fingerprint,
            },
        )

    for action in ir.get("actions", []):
        action_id = str(action["action_id"])
        implementation = action.get("implementation", {})
        kind = implementation.get("kind")
        tag = {
            "user-task": "userTask",
            "service-task": "serviceTask",
            "manual-task": "manualTask",
            "send-task": "sendTask",
            "receive-task": "receiveTask",
            "call-activity": "callActivity",
        }.get(kind, "task")
        element = ET.SubElement(
            process,
            q(BPMN_NS, tag),
            {"id": node_map[action_id], "name": str(action.get("name") or action_id)},
        )
        xml_element_by_canonical[action_id] = element
        properties = {
            "canonicalActionId": action_id,
            "canonicalPositionId": action.get("position_id", ""),
            "canonicalActionType": action.get("action_type", ""),
            "versionId": process_data["version_id"],
            "modelFingerprint": fingerprint,
            "materialIds": action.get("material_ids", []),
            "informationSystemIds": action.get("information_system_ids", []),
            "productIds": action.get("product_ids", []),
            "counterpartyIds": action.get("counterparty_ids", []),
        }
        add_properties(element, properties)
        extension = element.find(q(BPMN_NS, "extensionElements"))
        assert extension is not None
        if kind == "user-task" and implementation.get("implementation_type") == "camunda-user-task":
            ET.SubElement(extension, q(ZEEBE_NS, "userTask"))
        elif kind in {"service-task", "send-task"} and implementation.get("job_type"):
            attributes = {"type": str(implementation["job_type"])}
            if implementation.get("retries") is not None:
                attributes["retries"] = str(implementation["retries"])
            ET.SubElement(extension, q(ZEEBE_NS, "taskDefinition"), attributes)
        elif kind == "call-activity" and implementation.get("called_process_id"):
            attributes = {
                "processId": str(implementation["called_process_id"]),
                "bindingType": str(implementation.get("binding_type", "latest")),
            }
            if implementation.get("version_tag"):
                attributes["versionTag"] = str(implementation["version_tag"])
            ET.SubElement(extension, q(ZEEBE_NS, "calledElement"), attributes)

    for gateway in ir.get("gateways", []):
        gateway_id = str(gateway["gateway_id"])
        tag = "exclusiveGateway" if gateway["gateway_kind"] == "exclusive" else "parallelGateway"
        attributes = {"id": node_map[gateway_id], "name": str(gateway.get("name") or "")}
        if gateway_id in default_edges:
            attributes["default"] = default_edges[gateway_id]
        element = ET.SubElement(process, q(BPMN_NS, tag), attributes)
        xml_element_by_canonical[gateway_id] = element
        add_properties(
            element,
            {
                "canonicalGatewayId": gateway_id,
                "canonicalGatewayKind": gateway["gateway_kind"],
                "versionId": process_data["version_id"],
                "modelFingerprint": fingerprint,
            },
        )

    for canonical_id, element in xml_element_by_canonical.items():
        for flow_id in incoming.get(canonical_id, []):
            ET.SubElement(element, q(BPMN_NS, "incoming")).text = flow_id
        for flow_id in outgoing.get(canonical_id, []):
            ET.SubElement(element, q(BPMN_NS, "outgoing")).text = flow_id

    for flow in ir.get("flows", []):
        flow_element = ET.SubElement(
            process,
            q(BPMN_NS, "sequenceFlow"),
            {
                "id": xml_id("Flow", str(flow["edge_id"])),
                "name": str(flow.get("name") or ""),
                "sourceRef": node_map[str(flow["source_id"])],
                "targetRef": node_map[str(flow["target_id"])],
            },
        )
        add_properties(
            flow_element,
            {
                "canonicalEdgeId": flow["edge_id"],
                "canonicalLinkType": flow.get("link_type", ""),
                "versionId": process_data["version_id"],
                "modelFingerprint": fingerprint,
            },
        )
        if flow.get("condition") and not flow.get("is_default"):
            condition = ET.SubElement(flow_element, q(BPMN_NS, "conditionExpression"))
            condition.set(q(XSI_NS, "type"), "bpmn:tFormalExpression")
            condition.text = str(flow["condition"])

    diagram = ET.SubElement(definitions, q(BPMNDI_NS, "BPMNDiagram"), {"id": xml_id("Diagram", process_data["process_id"])})
    plane = ET.SubElement(
        diagram,
        q(BPMNDI_NS, "BPMNPlane"),
        {"id": xml_id("Plane", process_data["process_id"]), "bpmnElement": collaboration_xml_id},
    )

    pool = geometry["pool"]
    participant_shape = ET.SubElement(
        plane,
        q(BPMNDI_NS, "BPMNShape"),
        {"id": f"{participant_xml_id}_di", "bpmnElement": participant_xml_id, "isHorizontal": "true"},
    )
    ET.SubElement(participant_shape, q(DC_NS, "Bounds"), {key: str(value) for key, value in pool.items()})
    for lane in ir.get("lanes", []):
        lane_id = str(lane["position_id"])
        shape = ET.SubElement(
            plane,
            q(BPMNDI_NS, "BPMNShape"),
            {"id": f"{xml_id('Lane', lane_id)}_di", "bpmnElement": xml_id("Lane", lane_id), "isHorizontal": "true"},
        )
        ET.SubElement(shape, q(DC_NS, "Bounds"), {key: str(value) for key, value in geometry["lanes"][lane_id].items()})
    for node in all_nodes(ir):
        canonical_id = canonical_node_id(node)
        bounds = geometry["nodes"].get(canonical_id)
        if not bounds:
            continue
        shape = ET.SubElement(
            plane,
            q(BPMNDI_NS, "BPMNShape"),
            {"id": f"{node_map[canonical_id]}_di", "bpmnElement": node_map[canonical_id]},
        )
        ET.SubElement(shape, q(DC_NS, "Bounds"), {key: str(value) for key, value in bounds.items()})
    for flow in ir.get("flows", []):
        source = geometry["nodes"][str(flow["source_id"])]
        target = geometry["nodes"][str(flow["target_id"])]
        edge = ET.SubElement(
            plane,
            q(BPMNDI_NS, "BPMNEdge"),
            {"id": f"{xml_id('Flow', str(flow['edge_id']))}_di", "bpmnElement": xml_id("Flow", str(flow["edge_id"]))},
        )
        for x, y in flow_waypoints(source, target):
            ET.SubElement(edge, q(DI_NS, "waypoint"), {"x": str(x), "y": str(y)})

    ET.indent(definitions, space="  ")
    return ET.tostring(definitions, encoding="utf-8", xml_declaration=True) + b"\n"


def svg_bytes(ir: dict[str, Any], fingerprint: str, geometry: dict[str, Any]) -> bytes:
    canvas = geometry["canvas"]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas["width"]}" height="{canvas["height"]}" viewBox="0 0 {canvas["width"]} {canvas["height"]}" data-model-fingerprint="{fingerprint}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#344054"/></marker></defs>',
        '<style>text{font-family:Arial,sans-serif;fill:#101828}.lane{fill:#f8fafc;stroke:#98a2b3}.lane-head{fill:#eef2f6;stroke:#98a2b3}.task{fill:#fff;stroke:#344054;stroke-width:2}.event{fill:#fff;stroke:#344054;stroke-width:2}.gateway{fill:#fff7d6;stroke:#7f6500;stroke-width:2}.flow{stroke:#344054;stroke-width:2;fill:none;marker-end:url(#arrow)}.label{font-size:13px}.small{font-size:11px;fill:#475467}.node-label{font-size:12px;font-weight:600}</style>',
    ]
    pool = geometry["pool"]
    parts.append(f'<rect x="{pool["x"]}" y="{pool["y"]}" width="{pool["width"]}" height="{pool["height"]}" fill="#fff" stroke="#344054" stroke-width="2"/>')
    for lane in ir.get("lanes", []):
        lane_id = str(lane["position_id"])
        bounds = geometry["lanes"][lane_id]
        parts.append(f'<rect class="lane" x="{bounds["x"]}" y="{bounds["y"]}" width="{bounds["width"]}" height="{bounds["height"]}" data-position-id="{html.escape(lane_id)}"/>')
        parts.append(f'<rect class="lane-head" x="{bounds["x"]}" y="{bounds["y"]}" width="{geometry["lane_header_width"]}" height="{bounds["height"]}"/>')
        lane_label = str(lane.get("name") or lane_id)
        parts.append(svg_text_block(lane_label, bounds["x"] + geometry["lane_header_width"] / 2, bounds["y"] + 34, 22, "label"))
    for flow in ir.get("flows", []):
        source = geometry["nodes"][str(flow["source_id"])]
        target = geometry["nodes"][str(flow["target_id"])]
        waypoints = flow_waypoints(source, target)
        path = "M " + " L ".join(f"{x} {y}" for x, y in waypoints)
        parts.append(f'<path class="flow" d="{path}" data-edge-id="{html.escape(str(flow["edge_id"]))}"/>')
        if flow.get("name"):
            midpoint = waypoints[len(waypoints) // 2]
            parts.append(f'<rect x="{midpoint[0]-30}" y="{midpoint[1]-17}" width="60" height="18" fill="#ffffff" opacity="0.9"/>')
            parts.append(f'<text class="small" text-anchor="middle" x="{midpoint[0]}" y="{midpoint[1]-4}">{html.escape(str(flow["name"]))}</text>')
    for node in all_nodes(ir):
        canonical_id = canonical_node_id(node)
        bounds = geometry["nodes"][canonical_id]
        kind = node_kind(node)
        label = str(node.get("name") or canonical_id)
        if kind == "action":
            parts.append(f'<rect class="task" rx="10" x="{bounds["x"]}" y="{bounds["y"]}" width="{bounds["width"]}" height="{bounds["height"]}" data-action-id="{html.escape(canonical_id)}"/>')
            parts.append(svg_text_block(label, bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2 + 4, 22, "node-label"))
        elif kind == "gateway":
            cx, cy = bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
            parts.append(f'<polygon class="gateway" points="{cx},{bounds["y"]} {bounds["x"]+bounds["width"]},{cy} {cx},{bounds["y"]+bounds["height"]} {bounds["x"]},{cy}" data-gateway-id="{html.escape(canonical_id)}"/>')
            parts.append(svg_text_block(label, cx, bounds["y"] - 12, 18, "node-label"))
        else:
            parts.append(f'<circle class="event" cx="{bounds["x"]+bounds["width"]/2}" cy="{bounds["y"]+bounds["height"]/2}" r="{bounds["width"]/2}" data-event-id="{html.escape(canonical_id)}"/>')
            parts.append(svg_text_block(label, bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] + 18, 18, "node-label"))
    parts.append('</svg>')
    return ("\n".join(parts) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-version-id")
    parser.add_argument("--built-at", help="ISO timestamp только для manifest")
    args = parser.parse_args()

    ir = read_ir(args.ir)
    issues = validate_ir(ir, args.expected_version_id)
    initial_readiness = readiness_from_issues(issues)
    if initial_readiness == "не готова":
        print(json.dumps({"readiness_status": initial_readiness, "issues": [issue.as_dict() for issue in issues]}, ensure_ascii=False, indent=2))
        return 1

    fingerprint = model_fingerprint(ir)
    process = ir["process"]
    build_id = f"build::{process['process_id']}::{process['version_id']}::{fingerprint[:12]}"
    geometry = layout(ir)
    bpmn = bpmn_bytes(ir, fingerprint, geometry)
    svg = svg_bytes(ir, fingerprint, geometry)
    modeler_evidence = ir.get("build_metadata", {}).get("modeler_validation", {})
    if modeler_evidence.get("status") == "passed" and modeler_evidence.get("bpmn_sha256") != sha256_bytes(bpmn):
        issues.append(
            ProjectionIssue(
                "MODELER_EVIDENCE_STALE",
                "доказательство Modeler относится к другому BPMN hash",
                "build_metadata.modeler_validation.bpmn_sha256",
                blocks_view=False,
                blocks_deployment=True,
            )
        )
    readiness = readiness_from_issues(issues)
    try:
        process_file_id = safe_filename_component(process["process_id"], "process.process_id")
        version_file_id = safe_filename_component(process["version_id"], "process.version_id")
    except ValueError as exc:
        print(json.dumps({"readiness_status": "не готова", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    basename = f"{process_file_id}--{version_file_id}"
    output_dir = args.output_dir.resolve()
    bpmn_path = output_dir / f"{basename}.bpmn"
    svg_path = output_dir / f"{basename}.svg"
    manifest_path = output_dir / f"{basename}.manifest.json"
    for path in (bpmn_path, svg_path, manifest_path):
        if output_dir not in path.resolve().parents:
            print(json.dumps({"readiness_status": "не готова", "error": "output path вышел за --output-dir"}, ensure_ascii=False, indent=2))
            return 1
    write_bytes(bpmn_path, bpmn)
    write_bytes(svg_path, svg)
    built_at = args.built_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest = {
        "schema_version": "1.0",
        "projection_build_id": build_id,
        "projection_kind": ir.get("projection_kind", "BPMN процесса"),
        "process_id": process["process_id"],
        "version_id": process["version_id"],
        "model_fingerprint": fingerprint,
        "generator_version": GENERATOR_VERSION,
        "layout_version": LAYOUT_VERSION,
        "built_at": built_at,
        "readiness_status": readiness,
        "deployment_blockers": [issue.as_dict() for issue in issues if issue.blocks_deployment],
        "modeler_validation": modeler_evidence or None,
        "included_stable_ids": sorted(
            [process["process_id"], process["system_id"]]
            + [str(lane["position_id"]) for lane in ir.get("lanes", [])]
            + [canonical_node_id(node) for node in all_nodes(ir)]
            + [str(flow["edge_id"]) for flow in ir.get("flows", [])]
        ),
        "source_row_keys": sorted(set(ir.get("source_row_keys", []))),
        "bpmn_file": bpmn_path.name,
        "bpmn_sha256": sha256_bytes(bpmn),
        "svg_file": svg_path.name,
        "svg_sha256": sha256_bytes(svg),
    }
    write_bytes(manifest_path, (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
