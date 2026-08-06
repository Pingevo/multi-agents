# CLAUDE.md

## Agent skills

### Issue tracker

GitHub Issues — issues live at https://github.com/Pingevo/multi-agents/issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Recorded as GitHub labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — one `CONTEXT.md` at repo root, one `docs/adr/` at repo root. See `docs/agents/domain.md`.

## Working principles (Karpathy-inspired)

### 1. Think Before Coding

- State assumptions explicitly — if uncertain, ask rather than guess
- Present multiple interpretations — don't pick silently when ambiguity exists
- Push back when warranted — if a simpler approach exists, say so
- Stop when confused — name what's unclear and ask for clarification

### 2. Simplicity First

- Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked
- No abstractions for single-use code
- No "flexibility" or "configurability" that wasn't requested
- No error handling for impossible scenarios
- If 200 lines could be 50, rewrite it
- Test: Would a senior engineer say this is overcomplicated? If yes, simplify.

### 3. Surgical Changes

- Touch only what you must. Clean up only your own mess.
- Don't "improve" adjacent code, comments, or formatting
- Don't refactor things that aren't broken
- Match existing style, even if you'd do it differently
- If you notice unrelated dead code, mention it — don't delete it
- Remove imports/variables/functions that YOUR changes made unused
- Test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

- Define success criteria. Loop until verified.
- For multi-step tasks, state a brief plan with verification checks
- Strong success criteria let the assistant loop independently
- Weak criteria ("make it work") require constant clarification

## Project protocol

This project follows `SYSTEM_PROTOCOL.md` as its constitution. Key rules:

- **Market Parity Baseline (NON-NEGOTIABLE)**: อะไรที่ AI chat ในตลาด (Claude, ChatGPT, Gemini) ทำได้เป็นพื้นฐาน ระบบเราต้องทำได้ — ไม่ต้องถาม user ก่อนทำ parity feature. ดู checklist ใน `SYSTEM_PROTOCOL.md` section 14
- User is the Manager — all features need approval
- Agent Factory & Registry is single source of truth
- Dashboard-first UI
- No over-engineering — do not create Agents unless user orders it
- Summarize logic before big work
- Investigate stack traces before guessing
- Maintain `DEVELOPER_LOG.md` every time code is edited
- **Update GitHub issue after work is committed**: set Status=Done + add a comment summarizing what was done (files, tests, commit hash). Do NOT auto-close — let a human verify first. See `docs/agents/issue-tracker.md` → Issue lifecycle.
