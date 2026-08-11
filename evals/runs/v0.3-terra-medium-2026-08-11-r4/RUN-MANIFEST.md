# Fresh-agent release gate v0.3 — run 4

- Run ID: `v0.3-terra-medium-2026-08-11-r4`
- Date: 2026-08-11
- Candidate model: `gpt-5.6-terra`
- Reasoning effort: `medium`
- Controller: root Codex agent
- Topology: managed parallel fan-out, no more than six active trial agents
- Planned evidence: three independent trials for each of sixteen release-blocking cases
- Planned total: 48 fresh-agent trials
- Trial provenance: exact scalar `fresh_agent`

## Isolation contract

Each agent starts with `fork_turns=none` and receives only the selected skill, the raw user scenario, an in-memory fixture instruction, `evals/FRESH-AGENT-CONTRACT.md`, and the path of its own result. The deterministic simulator supplies minimal synthetic answers to every one-at-a-time question; absent fields in the one-line scenario are not blockers. Agents may not read case expectations, rubric, grader, earlier outputs, prior run results, git history, prior chat, or live Google Sheets.

Each trial owns exactly one JSON file. Before saving, the agent reconciles actions visible in transcript and outcome with the canonical event vocabulary without inventing steps. The controller grades every wave, never rewrites evidence and stops on a repeatable defect.
