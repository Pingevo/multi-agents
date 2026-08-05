# Triage Labels

## Canonical roles

| Role | Label | Description |
|------|-------|-------------|
| Needs evaluation | `needs-triage` | Maintainer needs to evaluate this issue |
| Waiting on reporter | `needs-info` | Waiting for more information from the reporter |
| AFK-ready | `ready-for-agent` | Fully specified, an agent can pick it up with no human context |
| Needs human | `ready-for-human` | Needs human implementation |
| Won't fix | `wontfix` | Will not be actioned |

## GitHub Issues mapping (active — migrated 2026-08-05)

Issues live on GitHub (`Pingevo/multi-agents`). Apply triage labels directly via `github-mcp-server` `issue_write` with `method: "update"` and the `labels` array.

Triage labels are applied IN ADDITION to the type/priority labels documented in `docs/agents/issue-tracker.md` (e.g. an issue can have `bug`, `P1`, AND `ready-for-agent`).

## Defaults

Each role's label string equals its canonical name. No overrides configured.
