# Fresh-agent release gate v0.3 — run 3

- Run ID: `v0.3-terra-medium-2026-08-11-r3`
- Date: 2026-08-11
- Candidate model: `gpt-5.6-terra`
- Reasoning effort: `medium`
- Controller: root Codex agent
- Topology: managed parallel fan-out, no more than six active trial agents
- Planned evidence: three independent trials for each of sixteen release-blocking cases
- Planned total: 48 fresh-agent trials
- Trial provenance: exact scalar `fresh_agent`

## Isolation contract

Each agent starts with `fork_turns=none` and receives only the selected skill, the raw user scenario, an in-memory fixture instruction, `evals/FRESH-AGENT-CONTRACT.md`, and the path of its own result. Agents may not read case expectations, rubric, grader, earlier outputs, prior run results, git history, prior chat, or live Google Sheets.

Each trial owns exactly one JSON file. Before saving, the agent reconciles actions visible in transcript and outcome with the canonical event vocabulary without inventing steps. The controller grades each wave, never rewrites trial evidence and stops on a repeatable defect.

## Result

Run stopped after the first six trials: one passed. Three agents incorrectly treated facts omitted from the one-line scenario as fixture blockers instead of continuing the deterministic simulated dialogue. The other evidence exposed two skill defects (early exit after material classification and premature inheritance proof) plus one genuinely wrong editor-registration sequence. One external-component trial was behaviorally valid and exposed two non-causal grader edges. Trial files remain unchanged; simulator semantics, three skill rules and the causal graph were corrected before run 4.
