# Triage Labels

## Canonical roles

| Role | Label | Description |
|------|-------|-------------|
| Needs evaluation | `needs-triage` | Maintainer needs to evaluate this issue |
| Waiting on reporter | `needs-info` | Waiting for more information from the reporter |
| AFK-ready | `ready-for-agent` | Fully specified, an agent can pick it up with no human context |
| Needs human | `ready-for-human` | Needs human implementation |
| Won't fix | `wontfix` | Will not be actioned |

## GitHub Issues mapping

Since we use GitHub Issues (see `issue-tracker.md`), triage status is recorded via GitHub labels. The canonical role maps to a GitHub label of the same name:

| Canonical role | GitHub label |
|----------------|--------------|
| `needs-triage` | `needs-triage` |
| `needs-info` | `needs-info` |
| `ready-for-agent` | `ready-for-agent` |
| `ready-for-human` | `ready-for-human` |
| `wontfix` | `wontfix` |

If a label does not yet exist in the repo, create it before applying.

## Defaults

Each role's label string equals its canonical name. No overrides configured.
