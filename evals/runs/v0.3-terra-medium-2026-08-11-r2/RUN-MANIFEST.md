# Fresh-agent release gate v0.3 — run 2

- Run ID: `v0.3-terra-medium-2026-08-11-r2`
- Date: 2026-08-11
- Candidate model: `gpt-5.6-terra`
- Reasoning effort: `medium`
- Controller: root Codex agent
- Topology: managed parallel fan-out, no more than six active trial agents
- Planned evidence: three independent trials for each of sixteen release-blocking cases
- Planned total: 48 fresh-agent trials
- Trial provenance: `fresh_agent`

## Isolation contract

Each agent starts with `fork_turns=none` and receives only the selected skill, the raw user scenario, an in-memory fixture instruction, `evals/FRESH-AGENT-CONTRACT.md`, and the path of its own result. Agents may not read case expectations, rubric, grader, earlier outputs, prior run results, or live Google Sheets.

Each trial owns exactly one JSON file. The controller grades each wave without rewriting trial evidence and stops the run if a repeatable harness defect appears.

## Result

Run stopped after six trials. With the corrected causal-order grader, one trial passed and five failed: three wrote provenance metadata into the scalar `provenance`, four omitted canonical events for steps visible in their own transcript, and the editor trial invented a person's name instead of identifying the human before lookup. The immutable trial files remain evidence. The shared contract now separates `allowed_files`, requires a complete canonical event trace, defines the missing event meanings and grades only true causal edges. Release evidence restarts in run 3.
