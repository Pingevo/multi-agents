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

## Issue lifecycle

เมื่อทำ issue เสร็จและ commit แล้ว ต้องอัปเดต GitHub issue ทุกครั้ง:

1. **เช็คว่า issue อยู่ใน Project Board แล้วหรือยัง** — ถ้ายัง ให้เพิ่มเข้า board ก่อน (ดูวิธีด้านล่าง)
2. **อัปเดต Status field → Done** บน Project Board (ผ่าน GraphQL API ด้วย token จาก .env)
3. **เพิ่ม comment สรุปงาน** ใน issue ประกอบด้วย:
   - ไฟล์ที่เปลี่ยน (ทั้งใหม่และแก้)
   - ผล test (ผ่านกี่จากกี่)
   - commit hash (หรือ reference เช่น `Refs #136`)
4. **ห้ามปิด issue อัตโนมัติ** — ปล่อยให้ human ตรวจสอบก่อน แล้วปิดเอง

เหตุผล: ถ้าไม่อัปเดต issue จะเห็นเป็น Todo ตลอด ทำให้สับสนว่ายังไม่ได้ทำ และคนที่มาทำต่อไม่รู้ว่าทำไปแล้ว

## Project Board (workaround — ไม่ใช่ repo board)

repo `Pingevo/multi-agents` เราไม่ใช่เจ้าของ สร้าง project board ใน repo ไม่ได้ — ใช้ board ของ token owner (`itdev3-bot`) แทน:

- **Board**: [Multi-Agents Board](https://github.com/users/itdev3-bot/projects/1) — project ID `PVT_kwHOEgEBqs4BdqeL`
- **Token**: ใน `.env` (`GITHUB_TOKEN`) — โหลดด้วย `set -a; source .env; set +a` แล้วใช้ `$GITHUB_TOKEN` (ห้าม echo ค่าจริง — ตามกฎ Secrets Section 16)
- **ดูรายละเอียด field, milestone, view ที่** [project-board.md](./project-board.md)

### ขั้นตอนอัปเดต Status (GraphQL)

```bash
set -a; source .env; set +a

# 1. หา issue node ID
ISSUE_NODE=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/Pingevo/multi-agents/issues/139 | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['node_id'])")

# 2. เพิ่ม issue เข้า board (ถ้ายังไม่อยู่)
curl -s -X POST -H "Authorization: bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"mutation{addProjectV2ItemById(input:{projectId:\\\"PVT_kwHOEgEBqs4BdqeL\\\",contentId:\\\"$ISSUE_NODE\\\"}){item{id}}}\"}" \
  https://api.github.com/graphql

# 3. หา item ID ของ issue ใน board
curl -s -X POST -H "Authorization: bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"query{node(id:\"PVT_kwHOEgEBqs4BdqeL\"){... on ProjectV2{items(first:100){nodes{id content{... on Issue{number}}}}}}}"}' \
  https://api.github.com/graphql

# 4. อัปเดต Status field → Done (ต้องการ item ID จากขั้น 3 + field ID + option ID จาก project-board.md)
```

**สำคัญ**: issue ไม่ได้ถูกเพิ่มเข้า board อัตโนมัติ — ต้องเพิ่มเองทุกครั้ง (ขั้นตอนที่ 2)

## PRs as a request surface

Yes — repo has remote `Pingevo/multi-agents`. PRs are welcome but not required for solo work.

## Migration (completed 2026-08-05)

Switched from local markdown to GitHub Issues. Existing `.scratch/` HANDOFF files are kept as feature-scoped notes only.
