// Agent OS — Retro Windows Mockup v2

let zCounter = 100;
let activeWin = null;
let openWindows = {};
let activeSession = 'marketing';

// ===== DATA =====
const sessions = [
  {id:'marketing',name:'Marketing Team',preview:'วิเคราะห์ภาพสินค้า...'},
  {id:'flashsale',name:'Flash Sale',preview:'แคมเปญ Flash Sale...'},
  {id:'seo',name:'SEO Analysis',preview:'วิเคราะห์ keyword...'},
  {id:'daily',name:'Daily Content',preview:'สร้างคอนเทนต์วันนี้...'},
];

const plans = [
  {
    id:'plan0',ic:'📝',title:'วิเคราะห์คู่แข่ง',status:'pending',statusText:'รออนุมัติ',
    progress:0,
    planSummary:'Manager เสนอ: 3 agents · วิเคราะห์คู่แข่งรายใหม่',
    waves:[
      {ic:'📊',name:'Product Analyst',task:'วิเคราะห์จุดแข็ง/อ่อนคู่แข่ง'},
      {ic:'🔍',name:'SEO Specialist',task:'วิเคราะห์ keyword ที่คู่แข่งใช้'},
      {ic:'✍️',name:'Copywriter',task:'เขียนคอนเทนต์เปรียบเทียบ'},
    ],
    agents:[
      {ic:'📊',name:'Product Analyst',stat:'idle',statText:'รออนุมัติ',output:''},
      {ic:'🔍',name:'SEO Specialist',stat:'idle',statText:'รออนุมัติ',output:''},
      {ic:'✍️',name:'Copywriter',stat:'idle',statText:'รออนุมัติ',output:''},
    ]
  },
  {
    id:'plan1',ic:'📊',title:'วิเคราะห์ภาพสินค้า',status:'running',statusText:'กำลังทำงาน',
    progress:50,
    planSummary:'4 agents · 2 waves',
    waves:[
      {ic:'📊',name:'Product Analyst',task:'วิเคราะห์จุดแข็ง'},
      {ic:'✍️',name:'Copywriter',task:'แคปชัน 3 แพลตฟอร์ม',depends:'Product Analyst'},
      {ic:'🎨',name:'Image Generator',task:'สร้างภาพ',depends:'Product Analyst'},
      {ic:'🔍',name:'SEO Specialist',task:'keyword',depends:'Copywriter'},
    ],
    agents:[
      {ic:'📊',name:'Product Analyst',stat:'done',statText:'เสร็จแล้ว',output:'สินค้ามีดีไซน์โดดเด่น วัสดุคุณภาพสูง ฟังก์ชัน 2-in-1 ที่คู่แข่งยังไม่มี แนะนำเน้น 3 จุด: ดีไซน์ คุณภาพ นวัตกรรม',model:'gpt-4o',duration:'2m'},
      {ic:'✍️',name:'Copywriter',stat:'running',statText:'กำลังทำงาน 65%',output:'กำลังเขียนแคปชัน 3 แพลตฟอร์ม...',model:'gpt-4o',duration:'1m'},
      {ic:'🎨',name:'Image Generator',stat:'waiting',statText:'รออนุมัติภาพ',output:'',approval:{type:'image',prompt:'สินค้าพรีเมียมบนโต๊ะไม้ แสงอบอุ่น',model:'dall-e-3'}},
      {ic:'🔍',name:'SEO Specialist',stat:'idle',statText:'รอคิว',output:''},
    ]
  },
  {
    id:'plan2',ic:'🎨',title:'สร้างคอนเทนต์ประจำวัน',status:'running',statusText:'กำลังทำงาน 65%',
    progress:65,
    planSummary:'3 agents · 1 wave',
    waves:[
      {ic:'📊',name:'Product Analyst',task:'วิเคราะห์เทรนด์'},
      {ic:'✍️',name:'Copywriter',task:'เขียนโพสต์ 3 แพลตฟอร์ม',depends:'Product Analyst'},
      {ic:'🎨',name:'Image Generator',task:'สร้างภาพประกอบ',depends:'Copywriter'},
    ],
    agents:[
      {ic:'📊',name:'Product Analyst',stat:'done',statText:'เสร็จแล้ว',output:'วิเคราะห์เทรนด์วันนี้เสร็จ พบ 3 หัวข้อน่าสนใจ',model:'gpt-4o',duration:'4m'},
      {ic:'✍️',name:'Copywriter',stat:'done',statText:'เสร็จแล้ว',output:'เขียนโพสต์ 3 แพลตฟอร์มเสร็จ: Facebook, IG, X',model:'gpt-4o',duration:'5m'},
      {ic:'🎨',name:'Image Generator',stat:'running',statText:'กำลังทำงาน 80%',output:'กำลังสร้างภาพประกอบ...',model:'dall-e-3',duration:'3m'},
    ]
  },
  {
    id:'plan3',ic:'🛒',title:'แคมเปญ Flash Sale',status:'done',statusText:'เสร็จสิ้น',
    progress:100,
    planSummary:'4 agents · 18m รวม · $0.04',
    waves:[
      {ic:'📊',name:'Product Analyst',task:'คัดเลือกสินค้า'},
      {ic:'✍️',name:'Copywriter',task:'copy โปรโมชัน',depends:'Product Analyst'},
      {ic:'🎨',name:'Image Generator',task:'ภาพ + วิดีโอ',depends:'Product Analyst'},
      {ic:'🔍',name:'SEO Specialist',task:'keyword',depends:'Copywriter'},
    ],
    agents:[
      {ic:'📊',name:'Product Analyst',stat:'done',statText:'เสร็จแล้ว',output:'คัดเลือก 5 สินค้าที่น่าสนใจสำหรับ Flash Sale',model:'gpt-4o',duration:'4m'},
      {ic:'✍️',name:'Copywriter',stat:'done',statText:'เสร็จแล้ว',output:'เขียน copy โปรโมชัน + แคปชันโซเชียล',model:'gpt-4o',duration:'5m'},
      {ic:'🎨',name:'Image Generator',stat:'done',statText:'เสร็จแล้ว',output:'สร้างภาพโปรโมชัน 5 ภาพ + วิดีโอ 15 วินาที',model:'dall-e-3',duration:'7m'},
      {ic:'🔍',name:'SEO Specialist',stat:'done',statText:'เสร็จแล้ว',output:'วิเคราะห์ keyword สำหรับ Flash Sale พร้อมแนะนำ 10 keyword',model:'auto',duration:'3m'},
    ]
  },
];

const historyLogs = [
  {task:'วิเคราะห์ภาพสินค้า',entries:[
    {time:'09:15',actor:'User',action:'สั่งงาน: ',target:'วิเคราะห์ภาพสินค้านี้ให้หน่อย'},
    {time:'09:15',actor:'Manager',action:'รับคำสั่ง วิเคราะห์ภาพ สร้าง plan',target:''},
    {time:'09:15',actor:'Manager',action:'แบ่งงาน 4 agents, 2 waves',target:''},
    {time:'09:15',actor:'Manager → Product Analyst',action:'มอบหมาย: ',target:'วิเคราะห์ภาพสินค้า หาจุดแข็ง'},
    {time:'09:16',actor:'Product Analyst',action:'เริ่มทำงาน (gpt-4o)',target:''},
    {time:'09:18',actor:'Product Analyst',action:'เสร็จสิ้น ส่งต่อให้ ',target:'Copywriter'},
    {time:'09:18',actor:'Manager → Copywriter',action:'มอบหมาย: ',target:'เขียนแคปชัน 3 แพลตฟอร์ม'},
    {time:'09:18',actor:'Copywriter',action:'เริ่มทำงาน (gpt-4o)',target:''},
    {time:'09:19',actor:'Manager → Image Generator',action:'มอบหมาย: ',target:'สร้างภาพสินค้า'},
    {time:'09:19',actor:'Image Generator',action:'รอ approval (dall-e-3)',target:''},
    {time:'09:20',actor:'Manager',action:'แจ้ง user: รออนุมัติภาพ',target:''},
  ]},
  {task:'สร้างคอนเทนต์ประจำวัน',entries:[
    {time:'08:00',actor:'System',action:'trigger อัตโนมัติ (schedule)',target:''},
    {time:'08:00',actor:'Manager',action:'สร้าง plan 3 agents',target:''},
    {time:'08:01',actor:'Manager → Product Analyst',action:'มอบหมาย: ',target:'วิเคราะห์เทรนด์วันนี้'},
    {time:'08:05',actor:'Product Analyst',action:'เสร็จ ส่งต่อ ',target:'Copywriter'},
    {time:'08:05',actor:'Copywriter',action:'เขียนโพสต์ 3 แพลตฟอร์ม',target:''},
    {time:'08:10',actor:'Copywriter',action:'เสร็จ ส่งต่อ ',target:'Image Generator'},
    {time:'08:10',actor:'Image Generator',action:'กำลังสร้างภาพ (80%)',target:''},
  ]},
  {task:'แคมเปญ Flash Sale',entries:[
    {time:'14:00',actor:'User',action:'สั่งงาน: ',target:'ทำแคมเปญ Flash Sale'},
    {time:'14:00',actor:'Manager',action:'สร้าง plan 4 agents',target:''},
    {time:'14:01',actor:'Manager → Product Analyst',action:'มอบหมาย: ',target:'คัดเลือกสินค้า Flash Sale'},
    {time:'14:05',actor:'Product Analyst',action:'เสร็จ ส่งต่อ ',target:'Copywriter + Image Generator'},
    {time:'14:10',actor:'Copywriter',action:'เขียน copy เสร็จ',target:''},
    {time:'14:12',actor:'Image Generator',action:'สร้างภาพ 5 ภาพ + วิดีโอเสร็จ',target:''},
    {time:'14:15',actor:'Manager → SEO Specialist',action:'มอบหมาย: ',target:'วิเคราะห์ keyword'},
    {time:'14:18',actor:'SEO Specialist',action:'เสร็จ แนะนำ 10 keyword',target:''},
    {time:'14:18',actor:'Manager',action:'ทีมทำงานเสร็จทั้งหมด ✅',target:''},
  ]},
];

// ===== DESKTOP ICONS =====
function renderDesktop() {
  return `
    <div class="desk-icons">
      <div class="desk-icon" ondblclick="openWindow('chat')"><div class="di-ic">💬</div><div class="di-label">Chat</div></div>
      <div class="desk-icon" ondblclick="openWindow('tasks')"><div class="di-ic">📋</div><div class="di-label">Tasks</div></div>
      <div class="desk-icon" ondblclick="openWindow('history')"><div class="di-ic">📁</div><div class="di-label">History</div></div>
      <div class="desk-icon" ondblclick="openWindow('agents')"><div class="di-ic">⚙️</div><div class="di-label">Agents</div></div>
      <div class="desk-icon" ondblclick="openWindow('schedule')"><div class="di-ic">📅</div><div class="di-label">Schedule</div></div>
    </div>`;
}

// ===== TASKBAR =====
function renderTaskbar() {
  const tasks = Object.entries(openWindows).map(([id, w]) => `
    <div class="tb-task ${activeWin===id?'active':''}" onclick="focusWindow('${id}')">
      <span class="tt-ic">${w.icon}</span>
      <span class="tt-name">${w.title}</span>
    </div>`).join('');
  return `
    <div class="start-btn ${document.getElementById('start-menu').classList.contains('show')?'active':''}" onclick="toggleStart()">
      <span class="sb-ic">🪟</span> Start
    </div>
    <div class="tb-sep"></div>
    <div class="tb-tasks">${tasks}</div>
    <div class="tb-sep"></div>
    <div class="tb-tray">
      <div class="tb-tray-ic notify" onclick="showDialog('image')" title="2 items need approval">
        🔔<div class="badge">2</div>
      </div>
      <div class="tb-tray-ic" onclick="showClippy()" title="Assistant">💡</div>
      <div class="tb-clock">9:41 AM</div>
    </div>`;
}

function renderStatusBar() { return ''; }

// ===== START MENU =====
function renderStartMenu() {
  return `
    <div class="sm-header">
      <div class="sm-av">U</div>
      <div>Welcome back, User</div>
    </div>
    <div class="sm-list">
      <div class="sm-item" onclick="openWindow('chat');toggleStart()"><span class="si-ic">💬</span> Chat<span class="si-arrow">›</span></div>
      <div class="sm-item" onclick="openWindow('tasks');toggleStart()"><span class="si-ic">📋</span> Tasks<span class="si-arrow">›</span></div>
      <div class="sm-item" onclick="openWindow('history');toggleStart()"><span class="si-ic">📁</span> History<span class="si-arrow">›</span></div>
      <div class="sm-item" onclick="openWindow('agents');toggleStart()"><span class="si-ic">⚙️</span> Agent Settings<span class="si-arrow">›</span></div>
      <div class="sm-item" onclick="openWindow('schedule');toggleStart()"><span class="si-ic">📅</span> Schedule<span class="si-arrow">›</span></div>
      <div class="sm-sep"></div>
      <div class="sm-item" onclick="toggleStart()"><span class="si-ic">🔌</span> Disconnect</div>
    </div>
    <div class="sm-footer">
      <span>Agent OS v2.0</span>
      <span>$4.82 / $10.00</span>
    </div>`;
}

// ===== WINDOW CONTENT =====
function getWindowContent(type) {
  if (type === 'chat') return renderChatWindow();
  if (type === 'tasks') return renderTasksWindow();
  if (type === 'history') return renderHistoryWindow();
  if (type === 'agents') return renderAgentsWindow();
  if (type === 'schedule') return renderScheduleWindow();
  return '<div style="padding:20px">Empty</div>';
}

const windowConfigs = {
  chat:    {icon:'💬',title:'Chat',w:560,h:520,x:60,y:20},
  tasks:   {icon:'📋',title:'Tasks',w:480,h:520,x:640,y:20},
  history: {icon:'📁',title:'History',w:440,h:480,x:200,y:40},
  agents:  {icon:'⚙️',title:'Agent Settings',w:420,h:480,x:300,y:30},
  schedule:{icon:'📅',title:'Schedule',w:360,h:360,x:120,y:80},
};

function openWindow(type) {
  if (openWindows[type]) { focusWindow(type); return; }
  const cfg = windowConfigs[type];
  const id = type;
  const win = document.createElement('div');
  win.className = 'win active';
  win.id = 'win-' + id;
  win.style.width = cfg.w + 'px';
  win.style.height = cfg.h + 'px';
  win.style.left = cfg.x + 'px';
  win.style.top = cfg.y + 'px';
  win.style.zIndex = ++zCounter;
  win.innerHTML = `
    <div class="win-titlebar" onmousedown="startDrag(event,'${id}')">
      <span class="wt-ic">${cfg.icon}</span>
      <span class="wt-title">${cfg.title}</span>
      <div class="win-controls">
        <div class="win-btn" onclick="minimizeWindow('${id}')">_</div>
        <div class="win-btn close" onclick="closeWindow('${id}')">✕</div>
      </div>
    </div>
    <div class="win-body">${getWindowContent(type)}</div>
    <div class="win-resize" onmousedown="startResize(event,'${id}')"></div>`;
  document.getElementById('desktop').appendChild(win);
  openWindows[id] = {icon:cfg.icon, title:cfg.title, el:win};
  activeWin = id;
  win.addEventListener('mousedown', () => focusWindow(id));
  refreshTaskbar();
}

function closeWindow(id) {
  if (openWindows[id]) {
    openWindows[id].el.remove();
    delete openWindows[id];
    if (activeWin === id) activeWin = null;
    refreshTaskbar();
  }
}

function minimizeWindow(id) {
  if (openWindows[id]) {
    openWindows[id].el.style.display = 'none';
    if (activeWin === id) activeWin = null;
    refreshTaskbar();
  }
}

function focusWindow(id) {
  if (!openWindows[id]) return;
  const w = openWindows[id];
  w.el.style.display = 'flex';
  w.el.style.zIndex = ++zCounter;
  activeWin = id;
  document.querySelectorAll('.win').forEach(x => x.classList.remove('active'));
  w.el.classList.add('active');
  refreshTaskbar();
}

// ===== DRAG =====
let dragData = null;
function startDrag(e, id) {
  if (e.target.classList.contains('win-btn')) return;
  const win = document.getElementById('win-' + id);
  if (!win) return;
  dragData = {id, win, startX:e.clientX, startY:e.clientY, origX:parseInt(win.style.left), origY:parseInt(win.style.top)};
}
document.addEventListener('mousemove', e => {
  if (!dragData) return;
  dragData.win.style.left = (dragData.origX + e.clientX - dragData.startX) + 'px';
  dragData.win.style.top = (dragData.origY + e.clientY - dragData.startY) + 'px';
});
document.addEventListener('mouseup', () => { dragData = null; resizeData = null; });

// ===== RESIZE =====
let resizeData = null;
function startResize(e, id) {
  e.stopPropagation();
  const win = document.getElementById('win-' + id);
  if (!win) return;
  resizeData = {win, startX:e.clientX, startY:e.clientY, startW:win.offsetWidth, startH:win.offsetHeight};
}
document.addEventListener('mousemove', e => {
  if (!resizeData) return;
  const w = Math.max(280, resizeData.startW + e.clientX - resizeData.startX);
  const h = Math.max(180, resizeData.startH + e.clientY - resizeData.startY);
  resizeData.win.style.width = w + 'px';
  resizeData.win.style.height = h + 'px';
});

// ===== START MENU =====
function toggleStart() {
  document.getElementById('start-menu').classList.toggle('show');
  refreshTaskbar();
}

// ===== REFRESH =====
function refreshTaskbar() {
  document.getElementById('taskbar').innerHTML = renderTaskbar();
}

function refreshWindow(id) {
  if (openWindows[id]) {
    openWindows[id].el.querySelector('.win-body').innerHTML = getWindowContent(id);
  }
}

// ===== CHAT WINDOW =====
function renderChatWindow() {
  const sessionList = sessions.map(s => `
    <div class="cs-item ${activeSession===s.id?'active':''}" onclick="switchSession('${s.id}')">
      <div class="cs-name">${s.name}</div>
      <div class="cs-preview">${s.preview}</div>
    </div>`).join('');

  let msgs = '';
  if (activeSession === 'marketing') {
    msgs = `
      <div class="feed-user">วิเคราะห์ภาพสินค้านี้ให้หน่อย<br><img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='120' fill='%23ddd'%3E%3Crect width='200' height='120' rx='4'/%3E%3Ctext x='50%25' y='50%25' fill='%23666' font-size='12' text-anchor='middle' dy='.3em'%3EProduct%3C/text%3E%3C/svg%3E"></div>
      <div class="feed-thinking"><div class="ft-av">🧠</div><div class="ft-bubble"><span class="dots"><span></span><span></span><span></span></span></div></div>
      <div class="feed-agent"><div class="fa-av">🧠</div><div class="fa-bubble"><span class="fa-name">Manager</span>วางแผนเรียบร้อย ตามนี้ได้ไหม?</div></div>
      <div class="chat-plan">
        <div class="chat-plan-waves">
          <div class="chat-plan-wave">
            <div class="cpw-label">Wave 1</div>
            <div class="chat-plan-step"><span class="cps-ic">📊</span><span>Product Analyst — วิเคราะห์จุดแข็ง</span></div>
          </div>
          <div class="chat-plan-wave">
            <div class="cpw-label">Wave 2</div>
            <div class="chat-plan-step"><span class="cps-ic">✍️</span><span>Copywriter — แคปชัน 3 แพลตฟอร์ม</span></div>
            <div class="chat-plan-step"><span class="cps-ic">🎨</span><span>Image Generator — สร้างภาพ</span></div>
          </div>
          <div class="chat-plan-wave">
            <div class="cpw-label">Wave 3</div>
            <div class="chat-plan-step"><span class="cps-ic">🔍</span><span>SEO Specialist — keyword</span></div>
          </div>
        </div>
        <div class="chat-plan-meta">4 agents · 3 waves · ~10 นาที · $0.05</div>
        <div class="chat-plan-actions">
          <button class="cp-btn reject">ปฏิเสธ</button>
          <button class="cp-btn approve" onclick="showDialog('plan-approve')">อนุมัติแผน</button>
        </div>
      </div>
      <div class="feed-progress"><span class="dots"><span></span><span></span><span></span></span> กำลังทำงาน... <button class="fe-btn sm" onclick="openWindow('tasks')">ดู progress</button></div>
      <div class="feed-agent"><div class="fa-av">📊</div><div class="fa-bubble"><span class="fa-name">Product Analyst</span>สินค้ามีจุดเด่นที่ดีไซน์ วัสดุพรีเมียม แนะนำเน้น 3 จุด: ดีไซน์ · คุณภาพ · นวัตกรรม</div></div>
      <div class="feed-agent"><div class="fa-av">✍️</div><div class="fa-bubble"><span class="fa-name">Copywriter</span>FB: สินค้าพรีเมียมที่ใครก็ต้องมี ✨<br>IG: ดีไซน์ที่เกินคาด 💫<br>X: 2-in-1 ที่คู่แข่งยังไม่มี 🔥</div></div>
      <div class="feed-agent"><div class="fa-av">🎨</div><div class="fa-bubble"><span class="fa-name">Image Generator</span><img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='280' height='160' fill='%23e8dcc8'%3E%3Crect width='280' height='160' rx='4'/%3E%3Ctext x='50%25' y='50%25' fill='%239a9088' font-size='13' text-anchor='middle' dy='.3em'%3EGenerated Image%3C/text%3E%3C/svg%3E" style="max-width:100%;border-radius:6px;margin-top:4px;display:block"></div></div>
      <div class="feed-agent"><div class="fa-av">🔍</div><div class="fa-bubble"><span class="fa-name">SEO Specialist</span>10 keywords: สินค้าพรีเมียม · ดีไซน์ทันสมัย · 2-in-1 คุณภาพ · และอีก 7...</div></div>
      <div class="feed-agent"><div class="fa-av">🧠</div><div class="fa-bubble"><span class="fa-name">Manager</span>เสร็จหมดแล้วครับ ✅ <span class="fa-meta">10m · $0.05</span></div></div>`;
  } else if (activeSession === 'flashsale') {
    msgs = `
      <div class="feed-user">ทำแคมเปญ Flash Sale ให้หน่อย</div>
      <div class="feed-thinking"><div class="ft-av">🧠</div><div class="ft-bubble"><span class="dots"><span></span><span></span><span></span></span></div></div>
      <div class="feed-agent"><div class="fa-av">🧠</div><div class="fa-bubble"><span class="fa-name">Manager</span>วางแผนเรียบร้อย ตามนี้ได้ไหม?</div></div>
      <div class="chat-plan">
        <div class="chat-plan-waves">
          <div class="chat-plan-wave">
            <div class="cpw-label">Wave 1</div>
            <div class="chat-plan-step"><span class="cps-ic">📊</span><span>Product Analyst — คัดเลือกสินค้า</span></div>
          </div>
          <div class="chat-plan-wave">
            <div class="cpw-label">Wave 2</div>
            <div class="chat-plan-step"><span class="cps-ic">✍️</span><span>Copywriter — copy โปรโมชัน</span></div>
            <div class="chat-plan-step"><span class="cps-ic">🎨</span><span>Image Generator — ภาพ + วิดีโอ</span></div>
          </div>
          <div class="chat-plan-wave">
            <div class="cpw-label">Wave 3</div>
            <div class="chat-plan-step"><span class="cps-ic">🔍</span><span>SEO Specialist — keyword</span></div>
          </div>
        </div>
        <div class="chat-plan-meta">4 agents · 3 waves · ~18 นาที · $0.04</div>
        <div class="chat-plan-actions">
          <button class="cp-btn reject">ปฏิเสธ</button>
          <button class="cp-btn approve" onclick="showDialog('plan-approve')">อนุมัติแผน</button>
        </div>
      </div>
      <div class="feed-progress"><span class="dots"><span></span><span></span><span></span></span> กำลังทำงาน... <button class="fe-btn sm" onclick="openWindow('tasks')">ดู progress</button></div>
      <div class="feed-agent"><div class="fa-av">📊</div><div class="fa-bubble"><span class="fa-name">Product Analyst</span>คัดเลือก 5 สินค้าน่าสนใจสำหรับ Flash Sale</div></div>
      <div class="feed-agent"><div class="fa-av">✍️</div><div class="fa-bubble"><span class="fa-name">Copywriter</span>เขียน copy โปรโมชัน + แคปชันครบทุกแพลตฟอร์ม</div></div>
      <div class="feed-agent"><div class="fa-av">🎨</div><div class="fa-bubble"><span class="fa-name">Image Generator</span>สร้างภาพ 5 ภาพ + วิดีโอ 15 วินาที</div></div>
      <div class="feed-agent"><div class="fa-av">🔍</div><div class="fa-bubble"><span class="fa-name">SEO Specialist</span>10 keywords สำหรับ Flash Sale</div></div>
      <div class="feed-agent"><div class="fa-av">🧠</div><div class="fa-bubble"><span class="fa-name">Manager</span>เสร็จหมดแล้วครับ ✅ <button class="fe-btn sm" onclick="showDialog('flashsale-results')">ดูผลลัพธ์ทั้งหมด</button></div></div>`;
  } else if (activeSession === 'seo') {
    msgs = `
      <div class="feed-user">วิเคราะห์ keyword ให้หน่อย</div>
      <div class="feed-agent"><div class="fa-av">🧠</div><div class="fa-bubble"><span class="fa-name">Manager</span>วางแผนเรียบร้อย ตามนี้ได้ไหม?</div></div>
      <div class="chat-plan">
        <div class="chat-plan-waves">
          <div class="chat-plan-wave">
            <div class="cpw-label">Wave 1</div>
            <div class="chat-plan-step"><span class="cps-ic">🔍</span><span>SEO Specialist — วิเคราะห์ 10 keywords</span></div>
          </div>
        </div>
        <div class="chat-plan-meta">1 agent · 1 wave · ~3 นาที · $0.01</div>
        <div class="chat-plan-actions">
          <button class="cp-btn reject">ปฏิเสธ</button>
          <button class="cp-btn approve" onclick="showDialog('plan-approve')">อนุมัติแผน</button>
        </div>
      </div>
      <div class="feed-agent"><div class="fa-av">🔍</div><div class="fa-bubble"><span class="fa-name">SEO Specialist</span>10 keywords: สินค้าพรีเมียม · ดีไซน์ทันสมัย · 2-in-1 คุณภาพ · ของแต่งบ้าน · และอีก 6...</div></div>
      <div class="feed-agent"><div class="fa-av">🧠</div><div class="fa-bubble"><span class="fa-name">Manager</span>เสร็จแล้วครับ ✅ <span class="fa-meta">3m · $0.01</span></div></div>`;
  } else {
    msgs = `
      <div class="feed-event system"><span class="fe-ic">🤖</span><div class="fe-body"><div class="fe-title">ระบบเริ่มอัตโนมัติ</div><div class="fe-sub">Schedule: คอนเทนต์ประจำวัน</div></div><span class="fe-time">08:00</span></div>
      <div class="feed-progress"><span class="dots"><span></span><span></span><span></span></span> กำลังทำงาน... <button class="fe-btn sm" onclick="openWindow('tasks')">ดู progress</button></div>`;
  }

  return `
    <div class="chat-body" style="flex-direction:row">
      <div class="chat-sessions">
        <div class="cs-header">Sessions</div>
        <div class="cs-new" onclick="alert('New session')">+ New Session</div>
        <div class="cs-list">${sessionList}</div>
      </div>
      <div style="flex:1;display:flex;flex-direction:column;min-width:0;min-height:0">
        <div class="chat-feed">${msgs}</div>
        <div class="chat-input">
          <div class="ci-top">
            <div class="ci-model">⚡ auto-router</div>
            <div class="ci-mode"><button class="ci-mode-btn">💬 Chat</button><button class="ci-mode-btn active">✨ Plan</button></div>
          </div>
          <div class="ci-row">
            <button class="ci-plus">+</button>
            <textarea class="ci-input" placeholder="พิมพ์คำสั่งถึงทีม..." rows="1"></textarea>
            <button class="ci-send">➤</button>
          </div>
        </div>
      </div>
    </div>`;
}

function switchSession(id) {
  activeSession = id;
  refreshWindow('chat');
}

// ===== TASKS WINDOW =====
function renderTasksWindow() {
  function renderCards(agents) {
    return agents.map(a => {
      let actions = '';
      if (a.approval) {
        actions = `<button class="kcard-btn approve" onclick="showDialog('image')">Approve</button>`;
      } else if (a.output) {
        const dlgId = a.name.toLowerCase().replace(/\s/g,'-') + '-output';
        actions = `<button class="kcard-btn view" onclick="showDialog('${dlgId}')">View</button>`;
      }
      return `
        <div class="kcard">
          <div class="kcard-av ${a.stat}">${a.ic}</div>
          <div class="kcard-name">${a.name}</div>
          <span class="kcard-badge ${a.stat}">${a.statText}</span>
          ${actions}
        </div>`;
    }).join('');
  }

  const planFrames = plans.map((p, i) => {
    const doneCount = p.agents.filter(a => a.stat === 'done').length;
    const totalCount = p.agents.length;
    const approveBtn = p.status === 'pending'
      ? `<div class="kcard-plan-actions"><button class="kcard-btn reject">Reject</button><button class="kcard-btn approve" onclick="showDialog('plan-approve')">Approve Plan</button></div>`
      : '';
    return `
      <div class="plan-frame ${p.status}">
        <div class="plan-frame-hdr" onclick="togglePlan(this)">
          <span class="pf-ic">${p.ic}</span>
          <div class="pf-info">
            <div class="pf-title">${p.title}</div>
            <div class="pf-bar"><div class="pf-bar-fill" style="width:${p.progress}%"></div></div>
          </div>
          <span class="pf-badge">${p.statusText}</span>
          <span class="pf-count">${doneCount}/${totalCount}</span>
          <span class="pf-toggle">▾</span>
        </div>
        <div class="plan-frame-body">
          ${approveBtn}
          ${renderCards(p.agents)}
        </div>
      </div>`;
  }).join('');

  return `<div class="tasks-list">${planFrames}</div>`;
}

function togglePlan(el) {
  const body = el.nextElementSibling;
  const toggle = el.querySelector('.pf-toggle');
  if (body.style.display === 'none') {
    body.style.display = '';
    toggle.textContent = '▾';
  } else {
    body.style.display = 'none';
    toggle.textContent = '▸';
  }
}

function toggleTPContent(el) {
  const content = el.nextElementSibling;
  if (content.style.display === 'none') {
    content.style.display = '';
  } else {
    content.style.display = 'none';
  }
}

function toggleTPAgent(el) {
  // no longer needed — agents are flat
}

// ===== HISTORY WINDOW =====
function renderHistoryWindow() {
  let html = '<div class="hist-log" style="overflow-y:auto;height:100%">';
  historyLogs.forEach(log => {
    html += `<div class="hist-log-task">📁 ${log.task}</div>`;
    log.entries.forEach(e => {
      html += `<div class="hist-log-entry"><span class="hist-log-time">${e.time}</span> <span class="hist-log-actor">${e.actor}</span> <span class="hist-log-action">${e.action}</span><span class="hist-log-target">${e.target}</span></div>`;
    });
  });
  html += '</div>';
  return html;
}

// ===== AGENTS WINDOW =====
let selectedAgent = null;
function renderAgentsWindow() {
  const agents = [
    {name:'Manager',ic:'🧠',role:'Project Manager',stat:'idle',statText:'Idle',goal:'ประสานงานทีม วางแผน ตรวจสอบผล',persona:'ผู้จัดการโปรเจกต์ มองภาพรวม',tools:['orchestrate','review'],model:'auto-router',stats:[80,60,70]},
    {name:'Product Analyst',ic:'📊',role:'วิเคราะห์สินค้า',stat:'idle',statText:'Idle',goal:'วิเคราะห์ภาพสินค้า หาจุดแข็ง',persona:'นักวิเคราะห์ตลาด',tools:['search','vision'],model:'gpt-4o',stats:[85,40,70]},
    {name:'Copywriter',ic:'✍️',role:'เขียนคอนเทนต์',stat:'running',statText:'Running 65%',goal:'เขียนแคปชันโซเชียล 3 แพลตฟอร์ม',persona:'นักเขียนสร้างสรรค์',tools:['write'],model:'gpt-4o',stats:[50,90,60]},
    {name:'Image Generator',ic:'🎨',role:'สร้างภาพ/วิดีโอ',stat:'idle',statText:'Pending',goal:'สร้างภาพสินค้าตาม prompt',persona:'ศิลปินดิจิทัล',tools:['generate_image','generate_video'],model:'dall-e-3',stats:[30,95,40]},
    {name:'SEO Specialist',ic:'🔍',role:'วิเคราะห์ SEO',stat:'review',statText:'Under Review',goal:'วิเคราะห์ SEO แนะนำ keywords',persona:'ผู้เชี่ยวชาญ SEO',tools:['search_web','analyze'],model:'auto',stats:[75,50,80]},
  ];
  let html = '<div class="agents-body" style="overflow-y:auto">';
  agents.forEach(a => {
    html += `<div class="agent-row ${selectedAgent===a.name?'selected':''}" onclick="selectAgent('${a.name}')">
      <div class="ar-av" style="background:var(--cream2)">${a.ic}</div>
      <div class="ar-body"><div class="ar-name">${a.name}</div><div class="ar-role">${a.role}</div></div>
      <span class="ar-stat ${a.stat}">${a.statText}</span>
    </div>`;
    if (selectedAgent === a.name) {
      html += `<div class="agent-detail">
        <div class="ad-section"><div class="ad-lbl">🎯 Goal</div><div class="ad-val">${a.goal}</div></div>
        <div class="ad-section"><div class="ad-lbl">🎭 Persona</div><div class="ad-val">${a.persona}</div></div>
        <div class="ad-section"><div class="ad-lbl">🛠️ Tools</div><div class="ad-tools">${a.tools.map(t=>`<span class="ad-tool">${t}</span>`).join('')}</div></div>
        <div class="ad-section"><div class="ad-lbl">🤖 Model</div><div class="ad-val" style="color:var(--amber);font-family:var(--mono);font-weight:600">${a.model}</div></div>
        <div class="ad-lbl">📊 Stats</div>
        <div class="ad-stats">
          <div class="ad-stat"><div class="as-lbl">Analysis</div><div class="as-val">${a.stats[0]}</div><div class="ad-stat-bar"><div class="ad-stat-bar-f" style="width:${a.stats[0]}%"></div></div></div>
          <div class="ad-stat"><div class="as-lbl">Creative</div><div class="as-val">${a.stats[1]}</div><div class="ad-stat-bar"><div class="ad-stat-bar-f" style="width:${a.stats[1]}%"></div></div></div>
          <div class="ad-stat"><div class="as-lbl">Speed</div><div class="as-val">${a.stats[2]}</div><div class="ad-stat-bar"><div class="ad-stat-bar-f" style="width:${a.stats[2]}%"></div></div></div>
        </div>
        <div class="ad-actions"><button class="btn btn-warm">🚀 Assign</button><button class="btn btn-no">✏️ Edit</button></div>
      </div>`;
    }
  });
  html += '</div>';
  return html;
}

function selectAgent(name) {
  selectedAgent = name;
  refreshWindow('agents');
}

// ===== SCHEDULE WINDOW =====
function renderScheduleWindow() {
  return `
    <div class="sched-body">
      <div class="sched-list">
        <div class="sched-item"><div class="si-time">08:00</div><div class="si-body"><div class="si-name">วิเคราะห์ตลาดประจำวัน</div><div class="si-meta">2 agents · Daily</div></div><div class="sched-toggle on" onclick="this.classList.toggle('on')"></div></div>
        <div class="sched-item"><div class="si-time">10:00</div><div class="si-body"><div class="si-name">สร้างคอนเทนต์โซเชียล</div><div class="si-meta">2 agents · Daily · 3 โพสต์</div></div><div class="sched-toggle on" onclick="this.classList.toggle('on')"></div></div>
        <div class="sched-item"><div class="si-time">14:00</div><div class="si-body"><div class="si-name">ตอบคอมเมนต์ลูกค้า</div><div class="si-meta">1 agent · Daily · รอ approve</div></div><div class="sched-toggle on" onclick="this.classList.toggle('on')"></div></div>
        <div class="sched-item"><div class="si-time">17:00</div><div class="si-body"><div class="si-name">สรุปยอดขายประจำวัน</div><div class="si-meta">1 agent · Daily</div></div><div class="sched-toggle" onclick="this.classList.toggle('on')"></div></div>
      </div>
    </div>`;
}

// ===== DIALOGS =====
function showDialog(type) {
  const overlay = document.getElementById('dialog-overlay') || createDialogOverlay();
  let content = '';
  if (type === 'plan-approve') {
    content = `<div class="dialog" style="max-width:440px"><div class="dialog-titlebar"><span class="dt-ic">📝</span><span class="dt-title">อนุมัติ Plan: วิเคราะห์คู่แข่ง</span></div>
      <div class="dialog-body">
        <div class="dlg-desc" style="text-align:left;font-size:11px;color:var(--ink2);line-height:1.6">Manager เสนอแผนงาน:<br><br>
        <b>1. 📊 Product Analyst</b> — วิเคราะห์จุดแข็ง/อ่อนคู่แข่ง<br>
        <b>2. 🔍 SEO Specialist</b> — วิเคราะห์ keyword ที่คู่แข่งใช้<br>
        <b>3. ✍️ Copywriter</b> — เขียนคอนเทนต์เปรียบเทียบ<br><br>
        <span style="color:var(--ink3);font-size:10px">3 agents · ประมาณ 8 นาที · $0.03</span></div>
      </div>
      <div class="dialog-footer"><button class="btn btn-no" onclick="closeDialog()">ปฏิเสธ</button><button class="btn btn-yes" onclick="closeDialog()">✓ อนุมัติ</button></div></div>`;
  } else if (type === 'image') {
    content = `<div class="dialog"><div class="dialog-titlebar"><span class="dt-ic">🖼️</span><span class="dt-title">Image Approval</span></div>
      <div class="dialog-body"><div class="dlg-preview"><img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='280' height='180' fill='%23e8dcc8'%3E%3Crect width='280' height='180' rx='4'/%3E%3Ctext x='50%25' y='50%25' fill='%239a9088' font-size='13' text-anchor='middle' dy='.3em'%3EGenerated Image%3C/text%3E%3C/svg%3E"></div><div class="dlg-desc">"สินค้าพรีเมียมบนโต๊ะไม้ แสงอบอุ่น มุม 45 องศา"<br>Model: dall-e-3</div></div>
      <div class="dialog-footer"><button class="btn btn-no" onclick="closeDialog()">❌ Cancel</button><button class="btn btn-warm" onclick="closeDialog()">🖼️ Generate</button></div></div>`;
  } else if (type === 'review') {
    content = `<div class="dialog"><div class="dialog-titlebar"><span class="dt-ic">🧠</span><span class="dt-title">Agent Review</span></div>
      <div class="dialog-body"><div class="dlg-title">อนุมัติผลงาน Product Analyst?</div><div class="dlg-preview" style="text-align:left;font-size:11px;color:var(--ink2);line-height:1.5">สินค้ามีจุดเด่นที่ดีไซน์ทันสมัย วัสดุพรีเมียม แนะนำเน้น 3 ด้าน: ดีไซน์, คุณภาพ, นวัตกรรม</div></div>
      <div class="dialog-footer"><button class="btn btn-no" onclick="closeDialog()">✕ Send Back</button><button class="btn btn-yes" onclick="closeDialog()">✓ Approve</button></div></div>`;
  } else if (type === 'tuning') {
    content = `<div class="dialog"><div class="dialog-titlebar"><span class="dt-ic">📝</span><span class="dt-title">Agent Tuning</span></div>
      <div class="dialog-body"><div class="dlg-title">ปรับ model Copywriter?</div><div class="dlg-desc" style="text-align:left"><span class="ti-old">gpt-4o</span> → <span class="ti-new">claude-3.5-sonnet</span><br><span style="color:var(--ink3);font-size:10px">เหมาะกับการเขียนคอนเทนต์ภาษาไทยมากกว่า</span></div></div>
      <div class="dialog-footer"><button class="btn btn-no" onclick="closeDialog()">ปฏิเสธ</button><button class="btn btn-yes" onclick="closeDialog()">ยืนยัน</button></div></div>`;
  } else if (type === 'product-analyst-output') {
    content = `<div class="dialog" style="max-width:420px"><div class="dialog-titlebar"><span class="dt-ic">📊</span><span class="dt-title">Product Analyst — Output</span></div>
      <div class="dialog-body"><div class="dlg-preview" style="text-align:left;font-size:11px;color:var(--ink);line-height:1.6">สินค้ามีดีไซน์โดดเด่น วัสดุคุณภาพสูง ฟังก์ชัน 2-in-1 ที่คู่แข่งยังไม่มี<br><br>แนะนำเน้น 3 จุด:<br>• ดีไซน์ทันสมัย<br>• คุณภาพพรีเมียม<br>• นวัตกรรม 2-in-1</div><div class="dlg-desc" style="text-align:left;font-size:9px;color:var(--ink3);font-family:var(--mono)">🤖 gpt-4o · ⏱️ 2m</div></div>
      <div class="dialog-footer"><button class="btn btn-no" onclick="closeDialog()">Close</button></div></div>`;
  } else if (type === 'copywriter-output') {
    content = `<div class="dialog" style="max-width:420px"><div class="dialog-titlebar"><span class="dt-ic">✍️</span><span class="dt-title">Copywriter — Output</span></div>
      <div class="dialog-body"><div class="dlg-preview" style="text-align:left;font-size:11px;color:var(--ink);line-height:1.6"><b>Facebook:</b> สินค้าพรีเมียมที่ใครก็ต้องมี ✨<br><b>Instagram:</b> ดีไซน์ที่เกินคาด 💫 #premium<br><b>X:</b> 2-in-1 ที่คู่แข่งยังไม่มี 🔥</div><div class="dlg-desc" style="text-align:left;font-size:9px;color:var(--ink3);font-family:var(--mono)">🤖 gpt-4o · ⏱️ 4m</div></div>
      <div class="dialog-footer"><button class="btn btn-no" onclick="closeDialog()">Close</button></div></div>`;
  } else if (type === 'image-generator-output') {
    content = `<div class="dialog" style="max-width:420px"><div class="dialog-titlebar"><span class="dt-ic">🎨</span><span class="dt-title">Image Generator — Output</span></div>
      <div class="dialog-body"><div class="dlg-preview"><img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='280' height='180' fill='%23e8dcc8'%3E%3Crect width='280' height='180' rx='4'/%3E%3Ctext x='50%25' y='50%25' fill='%239a9088' font-size='13' text-anchor='middle' dy='.3em'%3EGenerated Image%3C/text%3E%3C/svg%3E"></div><div class="dlg-desc" style="text-align:left;font-size:9px;color:var(--ink3);font-family:var(--mono)">🤖 dall-e-3 · ⏱️ 7m</div></div>
      <div class="dialog-footer"><button class="btn btn-no" onclick="closeDialog()">Close</button></div></div>`;
  } else if (type === 'seo-specialist-output') {
    content = `<div class="dialog" style="max-width:420px"><div class="dialog-titlebar"><span class="dt-ic">🔍</span><span class="dt-title">SEO Specialist — Output</span></div>
      <div class="dialog-body"><div class="dlg-preview" style="text-align:left;font-size:11px;color:var(--ink);line-height:1.6">แนะนำ 10 keywords:<br>• สินค้าพรีเมียม<br>• ดีไซน์ทันสมัย<br>• 2-in-1 คุณภาพ<br>• ของแต่งบ้าน<br>• ของใช้พรีเมียม<br>• และอีก 5 keywords...</div><div class="dlg-desc" style="text-align:left;font-size:9px;color:var(--ink3);font-family:var(--mono)">🤖 auto · ⏱️ 3m</div></div>
      <div class="dialog-footer"><button class="btn btn-no" onclick="closeDialog()">Close</button></div></div>`;
  } else if (type === 'flashsale-results') {
    content = `<div class="dialog" style="max-width:440px"><div class="dialog-titlebar"><span class="dt-ic">🛒</span><span class="dt-title">Flash Sale — Results</span></div>
      <div class="dialog-body"><div class="dlg-preview" style="text-align:left;font-size:11px;color:var(--ink);line-height:1.6"><b>📊 Product Analyst:</b> คัดเลือก 5 สินค้า<br><b>✍️ Copywriter:</b> copy โปรโมชัน + แคปชัน<br><b>🎨 Image Generator:</b> 5 ภาพ + วิดีโอ 15s<br><b>🔍 SEO Specialist:</b> 10 keywords</div><div class="dlg-desc" style="text-align:left;font-size:9px;color:var(--ink3);font-family:var(--mono)">4 agents · ⏱️ 18m total · $0.04</div></div>
      <div class="dialog-footer"><button class="btn btn-no" onclick="closeDialog()">Close</button></div></div>`;
  }
  if (!content) {
    content = `<div class="dialog"><div class="dialog-titlebar"><span class="dt-ic">❓</span><span class="dt-title">Unknown</span></div>
      <div class="dialog-body"><div class="dlg-desc">Dialog type "${type}" not found.</div></div>
      <div class="dialog-footer"><button class="btn btn-no" onclick="closeDialog()">Close</button></div></div>`;
  }
  overlay.innerHTML = content;
  overlay.classList.add('show');
}

function createDialogOverlay() {
  const ov = document.createElement('div');
  ov.id = 'dialog-overlay';
  ov.className = 'dialog-overlay';
  document.body.appendChild(ov);
  return ov;
}

function closeDialog() {
  document.getElementById('dialog-overlay').classList.remove('show');
}

// ===== CLIPPY =====
function showClippy() {
  let clippy = document.getElementById('clippy');
  if (!clippy) {
    clippy = document.createElement('div');
    clippy.id = 'clippy';
    clippy.className = 'clippy show';
    clippy.innerHTML = `
      <button class="clippy-close" onclick="document.getElementById('clippy').classList.remove('show')">✕</button>
      <div class="clippy-ic">🔔</div>
      <div class="clippy-title">2 รายการรออนุมัติ</div>
      <div class="clippy-desc">Image Generator รออนุมัติภาพ · Manager รอรีวิวงาน</div>
      <div class="clippy-actions"><button class="btn btn-warm" onclick="showDialog('image');document.getElementById('clippy').classList.remove('show')">อนุมัติเลย</button></div>`;
    document.body.appendChild(clippy);
  } else {
    clippy.classList.toggle('show');
  }
}

// ===== HELPERS =====
function toggleRA(el) {
  const body = el.nextElementSibling;
  body.classList.toggle('open');
  el.querySelector('.ra-toggle').textContent = body.classList.contains('open') ? '▲' : '▼';
}

// ===== INIT =====
document.getElementById('desktop').innerHTML = renderDesktop();
document.getElementById('taskbar').innerHTML = renderTaskbar();
document.getElementById('start-menu').innerHTML = renderStartMenu();
createDialogOverlay();

// Auto-open chat window
setTimeout(() => openWindow('chat'), 300);

// Show clippy after 2s
setTimeout(() => showClippy(), 2000);

// Close start menu on outside click
document.addEventListener('click', e => {
  if (!e.target.closest('.start-menu') && !e.target.closest('.start-btn')) {
    document.getElementById('start-menu').classList.remove('show');
    refreshTaskbar();
  }
});
