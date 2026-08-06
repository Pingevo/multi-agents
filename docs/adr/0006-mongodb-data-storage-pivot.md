# ADR-0006: MongoDB = data storage ของเรา (pivot จากดึงสินค้า)

## Status

Accepted

## Context

OST Opportunity 7 วาง assumption ไว้ว่า "สินค้า/ราคา/โปร/รูป → MongoDB → ดึงข้อมูล" — สมมติว่า MongoDB มีสินค้าอยู่แล้วและเรามีสิทธิ์ read

เมื่อทดสอบเชื่อมต่อจริง (2026-08-06) พบว่า:
- Database `itsAgents` บน `digital.in.th:27017` ว่างเปล่า (0 collections)
- User `itsag_srv_x81rw` มีสิทธิ์ `readWrite` ใน `itsAgents` เท่านั้น (ไม่มีสิทธิ์ database อื่น)
- ชื่อ database + user ชี้ว่าเป็นของระบบเรา (`its` + `Agents`)

**Assumption ที่พัง:** MongoDB มีสินค้าอยู่แล้ว, เรามีสิทธิ์ read
**ความจริง:** MongoDB คือ data storage สำหรับระบบเราเก็บข้อมูลเอง (readWrite)

## Decision

1. **MongoDB `itsAgents` = data storage ของระบบเรา** — เก็บ chat, agents, tasks, brands, teams, generated media, ฯลฯ (ย้ายจาก JSON files ตาม ADR-0003)
2. **เรื่อง "ดึงสินค้าจาก MongoDB" พักไว้ก่อน** — สินค้าอยู่ที่ไหนยังไม่รู้ (อาจเป็น database อื่น, REST API, หรือ user กรอกเอง) — ไว้ค่อยคิด
3. **สร้าง milestone ใหม่ M6.5: Data Persistence Migration** — ย้าย JSON → MongoDB ทีละ store (strangler fig pattern)
4. **M6 เดิมลด scope** — เหลือ Brand entity + Knowledge Store (พักสินค้า)

## Consequences

- ADR-0003 (JSON persistence) ถึงเวลาย้าย — store classes (AgentRegistry, TaskStore, ChatStore, ...) คือ seam ที่เตรียมไว้แล้ว
- ต้องสร้าง `DataStore` abstraction (facade) ก่อนย้าย — ซ่อน JSON/MongoDB จากโค้ดอื่น
- ย้ายทีละ store: agent → team → brand → chat → task → ... (1 issue = 1 store)
- M8, M9, M10, M11 ที่สมมติว่า "เก็บใน JSON" ต้องปรับ — ใช้ MongoDB ผ่าน DataStore แทน
- ระบบเหมือน AI chat ในตลาด (เก็บใน DB ไม่ใช่ JSON) — ตาม Market Parity Baseline

## Impact Analysis

### Issue ที่กระทบโดยตรง
- **#129** (ดึงสินค้าจาก MongoDB) → pivot: assumption ผิด, mark ใน body, ไม่ลบ
- **#106** (Knowledge Store) → ลบ "MongoDB connector ดึงสินค้า" ออก (สินค้าไม่ได้อยู่ใน Mongo)

### Issue ที่ซ่อน assumption "เก็บใน JSON"
- **#24** (บันทึก learning) → อาจย้ายไป MongoDB
- **#31** (memory window) → อาจย้ายไป MongoDB
- **#36** (persist error pattern) → อาจย้ายไป MongoDB
- **#116** (Credential Manager) → ต้องย้ายไป MongoDB (security)
- **#132** (Content Library) → อาจย้ายไป MongoDB

### Scope ใหม่ที่ไม่เคยมีในแผน
- "data persistence layer" — ไม่เคยเป็น issue ของตัวเอง ไม่เคยอยู่ใน OST

## Refs
- ADR-0003 (JSON persistence — ชั่วคราว, มี seam ไว้ย้าย)
- OST Opportunity 7 (assumption ที่พัง)
- SYSTEM_PROTOCOL Section 16 (Assumption & Pivot Protocol)
