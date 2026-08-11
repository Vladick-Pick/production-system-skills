# Fresh-agent release gate v0.3

- Run ID: `v0.3-terra-medium-2026-08-11`
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

Each trial owns exactly one JSON file. No failed trial is rewritten after grading. The deterministic result and final pass/fail summary are appended after all 48 files exist.

## Result

Run stopped after the first six trials: three passed and three exposed missing observable completion/event semantics. The source trial files remain unchanged. The grader's false failure on a valid later checkpoint and its over-strict ordering of independent research events were corrected separately; the common runner contract now defines completion and ambiguous canonical event meanings. Release evidence restarts in a new isolated run instead of replacing these failed files.
