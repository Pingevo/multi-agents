// Agent Dispatch Mockup — all rendering logic

let selectedAgent = null;
let currentTab = 'chat';

// ===== TOP BAR =====
function renderTopBar() {
  return `
    <div class="tb-logo"><div class="logo-ic">⚡</div><div>AGENT<span>DISPATCH</span></div></div>
    <div class="tb-divider"></div>
    <div class="tb-status"><div class="dot"></div> Online · 5 Agents Ready</div>
    <div class="tb-divider"></div>
    <div class="tb-credits">💰 $4.82 / $10.00</div>
    <div class="tb-spacer"></div>
    <button class="tb-btn" onclick="openModal('history')">📋 Task History</button>
    <button class="tb-btn" onclick="openModal('config')">⚙️ Agent Config</button>
    <button class="tb-btn">📅 Schedule</button>
    <div class="tb-avatar">U</div>`;
}

// ===== LEFT PANEL =====
function renderLeftPanel() {
  return `
    <div class="lp-header"><div class="lp-title">⚡ Dispatch Queue</div><div class="lp-count">7</div></div>
    <div class="lp-list">
      <div class="lp-section">🔴 Urgent — Needs Action</div>
      <div class="job-card urgent active" onclick="selectJob(this)"><div class="job-title">อนุมัติภาพสินค้า</div><div class="job-meta"><span class="jtype jtype-approval">Approval</span><span class="job-time">2m</span></div></div>
      <div class="job-card urgent" onclick="selectJob(this)"><div class="job-title">รอตรวจสอบ Product Analyst</div><div class="job-meta"><span class="jtype jtype-review">Review</span><span class="job-time">5m</span></div></div>
      <div class="job-card urgent" onclick="selectJob(this)"><div class="job-title">ปรับ model Copywriter</div><div class="job-meta"><span class="jtype jtype-tuning">Tuning</span><span class="job-time">10m</span></div></div>
      <div class="lp-section">🟡 In Progress</div>
      <div class="job-card running" onclick="selectJob(this)"><div class="job-title">วิเคราะห์สินค้า Shopee</div><div class="job-meta"><span class="jtype jtype-result">Running</span><span>50%</span><span class="job-time">15m</span></div></div>
      <div class="job-card running" onclick="selectJob(this)"><div class="job-title">สร้างคอนเทนต์ประจำวัน</div><div class="job-meta"><span class="jtype jtype-result">Running</span><span>65%</span><span class="job-time">20m</span></div></div>
      <div class="lp-section">🟢 Completed</div>
      <div class="job-card done" onclick="selectJob(this)"><div class="job-title">แคมเปญ Flash Sale</div><div class="job-meta"><span class="jtype jtype-result">Done</span><span class="job-time">1h</span></div></div>
      <div class="lp-section">🔵 Scheduled</div>
      <div class="job-card scheduled" onclick="selectJob(this)"><div class="job-title">วิเคราะห์ตลาดประจำวัน</div><div class="job-meta"><span class="jtype jtype-scheduled">08:00</span><span>Daily</span></div></div>
      <div class="job-card scheduled" onclick="selectJob(this)"><div class="job-title">สรุปยอดขาย</div><div class="job-meta"><span class="jtype jtype-scheduled">17:00</span><span>Daily</span></div></div>
    </div>`;
}

// ===== CENTER — CHAT VIEW =====
function renderChatView() {
  return `
    <div class="center-tabs">
      <div class="ct-tab active" onclick="switchTab('chat')">💬 Chat</div>
      <div class="ct-tab" onclick="switchTab('flow')">🔀 Flow</div>
      <div class="ct-spacer"></div>
      <div class="ct-team-sel">👥 Marketing Team ▾</div>
    </div>
    <div class="chat-view" id="view-chat">
      <div class="msg user"><div class="msg-av" style="background:var(--red)">U</div><div class="msg-body"><div class="msg-name">You</div><div class="msg-bubble">วิเคราะห์ภาพสินค้านี้ให้หน่อย และบอกจุดแข็งที่ควรนำไปทำการตลาด<br><img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='120' fill='%23ddd'%3E%3Crect width='200' height='120' rx='4'/%3E%3Ctext x='50%25' y='50%25' fill='%23666' font-size='12' text-anchor='middle' dy='.3em'%3EProduct Image%3C/text%3E%3C/svg%3E" alt="product"></div></div></div>
      <div class="msg thinking"><div class="msg-av" style="background:rgba(230,57,70,.15)">🧠</div><div class="msg-body"><div class="msg-name">Manager <span class="msg-role">Planning</span></div><div class="msg-bubble"><div class="dots"><span></span><span></span><span></span></div><span class="think-dur">3s</span></div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(230,57,70,.15)">🧠</div><div class="msg-body"><div class="msg-name">Manager <span class="msg-role">Project Manager</span></div><div class="msg-bubble">นี่คือแผนที่ฉันคิดไว้ ลองดูแล้วกดยืนยันได้เลยครับ
        <div class="card plan"><div class="card-hdr"><span class="ch-ic">📋</span> Dispatch Plan <span class="ch-badge" style="background:rgba(230,57,70,.15);color:var(--red)">4 AGENTS · 2 WAVES</span></div><div class="card-body">วิเคราะห์ภาพสินค้าและหาจุดแข็งเพื่อนำไปทำการตลาด
          <div class="plan-agents">
            <div class="plan-agent"><div class="pa-av" style="background:rgba(72,149,239,.15)">📊</div><div class="pa-info"><div class="pa-name">Product Analyst</div><div class="pa-role">วิเคราะห์สินค้า</div></div><span class="pa-tag new">NEW</span></div>
            <div class="plan-agent"><div class="pa-av" style="background:rgba(244,162,97,.15)">✍️</div><div class="pa-info"><div class="pa-name">Copywriter</div><div class="pa-role">เขียนคอนเทนต์</div></div><span class="pa-tag new">NEW</span></div>
            <div class="plan-agent"><div class="pa-av" style="background:rgba(157,78,221,.15)">🎨</div><div class="pa-info"><div class="pa-name">Image Generator</div><div class="pa-role">สร้างภาพ</div></div><span class="pa-tag new">NEW</span></div>
            <div class="plan-agent"><div class="pa-av" style="background:rgba(42,157,143,.15)">🔍</div><div class="pa-info"><div class="pa-name">SEO Specialist</div><div class="pa-role">วิเคราะห์ SEO</div></div><span class="pa-tag exist">EXISTING</span></div>
          </div>
          <div class="plan-models"><span class="plan-model">Manager: auto-router</span><span class="plan-model">Image: dall-e-3</span><span class="plan-model">Search: auto</span></div>
        </div><div class="card-footer"><button class="btn btn-approve">✓ Dispatch</button><button class="btn btn-reject">✕ Reject</button></div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(244,162,97,.15)">⚡</div><div class="msg-body"><div class="msg-name">System <span class="msg-role">Status</span></div><div class="msg-bubble">ทีมกำลังปฏิบัติงาน...
        <div class="card progress"><div class="card-hdr"><span class="ch-ic">⏳</span> In Progress <span class="ch-badge" style="background:rgba(244,162,97,.15);color:var(--amber)">50%</span></div><div class="card-body">
          <div class="prog-bar"><div class="prog-fill" style="width:50%"></div></div>
          <div class="prog-agents">
            <div class="prog-agent"><span class="pa-dot ok"></span><span>Product Analyst</span><span class="pa-stat">✓ เสร็จ</span></div>
            <div class="prog-agent"><span class="pa-dot run"></span><span>Copywriter</span><span class="pa-stat">65% · กำลังเขียน</span></div>
            <div class="prog-agent"><span class="pa-dot wt"></span><span>Image Generator</span><span class="pa-stat">รออนุมัติภาพ</span></div>
            <div class="prog-agent"><span class="pa-dot idle"></span><span>SEO Specialist</span><span class="pa-stat">รอ</span></div>
          </div>
        </div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(157,78,221,.15)">🎨</div><div class="msg-body"><div class="msg-name">Image Generator <span class="msg-role">สร้างภาพ</span></div><div class="msg-bubble">สร้างภาพเสร็จแล้ว รบกวนอนุมัติด้วยครับ
        <div class="card img-approve"><div class="card-hdr"><span class="ch-ic">🖼️</span> Image Approval <span class="ch-badge" style="background:rgba(230,57,70,.15);color:var(--red)">PENDING</span></div><div class="card-body">
          <div class="img-prompt">"สินค้าพรีเมียมบนโต๊ะไม้ แสงอบอุ่น มุม 45 องศา"</div>
          <div class="img-model-sel">🎨 dall-e-3 ▾</div>
        </div><div class="card-footer"><button class="btn btn-approve">🖼️ Generate</button><button class="btn btn-reject">❌ Cancel</button></div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(157,78,221,.15)">🎨</div><div class="msg-body"><div class="msg-name">Image Generator</div><div class="msg-bubble">ภาพที่สร้างเสร็จแล้วครับ
        <div class="img-result"><img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='200' fill='%23333'%3E%3Crect width='300' height='200'/%3E%3Ctext x='50%25' y='50%25' fill='%23888' font-size='14' text-anchor='middle' dy='.3em'%3EGenerated Image%3C/text%3E%3C/svg%3E" alt="gen"><div class="ir-info">"สินค้าพรีเมียมบนโต๊ะไม้ แสงอบอุ่น"</div><div class="ir-actions"><button class="btn btn-neutral">✏️ Edit Prompt</button><button class="btn btn-neutral">🔄 Regenerate</button></div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(72,149,239,.15)">🧠</div><div class="msg-body"><div class="msg-name">Manager <span class="msg-role">Review</span></div><div class="msg-bubble">รบกวนตรวจสอบงานของ Product Analyst ด้วยครับ
        <div class="card review"><div class="card-hdr"><span class="ch-ic">🧠</span> Agent Review <span class="ch-badge" style="background:rgba(72,149,239,.15);color:var(--blue)">Product Analyst</span></div><div class="card-body">
          <div class="review-output">สินค้ามีจุดเด่นที่ดีไซน์ทันสมัย วัสดุพรีเมียม และฟังก์ชันพิเศษที่คู่แข่งยังไม่มี แนะนำให้เน้นจุดขาย 3 ด้าน: ดีไซน์, คุณภาพ, นวัตกรรม</div>
          <div class="review-feedback"><textarea placeholder="feedback หากต้องการให้แก้ไข..."></textarea></div>
        </div><div class="card-footer"><button class="btn btn-approve">✓ Approve</button><button class="btn btn-reject">✕ Send Back</button></div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(42,157,143,.15)">🤖</div><div class="msg-body"><div class="msg-name">Manager <span class="msg-role">Summary</span></div><div class="msg-bubble">ทุก agent ทำงานเสร็จแล้ว นี่คือสรุปครับ
        <div class="card result"><div class="card-hdr"><span class="ch-ic">✓</span> Mission Complete <span class="ch-badge" style="background:rgba(42,157,143,.15);color:var(--green)">2 AGENTS</span></div><div class="card-body">
          <div class="result-summary">วิเคราะห์ภาพสินค้าเสร็จ พบจุดแข็ง 3 ด้าน พร้อมแนวทางการตลาด</div>
          <div class="result-agents">
            <div class="result-agent"><div class="ra-hdr" onclick="toggleRA(this)"><div class="ra-av" style="background:rgba(72,149,239,.15)">📊</div><span>Product Analyst</span><span class="ra-toggle">▼</span></div><div class="ra-body">สินค้ามีดีไซน์โดดเด่น ใช้วัสดุคุณภาพสูง มีฟังก์ชัน 2-in-1 ที่คู่แข่งยังไม่มี กลุ่มเป้าหมายหลักคือคนรักการออกแบบ อายุ 25-40 ปี</div></div>
            <div class="result-agent"><div class="ra-hdr" onclick="toggleRA(this)"><div class="ra-av" style="background:rgba(244,162,97,.15)">✍️</div><span>Copywriter</span><span class="ra-toggle">▼</span></div><div class="ra-body">แนะนำแคมเปญ "ดีไซน์ที่เกินคาด" เน้นฟังก์ชันพิเศษ ใช้โทนพรีเมียมแต่เข้าถึงง่าย พร้อมแคปชันสำหรับโซเชียล 3 แพลตฟอร์ม</div></div>
          </div>
        </div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(157,78,221,.15)">🤖</div><div class="msg-body"><div class="msg-name">Manager <span class="msg-role">Tuning</span></div><div class="msg-bubble">แนะนำให้ปรับ model เพื่อผลลัพธ์ที่ดีขึ้น
        <div class="card tuning"><div class="card-hdr"><span class="ch-ic">📝</span> Agent Tuning</div><div class="card-body">
          <div class="tuning-item"><div class="ti-agent">Copywriter</div><div class="ti-change"><span class="ti-old">gpt-4o</span><span class="ti-arrow">→</span><span class="ti-new">claude-3.5-sonnet</span></div><div class="ti-reason">เหมาะกับการเขียนคอนเทนต์ภาษาไทยมากกว่า</div></div>
        </div><div class="card-footer"><button class="btn btn-approve">ยืนยัน</button><button class="btn btn-reject">ปฏิเสธ</button></div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(42,157,143,.15)">🔊</div><div class="msg-body"><div class="msg-name">Copywriter <span class="msg-role">TTS</span></div><div class="msg-bubble">ไฟล์เสียงสำหรับโฆษณาครับ
        <div class="media-result"><div class="mr-hdr">🔊 Audio Result</div><div class="mr-body"><audio controls src="" style="width:100%;height:32px"></audio></div><div class="mr-info"><span>Agent: Copywriter</span><span>Model: tts-1</span></div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(157,78,221,.15)">🎬</div><div class="msg-body"><div class="msg-name">Image Generator <span class="msg-role">Video</span></div><div class="msg-bubble">วิดีโอโฆษณา 5 วินาทีครับ
        <div class="media-result"><div class="mr-hdr">🎬 Video Result</div><div class="mr-body"><video controls src="" style="width:100%;border-radius:4px"></video></div><div class="mr-info"><span>Agent: Image Gen</span><span>Model: sora</span><span>5s</span></div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(244,162,97,.15)">📄</div><div class="msg-body"><div class="msg-name">SEO Specialist</div><div class="msg-bubble">รายงาน SEO พร้อมดาวน์โหลด
        <div class="media-result"><div class="mr-hdr">📄 File Result</div><div class="mr-file"><div class="mr-file-ic">📄</div><div><div class="mr-file-n">seo-report.pdf</div><div class="mr-file-t">PDF · 2.3MB</div></div></div><div class="mr-info"><span>Agent: SEO Specialist</span></div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(6,214,160,.15)">🎤</div><div class="msg-body"><div class="msg-name">SEO Specialist <span class="msg-role">STT</span></div><div class="msg-bubble">ถอดเสียงจากคลิปสินค้าเรียบร้อย
        <div class="media-result"><div class="mr-hdr">🎤 Transcription</div><div class="mr-body" style="font-size:11px;color:var(--txt2);line-height:1.5">"สวัสดีครับ วันนี้ผมจะมาแนะนำสินค้าใหม่ของเรา ที่มีดีไซน์ทันสมัยและฟังก์ชันที่ครบครัน..."</div><div class="mr-info"><span>Agent: SEO</span><span>Model: whisper-1</span></div></div>
      </div></div></div>
      <div class="msg"><div class="msg-av" style="background:rgba(230,57,70,.15)">🤖</div><div class="msg-body"><div class="msg-name">Manager</div><div class="msg-bubble">มีอะไรให้ช่วยอีกไหมครับ? พิมพ์คำสั่งใหม่ได้เลย</div></div></div>
    </div>`;
}

// ===== CENTER — FLOW VIEW =====
function renderFlowView() {
  return `
    <div class="center-tabs">
      <div class="ct-tab" onclick="switchTab('chat')">💬 Chat</div>
      <div class="ct-tab active" onclick="switchTab('flow')">🔀 Flow</div>
      <div class="ct-spacer"></div>
      <div class="ct-team-sel">👥 Marketing Team ▾</div>
    </div>
    <div class="flow-view">
      <div class="flow-task"><div class="ft-label">⚡ Active Mission</div><div class="ft-title">วิเคราะห์สินค้า Shopee</div></div>
      <div class="flow-wave-label">Wave 1 — Analysis</div>
      <div class="flow-nodes">
        <div class="flow-node done" onclick="selectAgentByNode('Product Analyst')"><div class="fn-av" style="background:rgba(72,149,239,.15)">📊</div><div class="fn-name">Product Analyst</div><div class="fn-role">วิเคราะห์สินค้า</div><div class="fn-status done">✓ Done</div><div class="fn-prog"><div class="fn-prog-f" style="width:100%;background:var(--green)"></div></div></div>
        <div class="flow-node review" onclick="selectAgentByNode('SEO Specialist')"><div class="fn-av" style="background:rgba(42,157,143,.15)">🔍</div><div class="fn-name">SEO Specialist</div><div class="fn-role">วิเคราะห์ SEO</div><div class="fn-status review">🧠 Review</div><div class="fn-prog"><div class="fn-prog-f" style="width:100%;background:var(--blue)"></div></div></div>
      </div>
      <div class="flow-connector active"></div>
      <div class="flow-wave-label">Wave 2 — Content Creation</div>
      <div class="flow-nodes">
        <div class="flow-node running" onclick="selectAgentByNode('Copywriter')"><div class="fn-av" style="background:rgba(244,162,97,.15)">✍️</div><div class="fn-name">Copywriter</div><div class="fn-role">เขียนคอนเทนต์</div><div class="fn-status running">⏳ 65%</div><div class="fn-prog"><div class="fn-prog-f" style="width:65%"></div></div></div>
        <div class="flow-node pending" onclick="selectAgentByNode('Image Generator')"><div class="fn-av" style="background:rgba(157,78,221,.15)">🎨</div><div class="fn-name">Image Generator</div><div class="fn-role">สร้างภาพ</div><div class="fn-status pending">⏸ Pending</div><div class="fn-prog"><div class="fn-prog-f" style="width:0%"></div></div></div>
      </div>
      <div class="flow-connector"></div>
      <div class="flow-wave-label">Synthesis</div>
      <div class="flow-nodes">
        <div class="flow-node pending" onclick="selectAgentByNode('Manager')"><div class="fn-av" style="background:rgba(230,57,70,.15)">🧠</div><div class="fn-name">Manager</div><div class="fn-role">Project Manager</div><div class="fn-status pending">⏸ Waiting</div><div class="fn-prog"><div class="fn-prog-f" style="width:0%"></div></div></div>
      </div>
    </div>`;
}

// ===== RIGHT PANEL =====
function renderRightPanel() {
  if (!selectedAgent) {
    return `<div class="rp-empty"><div class="rp-ic">👤</div><div>เลือก Agent เพื่อดูรายละเอียด</div><div style="font-size:9px;opacity:.5">คลิกการ์ดด้านล่างหรือ node ใน Flow</div></div>`;
  }
  const agents = {
    'Product Analyst': {ic:'📊',bg:'rgba(72,149,239,.15)',role:'วิเคราะห์สินค้าและตลาด',status:'done',statusText:'✓ Idle',goal:'วิเคราะห์ภาพสินค้า หาจุดแข็ง กลุ่มเป้าหมาย และแนวทางการตลาด',persona:'นักวิเคราะห์ตลาดมืออาชีพ มองข้อมูลเป็นตัวเลขและแนวโน้ม',tools:['🔍 search','👁️ vision'],model:'gpt-4o',prog:100},
    'Copywriter': {ic:'✍️',bg:'rgba(244,162,97,.15)',role:'เขียนคอนเทนต์',status:'running',statusText:'● Running · 65%',goal:'เขียนแคปชันและคอนเทนต์สำหรับโซเชียลมีเดีย 3 แพลตฟอร์ม',persona:'นักเขียนสร้างสรรค์ เน้นการเล่าเรื่องที่ดึงดูดอารมณ์',tools:['✍️ write'],model:'gpt-4o',prog:65},
    'Image Generator': {ic:'🎨',bg:'rgba(157,78,221,.15)',role:'สร้างภาพและวิดีโอ',status:'pending',statusText:'⏸ Pending Approval',goal:'สร้างภาพสินค้าพรีเมียมตาม prompt ที่อนุมัติ',persona:'ศิลปินดิจิทัล สนใจ composition และแสง',tools:['🎨 generate_image','🎬 generate_video'],model:'dall-e-3',prog:0},
    'SEO Specialist': {ic:'🔍',bg:'rgba(42,157,143,.15)',role:'วิเคราะห์ SEO',status:'review',statusText:'🧠 Under Review',goal:'วิเคราะห์ SEO ของสินค้าและคู่แข่ง แนะนำ keywords',persona:'ผู้เชี่ยวชาญ SEO มองข้อมูลเป็น ranking และ traffic',tools:['🔍 search_web','📊 analyze'],model:'auto-router',prog:100},
    'Manager': {ic:'🧠',bg:'rgba(230,57,70,.15)',role:'Project Manager',status:'pending',statusText:'⏸ Waiting',goal:'ประสานงานทีม วางแผน ตรวจสอบผล และสรุปผลลัพธ์',persona:'ผู้จัดการโปรเจกต์ มองภาพรวม ตัดสินใจเชิงกลยุทธ์',tools:['🧠 orchestrate','📝 review'],model:'auto-router',prog:0},
  };
  const a = agents[selectedAgent];
  if (!a) return renderRightPanel();
  const statusColor = a.status==='done'?'var(--green)':a.status==='running'?'var(--amber)':a.status==='review'?'var(--blue)':'var(--txt3)';
  return `
    <div class="rp-detail show">
      <div class="rp-hdr">
        <div class="rp-av" style="background:${a.bg}">${a.ic}</div>
        <div class="rp-name">${selectedAgent}</div>
        <div class="rp-role">${a.role}</div>
        <div class="rp-status" style="background:${a.status==='done'?'rgba(42,157,143,.15)':a.status==='running'?'rgba(244,162,97,.15)':a.status==='review'?'rgba(72,149,239,.15)':'var(--panel2)'};color:${statusColor}">${a.statusText}</div>
      </div>
      <div class="rp-sec"><div class="rp-lbl">⚡ Progress</div><div class="rp-prog-bar"><div class="rp-prog-f" style="width:${a.prog}%;background:${a.status==='done'?'var(--green)':a.status==='review'?'var(--blue)':'var(--amber)'}"></div></div><div class="rp-val" style="font-size:9px">${a.prog}%</div></div>
      <div class="rp-sec"><div class="rp-lbl">🎯 Goal</div><div class="rp-val">${a.goal}</div></div>
      <div class="rp-sec"><div class="rp-lbl">🎭 Persona</div><div class="rp-val">${a.persona}</div></div>
      <div class="rp-sec"><div class="rp-lbl">🛠️ Tools</div><div class="rp-tools">${a.tools.map(t=>`<span class="rp-tool">${t}</span>`).join('')}</div></div>
      <div class="rp-sec"><div class="rp-lbl">🤖 Model</div><div class="rp-val" style="color:var(--amber);font-weight:600">${a.model}</div></div>
      <div class="rp-actions">
        <button class="rp-btn assign" onclick="openModal('config')">🚀 Assign</button>
        <button class="rp-btn edit" onclick="openModal('config')">✏️ Edit</button>
        <button class="rp-btn del">🗑️</button>
      </div>
    </div>`;
}

// ===== ROSTER =====
function renderRoster() {
  const agents = [
    {name:'Manager',ic:'🧠',bg:'rgba(230,57,70,.15)',stat:'Idle'},
    {name:'Product Analyst',ic:'📊',bg:'rgba(72,149,239,.15)',stat:'Idle'},
    {name:'Copywriter',ic:'✍️',bg:'rgba(244,162,97,.15)',stat:'Running',running:true},
    {name:'Image Generator',ic:'🎨',bg:'rgba(157,78,221,.15)',stat:'Pending'},
    {name:'SEO Specialist',ic:'🔍',bg:'rgba(42,157,143,.15)',stat:'Review'},
  ];
  return `<div class="roster-lbl">ROSTER</div>` +
    agents.map(a => `
      <div class="agent-card ${a.running?'running':''} ${selectedAgent===a.name?'selected':''}" onclick="selectAgent('${a.name}')">
        <div class="ac-av" style="background:${a.bg}">${a.ic}</div>
        <div class="ac-name">${a.name}</div>
        <div class="ac-stat">${a.stat}</div>
      </div>`).join('') +
    `<div class="agent-card add" onclick="openModal('config')">+</div>`;
}

// ===== INPUT BAR =====
function renderInputBar() {
  return `
    <div class="ib-top">
      <div class="ib-model">⚡ <span>Auto Router</span> <span style="font-size:8px;color:var(--green)">AUTO</span></div>
      <div class="ib-mode"><button class="ib-mode-btn">💬 Chat</button><button class="ib-mode-btn active">✨ Plan</button></div>
    </div>
    <div class="ib-row">
      <button class="ib-plus">+</button>
      <textarea class="ib-input" placeholder="พิมพ์คำสั่งถึงทีม..." rows="1"></textarea>
      <button class="ib-send">➤</button>
    </div>`;
}

// ===== MODALS =====
function renderModal(type) {
  if (type === 'config') {
    return `
      <div class="modal">
        <div class="modal-hdr"><div class="modal-title">⚙️ Agent Configuration</div><div class="modal-close" onclick="closeModal()">✕</div></div>
        <div class="modal-body">
          <div class="cfg-section"><div class="cfg-lbl">Name</div><input class="cfg-input" value="Product Analyst"></div>
          <div class="cfg-section"><div class="cfg-lbl">Role</div><input class="cfg-input" value="วิเคราะห์สินค้าและตลาด"></div>
          <div class="cfg-section"><div class="cfg-lbl">🎯 Goal</div><textarea class="cfg-input cfg-textarea">วิเคราะห์ภาพสินค้า หาจุดแข็ง กลุ่มเป้าหมาย และแนวทางการตลาด</textarea></div>
          <div class="cfg-section"><div class="cfg-lbl">🎭 Persona</div><textarea class="cfg-input cfg-textarea">นักวิเคราะห์ตลาดมืออาชีพ มองข้อมูลเป็นตัวเลขและแนวโน้ม</textarea></div>
          <div class="cfg-section"><div class="cfg-lbl">🛠️ Tools</div><div class="cfg-tools">
            <div class="cfg-tool selected">🔍 search</div><div class="cfg-tool selected">👁️ vision</div><div class="cfg-tool">✍️ write</div><div class="cfg-tool">🎨 generate_image</div><div class="cfg-tool">🎬 generate_video</div><div class="cfg-tool">🔊 tts</div><div class="cfg-tool">🎤 stt</div><div class="cfg-tool">📊 analyze</div>
          </div></div>
          <div class="cfg-section"><div class="cfg-lbl">🤖 Model</div><input class="cfg-input" value="gpt-4o" style="color:var(--amber);font-weight:600"></div>
          <div class="cfg-section"><div class="cfg-lbl">📊 Capability Stats</div><div class="cfg-stats">
            <div class="cfg-stat"><div class="cs-lbl">Analysis</div><div class="cs-val">85</div><div class="cfg-stat-bar"><div class="cfg-stat-bar-f" style="width:85%"></div></div></div>
            <div class="cfg-stat"><div class="cs-lbl">Creativity</div><div class="cs-val">40</div><div class="cfg-stat-bar"><div class="cfg-stat-bar-f" style="width:40%"></div></div></div>
            <div class="cfg-stat"><div class="cs-lbl">Speed</div><div class="cs-val">70</div><div class="cfg-stat-bar"><div class="cfg-stat-bar-f" style="width:70%"></div></div></div>
          </div></div>
        </div>
        <div class="modal-footer"><button class="btn btn-reject">🗑️ Delete</button><button class="btn btn-neutral">Cancel</button><button class="btn btn-approve">✓ Save</button></div>
      </div>`;
  }
  if (type === 'history') {
    return `
      <div class="modal">
        <div class="modal-hdr"><div class="modal-title">📋 Task History</div><div class="modal-close" onclick="closeModal()">✕</div></div>
        <div class="modal-body">
          <div class="hist-list">
            <div class="hist-item"><div class="hi-ic" style="background:rgba(42,157,143,.15)">📊</div><div class="hi-body"><div class="hi-title">วิเคราะห์สินค้า Shopee</div><div class="hi-meta"><span>4 agents</span><span>20 ก.ค. 09:15</span></div></div><span class="hi-result" style="background:rgba(42,157,143,.15);color:var(--green)">✓ Done</span></div>
            <div class="hist-item"><div class="hi-ic" style="background:rgba(157,78,221,.15)">🎨</div><div class="hi-body"><div class="hi-title">สร้างคอนเทนต์ประจำวัน</div><div class="hi-meta"><span>3 agents</span><span>20 ก.ค. 08:00</span></div></div><span class="hi-result" style="background:rgba(42,157,143,.15);color:var(--green)">✓ Done</span></div>
            <div class="hist-item"><div class="hi-ic" style="background:rgba(244,162,97,.15)">🛒</div><div class="hi-body"><div class="hi-title">แคมเปญ Flash Sale</div><div class="hi-meta"><span>5 agents</span><span>19 ก.ค. 14:00</span></div></div><span class="hi-result" style="background:rgba(42,157,143,.15);color:var(--green)">✓ Done</span></div>
            <div class="hist-item"><div class="hi-ic" style="background:rgba(72,149,239,.15)">📈</div><div class="hi-body"><div class="hi-title">วิเคราะห์คู่แข่ง</div><div class="hi-meta"><span>2 agents</span><span>19 ก.ค. 10:00</span></div></div><span class="hi-result" style="background:rgba(42,157,143,.15);color:var(--green)">✓ Done</span></div>
            <div class="hist-item"><div class="hi-ic" style="background:rgba(230,57,70,.15)">❌</div><div class="hi-body"><div class="hi-title">สร้างวิดีโอโฆษณา</div><div class="hi-meta"><span>2 agents</span><span>18 ก.ค. 16:00</span></div></div><span class="hi-result" style="background:rgba(230,57,70,.15);color:var(--red)">✕ Failed</span></div>
            <div class="hist-item"><div class="hi-ic" style="background:rgba(42,157,143,.15)">📝</div><div class="hi-body"><div class="hi-title">เขียนบทความบล็อก</div><div class="hi-meta"><span>1 agent</span><span>18 ก.ค. 09:00</span></div></div><span class="hi-result" style="background:rgba(42,157,143,.15);color:var(--green)">✓ Done</span></div>
          </div>
        </div>
      </div>`;
  }
  return '';
}

// ===== INTERACTIONS =====
function switchTab(tab) {
  currentTab = tab;
  document.getElementById('center').innerHTML = tab === 'chat' ? renderChatView() : renderFlowView();
}

function selectAgent(name) {
  selectedAgent = name;
  document.getElementById('right-panel').innerHTML = renderRightPanel();
  document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('selected'));
  event.currentTarget.classList.add('selected');
}

function selectAgentByNode(name) {
  selectedAgent = name;
  document.getElementById('right-panel').innerHTML = renderRightPanel();
  document.querySelectorAll('.agent-card').forEach(c => {
    c.classList.toggle('selected', c.querySelector('.ac-name')?.textContent === name);
  });
}

function selectJob(el) {
  document.querySelectorAll('.job-card').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}

function toggleRA(el) {
  const body = el.nextElementSibling;
  body.classList.toggle('open');
  el.querySelector('.ra-toggle').textContent = body.classList.contains('open') ? '▲' : '▼';
}

function openModal(type) {
  const overlay = document.getElementById('modal-overlay');
  overlay.innerHTML = renderModal(type);
  overlay.classList.add('show');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('show');
}

// ===== INIT =====
document.getElementById('topbar').innerHTML = renderTopBar();
document.getElementById('left-panel').innerHTML = renderLeftPanel();
document.getElementById('center').innerHTML = renderChatView();
document.getElementById('right-panel').innerHTML = renderRightPanel();
document.getElementById('roster').innerHTML = renderRoster();
document.getElementById('input-bar').innerHTML = renderInputBar();
