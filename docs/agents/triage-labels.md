# Triage Labels

## Canonical roles

| Role | Label | Description |
|------|-------|-------------|
| Needs evaluation | `needs-triage` | Maintainer needs to evaluate this issue |
| Waiting on reporter | `needs-info` | Waiting for more information from the reporter |
| AFK-ready | `ready-for-agent` | Fully specified, an agent can pick it up with no human context |
| Needs human | `ready-for-human` | Needs human implementation |
| Won't fix | `wontfix` | Will not be actioned |

## Local markdown mapping

Since we use local markdown (no label system), labels are recorded as a `status:` field in the front matter of each issue file:

```markdown
---
status: needs-triage
---
```

## Defaults

Each role's label string equals its canonical name. No overrides configured.
