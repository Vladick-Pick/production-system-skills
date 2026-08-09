# Fresh-agent release-gate v0.2

- Run ID: `v0.2-terra-medium-2026-08-09`
- Date: 2026-08-09
- Candidate model: `gpt-5.6-terra`
- Reasoning effort: `medium`
- Controller: root Codex agent
- Topology: managed parallel fan-out, no more than six active trial agents
- Planned evidence: three independent trials for each of ten release-blocking cases
- Trial provenance: `fresh_agent`

## Isolation contract

Each trial agent starts with `fork_turns=none` and receives only:

1. the selected repository skill and the references that skill requires;
2. one user scenario;
3. one bounded local or in-memory test artifact;
4. the path of its own trial result.

Trial agents must not read `evals/cases.yaml`, `evals/rubric.yaml`, the grader,
other trial outputs, or prior conversation history. They must not mutate live
Google Sheets or any other external system. Parallel agents own different files
and output directories.

## Evidence contract

The stored trial must contain the observed transcript, ordered event stream,
environment outcome, tool/model metadata, and absence of external mutations.
The controller checks that the persisted transcript matches the actual agent
turns and runs `scripts/run_behavioral_evals.py --release-gate` over all 30
unique trial files. A failed trial remains failed; it is not rewritten to fit
the rubric.

## Instrumentation limitation

The current Codex collaboration surface does not export a provider-signed raw
tool trace. Trial agents therefore persist their own structured event stream,
while the controller verifies it against their visible turns and local output
artifacts. This is stronger than a recorded fixture but weaker than an
independently captured production trace and must remain visible in the release
assessment.

## Raw release-gate result

- Completed: 30 of 30 planned fresh-agent trials.
- Coverage: 10 release-blocking cases, 3 independent trials per case.
- Model: `gpt-5.6-terra`, reasoning effort `medium`.
- Deterministic grader result: **FAIL**, 0 of 30 trial files passed the strict
  transcript/outcome contract.
- Critical violations: 0.
- External mutations: 0.
- Result artifact:
  `evals/results/v0.2-terra-medium-2026-08-10-raw.json`.

The raw result is not normalized or rewritten to satisfy the grader. Before
repository publication, absolute controller filesystem paths are mechanically
redacted to `${REPO_ROOT}`; event, transcript and outcome content is unchanged.
The dominant failure is the instrumentation boundary: fresh agents persisted semantically equivalent event
names, `event` instead of `type`, `telemetry` instead of top-level `events`, or
non-canonical transcript/outcome shapes. Three external-component trials also
placed `consumer_actions_linked` before `transfer_interface_resolved`; one
compaction trial nested `active_question_id` inside its question object instead
of the assistant message. These remain release-gate failures until the harness
captures the canonical trace itself and the ordering contract is resolved.
