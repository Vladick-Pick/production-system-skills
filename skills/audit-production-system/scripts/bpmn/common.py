#!/usr/bin/env python3
"""Общие детерминированные функции BPMN/SVG-проекции v0.2."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
GENERATOR_VERSION = "0.2.0"
LAYOUT_VERSION = "horizontal-lanes-v1"

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
ZEEBE_NS = "http://camunda.org/schema/zeebe/1.0"
MODELER_NS = "http://camunda.org/schema/modeler/1.0"

SUPPORTED_ACTION_IMPLEMENTATIONS = {
    "user-task",
    "service-task",
    "manual-task",
    "send-task",
    "receive-task",
    "call-activity",
}
SUPPORTED_GATEWAYS = {"exclusive", "parallel"}
SUPPORTED_EVENTS = {"start", "end", "boundary-timer"}
SAFE_FILENAME_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


@dataclass(frozen=True)
class ProjectionIssue:
    code: str
    message: str
    path: str
    blocks_view: bool = True
    blocks_deployment: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "blocks_view": self.blocks_view,
            "blocks_deployment": self.blocks_deployment,
        }


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def model_fingerprint(ir: dict[str, Any]) -> str:
    semantic = dict(ir)
    semantic.pop("build_metadata", None)
    return sha256_bytes(canonical_json(semantic).encode("utf-8"))


def xml_id(kind: str, stable_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", stable_id).strip("_.-") or "id"
    if not re.match(r"[A-Za-z_]", slug):
        slug = f"id_{slug}"
    digest = hashlib.sha256(stable_id.encode("utf-8")).hexdigest()[:8]
    return f"{kind}_{slug}_{digest}"


def safe_filename_component(value: Any, field: str) -> str:
    """Вернуть безопасный компонент имени файла или остановить сборку."""
    if not isinstance(value, str) or not SAFE_FILENAME_COMPONENT.fullmatch(value):
        raise ValueError(
            f"{field} должен быть безопасным filename-компонентом: "
            "1-128 ASCII символов [A-Za-z0-9._-], первый символ буквенно-цифровой"
        )
    if value in {".", ".."}:
        raise ValueError(f"{field} не может быть {value!r}")
    return value


def read_ir(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("projection IR должен быть JSON object")
    return value


def all_nodes(ir: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for section in ("events", "actions", "gateways"):
        value = ir.get(section, [])
        if isinstance(value, list):
            result.extend(item for item in value if isinstance(item, dict))
    return result


def canonical_node_id(node: dict[str, Any]) -> str:
    for key in ("event_id", "action_id", "gateway_id"):
        if key in node:
            return str(node[key])
    raise KeyError("узел не содержит canonical ID")


def node_kind(node: dict[str, Any]) -> str:
    if "event_id" in node:
        return "event"
    if "action_id" in node:
        return "action"
    if "gateway_id" in node:
        return "gateway"
    return "unknown"


def bpmn_node_id(node: dict[str, Any]) -> str:
    kind = node_kind(node)
    return xml_id(kind.capitalize(), canonical_node_id(node))


def validate_ir(ir: dict[str, Any], expected_version_id: str | None = None) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []

    if ir.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            ProjectionIssue(
                "IR_SCHEMA_VERSION",
                f"ожидалась schema_version {SCHEMA_VERSION}",
                "schema_version",
            )
        )

    process = ir.get("process")
    if not isinstance(process, dict):
        return issues + [ProjectionIssue("PROCESS_MISSING", "нет process object", "process")]

    for field in ("process_id", "version_id", "system_id", "name"):
        if not process.get(field):
            issues.append(ProjectionIssue("PROCESS_FIELD", f"нет обязательного {field}", f"process.{field}"))

    if expected_version_id and process.get("version_id") != expected_version_id:
        issues.append(
            ProjectionIssue(
                "STALE_VERSION",
                f"IR version_id={process.get('version_id')!r}, ожидалась {expected_version_id!r}",
                "process.version_id",
            )
        )

    lanes = ir.get("lanes", [])
    if not isinstance(lanes, list) or not lanes:
        issues.append(ProjectionIssue("LANES_MISSING", "нет lanes", "lanes"))
        lanes = []
    lane_ids: set[str] = set()
    for index, lane in enumerate(lanes):
        lane_id = lane.get("position_id")
        if not lane_id or lane_id in lane_ids:
            issues.append(ProjectionIssue("LANE_ID", "lane position_id отсутствует или повторяется", f"lanes[{index}]"))
        else:
            lane_ids.add(str(lane_id))
        if lane.get("kind", "position") not in {"position", "information-system"}:
            issues.append(ProjectionIssue("LANE_KIND", "неподдерживаемый kind lane", f"lanes[{index}].kind"))

    node_by_id: dict[str, dict[str, Any]] = {}
    starts: list[str] = []
    ends: list[str] = []
    boundary_ids: set[str] = set()

    sections: dict[str, list[dict[str, Any]]] = {}
    for section in ("events", "actions", "gateways"):
        raw_section = ir.get(section, [])
        if not isinstance(raw_section, list):
            issues.append(ProjectionIssue("IR_SECTION_TYPE", f"{section} должен быть list", section))
            sections[section] = []
            continue
        invalid_items = [index for index, item in enumerate(raw_section) if not isinstance(item, dict)]
        for index in invalid_items:
            issues.append(ProjectionIssue("IR_ITEM_TYPE", "узел должен быть object", f"{section}[{index}]"))
        sections[section] = [item for item in raw_section if isinstance(item, dict)]

    for index, event in enumerate(sections["events"]):
        event_id = event.get("event_id")
        event_kind = event.get("event_kind")
        if not event_id or event_id in node_by_id:
            issues.append(ProjectionIssue("NODE_ID", "event_id отсутствует или повторяется", f"events[{index}]"))
            continue
        node_by_id[str(event_id)] = event
        if event_kind not in SUPPORTED_EVENTS:
            issues.append(ProjectionIssue("EVENT_UNSUPPORTED", f"неподдерживаемое событие {event_kind!r}", f"events[{index}].event_kind"))
        elif event_kind == "start":
            starts.append(str(event_id))
        elif event_kind == "end":
            ends.append(str(event_id))
        elif event_kind == "boundary-timer":
            boundary_ids.add(str(event_id))
            if not event.get("attached_to_action_id"):
                issues.append(ProjectionIssue("TIMER_ATTACHMENT", "boundary timer не привязан к action", f"events[{index}]"))
            if not event.get("timer_definition"):
                issues.append(ProjectionIssue("TIMER_DEFINITION", "нет timer_definition", f"events[{index}]"))

    for index, action in enumerate(sections["actions"]):
        action_id = action.get("action_id")
        implementation = action.get("implementation", {})
        implementation_kind = implementation.get("kind")
        if not action_id or action_id in node_by_id:
            issues.append(ProjectionIssue("NODE_ID", "action_id отсутствует или повторяется", f"actions[{index}]"))
            continue
        node_by_id[str(action_id)] = action
        if not action.get("name"):
            issues.append(ProjectionIssue("ACTION_NAME", "нет имени действия", f"actions[{index}].name"))
        position_id = action.get("position_id")
        if position_id not in lane_ids:
            issues.append(ProjectionIssue("ACTION_LANE", "position_id действия не разрешается в lanes", f"actions[{index}].position_id"))
        if implementation_kind not in SUPPORTED_ACTION_IMPLEMENTATIONS:
            issues.append(
                ProjectionIssue(
                    "ACTION_IMPLEMENTATION_UNKNOWN",
                    f"неизвестная реализация {implementation_kind!r}",
                    f"actions[{index}].implementation.kind",
                    blocks_view=False,
                    blocks_deployment=True,
                )
            )
        elif implementation_kind in {"service-task", "send-task"} and not implementation.get("job_type"):
            issues.append(
                ProjectionIssue(
                    "JOB_TYPE_MISSING",
                    "для deployment нужен job_type",
                    f"actions[{index}].implementation.job_type",
                    blocks_view=False,
                    blocks_deployment=True,
                )
            )
        elif implementation_kind == "user-task" and not implementation.get("implementation_type"):
            issues.append(
                ProjectionIssue(
                    "USER_TASK_IMPLEMENTATION",
                    "не указан implementation_type=camunda-user-task",
                    f"actions[{index}].implementation.implementation_type",
                    blocks_view=False,
                    blocks_deployment=True,
                )
            )
        elif implementation_kind == "call-activity":
            if not implementation.get("called_process_id"):
                issues.append(
                    ProjectionIssue(
                        "CALLED_PROCESS_MISSING",
                        "не указан called_process_id",
                        f"actions[{index}].implementation.called_process_id",
                        blocks_view=False,
                        blocks_deployment=True,
                    )
                )
            if implementation.get("binding_type") not in {"deployment", "versionTag"}:
                issues.append(
                    ProjectionIssue(
                        "CALL_BINDING_UNSAFE",
                        "для deployment нужен binding_type deployment или versionTag",
                        f"actions[{index}].implementation.binding_type",
                        blocks_view=False,
                        blocks_deployment=True,
                    )
                )

    for index, gateway in enumerate(sections["gateways"]):
        gateway_id = gateway.get("gateway_id")
        gateway_kind = gateway.get("gateway_kind")
        if not gateway_id or gateway_id in node_by_id:
            issues.append(ProjectionIssue("NODE_ID", "gateway_id отсутствует или повторяется", f"gateways[{index}]"))
            continue
        node_by_id[str(gateway_id)] = gateway
        if gateway_kind not in SUPPORTED_GATEWAYS:
            issues.append(ProjectionIssue("GATEWAY_UNSUPPORTED", f"неподдерживаемый gateway {gateway_kind!r}", f"gateways[{index}]"))

    for event_id in boundary_ids:
        attached = node_by_id[event_id].get("attached_to_action_id")
        if attached not in node_by_id or "action_id" not in node_by_id.get(attached, {}):
            issues.append(ProjectionIssue("TIMER_ATTACHMENT", "attached action не существует", f"events[{event_id}]"))

    if not starts:
        issues.append(ProjectionIssue("START_MISSING", "нет start event", "events"))
    if not ends:
        issues.append(ProjectionIssue("END_MISSING", "нет end event", "events"))

    flows = ir.get("flows", [])
    if not isinstance(flows, list):
        issues.append(ProjectionIssue("FLOWS_TYPE", "flows должен быть list", "flows"))
        flows = []
    edge_ids: set[str] = set()
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    valid_flows: list[dict[str, Any]] = []
    for index, flow in enumerate(flows):
        if not isinstance(flow, dict):
            issues.append(ProjectionIssue("FLOW_ITEM_TYPE", "flow должен быть object", f"flows[{index}]"))
            continue
        valid_flows.append(flow)
        edge_id = flow.get("edge_id")
        source_id = flow.get("source_id")
        target_id = flow.get("target_id")
        if not edge_id or edge_id in edge_ids:
            issues.append(ProjectionIssue("EDGE_ID", "edge_id отсутствует или повторяется", f"flows[{index}]"))
        else:
            edge_ids.add(str(edge_id))
        if source_id not in node_by_id:
            issues.append(ProjectionIssue("EDGE_SOURCE", "source_id не существует", f"flows[{index}].source_id"))
        if target_id not in node_by_id:
            issues.append(ProjectionIssue("EDGE_TARGET", "target_id не существует", f"flows[{index}].target_id"))
        if source_id in node_by_id and target_id in node_by_id:
            outgoing[str(source_id)].append(flow)
            incoming[str(target_id)].append(flow)

    for gateway in sections["gateways"]:
        gateway_id = str(gateway.get("gateway_id"))
        gateway_kind = gateway.get("gateway_kind")
        branches = outgoing.get(gateway_id, [])
        if gateway_kind == "exclusive" and len(branches) > 1:
            defaults = [flow for flow in branches if flow.get("is_default") is True]
            if len(defaults) != 1:
                issues.append(ProjectionIssue("EXCLUSIVE_DEFAULT", "exclusive gateway должен иметь ровно один default flow", f"gateways[{gateway_id}]"))
            for flow in branches:
                if flow.get("is_default"):
                    if flow.get("condition"):
                        issues.append(ProjectionIssue("DEFAULT_CONDITION", "default flow не должен иметь condition", f"flows[{flow.get('edge_id')}]"))
                    continue
                condition = flow.get("condition")
                if not condition:
                    issues.append(ProjectionIssue("EXCLUSIVE_CONDITION", "ветка exclusive не имеет condition", f"flows[{flow.get('edge_id')}]"))
                elif not str(condition).lstrip().startswith("="):
                    issues.append(
                        ProjectionIssue(
                            "FEEL_NOT_EXECUTABLE",
                            "условие не является явным FEEL выражением",
                            f"flows[{flow.get('edge_id')}].condition",
                            blocks_view=False,
                            blocks_deployment=True,
                        )
                    )
        if gateway_kind == "parallel" and len(branches) == 1 and len(incoming.get(gateway_id, [])) == 1:
            issues.append(ProjectionIssue("PARALLEL_REDUNDANT", "parallel gateway не разделяет и не объединяет поток", f"gateways[{gateway_id}]"))

    for start_id in starts:
        if incoming.get(start_id):
            issues.append(ProjectionIssue("START_HAS_INCOMING", "start event не должен иметь входящий flow", f"node:{start_id}"))
    for end_id in ends:
        if outgoing.get(end_id):
            issues.append(ProjectionIssue("END_HAS_OUTGOING", "end event не должен иметь исходящий flow", f"node:{end_id}"))

    if starts:
        reachable: set[str] = set(starts)
        queue: deque[str] = deque(starts)
        while queue:
            current = queue.popleft()
            for flow in outgoing.get(current, []):
                target = str(flow["target_id"])
                if target not in reachable:
                    reachable.add(target)
                    queue.append(target)
            for boundary_id in boundary_ids:
                attached = str(node_by_id[boundary_id].get("attached_to_action_id"))
                if attached == current and boundary_id not in reachable:
                    reachable.add(boundary_id)
                    queue.append(boundary_id)
        for node_id in node_by_id:
            if node_id in boundary_ids:
                continue
            if node_id not in reachable:
                issues.append(ProjectionIssue("NODE_UNREACHABLE", "узел недостижим от start", f"node:{node_id}"))
        if not any(end in reachable for end in ends):
            issues.append(ProjectionIssue("END_UNREACHABLE", "ни один end не достижим", "events"))

        for node_id in sorted(reachable):
            if node_id not in ends and not outgoing.get(node_id):
                issues.append(
                    ProjectionIssue(
                        "DEAD_END_NODE",
                        "достижимый незавершающий узел не имеет исходящего flow",
                        f"node:{node_id}",
                    )
                )

        can_reach_end: set[str] = set(ends)
        reverse_queue: deque[str] = deque(ends)
        while reverse_queue:
            current = reverse_queue.popleft()
            for flow in incoming.get(current, []):
                source = str(flow["source_id"])
                if source not in can_reach_end:
                    can_reach_end.add(source)
                    reverse_queue.append(source)
        for node_id in sorted(reachable - can_reach_end):
            issues.append(
                ProjectionIssue(
                    "DEAD_END_PATH",
                    "из достижимого узла нет пути к end event",
                    f"node:{node_id}",
                )
            )

        def descendants(origin: str) -> set[str]:
            seen: set[str] = {origin}
            pending: deque[str] = deque([origin])
            while pending:
                current = pending.popleft()
                for flow in outgoing.get(current, []):
                    target = str(flow["target_id"])
                    if target not in seen:
                        seen.add(target)
                        pending.append(target)
            return seen

        parallel_gateways = {
            str(gateway.get("gateway_id")): gateway
            for gateway in sections["gateways"]
            if gateway.get("gateway_kind") == "parallel" and gateway.get("gateway_id")
        }
        split_ids = {gateway_id for gateway_id in parallel_gateways if len(outgoing.get(gateway_id, [])) > 1}
        join_ids = {gateway_id for gateway_id in parallel_gateways if len(incoming.get(gateway_id, [])) > 1}
        for split_id in sorted(split_ids):
            branch_targets = [str(flow["target_id"]) for flow in outgoing[split_id]]
            common = set.intersection(*(descendants(target) for target in branch_targets)) if branch_targets else set()
            if not common.intersection(join_ids):
                issues.append(
                    ProjectionIssue(
                        "PARALLEL_JOIN_MISSING",
                        "ветки parallel split не сходятся в явном parallel join",
                        f"node:{split_id}",
                    )
                )
        for join_id in sorted(join_ids):
            if not any(join_id in descendants(split_id) for split_id in split_ids):
                issues.append(
                    ProjectionIssue(
                        "PARALLEL_SPLIT_MISSING",
                        "parallel join не связан с предшествующим parallel split",
                        f"node:{join_id}",
                    )
                )

    if process.get("is_executable") is not True:
        issues.append(
            ProjectionIssue(
                "PROCESS_NOT_EXECUTABLE",
                "is_executable не установлен в true",
                "process.is_executable",
                blocks_view=False,
                blocks_deployment=True,
            )
        )
    if not process.get("target_camunda_version"):
        issues.append(
            ProjectionIssue(
                "CAMUNDA_VERSION_UNKNOWN",
                "не задан target_camunda_version",
                "process.target_camunda_version",
                blocks_view=False,
                blocks_deployment=True,
            )
        )

    modeler_evidence = ir.get("build_metadata", {}).get("modeler_validation", {})
    if modeler_evidence.get("status") != "passed" or not modeler_evidence.get("bpmn_sha256"):
        issues.append(
            ProjectionIssue(
                "MODELER_VALIDATION_MISSING",
                "нет доказательства открытия/lint точного BPMN hash в Camunda Desktop Modeler",
                "build_metadata.modeler_validation",
                blocks_view=False,
                blocks_deployment=True,
            )
        )

    return issues


def readiness_from_issues(issues: list[ProjectionIssue]) -> str:
    if any(issue.blocks_view for issue in issues):
        return "не готова"
    if any(issue.blocks_deployment for issue in issues):
        return "готова к просмотру"
    return "готова к deployment"


def layout(ir: dict[str, Any]) -> dict[str, Any]:
    lanes = ir.get("lanes", [])
    lane_height = 230
    pool_x = 20
    pool_y = 20
    lane_header_width = 180
    node_start_x = pool_x + lane_header_width + 70
    node_gap = 230
    node_width = 170
    node_height = 82
    lane_index = {str(lane["position_id"]): index for index, lane in enumerate(lanes)}

    nodes = all_nodes(ir)
    node_by_id = {canonical_node_id(node): node for node in nodes}
    boundary_ids = {
        canonical_node_id(node)
        for node in ir.get("events", [])
        if node.get("event_kind") == "boundary-timer"
    }
    ranks: dict[str, int] = {
        canonical_node_id(node): 0
        for node in ir.get("events", [])
        if node.get("event_kind") == "start"
    }
    rank_flows = [
        flow
        for flow in ir.get("flows", [])
        if flow.get("link_type") != "возврат"
    ]
    for _ in range(max(1, len(nodes) * 2)):
        changed = False
        for boundary_id in boundary_ids:
            attached = str(node_by_id[boundary_id].get("attached_to_action_id"))
            if attached in ranks and ranks.get(boundary_id) != ranks[attached]:
                ranks[boundary_id] = ranks[attached]
                changed = True
        for flow in rank_flows:
            source = str(flow["source_id"])
            target = str(flow["target_id"])
            if source not in ranks:
                continue
            candidate = ranks[source] + 1
            if candidate > ranks.get(target, -1):
                ranks[target] = candidate
                changed = True
        if not changed:
            break
    for node_id in node_by_id:
        ranks.setdefault(node_id, 0)

    groups: dict[tuple[int, int], list[str]] = defaultdict(list)
    for node in nodes:
        if canonical_node_id(node) in boundary_ids:
            continue
        lane_no = lane_index.get(str(node.get("position_id")), 0)
        groups[(lane_no, ranks[canonical_node_id(node)])].append(canonical_node_id(node))

    positions: dict[str, dict[str, float]] = {}
    for (lane_no, rank), node_ids in groups.items():
        count = len(node_ids)
        for index, node_id in enumerate(sorted(node_ids)):
            node = node_by_id[node_id]
            width = 50 if node_kind(node) in {"event", "gateway"} else node_width
            height = 50 if node_kind(node) in {"event", "gateway"} else node_height
            x = node_start_x + rank * node_gap
            if count == 1:
                y = pool_y + lane_no * lane_height + (lane_height - height) / 2
            else:
                spacing = (lane_height - count * height) / (count + 1)
                y = pool_y + lane_no * lane_height + spacing * (index + 1) + height * index
            positions[node_id] = {"x": x, "y": y, "width": width, "height": height}

    for event in ir.get("events", []):
        if event.get("event_kind") != "boundary-timer":
            continue
        attached = positions.get(str(event.get("attached_to_action_id")))
        if attached:
            positions[str(event["event_id"])] = {
                "x": attached["x"] + attached["width"] - 18,
                "y": attached["y"] + attached["height"] - 18,
                "width": 36,
                "height": 36,
            }

    max_rank = max(ranks.values(), default=1)
    pool_width = max(900, node_start_x + (max_rank + 1) * node_gap + 120)
    pool_height = max(lane_height, len(lanes) * lane_height)
    return {
        "pool": {"x": pool_x, "y": pool_y, "width": pool_width, "height": pool_height},
        "lanes": {
            str(lane["position_id"]): {
                "x": pool_x,
                "y": pool_y + index * lane_height,
                "width": pool_width,
                "height": lane_height,
            }
            for index, lane in enumerate(lanes)
        },
        "nodes": positions,
        "lane_header_width": lane_header_width,
        "canvas": {"width": pool_width + 60, "height": pool_height + 100},
    }


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
