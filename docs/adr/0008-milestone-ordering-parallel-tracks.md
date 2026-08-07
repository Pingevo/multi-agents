# ADR-0008: Milestone Ordering — M7-M11 เป็น Parallel Feature Tracks

**Date:** 2026-08-07
**Status:** Accepted

## Context

M1–M6 ทำตามลำดับเลข milestone มาตลอด เพราะทุก milestone เป็น finish-to-start (ตัวถัดไป depend ตัวก่อน) ทำงานได้ปกติ

แต่หลัง M6.5 โครงสร้าง dependency เปลี่ยน — M7, M8, M9, M10, M11 เป็น feature คนละสาย ไม่ depend กันโดยตรง:

| Milestone | งานหลัก | Depend อะไร |
|---|---|---|
| M7 | Product Content, Output Format | Knowledge Store (#106, M6) — ไม่ depend M8-M11 |
| M8 | Scheduler UI, Automation Loop | DataStore (M6.5) — ไม่ depend M7, M9-M11 |
| M9 | Social Post, Credential, Adapters | DataStore (M6.5) — ไม่ depend M7-M8, M10-M11 |
| M10 | Content Library | DataStore (M6.5) — ไม่ depend M7-M9, M11 |
| M11 | Learning, Memory, Trust Score | Knowledge Store (#106, M6) + chromadb (ADR-0007) — ไม่ depend M7-M10 |

ตรวจสอบ dependency จริงใน issue body ทุกตัว — ไม่มี issue ใน M7-M10 ที่ depend M11 และไม่มี issue ใน M11 ที่ depend M7-M10

## Decision

**แบ่ง milestone เป็น 2 ช่วง:**

1. **Foundation (M1–M6.5)** — ทำตามลำดับเลข (finish-to-start ต่อเนื่อง)
2. **Feature tracks (M7–M11)** — user เลือกทำตามความเร่งด่วน (ขนานกัน ไม่ depend กัน)

**ลำดับปัจจุบัน:** M6 → M6.5 → **M11** (user เลือก เพราะเร่งด่วน) → M7 → M8 → M9 → M10

## Rationale (สากล)

- **Critical Path Method (CPM)**: ลำดับมาจาก dependency graph ไม่ใช่เลขลำดับ
- **Scrum.org / Growing Scrum Masters**: "Prioritisation ≠ Ordering — A high-priority item might be ordered later because it has dependencies"
- **Atlassian**: "Sequence milestones around dependencies—including the critical path"
- **Reforge**: "Great milestones ensure prompt value delivery AND sequence work appropriately accounting for dependencies"

สากลไม่ได้บอกให้เลิก milestone — บอกให้แยก "ชื่อกลุ่มงาน" (milestone) ออกจาก "ลำดับทำจริง" (ordering by dependency)

## Consequences

- M7-M10 ไม่ต้องรอกัน ทำขนานได้ถ้ามี resource
- User เป็นคนตัดสินใจลำดับใน feature tracks ไม่ใช่เลข milestone
- ถ้าสละลำดับต้องบันทึก ADR (เช่น ADR-0008 นี้)
- ต้องระบุ `Depends on: #XX` ใน issue ที่มี dependency จริง
- SYSTEM_PROTOCOL Section 18 เพิ่มใหม่เป็นกฎการจัดลำดับ

## Refs

- SYSTEM_PROTOCOL.md Section 18 (ใหม่)
- CPM: https://en.wikipedia.org/wiki/Critical_path_method
- Atlassian: https://www.atlassian.com/agile/project-management/project-management-dependencies
- Scrum.org: https://www.scrum.org/resources/blog/how-can-dependencies-impact-order-product-backlog
- M11 due date ย้ายจาก 2027-01-10 → 2026-11-15 (หลัง M6.5 due 2026-10-14)
