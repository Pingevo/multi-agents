"""Agent templates — predefined agent configurations with runtime contracts."""

AGENT_TEMPLATES: list[dict] = [
    {
        "id": "product_analysis",
        "label": "วิเคราะห์สินค้า",
        "description": "วิเคราะห์สินค้าที่ user ระบุ พร้อมค้นหาคู่แข่งและข้อมูลจริง",
        "spec": {
            "name": "Product Analyst",
            "role": "Product Analyst",
            "goal": "วิเคราะห์สินค้าตามข้อมูลที่ได้รับ และค้นหาข้อมูลเพิ่มเติมเพื่อเปรียบเทียบกับคู่แข่งในตลาด โดยอ้างอิงแหล่งข้อมูลที่ตรวจสอบได้จริง",
            "persona": (
                "You are a senior product analyst with deep expertise in competitive analysis, "
                "market positioning, and product strategy. You research products thoroughly, "
                "verify claims with real sources, and never fabricate data. "
                "You communicate findings in structured Thai-language reports. "
                "You are rigorous about evidence — if you cannot verify a claim, you say so explicitly."
            ),
            "tools": ["analyze_image"],
            "model": "",
        },
    },
]

TEMPLATES_BY_ID: dict[str, dict] = {t["id"]: t for t in AGENT_TEMPLATES}


def get_template(template_id: str) -> dict | None:
    return TEMPLATES_BY_ID.get(template_id)


def get_template_spec(template_id: str) -> dict | None:
    tmpl = TEMPLATES_BY_ID.get(template_id)
    if tmpl:
        return tmpl["spec"]
    return None


def list_templates() -> list[dict]:
    return AGENT_TEMPLATES


# ── Runtime contract for product_analysis template ──

PRODUCT_ANALYSIS_CONTRACT = """\
=== PRODUCT ANALYSIS CONTRACT — FOLLOW EXACTLY ===

You are performing a product analysis. The user's prompt and any attached files contain the product information.
If the user provided only a product name, you MUST research it using your built-in web search capability before analyzing.
If the user provided files (datasheets, images, descriptions), use that information as your primary source
and supplement with web research for competitor/market context.

## EVIDENCE RULES (CRITICAL)
- You MUST NOT invent product names, brand names, prices, specifications, or competitor claims.
- Every named competitor or material claim MUST include a source URL.
- If you cannot find a reliable source for a claim, write **"ตรวจสอบไม่ได้จากแหล่งข้อมูลที่พบ"** instead of guessing.
- Use your built-in web search to find information, then use web fetch to read and verify the sources you cite.
- Distinguish between information from the user's files and information from web research.

## OUTPUT FORMAT (MANDATORY — use exactly these 4 numbered headings in Thai)

1. **จุดแข็งหลักและนวัตกรรม (Core Strengths & Innovation / USP)**
   * คำถามนำทาง: อะไรคือสิ่งที่สินค้านี้ทำได้ แต่คู่แข่งในตลาดที่ราคาถูกกว่าทำไม่ได้? (เช่น การประหยัดเวลา, ความปลอดภัยที่สูงกว่า, ฟังก์ชัน Hybrid สองในหนึ่งเดียว)
   — ต้องอ้างชื่อสินค้าคู่แข่งจริงที่พบจากการค้นหา พร้อม URL หลักฐาน หากไม่พบข้อมูลให้ระบุชัดเจน

2. **กลุ่มเป้าหมายและกำลังซื้อ (Targeting & Purchasing Power)**
   * คำถามนำทาง: ใครคือกลุ่มคนที่ยอมจ่ายแพงกว่าเพื่อสเปกที่ดีที่สุด? สินค้านี้เข้าไปอยู่ในนิเวศ (Ecosystem) ของอุปกรณ์อะไรของพวกเขา (เช่น ผู้ใช้ Flagship, คนจัดโต๊ะคอม, กลุ่มผู้ผลิตคอนเทนต์)

3. **การเพิ่มมูลค่าเฉลี่ยต่อออเดอร์ (Upselling / Value Bundle Strategy)**
   * คำถามนำทาง: พฤติกรรมผู้ใช้สินค้าประเภทนี้ จะต้องการอะไรเพิ่มเติมอีกไหม? สามารถจัดเซ็ตร่วมกับอะไรเพื่อเพิ่มยอดขายต่อบิลได้บ้าง (เช่น ตัวเลือกเพิ่มอะไหน่แยก, เซ็ตคู่หูเปิดกล่องพร้อมใช้)

4. **การบริหารความเสี่ยงและแนวทางแก้ไข (Risk Management & Operations)**
   * คำถามนำทาง: ปัญหาการใช้งานแบบใดที่เกิดจากพฤติกรรมลูกค้าแต่ลูกค้ามักโทษสินค้า? (เช่น ความสะอาด, ความร้อน, คราบสกปรก) และเราจะป้องกันหรือรับประกันอย่างไรเพื่อเซฟฝั่งผู้ขาย

---

หลังจาก 4 หัวข้อข้างต้น ให้ลงท้ายด้วย:

**แหล่งข้อมูลที่ตรวจสอบแล้ว**
- แหล่งจากไฟล์/ข้อมูลผู้ใช้: (ระบุไฟล์หรือข้อมูลที่ผู้ใช้ให้มา)
- แหล่งจากเว็บ: (ระบุ URL ทั้งหมดที่ใช้ พร้อมคำอธิบายสั้นๆ ว่าดึงข้อมูลอะไรจากแต่ละ URL)

=== END CONTRACT ===
"""

TEMPLATE_CONTRACTS: dict[str, str] = {
    "product_analysis": PRODUCT_ANALYSIS_CONTRACT,
}


def get_template_contract(template_id: str) -> str | None:
    return TEMPLATE_CONTRACTS.get(template_id)


# ── Deterministic output validation (code-level, not LLM) ──

PRODUCT_ANALYSIS_REQUIRED_HEADINGS = [
    "จุดแข็งหลักและนวัตกรรม",
    "Core Strengths",
    "USP",
]
HEADING_2_MARKERS = ["กลุ่มเป้าหมายและกำลังซื้อ", "Targeting", "Purchasing Power"]
HEADING_3_MARKERS = ["การเพิ่มมูลค่าเฉลี่ยต่อออเดอร์", "Upselling", "Value Bundle"]
HEADING_4_MARKERS = ["การบริหารความเสี่ยงและแนวทางแก้ไข", "Risk Management", "Operations"]

ALL_HEADING_GROUPS = [
    ("หัวข้อ 1: จุดแข็งหลักและนวัตกรรม", PRODUCT_ANALYSIS_REQUIRED_HEADINGS),
    ("หัวข้อ 2: กลุ่มเป้าหมายและกำลังซื้อ", HEADING_2_MARKERS),
    ("หัวข้อ 3: การเพิ่มมูลค่าเฉลี่ยต่อออเดอร์", HEADING_3_MARKERS),
    ("หัวข้อ 4: การบริหารความเสี่ยงและแนวทางแก้ไข", HEADING_4_MARKERS),
]


def validate_template_output(template_id: str, output: str) -> dict | None:
    """Validate agent output against template requirements.
    
    Returns None if output passes validation, or a dict with:
      - "approved": False
      - "feedback": specific feedback string for retry
      - "summary": short summary
    """
    if template_id == "product_analysis":
        return _validate_product_analysis(output)
    return None


def _validate_product_analysis(output: str) -> dict | None:
    """Check that product analysis output has all 4 headings and source URLs."""
    issues = []
    output_lower = output.lower() if output else ""
    
    # Check each heading group — at least one marker must be present
    for label, markers in ALL_HEADING_GROUPS:
        found = any(m.lower() in output_lower for m in markers)
        if not found:
            issues.append(f"ขาด {label} — ต้องมีหัวข้อนี้ในผลลัพธ์ทุกครั้ง")
    
    # Check for source URLs section
    has_sources = (
        "แหล่งข้อมูล" in output or
        "source" in output_lower or
        "http" in output_lower
    )
    if not has_sources:
        issues.append("ขาดส่วน 'แหล่งข้อมูลที่ตรวจสอบแล้ว' — ต้องมี URL หรือระบุแหล่งข้อมูล")
    
    # Check for evidence rule compliance — should not have "ตรวจสอบไม่ได้" OR have URLs
    # (either is acceptable — the point is the agent didn't silently skip evidence)
    
    if issues:
        feedback = (
            "ผลลัพธ์ไม่ผ่านเกณฑ์ Product Analysis Contract:\n"
            + "\n".join(f"  - {issue}" for issue in issues)
            + "\n\nกรุณาแก้ไขและส่งใหม่ ต้องมีครบทั้ง 4 หัวข้อตามรูปแบบที่กำหนด "
            "และมีส่วน 'แหล่งข้อมูลที่ตรวจสอบแล้ว' ท้ายเอกสารเสมอ"
        )
        return {
            "approved": False,
            "feedback": feedback,
            "summary": f"ไม่ผ่าน — ขาด {len(issues)} ข้อ ({', '.join(issues[:2])})",
        }
    
    return None

