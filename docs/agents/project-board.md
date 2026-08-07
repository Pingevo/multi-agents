# Project Board & Roadmap

## GitHub Project

- **Project**: [Multi-Agents Board](https://github.com/users/itdev3-bot/projects/1)
- **Repo**: [Pingevo/multi-agents](https://github.com/Pingevo/multi-agents)
- **Owner**: `itdev3-bot` (bot account, separate from `Pingevo`)

## Views

| View | URL | ใช้ทำอะไร |
|---|---|---|
| Table | [/views/1](https://github.com/users/itdev3-bot/projects/1/views/1) | ดูทุก field |
| Board | [/views/2](https://github.com/users/itdev3-bot/projects/1/views/2) | ทำงานทุกวัน (kanban by Status) |
| Roadmap | [/views/3](https://github.com/users/itdev3-bot/projects/1/views/3) | timeline (ต้องตั้ง Date field = Target Ship Date ใน UI) |

## Custom Fields

| Field | Type | ค่า | ใช้ทำอะไร |
|---|---|---|---|
| Status | single select | Todo / In Progress / Done | สถานะงาน |
| Priority | single select | P0 วิกฤติ / P1 สำคัญ / P2 ปานกลาง / P3 รอง / P4 น่ามี / P5 รอเปิดใช้ | ความสำคัญ |
| Theme | single select | Opp1-Opp14 (เชื่อมกลับไป OST.md) | issue นี้มาจาก Opportunity ไหน |
| Target Ship Date | date | YYYY-MM-DD | วันที่คาดว่าจะเสร็จ (ใช้ใน Roadmap view) |
| Milestone | built-in | M6-M12 | กลุ่มงานตามเฟส |

## Milestones

### ปิดแล้ว (M1-M5)

| Milestone | งาน | สถานะ |
|---|---|---|
| M1: Foundation & Core Infrastructure | 15 issue | closed |
| M2: Multi-Agent Orchestration & Team System | 11 issue | closed |
| M3: Retro UI, CI/CD & Production Hardening | 27 issue | closed |
| M4: Enterprise Security & Data Isolation | 17 issue | closed |
| M5: Universal Multi-Modal AI | 19 issue | closed |

### กำลังทำ (M6-M12)

| Milestone | ทำอะไร | Due date | issue เปิด |
|---|---|---|---|
| M6: Company Knowledge Base (MongoDB + Brand) | เชื่อม MongoDB + ความรู้แบรนด์ | 2026-09-25 | 9 |
| M7: Product Content & Output Format | สร้าง content + กำหนด format | 2026-10-01 | 2 |
| M8: Autonomous Workforce (Scheduler + Calendar) | scheduler + calendar + อัตโนมัติ | 2026-11-01 | 6 |
| M9: External Platform (Social Post + Credential) | โพสต์ social + credential + อนุมัติ | 2026-11-20 | 9 |
| M10: Content Library | คลัง content | 2026-11-25 | 1 |
| M11: Continuous Learning & Memory | เรียนรู้ + memory + tune | 2027-01-10 | 13 |
| M12: Video Analysis & Competitor | วิเคราะห์วิดีโอ + คู่แข่ง | 2027-02-01 | 3 |

### Bug

Bug ไม่มี milestone — แก้ระหว่างทาง:
- สำคัญ → แกะเลย
- ไม่สำคัญ → เปิด issue ไว้ รอได้

## OST (Opportunity Solution Tree)

- **ไฟล์**: `OST.md` (repo root)
- **โครงสร้าง**: Outcome → 14 Opportunity → connect the dots → "ต้องมีอะไร"
- **ใช้ตอน**: เจอของใหม่ → เพิ่มใน OST ก่อน → สร้าง issue + ใส่ Theme field → เข้า project อัตโนมัติ
- **อย่าทำ**: ห้ามสร้าง issue โดยไม่ผ่าน OST

## วิธีใช้ทุกวัน

1. เปิด [Board view](https://github.com/users/itdev3-bot/projects/1/views/2)
2. ดูการ์ดในคอลัมน์ Todo → ลากที่จะทำไป In Progress
3. ทำเสร็จ → ลากไป Done
4. งานใหม่ขึ้นจาก Todo เอง

## วิธีตอบ user "ทำถึงไหนแล้ว"

ดู milestone ปัจจุบัน + due date:
- ตอนนี้อยู่ M6 (MongoDB + Brand) เสร็จ 25 ก.ย.
- ต่อไป M7 (Content) เสร็จ 1 ต.ค.
- ฯลฯ ดูตารางด้านบน

## Token

- เก็บใน `.env` (ห้าม commit)
- ใช้ผ่าน GraphQL API หรือ REST API
- scope: `project, repo`
- หมดอายุ → สร้างใหม่ที่ GitHub Settings → Developer settings → Personal access tokens
- **โหลดใน shell**: `set -a; source .env; set +a` แล้วใช้ `$GITHUB_TOKEN` (ห้าม echo ค่าจริง — ตามกฎ Secrets Section 16)

## IDs สำหรับ GraphQL (อัปเดต Status)

- **Project ID**: `PVT_kwHOEgEBqs4BdqeL`
- **Status field ID**: `PVTSSF_lAHOEgEBqs4BdqeLzhYKbwg`
- **Done option ID**: `98236657`

ตัวอย่าง mutation อัปเดต Status → Done:

```bash
curl -s -X POST -H "Authorization: bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"mutation{updateProjectV2ItemFieldValue(input:{projectId:\\\"PVT_kwHOEgEBqs4BdqeL\\\",itemId:\\\"<ITEM_ID>\\\",fieldId:\\\"PVTSSF_lAHOEgEBqs4BdqeLzhYKbwg\\\",value:{singleSelectOptionId:\\\"98236657\\\"}}){projectV2Item{id}}}\"}" \
  https://api.github.com/graphql
```

แทน `<ITEM_ID>` ด้วย item ID ของ issue ใน board (หาจาก query ใน issue-tracker.md)

## ข้อจำกัดที่รู้แล้ว

- GitHub API ไม่มีคำสั่งตั้ง timeline date field ของ Roadmap view → ต้องตั้งใน UI เอง
- GitHub API ไม่มี PATCH endpoint สำหรับ view → สร้างใหม่ได้แต่แก้ไม่ได้
- Milestone list ใน GitHub เรียงตาม database number ไม่ใช่ชื่อ → ใช้ sort by "Closest due date"
