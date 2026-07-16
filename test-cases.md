# Test Cases สำหรับทดสอบระบบ Multi-Agent

## 1. สร้างทีม (Create Agents)

### TC-1.1: สร้างทีมใหม่ใน Plan mode
**Prompt:** "สร้างทีมนักเขียนคอนเทนต์ 2 คน นักออกแบบภาพ 1 คน สำหรับทำคอนเทนต์การตลาด"
**คาดหวาง:**
- AI สร้าง plan card แสดง 3 agents (ไม่ถามคำถามเพิ่ม)
- แต่ละ agent มี role, goal, persona, personality, expertise, tools, model ครบ
- กด Approve → agent ถูกสร้างใน registry + แสดงใน team list
- กด Reject → กลับไป STATE_IDLE + พิมพ์ใหม่ได้

### TC-1.2: สร้างทีมใน Chat mode
**Prompt:** "อยากได้ทีมนักวิเคราะห์ข้อมูล 2 คน ไว้ในทีม"
**คาดหวาง:**
- AI สร้าง plan card (plan_type=create_agents)
- กด Approve → agent ถูกสร้างใน registry

---

## 2. ปรับแผน (Revise Plan)

### TC-2.1: Reject แล้วปรับแผน
**Prompt 1:** "สร้างทีมนักเขียน 1 คน นักออกแบบ 1 คน"
**Action:** กด Reject
**Prompt 2:** "เปลี่ยนนักเขียนเป็น 2 คน และเพิ่มนักวิเคราะห์ SEO 1 คน"
**คาดหวาง:**
- AI เห็น plan เดิมใน history + [REJECTED] marker
- AI สร้าง revised plan: 2 นักเขียน + 1 นักออกแบบ + 1 SEO (ไม่ใช่ plan ใหม่จากศูนย์)

### TC-2.2: ส่ง message ใหม่ขณะ plan รอ approval
**Prompt 1:** "สร้างแผนเขียนบทความ 1 บทความ"
**Action:** ไม่กด Approve/Reject แสดงว่า plan ยัง pending
**Prompt 2:** "เพิ่มการทำภาพประกอบด้วย"
**คาดหวาง:**
- ระบบ discard plan เดิม + ประมวลผล prompt ใหม่

---

## 3. สร้างแผนการทำงาน (Plan + Execute)

### TC-3.1: สั่งงานใน Plan mode
**Prompt:** "เขียนบทความเกี่ยวกับ AI 1 บทความ และทำภาพประกอบ 1 ภาพ"
**คาดหวาง:**
- AI สร้าง plan: Content Writer (no depends_on) + Image Designer (depends_on Content Writer)
- ไม่ถามคำถามเพิ่ม (Plan mode ห้าม ask)
- กด Approve → orchestrator ทำงาน
- Content Writer ทำก่อน → review card → approve → Image Designer ทำต่อ
- Manager review → result card

### TC-3.2: สั่งงานใน Chat mode
**Prompt:** "ช่วยเขียนแคปชั่นโพสต์ Facebook 3 โพสต์ สำหรับร้านกาแฟ"
**คาดหวาง:**
- AI ประเมิน → สร้าง plan → plan card → approve → execute

---

## 4. Agent Review (Approve/Reject)

### TC-4.1: Approve agent
**Prompt:** "เขียนบทความเกี่ยวกับการตลาดดิจิทัล 1 บทความ"
**Action:** รอ review card ขึ้น → กด Approve
**คาดหวาง:**
- ปุ่ม Approve/Reject หายไป
- สถานะเปลี่ยนเป็น "Approved"
- Agent ถัดไป (ถ้ามี) เริ่มทำงาน

### TC-4.2: Reject agent พร้อม feedback
**Prompt:** "เขียนบทความเกี่ยวกับสุขภาพ 1 บทความ"
**Action:** รอ review card → กด Reject → ใส่ feedback "เขียนสั้นเกินไป ขอให้ละเอียดขึ้น"
**คาดหวาง:**
- ปุ่มหายไป + สถานะเปลี่ยนเป็น "Rejected — Re-running"
- Agent ทำใหม่พร้อม feedback
- Review card ใหม่ขึ้นอีกครั้ง

### TC-4.3: Review card แสดง output เต็ม
**Action:** ตรวจสอบ review card ตอน agent เสร็จ
**คาดหวาง:**
- แสดง output เต็ม ไม่มี "Show more"
- ตัวหนังสือขนาดปกติ (text-sm) ไม่ใช่ text-xs
- ไม่มี max-height จำกัด

---

## 5. ปรับแต่ง Agent (Tuning)

### TC-5.1: Tune personality.tone
**Prompt:** "ปรับโทนของ Content Writer #1 ให้เป็นมิตรและเป็นกันเองมากขึ้น"
**คาดหวาง:**
- AI สร้าง tuning proposal card
- แสดง field: personality.tone, old_value, new_value, reason
- กด Confirm → registry.update_agent → persona เปลี่ยน
- ครั้งต่อไปที่ agent ทำงาน → backstory มี tone ใหม่

### TC-5.2: Tune goal
**Prompt:** "Content Writer #1 ควรมีเป้าหมายในการเขียนบทความที่ดีที่สุดเกี่ยวกับไอที"
**คาดหวาง:**
- tuning proposal: field=goal, new_value="Write the best possible articles about IT"
- กด Confirm → goal เปลี่ยนใน registry
- ครั้งต่อไป → CrewAI Agent.goal เปลี่ยน → งานออกมาเกี่ยวกับ IT

### TC-5.3: Tune tools
**Prompt:** "ให้ Content Writer #1 ใช้ search_web ด้วย เพื่อค้นหาข้อมูลล่าสุดก่อนเขียน"
**คาดหวาง:**
- tuning proposal: field=tools, new_value=["search_web", ...existing]
- กด Confirm → tools เปลี่ยนใน registry
- ครั้งต่อไป → agent ได้รับ search_web tool → ค้นหาข้อมูลก่อนเขียน

### TC-5.4: Tune expertise
**Prompt:** "Content Writer #1 ควรมีความเชี่ยวชาญในด้าน AI และ Machine Learning"
**คาดหวาง:**
- tuning proposal: field=expertise, new_value=["AI", "Machine Learning", ...existing]
- กด Confirm → expertise เปลี่ยน → backstory รวม expertise ใหม่

### TC-5.5: Tune brand_context
**Prompt:** "Content Writer #1 ทำงานให้แบรนด์ TechCorp เขียนให้กลุ่มนักพัฒนามือใหม่"
**คาดหวาง:**
- tuning proposal: brand_context.brand_name + brand_context.target_audience
- กด Confirm → brand_context เปลี่ยน → backstory รวม brand + audience

### TC-5.6: Tune model
**Prompt:** "ให้ Content Writer #1 ใช้ openrouter/auto เป็นโมเดล"
**คาดหวาง:**
- tuning proposal: field=model, new_value="openrouter/auto"
- กด Confirm → model เปลี่ยน → ครั้งต่อไปใช้ model ใหม่

### TC-5.7: Reject tuning
**Prompt:** "ปรับ Content Writer #1 ให้เป็นทางการมากขึ้น"
**Action:** กด Reject tuning
**คาดหวาง:**
- ไม่เปลี่ยนอะไรใน registry
- กลับไป STATE_IDLE

### TC-5.8: Tune หลาย agent พร้อมกัน
**Prompt:** "ปรับทุก agent ในทีมให้ใช้ภาษาอังกฤษทั้งหมด"
**คาดหวาง:**
- tuning proposal หลาย agent แต่ละตัวเปลี่ยน personality.language → "en"
- กด Confirm → ทุก agent เปลี่ยนพร้อมกัน

---

## 6. Context / Conversation Continuity

### TC-6.1: คุยต่อเนื่องใน session
**Prompt 1:** "สร้างทีมนักเขียน 2 คน"
**Action:** Approve
**Prompt 2:** "เพิ่มนักออกแบบ 1 คนด้วย"
**คาดหวาง:**
- AI รู้ว่ามีทีมนักเขียน 2 คนอยู่แล้ว (จาก history)
- สร้าง plan เพิ่มแค่นักออกแบบ ไม่สร้างนักเขียนใหม่

### TC-6.2: สั่งงานต่อจากทีมที่มี
**Prompt 1:** "สร้างทีมนักเขียน 1 คน นักออกแบบ 1 คน" → Approve
**Prompt 2:** "ให้ทีมนี้เขียนบทความเกี่ยวกับ AI พร้อมภาพประกอบ"
**คาดหวาง:**
- AI reuse agent เดิม (ไม่สร้างใหม่)
- สร้าง plan โดยอ้างถึง agent ที่มีอยู่

---

## 7. Manager Quality Review

### TC-7.1: Manager review หลัง agent ทำงานเสร็จ
**Prompt:** "เขียนบทความเกี่ยวกับการตลาด 1 บทความ และทำภาพประกอบ 1 ภาพ"
**Action:** Approve ทุก agent
**คาดหวาง:**
- Manager แสดง progress "Reviewing deliverables"
- Manager output เป็น quality assessment (ไม่ใช่ copy agent output)
- ตรวจสอบ scope, gaps, consistency, alignment
- ถ้าไม่มีปัญหา → "All deliverables verified — no issues found."

---

## 8. Edge Cases

### TC-8.1: Plan mode ไม่ถามคำถาม
**Prompt (Plan mode):** "สร้างบทความและทำภาพประกอบ"
**คาดหวาง:**
- ไม่ถาม "topic อะไร / ความยาวเท่าไหร่ / โทนอะไร"
- สมมติเองและสร้าง plan เลย

### TC-8.2: Chat mode ถามได้ แต่ไม่ถามซ้ำ
**Prompt 1 (Chat mode):** "เขียนบทความ"
**คาดหวาง:** อาจถาม "เกี่ยวกับอะไร"
**Prompt 2:** "เกี่ยวกับ AI"
**คาดหวาง:** ไม่ถามซ้ำ สร้าง plan เลย

### TC-8.3: สั่งงานหลัง task เสร็จ (follow-up)
**Prompt 1:** "เขียนบทความเกี่ยวกับ AI" → Approve → Execute → ดูผลลัพธ์
**Prompt 2:** "เขียนใหม่ให้สั้นกว่าเดิม"
**คาดหวาง:**
- AI เห็น last task result ใน context
- สร้าง plan ที่ refine งานเดิม (ไม่เริ่มใหม่)

---

## Section 9: Product Analyst Agent (Multi-Input Analysis)

โจทย์: สร้าง agent ที่วิเคราะห์สินค้าจากหลายแหล่งข้อมูล (PDF, รูปภาพ, URL) และกรอกข้อมูลใน 4 หัวข้อเพื่อหาจุดขายที่ทรงพลังที่สุด:
1. **จุดแข็งหลักและนวัตกรรม (Core Strengths & Innovation / USP)** — อะไรคือสิ่งที่สินค้านี้ทำได้ แต่คู่แข่งในตลาดที่ราคาถูกกว่าทำไม่ได้?
2. **กลุ่มเป้าหมายและกำลังซื้อ (Targeting & Purchasing Power)** — ใครคือกลุ่มคนที่ยอมจ่ายแพงกว่าเพื่อสเปกที่ดีที่สุด? สินค้านี้เข้าไปอยู่ในนิเวศของอุปกรณ์อะไร?
3. **การเพิ่มมูลค่าเฉลี่ยต่อออเดอร์ (Upselling / Value Bundle Strategy)** — พฤติกรรมผู้ใช้สินค้าประเภทนี้จะต้องการอะไรเพิ่ม? สามารถจัดเซ็ตร่วมกับอะไรเพื่อเพิ่มยอดขายต่อบิล?
4. **การบริหารความเสี่ยงและแนวทางแก้ไข (Risk Management & Operations)** — ปัญหาการใช้งานแบบใดที่ลูกค้ามักโทษสินค้า? จะป้องกันหรือรับประกันอย่างไร?

### TC-9.1: วิเคราะห์สินค้าจากลิงก์ (URL)
**Input:** ลิงก์สินค้า (เช่น https://example.com/product) + prompt สั่งวิเคราะห์ 4 หัวข้อ
**Flow:**
1. User ส่งข้อความพร้อมลิงก์ใน chat
2. ระบบ auto-detect URL → `process_url()` scrape เนื้อหา
3. Manager วางแผนสร้าง agent (มี `scrape_web` tool)
4. Agent อ่านเนื้อหาจากลิงก์ + กรอก 4 หัวข้อ
5. Manager auto-review ผลลัพธ์
**คาดหวัง:**
- ผลลัพธ์มี 4 หัวข้อครบ
- แต่ละหัวข้อตอบคำถามนำทางได้
- เนื้อหามาจากลิงก์จริง (ไม่ hallucinate)

### TC-9.2: วิเคราะห์สินค้าจาก PDF
**Input:** อัปโหลด PDF (เช่น แคตตาล็อกสินค้า) + prompt สั่งวิเคราะห์ 4 หัวข้อ
**Flow:**
1. User อัปโหลด PDF พร้อมส่ง prompt
2. `process_attachment()` สกัด text จาก PDF (ใช้ `pdfplumber` หรือ `crewai_files.PDFFile`)
3. เนื้อหาถูก inject เข้า task ของ agent ผ่าน `attachment_context`
4. Agent กรอก 4 หัวข้อจากเนื้อหา PDF
5. Manager auto-review ผลลัพธ์
**คาดหวัง:**
- ผลลัพธ์มาจากเนื้อหา PDF จริง
- 4 หัวข้อครบ ตอบคำถามนำทางได้

### TC-9.3: วิเคราะห์สินค้าจากรูปภาพ
**Input:** อัปโหลดรูปสินค้า + prompt สั่งวิเคราะห์ 4 หัวข้อ
**Flow:**
1. User อัปโหลดรูปภาพพร้อมส่ง prompt
2. `process_attachment()` ส่งรูปเป็น multimodal content blocks
3. ระบบตั้ง `has_vision_input=True`
4. Plan card แสดงเฉพาะ vision-capable models ให้เลือก
5. Agent ใช้ vision model วิเคราะห์รูป + กรอก 4 หัวข้อ
6. Manager auto-review ผลลัพธ์
**คาดหวัง:**
- Plan card กรอง agent model เฉพาะที่รองรับ vision input
- ผลลัพธ์วิเคราะห์จากรูปได้ (ไม่ใช่ hallucinate)
- 4 หัวข้อครบ

### TC-9.4: วิเคราะห์จากหลายแหล่ง (PDF + URL)
**Input:** อัปโหลด PDF + โยนลิงก์ในข้อความ + prompt สั่งวิเคราะห์ 4 หัวข้อ
**Flow:**
1. ระบบประมวลผลทั้ง PDF (text extraction) และ URL (scrape)
2. ข้อมูลทั้งสองแหล่งถูกรวมใน `attachment_context`
3. Agent ใช้ข้อมูลจากทั้งสองแหล่ง + กรอก 4 หัวข้อ
4. Manager auto-review ผลลัพธ์
**คาดหวัง:**
- ผลลัพธ์อ้างอิงข้อมูลจากทั้ง PDF และ URL
- 4 หัวข้อครบ

### TC-9.5: สั่ง agent เฉพาะเจาะจง (@AgentName)
**Input:** "@Product Analyst วิเคราะห์สินค้าจากลิงก์นี้ [URL] กรอก 4 หัวข้อ"
**Flow:**
1. Manager อ่าน prompt เห็น @AgentName
2. Manager ใช้ agent ที่ mention เท่านั้น (reuse existing)
3. ไม่สร้าง agent ใหม่เพิ่ม
4. Agent ทำงาน + Manager review
**คาดหวัง:**
- Plan card แสดงเฉพาะ agent ที่ mention
- ไม่มี agent อื่นปนเข้ามา
- ผลลัพธ์ 4 หัวข้อครบ

### TC-9.6: Manager auto-review ผลวิเคราะห์
**Input:** ลิงก์สินค้า + prompt 4 หัวข้อ → Agent ทำงานเสร็จ
**Flow:**
1. Manager ตรวจ output ว่ามี 4 หัวข้อครบไหม
2. ถ้าครบ → ส่งสรุปไป storyboard
3. ถ้าไม่ครบ → สั่ง agent แก้ไข
**คาดหวัง:**
- Manager ตรวจโครงสร้าง 4 หัวข้ออัตโนมัติ
- ถ้าไม่ครบ สั่ง retry ได้
- สรุปส่งไป storyboard กระชับ ไม่ใช่ output เต็ม

### TC-9.7: โครงสร้างผลลัพธ์ครบ 4 หัวข้อ
**Input:** ลิงก์หรือ PDF สินค้าใดๆ + prompt 4 หัวข้อ
**คาดหวัง:**
- Output มี 4 หัวข้อชัดเจน:
  1. **จุดแข็งหลักและนวัตกรรม (USP)** — ตอบคำถาม "อะไรที่ทำได้แต่คู่แข่งทำไม่ได้?"
  2. **กลุ่มเป้าหมายและกำลังซื้อ** — ตอบคำถาม "ใครยอมจ่ายแพง? เข้านิเวศอะไร?"
  3. **การเพิ่มมูลค่าต่อออเดอร์ (Upselling)** — ตอบคำถาม "ต้องการอะไรเพิ่ม? จัดเซ็ตร่วมกับอะไร?"
  4. **การบริหารความเสี่ยง** — ตอบคำถาม "ปัญหาอะไรที่ลูกค้าโทษสินค้า? ป้องกันอย่างไร?"
- แต่ละหัวข้อมีคำตอบที่เป็นประโยชน์ ไม่ใช่ generic filler
