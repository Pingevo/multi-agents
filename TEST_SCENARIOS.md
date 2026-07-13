# Test Scenarios — Agent Feedback Tuning

## วิธีทดสอบระบบ

### Scenario 1: สั่งงาน → ดูผล → ให้ feedback → ยืนยัน tuning

**Goal:** ตรวจสอบว่า feedback ผ่าน chat ส่งไปเลขา → เสนอ tuning → ยืนยัน → แก้ agent ได้

**Steps:**
1. Login ด้วย `admin` / `admin123`
2. พิมพ์: `เขียนบทความสั้นๆ 1 ย่อหน้าเกี่ยวกับร้านกาแฟ`
3. รอเลขาวางแผน → กดยืนยันแผน → รอ agent ทำงานเสร็จ
4. อ่านผลลัพธ์ที่ได้
5. พิมพ์ feedback: `เนื้อหาดู AI เกินไป ปรับให้มีความเป็นมนุษย์มากขึ้น`
6. **คาดหวัง:** เลขาแสดง "📝 กำลังวิเคราะห์ feedback..."
7. **คาดหวัง:** ขึ้นการ์ด tuning proposal แสดง:
   - ชื่อ agent ที่จะปรับ
   - Before: ค่าเดิม (เช่น tone = professional)
   - After: ค่าใหม่ (เช่น tone = casual, friendly)
   - เหตุผล: "เนื้อหาดู AI เกินไป → ปรับ tone..."
   - ปุ่ม ยืนยัน / ปฏิเสธ
8. กด **ยืนยัน**
9. **คาดหวัง:** ขึ้นแจ้งเตือน "✅ ปรับแต่ง agent แล้ว — พร้อมใช้งานในครั้งถัดไป"
10. **คาดหวัง:** ไม่มีการรัน task ใหม่อัตโนมัติ (กลับสู่ IDLE)

**ตรวจสอบ:**
- [ ] เลขาเข้าใจว่าเป็น feedback ไม่ใช่คำสั่งใหม่
- [ ] การ์ด tuning โชว์ before/after ชัดเจน
- [ ] กดยืนยันแล้ว agent ถูกแก้ใน registry (ดูใน Agent Panel)
- [ ] ไม่มี auto re-run

---

### Scenario 2: ปฏิเสธ tuning

**Goal:** ตรวจสอบว่าปฏิเสธแล้วไม่มีการแก้อะไร

**Steps:**
1. ทำ Scenario 1 ขั้นตอน 1-7
2. กด **ปฏิเสธ**
3. **คาดหวัง:** ขึ้นแจ้งเตือน "❌ ยกเลิกการปรับแต่ง agent"
4. **คาดหวัง:** Agent ใน registry ไม่เปลี่ยนแปลง

**ตรวจสอบ:**
- [ ] กดปฏิเสธแล้ว agent ไม่ถูกแก้
- [ ] กลับสู่ IDLE พร้อมรับคำสั่งใหม่

---

### Scenario 3: สั่งงานใหม่หลัง tuning → เช็คว่า agent ใช้ persona ใหม่

**Goal:** ตรวจสอบว่า tuning มีผลกับ task ถัดไป

**Steps:**
1. ทำ Scenario 1 จนครบ (ยืนยัน tuning แล้ว)
2. พิมพ์: `เขียนบทความสั้นๆ 1 ย่อหน้าเกี่ยวกับร้านกาแฟอีกครั้ง`
3. รอเลขาวางแผน → กดยืนยัน → รอผล
4. **คาดหวัง:** ผลลัพธ์ครั้งนี้มี tone เป็นมิตร/เป็นมนุษย์มากขึ้น (ตามที่ tune ไว้)

**ตรวจสอบ:**
- [ ] Agent ใช้ persona ใหม่ที่ tune ไว้
- [ ] ผลลัพธ์เปลี่ยนตาม feedback

---

### Scenario 4: Feedback โดยไม่มีงานล่าสุด

**Goal:** ตรวจสอบว่าระบบจัดการกรณีไม่มี last task

**Steps:**
1. เปิดเว็บใหม่ (session ใหม่ ไม่มี last task)
2. พิมพ์: `เนื้อหาดู AI เกินไป`
3. **คาดหวัง:** เลขาตอบเป็น chat ทั่วไป หรือ บอก "ไม่มีงานล่าสุดให้ปรับแต่ง"

**ตรวจสอบ:**
- [ ] ไม่ crash
- [ ] ไม่แสดง tuning proposal (เพราะไม่มีงานล่าสุด)

---

### Scenario 5: คำสั่งใหม่ (ไม่ใช่ feedback) หลัง task เสร็จ

**Goal:** ตรวจสอบว่าเลขาแยก feedback กับคำสั่งใหม่ได้

**Steps:**
1. ทำงานเสร็จ 1 ชิ้น
2. พิมพ์: `สร้าง content plan สำหรับร้านอาหาร`
3. **คาดหวัง:** เลขาวางแผนใหม่ (action = plan) ไม่ใช่ feedback

**ตรวจสอบ:**
- [ ] เลขาเข้าใจว่าเป็นคำสั่งใหม่ ไม่ใช่ feedback
- [ ] ขึ้นแผนงานใหม่ปกติ

---

### Scenario 6: Feedback เป็นภาษาอังกฤษ

**Goal:** ตรวจสอบว่ารองรับ feedback หลายภาษา

**Steps:**
1. ทำงานเสร็จ 1 ชิ้น
2. พิมพ์: `make it shorter and more casual`
3. **คาดหวัง:** เลขาเข้าใจเป็น feedback
4. **คาดหวัง:** tuning proposal แสดงเหตุผลเป็นภาษาอังกฤษ

**ตรวจสอบ:**
- [ ] รองรับ feedback ภาษาอังกฤษ
- [ ] เหตุผลในการ tuning ใช้ภาษาเดียวกับ feedback

---

### Scenario 7: ตรวจสอบ learnings ถูกเก็บ

**Goal:** ตรวจสอบว่า feedback ถูกเก็บเป็น learning ของ agent

**Steps:**
1. ทำ Scenario 1 จนครบ
2. รันคำสั่งใน terminal:
```bash
cd /Users/its-dev2/my-agent-app
source venv/bin/activate
python3 -c "
import json
with open('agent_registry.json') as f:
    agents = json.load(f)
for a in agents:
    learnings = a.get('learnings', [])
    print(f'{a[\"name\"]}: {len(learnings)} learnings')
    for l in learnings[-3:]:
        print(f'  - [{l.get(\"type\",\"')}] {l.get(\"lesson\",\"\")[:80]}')
"
```
3. **คาดหวัง:** มี learning ชนิด `user_feedback` และ `task_completion`

**ตรวจสอบ:**
- [ ] feedback ถูกเก็บเป็น learning
- [ ] task_completion ถูกเก็บอัตโนมัติ
- [ ] learnings ไม่เกิน 10 entries per agent
