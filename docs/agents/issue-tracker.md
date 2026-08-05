# Issue Tracker

## Type

GitHub Issues (migrated 2026-08-05 — repo now has remote `Pingevo/multi-agents`)

## Location

Issues live on GitHub: https://github.com/Pingevo/multi-agents/issues

`.scratch/<feature>/` is now used only for feature-scoped notes (e.g. `HANDOFF.md`), NOT for tracking issues.

## Convention

- Create issues via `github-mcp-server` tool `issue_write` with `method: "create"`
- One issue per bug/feature — do not batch unrelated bugs in a single issue
- Use `status:` front matter only for legacy `.scratch/` notes (deprecated for new issues)

### Title format

`[<type>] <short description in Thai or English>`

- `<type>` = `bug` | `feat` | `chore` | `docs` | `refactor` (lowercase, brackets)
- Description should be specific enough to identify the issue from the title alone
- Examples (from existing issues):
  - `[bug] Manager LLM ส่ง plan JSON ไม่สมบูรณ์เป็นบางครั้ง (flaky parse)` (#126)
  - `[bug] FreeModelRotator uses stale free-model slugs (all 404)` (#125)

### Body format (sections, in this order)

```markdown
## Symptom
<what the user sees / what goes wrong>

## Evidence (server log | browser capture, <date>)
<concrete logs, DOM captures, stack traces — not "I think it's broken">

## Repro
<numbered steps to reproduce — must be specific enough for an agent to follow>

## Root cause
<which file/line, why it happens — cite line numbers>

## Impact
<who is affected, how often, severity in plain language>

## Proposed fix
<concrete steps — file + line + what to change>

## Files
- `path/to/file.py` — line X (what's wrong)

## TDD status
<what RED test is needed, or "no test exists yet">

## Priority
P0 | P1 | P2 — with one-line justification referencing a comparable existing issue
```

### Labels

- `bug` — something is broken
- `feat` — new feature
- `ux` — user experience / visual issue
- `P0` — blocks usage for everyone (e.g. #125 free model 404)
- `P1` — UX bad but not blocking (e.g. #126 flaky parse)
- `P2` — cosmetic / minor

Always include a `P0`/`P1`/`P2` label — every issue needs a priority.

## PRs as a request surface

Yes — repo has remote `Pingevo/multi-agents`. PRs are welcome but not required for solo work.

## Migration (completed 2026-08-05)

Switched from local markdown to GitHub Issues. Existing `.scratch/` HANDOFF files are kept as feature-scoped notes only.
