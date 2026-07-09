# ADR-0001: Local markdown issue tracker

## Status

Accepted

## Context

The project does not have a git repository or GitHub remote. We need an issue tracker for the MattPocock engineering skills (triage, code-review, implement) to function.

## Decision

Use local markdown files under `.scratch/<feature>/` as the issue tracker. Each issue is a single `.md` file with a `status:` field in front matter for triage labels.

## Consequences

- Issues are portable — can be migrated to GitHub Issues when a remote is added
- No external dependencies required
- Triage labels are stored as front matter rather than platform labels
- If migrated to GitHub, update `docs/agents/issue-tracker.md` and move issues
