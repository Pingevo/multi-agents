# ADR-0007: Semantic Retrieval (RAG) สำหรับ Knowledge Store และ Agent Memory

**Date:** 2026-08-07
**Status:** Accepted

## Context

ระบบเรามี `chromadb==1.1.1` ใน requirements.txt ตั้งแต่ตอนเริ่มโปรเจกต์ แต่ไม่มี code ใช้งาน ไม่มี ADR ไม่มี issue อธิบายว่าจะใช้ยังไง

มี 2 ระบบที่ต้องการ retrieval:
1. **Knowledge Store** (#106, M6) — ค้นหาข้อมูลบริษัท (สินค้า, แบรนด์, เอกสาร)
2. **Agent Memory** (M11) — ดึง learnings ที่เกี่ยวข้องกับ task ปัจจุบัน

ตอนนี้ Agent Memory ดึง learnings แบบ "5 ล่าสุดเสมอ" ไม่มี relevance — ทำให้ agent ไม่จำบทเรียนที่เกี่ยวข้องถ้ามันอยู่ในตำแหน่งที่ 6 ขึ้นไป

## Decision

**ใช้ semantic retrieval (RAG) ผ่าน chromadb สำหรับทั้งสองระบบ**

### เหตุผล (Market Parity Baseline)

ตลาดที่เราเทียบด้วยใช้ semantic retrieval:
- **ChatGPT memory** — เก็บ facts เป็น embeddings, ดึงที่เกี่ยวข้องกับ context ปัจจุบัน (ไม่ใช่ last N)
- **Cursor** — semantic search across codebase (ไม่ใช่ keyword match)
- **Devin** — playbook retrieval by task similarity

ตามกฎ Market Parity Baseline: ถ้าตลาดทำได้ เราต้องทำได้ ใช้ OpenRouter API เหมือนกัน เราทำได้

### สถาปัตยกรรม

```
Knowledge Store (#106)
  └─ chromadb collection: "knowledge_{brand_id}"
     └─ ingest: REST API / URL / File / Text → chunk → embed → store
     └─ query: query_knowledge_base tool (#108) → semantic search → return top-K

Agent Memory (M11)
  └─ chromadb collection: "learnings_{agent_id}"
     └─ ingest: add_learning() → embed lesson → store with metadata (type, task_type, sentiment)
     └─ query: factory.py → embed current task → semantic search → return top-5 relevant
```

### ทำไม chromadb ไม่ใช่ตัวอื่น

- อยู่ใน requirements.txt แล้ว (วางไว้ตั้งแต่ตอนเริ่ม)
- embedded (ไม่ต้อง server แยก) — เหมาะกับ per-user isolation
- รองรับ metadata filtering (type, task_type, sentiment จาก #26)
- ใช้กับ local file storage ได้ (เก็บใน `data/users/{uid}/chromadb/`)

### ข้อจำกัด

- Embedding model: ใช้ผ่าน OpenRouter (มี embedding models ใน catalog แล้ว — `text-embedding-3-small` ฯลฯ)
- ถ้า OpenRouter ไม่มี embedding model ฟรี → ใช้ local embedding (sentence-transformers) เป็น fallback
- chromadb เก็บใน local disk → ต้อง migrate ตอนย้าย MongoDB (แต่ vector ไม่เก็บใน MongoDB โดยตรง — ใช้ MongoDB Atlas Vector Search หรือเก็บ chromadb ต่อ)

## Consequences

- **Knowledge Store (#106)**: เพิ่ม embedding step ตอน ingest + semantic search ตอน query
- **Agent Memory (#26)**: เพิ่ม embedding ตอน add_learning + semantic retrieval ตอน factory.py สร้าง persona
- **New dependency**: อาจต้องเพิ่ม `sentence-transformers` เป็น fallback embedding
- **Storage**: chromadb data ใน `data/users/{uid}/chromadb/` (per-user isolation)
- **Performance**: embedding ใช้เวลา ~100ms ต่อ item — ไม่กระทบมากเพราะ add_learning ไม่ได้เรียกบ่อย

## Refs

- Market parity: ChatGPT memory (semantic), Cursor (semantic codebase search), Devin (playbook retrieval)
- `chromadb==1.1.1` ใน requirements.txt (วางไว้ตั้งแต่ตอนเริ่มโปรเจกต์)
- #106 Knowledge Store, #108 query_knowledge_base tool
- #26 learnings structure, M11 Continuous Learning & Memory
- SYSTEM_PROTOCOL.md บรรทัด 110: "แปลง learnings ที่ใช้บ่อยเป็น expertise"
