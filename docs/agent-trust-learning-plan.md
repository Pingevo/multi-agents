# Agent Trust & Continuous-Learning System

สร้างระบบที่ให้ agent เรียนรู้จาก feedback ของ user สะสมไปเรื่อยๆ จนกว่า user จะพอใจสม่ำเสมอ แล้วลดความจำเป็นในการตรวจสอบซ้ำในอนาคต (ไม่รวมระบบ schedule ตามที่ user ระบุว่ายังไม่ต้องทำ)

## Gap Analysis — ตรวจทั้งโปรเจค 100% พบ 33 จุด

### A. Feedback ถูกเก็บแต่ไม่ถูกใช้ต่อ (dead data)
1. **`task_ratings_*.json`** (`chat.py:1194-1216`, action `rate_task`) — user ให้คะแนน 1-5 ดาว แต่**ไม่มีที่ไหนอ่านไฟล์นี้กลับมาใช้เลย**
2. **`registry.add_learning()`** (`registry.py:191-200`) — เก็บ flat list แค่ 10 รายการล่าสุด ไม่แยกตามประเภทงาน ไม่คำนวณ trend
3. **`approve_agent_result` ไม่บันทึก learning** (`chat.py:994-1014`) — user กดอนุมัติผลงาน agent แต่ไม่มี `add_learning` เรียกเลย ไม่มี positive signal บันทึก
4. **`reject_agent_result` ไม่บันทึก learning โดยตรง** (`chat.py:1015-1034`) — feedback ถูกส่งเข้า orchestrator retry loop ผ่าน `review_results` แต่ไม่ได้เรียก `add_learning` ที่จุดนี้ — learning ถูกบันทึกเฉพาะใน `finally` block ของ `execute_multi_agent_task` ผ่าน `agent_memories` เท่านั้น (เป็น indirect)
5. **`approve_image` ไม่บันทึก learning** (`chat.py:871-920`) — user อนุมัติภาพที่สร้างขึ้น แต่ไม่มี learning entry ว่า agent ทำภาพที่ user พอใจ
6. **`skip_review` ไม่บันทึก learning** (`chat.py:1397-1403`) — user ข้ามการตรวจ แต่ไม่มีการบันทึกว่า user ยอมรับ output นี้โดยไม่ตรวจ (implicit approval)

### B. ไม่มีช่องกรอก/บันทึก feedback ในบางจุด
7. **Image/video reject ไม่มีช่องกรอกเหตุผลเลย** (`chat.py:987-993`) — กดปฏิเสธแล้วจบ ไม่มี feedback text ไม่มี learning บันทึก
8. **TTS/STT/Vision/Document — ไม่มี execution path เลย ไม่ใช่แค่ไม่มี approval loop** — tools คิว prompt เข้า `_media_tool_results` แต่:
   - `_send_approval_card` (`chat.py:273`) เช็ค `if not media_prompt: return` — TTS ใช้ key `text`, STT ใช้ `audio_url`, vision ใช้ `image_url`, document ใช้ `filename` — **ทุกชนิดที่ไม่ใช่ image/video ถูก skip เงียบๆ**
   - `approve_image` (`chat.py:871-920`) มีแค่ `if media_type == "video": ... else: generate_image` — ไม่มี branch สำหรับ tts/stt/vision/document
   - `MediaGenerationManager` (`media/manager.py`) มี `set_models` รับ tts/stt/vision model แต่**ไม่มี method `generate_tts`, `generate_stt`, `generate_vision` เลย** — มีแค่ `generate_image` กับ `generate_video`
   - `reply_audio_result`, `reply_transcription_result`, `reply_file_result` ใน `messenger.py` ถูก define แต่**ไม่มีที่ไหนเรียกใช้**
   - สรุป: TTS/STT/Vision/Document เป็น **dead pipeline** ทั้งระบบ — tool ทำงาน คิวผล แต่ผลหายเงียบๆ ไม่ถึง user ไม่มี approval ไม่มี feedback
9. **`reject_plan` frontend ไม่ส่ง feedback** — frontend เรียก `onRejectPlan()` โดยไม่มี feedback text (ไม่มี input field) แต่ backend `actions.py:191-235` คาดไว้ใน `action.payload.get("feedback")` — **ช่องกรอกเหตุผลมีฝั่ง backend รอรับ แต่ frontend ไม่มี UI ส่ง**
10. **`agent_feedback` action เป็น dead code** (`actions.py:404-438`) — backend มี handler รับ feedback + rating โดยตรงต่อ agent แต่ **frontend ไม่เคยเรียก action นี้เลย** (grep ใน `frontend/src` ไม่พบ) เป็นช่องทาง feedback ที่สร้างไว้แต่ใช้ไม่ได้

### C. ไม่มี Trust Score / Confidence
11. ไม่มีการนับ "approval streak" ต่อ agent+task-type — Manager review (`orchestrator.py: _batch_manager_review`) ตรวจเข้มเท่าเดิมทุกครั้ง ไม่ว่า agent จะผ่านมาแล้วกี่รอบ
12. **ไม่มีการเรียนรู้ระดับ Model** — `ModelSelector.assign_models` (`selector.py:150`) เลือก model แบบ heuristic ครั้งเดียว ไม่ติดตามว่า model ไหนทำให้ agent ผ่านการตรวจบ่อยกว่า
13. **`_batch_manager_review` ไม่รับข้อมูล trust/learnings** (`orchestrator.py:620-730`) — review prompt ส่งเฉพาะ name, role, goal, output, quality_criteria, output_format — **ไม่ส่ง learnings หรือ trust indicator ให้ Manager เลย** Manager ตรวจสายตาบอดทุกครั้ง
14. **`check_resources` ไม่พิจารณา trust/performance** (`secretary.py:1032-1067`) — การตัดสินใจ reuse agent เดิม ดูแค่ name match หรือ role/tools match ไม่ดูว่า agent ตัวนั้นทำงานได้ดีแค่ไหน

### D. ไม่มี Auto-tune จาก pattern
15. Tuning (`secretary.py: analyze_feedback`) ทำงานเฉพาะเมื่อ user สั่งเองเท่านั้น — ถ้า agent ถูก reject ซ้ำๆด้วยเหตุผลคล้ายกัน ระบบไม่เสนอปรับอัตโนมัติ
16. **ไม่มี permanent quality_criteria จาก approval pattern** — แม้ agent จะถูก approve ซ้ำๆโดยไม่มี feedback ต้องแก้ ก็ไม่มีจุดที่ "ล็อกมาตรฐานนี้เป็นค่าเริ่มต้น" ให้อัตโนมัติ
17. **ไม่มี feedback loop validation** — หลัง apply tuning (`confirm_tuning`) ไม่มีกลไกตรวจสอบว่า output หลัง tuning ดีขึ้นจริงไหม ไม่มี before/after comparison

### E. Context ไม่ละเอียดพอ / หน่วยความจำจำกัด
18. `last_task_context` (`secretary.py:110-124`) ส่งแค่สรุปย่อ 1,500 ตัวอักษร ไม่ใช่ output เต็มของ agent ที่เกี่ยวข้อง — follow-up ("แคปชั่นยังไม่ดี") เดางานใหม่ไม่ตรงจุด
19. **`conversation_history` ตัดแค่ 20 ข้อความเสมอ** (พบ 5 จุดใน `secretary.py`) — preference ที่ user บอกไว้นานแล้วจะถูกลืมถ้าคุยเกิน 20 ข้อความ

### F. ไม่มี Layer ระดับ Team/User (แค่ระดับ Agent เดี่ยว)
20. **`brand_context` ผูกกับ agent แต่ละตัว ไม่ผูกกับ team** — เสี่ยง drift ถ้า agent 2 ตัวในทีมเดียวกันมี brand_context ไม่ตรงกัน (สร้างคนละครั้ง คนละค่า)
21. **ไม่มี user-level preference/profile ข้าม team** — ทุก learning ผูกกับ agent ตัวเดียว ไม่มี "user คนนี้ชอบแบบนี้เสมอ" ที่ apply ข้าม agent/team ทั้งหมด

### G. อื่นๆ
22. **ไม่มี cost-vs-quality awareness** — `credit_logger.py` เก็บ cost ต่อ call แต่ไม่เชื่อมกับ trust score — ไม่รู้ว่า agent trust สูงใช้ model แพงหรือถูก ไม่มีการเสนอลด cost โดยไม่เสีย quality
23. **ไม่มี pattern tracking ของ error ที่เกิดซ้ำ** — `last_failed_task` เก็บแค่ใน session (`cl.user_session`) ไม่ persist ข้าม session ไม่มีการเรียนรู้ว่า tool/model ไหนล้มเหลวบ่อยกับ agent ไหน
24. **ไม่มี task-type categorization ใน learnings** — learning ไม่ tag ประเภทงาน — agent อาจเก่งเขียนแคปชั่นแต่แย่เขียนบทความ ระบบแยกไม่ได้
25. **`ChatStore` / `HistoryStore` ไม่ถูกใช้เพื่อเรียนรู้** — `chat_store.py` เก็บประวัติแชททุก session, `history_store.py` เก็บ action log ต่อ task — ข้อมูลทั้งสองแหล่งไม่ถูก mine เพื่อหา pattern หรือ preference
26. **`rate_task` มีใน TeamDetailPage แต่ไม่มีใน MainLayout** — `MainLayout.tsx` ส่ง `onSkipReview` แต่ไม่ส่ง `onRateTask` — user ให้คะแนนได้เฉพาะมุมมอง Team เท่านั้น มุมมองหลักไม่มีปุ่ม rate
27. **`BackgroundScheduler._execute_scheduled` รันแบบ context-blind** (`scheduler.py:70-91`) — เรียก `assess_and_plan(prompt)` โดยไม่ส่ง conversation_history, last_task_context, registry_agents, team_agents — scheduled task ทำงานโดยไม่รู้อะไรเลยนอกจาก prompt เปล่า ไม่มีการเรียนรู้จากครั้งก่อน
28. **`credit_logger.py` เขียน JSONL แต่ไม่มี readback** — log ทุก call แต่ไม่มี analytics สรุป cost ต่อ agent/model/task ไม่มีที่ใช้ข้อมูลนี้

### H. Task Templates ไม่ผูกกับคุณภาพ
29. **`TaskTemplateStore`** (`template_store.py`) เก็บแค่ prompt string เปล่า — ไม่ผูกกับ agent config/quality_criteria ที่ user เคยปรับจนพอใจแล้ว ใช้ template ซ้ำก็ต้องคุม quality เองใหม่ทุกครั้ง

### I. Learnings injection ไม่มีโครงสร้าง
30. **`factory.py` ฉีด learnings แบบ flat text** (`factory.py:64-72`) — ทุกประเภท learning (task_completion, rejection_feedback, user_feedback) ถูกฉีดเป็น "Lessons from past work" แบบเรียบๆ ไม่แยก positive/negative/neutral — agent เห็นแค่รายการบทเรียน ไม่รู้ว่าอะไรคือสิ่งที่ทำได้ดี อะไรคือสิ่งที่ต้องแก้

### J. Tuning rejection ไม่เก็บ feedback
31. **`reject_tuning` ไม่ capture feedback** (`actions.py:542-550`) — user ปฏิเสธ tuning proposal แล้วจบเลย ไม่มีช่องถามว่าทำไมไม่เอา — เสียโอกาสเรียนรู้ว่า user ไม่ต้องการการปรับแบบไหน (เหมือน `reject_image` ที่ไม่มี feedback ใน gap #7)

### K. Tuning analysis ไม่ใช้ประวัติ
32. **`analyze_feedback` ไม่ส่ง learnings เข้า prompt** (`secretary.py:568-682`) — ตอนวิเคราะห์ feedback เพื่อเสนอ tuning ส่งแค่ name, role, goal, persona, personality, expertise, brand_context, tools, model — **ไม่ส่ง learnings หรือ trust score** ทำให้ LLM อาจเสนอการปรับที่ซ้ำกับ feedback ที่ agent เคยได้รับแล้ว หรือเสนอเปลี่ยน field ที่ user เคยบอกว่าห้ามเปลี่ยน

### L. Template validation ไม่เชื่อมกับ learning/trust
33. **`validate_template_output` ไม่บันทึก learning และไม่มี trust impact** (`templates.py:130-179`, `orchestrator.py:878-934`) — มี deterministic validation (code-level, ไม่ใช้ LLM) ที่ตรวจ output ตาม template contract ก่อน Manager review — แต่:
   - มีแค่ template `product_analysis` เดียว — ไม่มี template อื่นๆ ที่ควรมี validation
   - ผล validation (pass/fail) **ไม่ถูกบันทึกเป็น `add_learning`** — agent ที่ผ่าน/ไม่ผ่าน validation ซ้ำๆ ไม่มีบันทึก
   - ไม่มี trust score impact — agent ที่ผ่าน validation บ่อยๆ ไม่ได้ trust เพิ่ม ถูกตรวจเข้มเท่าเดิมทุกครั้ง
   - template contract ถูกฉีดเข้า agent prompt (`factory.py:166-174`) และ Manager review prompt (`orchestrator.py:643-662`) แต่ผล validation ไม่ feed back เข้าระบบเรียนรู้



## แผนที่เสนอ (ไม่รวม scheduling)

### Step 1: แก้ feedback capture ให้ครบทุกช่อง + ซ่อม TTS/STT/Vision/Document dead pipeline (แก้ B.7-10, J.31)
- **เพิ่ม `generate_tts`, `generate_stt`, `generate_vision` methods ใน `MediaGenerationManager`** — ปัจจุบันมีแค่ image/video ที่ทำงานได้จริง
- **แก้ `_send_approval_card`** ให้ส่ง approval card สำหรับ TTS/STT/vision/document ด้วย (ปัจจุบัน skip เงียบเพราะไม่มี key `prompt`)
- **แก้ `approve_image`** ให้มี branch สำหรับ tts/stt/vision/document (ปัจจุบันมีแค่ image vs video)
- **เรียก `reply_audio_result`, `reply_transcription_result`, `reply_file_result`** จาก handler หลัง generate สำเร็จ (ปัจจุบันเป็น dead methods)
- เพิ่ม feedback text field ให้ `reject_image`/`reject_video` action (ปัจจุบันไม่มีเลย)
- เพิ่มปุ่ม 👍/👎 ให้ audio_result, file_result, transcription_result (ปัจจุบันไม่มี approval loop เลย)
- เพิ่ม feedback input ใน `reject_plan` UI (frontend ไม่ส่ง feedback แต่ backend รอรับ)
- เพิ่ม feedback input ใน `reject_tuning` UI (ปัจจุบันไม่มี และ backend ไม่รอรับ — ต้องเพิ่มทั้งสองฝั่ง)
- เปิดใช้ `agent_feedback` action จาก frontend (ปัจจุบันเป็น dead code)
- เพิ่ม `onRateTask` ใน `MainLayout.tsx` (ปัจจุบันมีแค่ใน TeamDetailPage)

### Step 2: บันทึก learning ทุกจุดที่มี feedback (แก้ A.1-6)
- `rate_task`: บันทึก learning เข้า agent (ไม่ใช่แค่ไฟล์ลอย) — rating ≥ 4 → `positive_outcome`; rating ≤ 2 → `negative_outcome` พร้อม prompt ขอเหตุผล
- `approve_agent_result`: เรียก `add_learning` ประเภท `user_approval`
- `reject_agent_result`: เรียก `add_learning` ประเภท `user_rejection` ที่จุด action (ไม่ใช่แค่ indirect ผ่าน agent_memories)
- `approve_image`: เรียก `add_learning` ประเภท `media_approval`
- `skip_review`: เรียก `add_learning` ประเภท `implicit_approval`

### Step 3: เพิ่ม Trust Score ต่อ agent (ใน `registry.py`) (แก้ C.11, C.13, C.14, L.33)
- เพิ่ม field: `trust_score` (0-100), `consecutive_approvals`, `consecutive_rejections`, `total_approvals`, `total_rejections`
- อัปเดตจากทุกจุด feedback ที่เพิ่มใน Step 2: Manager batch review, approve/reject_agent_result, image/video approve/reject, rate_task, skip_review
- **เพิ่ม trust update จาก `validate_template_output`** — pass → trust +1, fail → trust -2
- ส่ง trust info เข้า `_batch_manager_review` prompt: "agent นี้มี trust score 85/100, approved 10 ครั้งล่าสุด" — Manager ใช้ประกอบการตัดสินใจ
- แก้ `check_resources`: เมื่อเลือก reuse agent ให้พิจารณา trust_score ด้วย — ถ้า agent มี trust ต่ำให้สร้างใหม่แทน

### Step 4: ปรับโครงสร้าง learnings ให้มี type + task_type (แก้ A.2, G.24, I.30, L.33)
- เพิ่ม `task_type` field ใน learning entry (เช่น "caption_writing", "image_generation", "product_analysis")
- เพิ่ม `sentiment` field: `positive` / `negative` / `neutral`
- ขยาย cap จาก 10 → 50 รายการ แต่ฉีดเข้า agent เฉพาะที่ relevant ต่อ task_type ปัจจุบัน (ไม่เกิน 5)
- แก้ `factory.py` ให้แยกฉีด: "สิ่งที่ทำได้ดี" (positive) vs "สิ่งที่ต้องระวัง" (negative) แทน flat list
- **เพิ่ม learning entry จาก `validate_template_output`** — บันทึก pass/fail เป็น `template_validation` learning type

### Step 5: Model-level trust (แก้ C.12)
- เก็บ `model_performance` ต่อ agent: `{model_id: {approvals, rejections, avg_rating}}`
- เมื่อจะเปลี่ยน model ให้ agent ในอนาคต ใช้ข้อมูลนี้ประกอบการเลือกใน `ModelSelector.assign_models`

### Step 6: ผ่อนความเข้มของ Manager review ตาม Trust Score (แก้ C.11)
- ใน `_batch_manager_review`: ถ้า `consecutive_approvals >= N` (เช่น 5) → ลด `review_iterations` ที่จำเป็น หรือแจ้ง Manager ว่า "agent นี้เชื่อถือได้ ตรวจแบบผ่อนคลาย"
- ยังคง fallback ให้ user กด skip_review ได้เสมอ — ไม่ auto-skip เต็มรูปแบบ

### Step 7: Auto-tune proposal จาก pattern การ reject ซ้ำ + ส่ง learnings เข้า tuning analysis (แก้ D.15, K.32)
- หลัง agent ถูก reject 2 รอบติดด้วย feedback ธีมคล้ายกัน → เรียก `analyze_feedback` อัตโนมัติ เสนอ tuning proposal ให้ user ยืนยัน (ไม่ auto-apply)
- แก้ `analyze_feedback` ให้ส่ง `learnings` และ `trust_score` ของ agent เข้า prompt — ป้องกันการเสนอ tuning ที่ซ้ำกับ feedback ที่ agent เคยได้รับแล้ว

### Step 8: ส่ง context เต็มให้ Secretary ตอน follow-up (แก้ E.18)
- แก้ `last_task_context` ให้เก็บ output เต็มของแต่ละ agent แยก per-agent ไม่ตัดที่ 1,500 ตัวอักษรเป็นสรุปเดียว

### Step 9: ขยาย conversation memory window แบบ smart (แก้ E.19)
- แทนตัดตายตัวที่ 20 ข้อความ — สรุป (summarize) ข้อความเก่ากว่านั้นเป็น "user preferences ที่เคยบอกไว้" เก็บแยกต่างหาก ไม่ให้หายไปเฉยๆ

### Step 10: Permanent quality_criteria จาก repeated approval pattern (แก้ D.16, D.17)
- เมื่อ agent ถูก approve ติดกันหลายรอบโดยไม่มี feedback ต้องแก้ → เสนอ "บันทึกมาตรฐานนี้เป็นค่าเริ่มต้น" ให้ user ยืนยันครั้งเดียว แล้วอัปเดต `quality_criteria`/`output_format` เข้า agent record permanent
- หลัง tuning ถูก apply → track ผลลัพธ์ 3 ครั้งถัดไป เทียบกับ before-tuning เพื่อยืนยันว่า tuning มีผลจริง

### Step 11: Team-level brand_context (แก้ F.20)
- ย้าย `brand_context` ให้ผูกกับ `team_id` เป็นค่ากลาง ไม่ duplicate ต่อ agent — agent ทุกตัวในทีมอ้างอิงค่าเดียวกัน ป้องกัน drift

### Step 12: User-level preference profile (แก้ F.21)
- เพิ่ม store ใหม่ `UserPreferenceStore` เก็บ preference ที่ apply ข้าม team/agent (เช่น ภาษา, tone พื้นฐาน) แยกจาก agent-specific learning

### Step 13: เชื่อม cost กับ trust + credit analytics (แก้ G.22, G.28)
- เมื่อ agent มี trust สูงแต่ใช้ model แพง → เสนอเปลี่ยนเป็น model ถูกกว่าที่ `model_performance` (Step 5) แสดงว่าผลลัพธ์ยังผ่านเท่าเดิม
- สร้าง analytics module ที่อ่าน `llm-call-log.jsonl` สรุป cost ต่อ agent/model/task-type — ปัจจุบันเขียน log ทุก call แต่ไม่มี readback

### Step 14: Persist error pattern (แก้ G.23)
- ย้าย `last_failed_task` จาก session-only ไปเก็บถาวรต่อ agent (เช่นใน `learnings` ประเภท `execution_error`) เพื่อดูเทรนด์ error ซ้ำๆ

### Step 15: ผูก Task Template กับ agent config (แก้ H.29)
- `TaskTemplateStore` เก็บ snapshot ของ agent config (`quality_criteria`, `output_format`, `tools`) ที่ใช้ตอน approve สำเร็จ ไม่ใช่แค่ prompt string — ใช้ template ซ้ำแล้วได้ config เดิมที่พิสูจน์แล้วว่า user พอใจ

### Step 16: Mine ChatStore/HistoryStore เพื่อเรียนรู้ (แก้ G.25)
- สร้าง analyzer ที่อ่าน `chat_store.py` และ `history_store.py` เพื่อหา pattern: user มัก reject งานประเภทไหน, agent ตัวไหนมีประวัติผ่านบ่อย, preference ที่ user บอกซ้ำๆ

### Step 17: แก้ BackgroundScheduler context-blind (แก้ G.27 — ทำเมื่อระบบ schedule เปิดใช้)
- แก้ `_execute_scheduled` ให้ส่ง `conversation_history`, `last_task_context`, `registry_agents`, `team_agents` เข้า `assess_and_plan` — ปัจจุบันส่งแค่ prompt เปล่า ไม่มี context เลย
- **หมายเหตุ: user ระบุว่า scheduling ยังไม่ต้องทำ แต่บันทึกไว้เป็น known gap**

### UI ที่ต้องเพิ่ม
- Badge บน agent card แสดง trust level (เช่น 🟢 เชื่อถือได้ หลัง 5 ครั้งติด)
- แสดง trust score + model performance ใน AgentDetail/config panel
- Feedback text field บน image/video reject + ปุ่ม 👍/👎 บน audio/document/transcription result
- Feedback input ใน reject_plan dialog
- Feedback input ใน reject_tuning dialog
- ปุ่ม "ให้ feedback" บน agent card เชื่อมกับ `agent_feedback` action

---

## ลำดับความสำคัญ
1. **Step 1** (ซ่อม TTS/STT/Vision/Document dead pipeline + แก้ feedback capture ให้ครบ) — **P0 วิกฤดิ** TTS/STT/Vision/Document ไม่ทำงานเลย ต้องซ่อมก่อนทุกอย่าง
2. **Step 2-3** (บันทึก learning ทุกจุด + trust score พื้นฐาน + ส่ง trust เข้า review) — foundation ที่ต้องมาก่อน ไม่มีข้อมูลก็เรียนรู้ไม่ได้
3. **Step 4** (ปรับโครงสร้าง learnings) — ต้องทำควบกับ Step 3 เพราะโครงสร้างเดิมฉีด flat text ไม่แยกประเภท
4. **Step 8** (context เต็มให้ Secretary) — แก้ปัญหาที่ user เจอบ่อยที่สุดตอน follow-up ทำได้เร็ว ผลกระทบสูง
5. **Step 6-7, 10** (ผ่อนตรวจ + auto-tune + permanent criteria + loop validation) — ตรงเป้าหมายหลักของ user มากที่สุด แต่ต้องมี foundation มั่นคงก่อน
6. **Step 5, 13** (model-level trust + cost analytics) — ประโยชน์รอง ทำหลังมี trust score พื้นฐานแล้ว
7. **Step 11-12** (team brand_context + user preference) — ปรับ architecture ระดับกลาง ควรทำก่อนระบบใหญ่ขึ้นเพื่อไม่ต้อง migrate ทีหลัง
8. **Step 9, 14-16** (conversation memory, error pattern, template config, data mining) — nice-to-have ทำหลังสุด
9. **Step 17** (scheduler context) — รอ user อนุมัติเปิดระบบ schedule ก่อน

