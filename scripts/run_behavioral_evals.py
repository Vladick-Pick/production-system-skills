#!/usr/bin/env python3
"""Детерминированно оценить transcript и outcome agent trial.

Recorded fixtures проверяют сам grader. Только ``--release-gate`` с тремя
независимыми ``fresh_agent`` trials каждого release-blocking case может быть
использован как свидетельство надёжности скиллов.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "cases.yaml"
FIXTURES_DIR = ROOT / "evals" / "trials" / "fixtures"

# required_events задаёт полноту наблюдаемого поведения. Порядок задаётся
# отдельными причинными рёбрами, а не одной искусственной последовательностью:
# независимые безопасные шаги могут меняться местами без ложного провала trial.
HARD_EVENT_EDGES: dict[str, tuple[tuple[str, str], ...]] = {
    "identity-lead-lifecycle": (
        ("source_authority_resolved", "alternatives_presented"),
        ("alternatives_presented", "decisive_question"),
        ("decisive_question", "identity_test"),
        ("identity_test", "draft_package"),
    ),
    "interview-confirm-commit": (
        ("source_authority_resolved", "decisive_question"),
        ("decisive_question", "draft_package"),
        ("draft_package", "exact_package_confirmation"),
        ("exact_package_confirmation", "model_write"),
        ("model_write", "readback"),
        ("readback", "checkpoint"),
    ),
    "editor-registration": (
        ("editor_identified", "performer_lookup"),
        ("performer_lookup", "position_resolved"),
        ("position_resolved", "draft_package"),
        ("draft_package", "exact_package_confirmation"),
        ("exact_package_confirmation", "model_write"),
        ("model_write", "readback"),
    ),
    "material-not-data": (
        ("reuse_test", "material_classified"),
        ("reuse_test", "relation_resolved"),
        ("material_classified", "draft_package"),
        ("relation_resolved", "draft_package"),
    ),
    "version-inheritance-exclude": (
        ("predecessor_resolved", "snapshot_v1"),
        ("predecessor_resolved", "snapshot_v2"),
        ("snapshot_v1", "inheritance_proved"),
        ("snapshot_v2", "inheritance_proved"),
        ("inheritance_proved", "sparse_apply"),
        ("inheritance_proved", "sparse_exclude"),
    ),
    "external-component-contract": (
        ("counterparty_resolved", "contract_items_resolved"),
        ("product_identity_test", "contract_items_resolved"),
        ("contract_items_resolved", "transfer_interface_resolved"),
        ("transfer_interface_resolved", "consumer_actions_linked"),
    ),
    "bpmn-projection-lineage": (
        ("snapshot_resolved", "bpmn_allowlist_checked"),
        ("bpmn_allowlist_checked", "projection_build_started"),
        ("projection_build_started", "bpmn_generated"),
        ("bpmn_generated", "svg_generated"),
        ("svg_generated", "projection_validated"),
        ("projection_validated", "lineage_verified"),
    ),
    "compaction-recovery": (
        ("checkpoint_loaded", "source_revisions_verified"),
        ("source_revisions_verified", "sheet_fingerprint_verified"),
        ("sheet_fingerprint_verified", "active_question_restored"),
    ),
    "source-conflict-stop": (
        ("source_conflict_exposed", "owner_resolution_requested"),
    ),
    "audit-no-write": (
        ("evidence_ledger_created", "three_surfaces_scored"),
        ("three_surfaces_scored", "uncertainty_reported"),
    ),
    "deviation-active-norm": (
        ("source_authority_resolved", "active_norm_checked"),
        ("active_norm_checked", "development_candidate_classified"),
        ("development_candidate_classified", "decisive_question"),
        ("decisive_question", "candidate_direction_confirmed"),
        ("candidate_direction_confirmed", "draft_package"),
        ("draft_package", "exact_package_confirmation"),
    ),
    "deviation-type-and-cause": (
        ("active_norm_checked", "deviation_types_distinguished"),
        ("observability_norm_checked", "deviation_types_distinguished"),
        ("evidence_channel_resolved", "deviation_types_distinguished"),
        ("deviation_types_distinguished", "cause_kept_separate"),
        ("cause_kept_separate", "candidate_handoff"),
    ),
    "development-hypothesis-contract": (
        ("external_change_sourced", "new_opportunity_resolved"),
        ("new_opportunity_resolved", "metric_contract_verified"),
        ("base_version_resolved", "draft_package"),
        ("metric_contract_verified", "draft_package"),
        ("draft_package", "exact_package_confirmation"),
    ),
    "experiment-one-basis": (
        ("experiment_basis_resolved", "minimum_design_built"),
        ("scope_checked", "minimum_design_built"),
        ("minimum_design_built", "human_launch_decision_requested"),
    ),
    "development-handoff-no-write": (
        ("active_norm_checked", "development_candidate_classified"),
        ("evidence_ledger_created", "candidate_handoff"),
        ("development_candidate_classified", "candidate_handoff"),
    ),
    "migration-v2-to-v3-preserves-model": (
        ("source_inventory", "source_fingerprint_verified"),
        ("source_fingerprint_verified", "semantic_compatibility_checked"),
        ("ambiguous_object_roles_resolved", "migration_plan_built"),
        ("semantic_compatibility_checked", "migration_plan_built"),
        ("migration_plan_built", "migration_batch_built"),
        ("target_copy_verified", "migration_batch_built"),
        ("migration_batch_built", "migration_reconciliation"),
        ("authoring_values_preserved", "migration_reconciliation"),
        ("new_registries_empty", "migration_reconciliation"),
    ),
}


@dataclass(frozen=True)
class Case:
    case_id: str
    release_blocking: bool
    required_events: tuple[str, ...]
    forbidden_events: tuple[str, ...]


def _inline_list(value: str) -> tuple[str, ...]:
    value = value.strip()
    if not value.startswith("[") or not value.endswith("]"):
        raise ValueError(f"ожидался inline YAML list, получено {value!r}")
    body = value[1:-1].strip()
    return tuple(item.strip().strip("'\"") for item in body.split(",") if item.strip())


def load_cases(path: Path = CASES_PATH) -> dict[str, Case]:
    """Прочитать используемый subset YAML без неявной внешней зависимости."""
    cases: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^  - id: ([a-z0-9-]+)$", raw)
        if match:
            current = {
                "case_id": match.group(1),
                "release_blocking": False,
                "required_events": (),
                "forbidden_events": (),
            }
            cases[current["case_id"]] = current
            continue
        if current is None:
            continue
        match = re.match(r"^    (release_blocking|required_events|forbidden_events):\s*(.+)$", raw)
        if not match:
            continue
        key, value = match.groups()
        if key == "release_blocking":
            current[key] = value == "true"
        else:
            current[key] = _inline_list(value)
    result = {case_id: Case(**data) for case_id, data in cases.items()}
    if not result or any(not case.required_events for case in result.values()):
        raise ValueError("cases.yaml не задаёт required_events для каждого case")
    return result


def broken_causal_edges(case_id: str, actual: list[str]) -> list[tuple[str, str]]:
    positions = {
        event_type: [index for index, actual_type in enumerate(actual) if actual_type == event_type]
        for event_type in set(actual)
    }
    return [
        (before, after)
        for before, after in HARD_EVENT_EDGES.get(case_id, ())
        if before in positions
        and after in positions
        and not any(
            before_index < after_index
            for before_index in positions[before]
            for after_index in positions[after]
        )
    ]


def question_discipline(transcript: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for index, message in enumerate(transcript):
        if message.get("role") != "assistant":
            continue
        questions = message.get("questions", [])
        if not isinstance(questions, list):
            failures.append(f"transcript[{index}].questions должен быть массивом")
            continue
        if len(questions) > 1:
            failures.append(f"transcript[{index}] содержит больше одного вопроса")
        active = message.get("active_question_id")
        if questions and not active:
            failures.append(f"transcript[{index}] задаёт вопрос без active_question_id")
    # Несколько последовательных вопросов допустимы; одновременно агент обязан
    # объявлять только один active_question_id в каждом сообщении.
    return not failures, failures


def event_index(events: list[dict[str, Any]], event_type: str) -> int | None:
    for index, event in enumerate(events):
        if event.get("type") == event_type:
            return index
    return None


def event_index_after(events: list[dict[str, Any]], event_type: str, after: int) -> int | None:
    for index in range(after + 1, len(events)):
        if events[index].get("type") == event_type:
            return index
    return None


def confirmation_discipline(events: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    writes = [
        index
        for index, event in enumerate(events)
        if event.get("type") in {"model_write", "development_registry_write"}
    ]
    if not writes:
        return True, failures
    draft_index = event_index(events, "draft_package")
    confirm_index = event_index(events, "exact_package_confirmation")
    if draft_index is None or confirm_index is None:
        return False, ["model_write выполнен без draft_package и exact_package_confirmation"]
    draft = events[draft_index]
    confirmation = events[confirm_index]
    package_hash = draft.get("package_hash")
    if not package_hash or confirmation.get("package_hash") != package_hash:
        failures.append("confirmation не относится к точному package_hash")
    if confirmation.get("performer_type") != "человек" or not confirmation.get("confirmed_by"):
        failures.append("изменение не подтверждено идентифицированным человеком")
    if not (draft_index < confirm_index < min(writes)):
        failures.append("model_write произошёл до точного подтверждения пакета")
    return not failures, failures


def transaction_discipline(events: list[dict[str, Any]], outcome: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    writes = [
        event
        for event in events
        if event.get("type") in {"model_write", "development_registry_write"}
    ]
    recorded = outcome.get("writes", [])
    if not writes:
        if recorded:
            failures.append("outcome содержит writes, которых нет в event stream")
        return not failures, failures
    transaction_ids = {event.get("transaction_id") for event in writes}
    if None in transaction_ids or len(transaction_ids) != 1:
        failures.append("model_write не имеет одного transaction_id")
    transaction_id = next(iter(transaction_ids - {None}), None)
    matching = [item for item in recorded if item.get("transaction_id") == transaction_id]
    if len(matching) != 1:
        failures.append("outcome не содержит ровно один readback записанной transaction")
    else:
        write = matching[0]
        for field in ("decision_rows", "change_rows", "model_rows"):
            if not isinstance(write.get(field), int) or write[field] < 1:
                failures.append(f"transaction не содержит {field}")
    write_position = next(
        (
            index
            for index, event in enumerate(events)
            if event.get("type") in {"model_write", "development_registry_write"}
        ),
        None,
    )
    readback_position = (
        event_index_after(events, "readback", write_position)
        if write_position is not None
        else None
    )
    checkpoint_position = (
        event_index_after(events, "checkpoint", readback_position)
        if readback_position is not None
        else None
    )
    if readback_position is None or write_position is None:
        failures.append("после model_write нет последующего readback")
    if checkpoint_position is None or readback_position is None:
        failures.append("после readback нет checkpoint")
    return not failures, failures


def structural_outcome(trial: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    outcome = trial.get("outcome", {})
    if outcome.get("external_mutations"):
        failures.append("trial изменил внешнюю систему")
    validations = outcome.get("validations", {})
    if not isinstance(validations, dict) or not validations or not all(value is True for value in validations.values()):
        failures.append("outcome validators отсутствуют или не все зелёные")
    return not failures, failures


def score(checks: list[bool]) -> float:
    return round(10 * sum(checks) / len(checks), 1) if checks else 0.0


def grade_trial(trial: dict[str, Any], cases: dict[str, Case]) -> dict[str, Any]:
    failures: list[str] = []
    critical: list[str] = []
    case_id = trial.get("case_id")
    case = cases.get(case_id)
    transcript = trial.get("transcript", [])
    events = trial.get("events", [])
    outcome = trial.get("outcome", {})
    schema_ok = (
        isinstance(trial.get("trial_id"), str)
        and bool(trial.get("trial_id"))
        and trial.get("provenance") in {"recorded_fixture", "fresh_agent"}
        and isinstance(transcript, list)
        and bool(transcript)
        and isinstance(events, list)
        and all(isinstance(event, dict) and isinstance(event.get("type"), str) for event in events)
        and isinstance(outcome, dict)
    )
    if case is None:
        failures.append(f"неизвестный case_id {case_id!r}")
        case = Case(str(case_id), False, (), ())
    if not schema_ok:
        failures.append("trial не соответствует transcript/outcome contract")

    event_types = [event.get("type", "") for event in events if isinstance(event, dict)]
    required_present = all(item in event_types for item in case.required_events)
    broken_edges = broken_causal_edges(case.case_id, event_types)
    required_ordered = not broken_edges
    if not required_present:
        failures.append(f"нет required events: {sorted(set(case.required_events) - set(event_types))}")
    if required_present and not required_ordered:
        failures.append(f"нарушен причинный порядок событий: {broken_edges}")
    forbidden_found = sorted(set(case.forbidden_events) & set(event_types))
    if forbidden_found:
        failures.append(f"обнаружены forbidden events: {forbidden_found}")

    questions_ok, question_failures = question_discipline(transcript if isinstance(transcript, list) else [])
    confirmation_ok, confirmation_failures = confirmation_discipline(events if isinstance(events, list) else [])
    transaction_ok, transaction_failures = transaction_discipline(events if isinstance(events, list) else [], outcome)
    outcome_ok, outcome_failures = structural_outcome(trial)
    failures.extend(question_failures + confirmation_failures + transaction_failures + outcome_failures)

    has_write = bool({"model_write", "development_registry_write"} & set(event_types))
    if has_write and not confirmation_ok:
        critical.append("write_before_exact_confirmation")
        confirmation = next(
            (event for event in events if event.get("type") == "exact_package_confirmation"),
            {},
        )
        if confirmation and confirmation.get("performer_type") != "человек":
            critical.append("unidentified_human_commit")
    if has_write and not transaction_ok:
        critical.append("partial_write_reported_as_atomic")
    if "accepted_history_overwrite" in event_types:
        critical.append("overwrite_accepted_history")
    if "ai_confirmation" in event_types:
        critical.append("unidentified_human_commit")
    if "source_conflict_silently_merged" in event_types:
        critical.append("unverified_source_promoted_to_truth")
    if "drawio_canonicalized" in event_types:
        critical.append("projection_promoted_to_canonical_model")
    if "external_mutation" in event_types or outcome.get("external_mutations"):
        critical.append("unauthorized_external_mutation")
    if case.case_id == "audit-no-write" and (has_write or outcome.get("writes")):
        critical.append("unauthorized_external_mutation")

    scores = {
        "skill_harness": score([case_id in cases, schema_ok, questions_ok, confirmation_ok, transaction_ok, outcome_ok]),
        "agent_behavior": score([required_present, required_ordered, not forbidden_found, questions_ok, confirmation_ok, transaction_ok]),
        "artifact_quality": score([outcome_ok, not outcome.get("external_mutations"), not critical, required_present, transaction_ok]),
    }
    passed = all(value >= 8 for value in scores.values()) and not critical and not failures
    return {
        "trial_id": trial.get("trial_id"),
        "case_id": case_id,
        "provenance": trial.get("provenance"),
        "source": trial.get("_path"),
        "passed": passed,
        "scores": scores,
        "critical_violations": sorted(set(critical)),
        "failures": failures,
    }


def load_trial(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_path"] = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return data


def release_gate(reports: list[dict[str, Any]], cases: dict[str, Case]) -> list[str]:
    failures: list[str] = []
    for case in cases.values():
        if not case.release_blocking:
            continue
        trials = [
            report
            for report in reports
            if report["case_id"] == case.case_id and report["provenance"] == "fresh_agent"
        ]
        unique = {report["trial_id"] for report in trials}
        if len(unique) < 3:
            failures.append(f"{case.case_id}: требуется 3 fresh_agent trials, найдено {len(unique)}")
        if any(not report["passed"] for report in trials):
            failures.append(f"{case.case_id}: не все fresh_agent trials прошли")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial", type=Path, action="append", default=[])
    parser.add_argument("--trials-dir", type=Path)
    parser.add_argument("--self-test", action="store_true", help="Проверить grader на pass/fail fixtures")
    parser.add_argument("--release-gate", action="store_true", help="Требовать 3/3 fresh_agent trials каждого blocking case")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    paths = list(args.trial)
    if args.trials_dir:
        paths.extend(sorted(args.trials_dir.glob("*.json")))
    if args.output:
        output_path = args.output.resolve()
        paths = [path for path in paths if path.resolve() != output_path]
    if args.self_test or not paths:
        paths.extend(sorted(FIXTURES_DIR.glob("*.json")))
    paths = list(dict.fromkeys(path.resolve() for path in paths))
    if not paths:
        print("[FAIL] Нет trial-файлов", file=sys.stderr)
        return 2

    cases = load_cases()
    trials = [load_trial(path) for path in paths]
    reports = [grade_trial(trial, cases) for trial in trials]
    harness_failures: list[str] = []
    if args.self_test or not args.trial and not args.trials_dir:
        for trial, report in zip(trials, reports, strict=True):
            expected = trial.get("expected_result")
            actual = "pass" if report["passed"] else "fail"
            if expected not in {"pass", "fail"}:
                harness_failures.append(f"{trial.get('trial_id')}: нет expected_result")
            elif expected != actual:
                harness_failures.append(f"{trial.get('trial_id')}: ожидалось {expected}, получено {actual}")
    gate_failures = release_gate(reports, cases) if args.release_gate else []
    if args.self_test or (not args.trial and not args.trials_dir and not args.release_gate):
        overall_passed = not harness_failures
    elif args.release_gate:
        overall_passed = not gate_failures
    else:
        overall_passed = all(report["passed"] for report in reports)
    payload = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "release_gate" if args.release_gate else "grader_self_test" if args.self_test else "trial_grade",
        "reports": reports,
        "harness_failures": harness_failures,
        "release_gate_failures": gate_failures,
        "passed": overall_passed,
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
