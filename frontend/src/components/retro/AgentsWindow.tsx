import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Cpu, ChevronDown, Check, Pencil, Trash2, Plus, Wrench, LayoutTemplate, Info } from 'lucide-react';
import type { Agent, ToolCatalogEntry } from '../../types/platform';
import { ModelPicker, findModelName, getProvider, PROVIDER_FAVICONS, type ModelCatalogEntry } from '../ModelPicker';

interface AgentsWindowProps {
  agents: Agent[];
  availableTools: ToolCatalogEntry[];
  onAddAgent: (data: any) => void;
  onConfigAgent: (data: any) => void;
  onDeleteAgent: (agentId: string) => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  onSearchModels?: (query: string) => void;
  onFetchModelCatalog?: () => void;
  selectedModel?: string;
}

// ============================================================
// Templates (from AgentFormModal)
// ============================================================

interface AgentTemplate {
  id: string;
  label: string;
  description: string;
  spec: { name: string; role: string; goal: string; persona: string; tools: string[]; model: string };
}

const TEMPLATES: AgentTemplate[] = [
  {
    id: 'product_analysis',
    label: 'วิเคราะห์สินค้า',
    description: 'วิเคราะห์สินค้าที่ user ระบุ พร้อมค้นหาคู่แข่งและข้อมูลจริง',
    spec: {
      name: 'Product Analyst',
      role: 'Product Analyst',
      goal: 'วิเคราะห์สินค้าตามข้อมูลที่ได้รับ และค้นหาข้อมูลเพิ่มเติมเพื่อเปรียบเทียบกับคู่แข่งในตลาด โดยอ้างอิงแหล่งข้อมูลที่ตรวจสอบได้จริง',
      persona: 'You are a senior product analyst with deep expertise in competitive analysis, market positioning, and product strategy. You research products thoroughly, verify claims with real sources, and never fabricate data. You communicate findings in structured Thai-language reports. You are rigorous about evidence — if you cannot verify a claim, you say so explicitly.',
      tools: ['analyze_image'],
      model: '',
    },
  },
];

// ============================================================
// Field Tooltips (from AgentConfigModal)
// ============================================================

const FIELD_TOOLTIPS: Record<string, { desc: string; example: string }> = {
  name: {
    desc: 'ชื่อที่ใช้แสดงในระบบและเรียกในแผนงาน ชื่อนี้จะถูกใช้เป็น identifier ของ agent',
    example: 'เช่น Content Writer, Data Analyst, Image Generator',
  },
  role: {
    desc: 'บทบาทหลักของ agent กำหนดว่า agent ทำหน้าที่อะไรในทีม ส่งผลต่อการที่ Manager เลือก agent ตัวไหนมาทำงาน',
    example: 'เช่น Writer, Researcher, Reviewer, Designer',
  },
  goal: {
    desc: 'เป้าหมายหลักของ agent — สิ่งที่ agent ต้องทำให้สำเร็จในแต่ละ task กำหนดทิศทางการทำงานและการตัดสินใจ',
    example: 'เช่น เขียนบทความที่อ่านง่าย น่าสนใจ และถูกต้องตามหลักการ SEO',
  },
  persona: {
    desc: 'บุคลิกและสไตล์การทำงานของ agent กำหนดว่า agent จะคิดและตอบอย่างไร ส่งผลโดยตรงต่อโทนและคุณภาพของผลลัพธ์',
    example: 'เช่น ครีเอทีฟ ชอบคิดนอกกรอบ เน้นความแปลกใหม่ ใส่ใจรายละเอียด',
  },
  model: {
    desc: 'โมเดล AI ที่ agent ใช้ โมเดลที่ทรงพลังกว่าให้ผลลัพธ์ดีกว่าแต่ใช้เครดิตมากกว่า เลือกตามความเหมาะสมของงาน',
    example: 'เช่น Auto (ให้ระบบเลือก), Google Gemini 3.5 Flash (เร็วประหยัด), Claude Sonnet 5 (คุณภาพสูง)',
  },
  tools: {
    desc: 'เครื่องมือที่ agent ใช้ได้ เครื่องมือเพิ่มความสามารถให้ agent เช่น ค้นหาเว็บ สร้างภาพ วิเคราะห์ไฟล์',
    example: 'เช่น web_search (ค้นหาเว็บ), generate_image (สร้างภาพ), analyze_document (วิเคราะห์ไฟล์)',
  },
  expertise: {
    desc: 'ความเชี่ยวชาญเฉพาะด้านของ agent ช่วยให้ Manager เลือก agent ที่เหมาะสมกับงานนั้นๆ',
    example: 'เช่น SEO, Marketing, Data Science, UX Writing',
  },
  'personality.tone': {
    desc: 'น้ำเสียงในการสื่อสารของ agent กำหนดว่าผลลัพธ์จะออกมาเป็นแบบไหน',
    example: 'เช่น เป็นทางการ, เป็นกันเอง, มืออาชีพ, สนุกสนาน',
  },
  'personality.communication_style': {
    desc: 'รูปแบบการสื่อสาร — ว่า agent จะนำเสนอข้อมูลอย่างไร',
    example: 'เช่น กระชับไปที่ประเด็น, อธิบายละเอียด, เล่าเรื่อง, ใช้ bullet points',
  },
  'personality.language': {
    desc: 'ภาษาที่ agent ใช้ในการทำงานและตอบกลับ',
    example: 'เช่น ไทย, English, ไทย-อังกฤษ (Bilingual)',
  },
  'brand.brand_name': {
    desc: 'ชื่อแบรนด์ที่ agent ควรอ้างถึงในการทำงาน ส่งผลต่อการใช้คำและสไตล์ในผลลัพธ์',
    example: 'เช่น ACME Corp, บริษัท สยาม จำกัด',
  },
  'brand.guidelines': {
    desc: 'แนวทางของแบรนด์ที่ agent ต้องปฏิบัติตาม เช่น กฎการใช้โลโก้ สี หรือคำที่ต้อง/ห้ามใช้',
    example: 'เช่น ใช้สีหลัก #FF0000, ห้ามใช้คำว่า "ถูกที่สุด", เน้นความพรีเมียม',
  },
  'brand.target_audience': {
    desc: 'กลุ่มเป้าหมายของเนื้อหาที่ agent สร้าง กำหนดระดับความซับซ้อนและภาษาที่ใช้',
    example: 'เช่น วัยรุ่น 18-25 ปี, ผู้บริหารระดับสูง, นักลงทุนมือใหม่',
  },
  learnings: {
    desc: 'บทเรียนที่ agent บันทึกจากการทำงานก่อนหน้า ช่วยให้ทำงานได้ดีขึ้นในครั้งต่อไป',
    example: 'เช่น "ผู้ใช้ชอบบทความสั้นๆ", "ควรใส่ตัวอย่างในทุกหัวข้อ"',
  },
  output_format: {
    desc: 'รูปแบบผลลัพธ์ที่ agent ต้องส่งออก Manager จะตรวจสอบว่าผลลัพธ์เป็นไปตามรูปแบบนี้',
    example: 'เช่น Markdown report with headings, JSON array, bullet point summary',
  },
  quality_criteria: {
    desc: 'เกณฑ์คุณภาพที่ Manager ใช้ตรวจสอบผลลัพธ์ของ agent — ถ้าไม่ผ่านเกณฑ์จะสั่งแก้',
    example: 'เช่น 1. ต้องมีแหล่งอ้างอิง 2. ห้ามมีคำกว้างๆ 3. ต้องมีตัวเลข/ข้อมูลเฉพาะ',
  },
  review_iterations: {
    desc: 'จำนวนรอบสูงสุดที่ Manager จะตรวจและสั่งแก้งานของ agent — 0 = ไม่จำกัด (Manager ตรวจจนกว่าจะผ่าน)',
    example: 'เช่น 0 = ไม่จำกัด (ค่าเริ่มต้น), 3 = ตรวจสูงสุด 3 รอบ, 1 = ตรวจครั้งเดียว',
  },
  max_iter: {
    desc: 'จำนวนรอบสูงสุดที่ agent จะคิดและทำงานในแต่ละ task — 0 = ไม่จำกัด (ใช้ค่า default ของระบบ)',
    example: 'เช่น 0 = ไม่จำกัด (ค่าเริ่มต้น), 5 = งานง่าย, 50 = งานซับซ้อน',
  },
  max_retry_limit: {
    desc: 'จำนวนครั้งสูงสุดที่ agent จะลองใหม่ถ้าเกิด error ระหว่างทำงาน — 0 = ไม่ลองใหม่',
    example: 'เช่น 0 = ไม่ลองใหม่ (ค่าเริ่มต้น), 3 = ลองใหม่สูงสุด 3 ครั้ง',
  },
  allow_delegation: {
    desc: 'อนุญาตให้ agent มอบหมายงานบางส่วนให้ agent ตัวอื่นในทีมทำแทน',
    example: 'เปิด = agent สามารถ delegate ได้, ปิด = agent ต้องทำเองทั้งหมด',
  },
};

// ============================================================
// Tooltip component (retro-styled, from AgentConfigModal)
// ============================================================

function Tooltip({ field }: { field: string }) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const iconRef = useRef<HTMLSpanElement>(null);
  const info = FIELD_TOOLTIPS[field];
  if (!info) return null;

  const handleEnter = () => {
    if (iconRef.current) {
      const rect = iconRef.current.getBoundingClientRect();
      setPos({ x: rect.left, y: rect.top });
    }
    setShow(true);
  };

  return (
    <>
      <span
        ref={iconRef}
        onMouseEnter={handleEnter}
        onMouseLeave={() => setShow(false)}
        style={{ display: 'inline-flex', alignItems: 'center', cursor: 'help' }}
      >
        <Info size={10} style={{ color: 'var(--ink3)' }} />
      </span>
      {show && pos && createPortal(
        <div
          style={{
            position: 'fixed',
            zIndex: 99999,
            width: '220px',
            padding: '6px 8px',
            background: 'var(--cream)',
            border: '1px solid var(--line)',
            borderRadius: '3px',
            boxShadow: '2px 2px 6px rgba(0,0,0,0.15)',
            pointerEvents: 'none',
            left: Math.max(8, pos.x - 230),
            top: pos.y + 16,
          }}
        >
          <div style={{ fontSize: '10px', color: 'var(--ink)', lineHeight: 1.4, marginBottom: '2px' }}>{info.desc}</div>
          <div style={{ fontSize: '9px', color: 'var(--orange)', fontStyle: 'italic' }}>ตัวอย่าง: {info.example}</div>
        </div>,
        document.body
      )}
    </>
  );
}

// ============================================================
// FieldRow — label + tooltip + children (retro-styled)
// ============================================================

function FieldRow({ label, field, children }: { label: string; field: string; children: React.ReactNode }) {
  return (
    <div className="ad-section">
      <div className="ad-lbl" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {label}
        <Tooltip field={field} />
      </div>
      {children}
    </div>
  );
}

// ============================================================
// DisplayValue — read-only display (retro-styled)
// ============================================================

function DisplayValue({ value, multiline }: { value: string; multiline?: boolean }) {
  if (!value) return <div className="ad-val" style={{ color: 'var(--ink3)' }}>—</div>;
  return (
    <div className="ad-val" style={multiline ? { whiteSpace: 'pre-wrap', wordBreak: 'break-word' } : undefined}>
      {value}
    </div>
  );
}

// ============================================================
// Helpers
// ============================================================

const agentIcon = (name: string, role: string): string => {
  const n = name.toLowerCase();
  const r = role.toLowerCase();
  if (n.includes('manager') || r.includes('manager')) return '🧠';
  if (n.includes('analyst') || n.includes('product') || r.includes('analyst')) return '📊';
  if (n.includes('copy') || n.includes('writer') || r.includes('writer') || r.includes('content')) return '✍️';
  if (n.includes('image') || n.includes('design') || n.includes('visual') || n.includes('artist')) return '🎨';
  if (n.includes('seo') || n.includes('search')) return '🔍';
  if (n.includes('video')) return '🎬';
  return '🤖';
};

const statusClass = (status: string): string => {
  const s = status.toLowerCase();
  if (s.includes('running') || s.includes('busy')) return 'running';
  if (s.includes('error')) return 'error';
  if (s.includes('review')) return 'review';
  return 'idle';
};

const statusText = (status: string): string => {
  const s = status.toLowerCase();
  if (s.includes('running') || s.includes('busy')) return 'Running';
  if (s.includes('error')) return 'Error';
  if (s.includes('review')) return 'Under Review';
  return 'Idle';
};

const isManager = (agent: Agent) =>
  agent.role?.toLowerCase().includes('manager') || agent.name?.toLowerCase().includes('manager') || agent.is_manager;

const inputCls = "w-full px-2.5 py-1.5 bg-[var(--paper)] border border-[var(--line)] rounded-[3px] text-[11px] text-[var(--ink)] focus:outline-none focus:border-[var(--orange)]";
const textareaCls = inputCls + ' resize-none';

// ============================================================
// Agent Config Form (inline edit mode — full feature parity with AgentConfigModal)
// ============================================================

const AgentConfigForm: React.FC<{
  agent: Agent;
  availableTools: ToolCatalogEntry[];
  onSave: (data: any) => void;
  onCancel: () => void;
  onDelete: (agentId: string) => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  onSearchModels?: (query: string) => void;
  onFetchModelCatalog?: () => void;
  selectedModel?: string;
}> = ({ agent, availableTools, onSave, onCancel, onDelete, modelCatalog, modelSearchResults, onSearchModels, onFetchModelCatalog, selectedModel }) => {
  const [name, setName] = useState(agent.name || '');
  const [role, setRole] = useState(agent.role || '');
  const [goal, setGoal] = useState(agent.goal || '');
  const [persona, setPersona] = useState(agent.persona || '');
  const [model, setModel] = useState(agent.model || '');
  const [tools, setTools] = useState<string[]>(agent.tools || []);
  const [expertise, setExpertise] = useState<string[]>((agent as any).expertise || []);
  const [personality, setPersonality] = useState<Record<string, string>>((agent as any).personality || {});
  const [brandContext, setBrandContext] = useState<Record<string, string>>((agent as any).brand_context || {});
  const [outputFormat, setOutputFormat] = useState((agent as any).output_format || '');
  const [qualityCriteria, setQualityCriteria] = useState((agent as any).quality_criteria || '');
  const [reviewIterations, setReviewIterations] = useState((agent as any).review_iterations ?? 3);
  const [maxIter, setMaxIter] = useState((agent as any).max_iter ?? 20);
  const [maxRetryLimit, setMaxRetryLimit] = useState((agent as any).max_retry_limit ?? 3);
  const [allowDelegation, setAllowDelegation] = useState((agent as any).allow_delegation ?? false);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const modelBtnRef = useRef<HTMLButtonElement>(null);

  const mgr = isManager(agent);
  const effectiveModel = mgr ? (selectedModel || model) : model;
  const modelDisplayName = effectiveModel ? findModelName(effectiveModel, modelCatalog || {}, modelSearchResults || []) : 'Free Router';
  const modelProvider = getProvider(effectiveModel);
  const modelFavicon = PROVIDER_FAVICONS[modelProvider];

  const toggleTool = (toolName: string) => {
    setTools(prev => prev.includes(toolName) ? prev.filter(t => t !== toolName) : [...prev, toolName]);
  };

  const handleSave = () => {
    onSave({
      agent_id: agent.id,
      name: name.trim(),
      role: role.trim(),
      goal: goal.trim(),
      persona: persona.trim(),
      model,
      tools,
      expertise,
      personality,
      brand_context: brandContext,
      output_format: outputFormat,
      quality_criteria: qualityCriteria,
      review_iterations: reviewIterations,
      max_iter: maxIter,
      max_retry_limit: maxRetryLimit,
      allow_delegation: allowDelegation,
    });
  };

  return (
    <div className="agent-detail" style={{ cursor: 'default' }}>
      {/* Name */}
      <FieldRow label="ชื่อ" field="name">
        <input value={name} onChange={e => setName(e.target.value)} className={inputCls} />
      </FieldRow>

      {/* Role — disabled for Manager because backend uses this exact role
          to identify the manager; changing it would break team coordination */}
      <FieldRow label="Role" field="role">
        <input value={role} onChange={e => setRole(e.target.value)} className={inputCls} disabled={mgr} style={mgr ? { opacity: 0.6, cursor: 'not-allowed' } : undefined} />
      </FieldRow>

      {/* Goal — disabled for Manager because goal is fixed to team coordination */}
      <FieldRow label="Goal" field="goal">
        <textarea value={goal} onChange={e => setGoal(e.target.value)} rows={3} className={textareaCls} disabled={mgr} style={mgr ? { opacity: 0.6, cursor: 'not-allowed' } : undefined} />
      </FieldRow>

      {/* Persona */}
      <FieldRow label="Persona" field="persona">
        <textarea value={persona} onChange={e => setPersona(e.target.value)} rows={3} className={textareaCls} />
      </FieldRow>

      {/* Model */}
      <FieldRow label="Model" field="model">
        {mgr && (
          <div style={{ fontSize: '9px', color: 'var(--ink3)', padding: '3px 6px', background: 'rgba(200,146,32,0.08)', border: '1px solid rgba(200,146,32,0.2)', borderRadius: '3px', marginBottom: '4px' }}>
            ⚡ เชื่อมกับตัวเลือกโมเดลด้านบนของแชท — เปลี่ยนที่จุดใดจุดหนึ่งจะอัปเดตทั้งสองจุด
          </div>
        )}
        <div ref={modelBtnRef as any} style={{ position: 'relative' }}>
          <button
            onClick={() => { if (onFetchModelCatalog) onFetchModelCatalog(); setModelPickerOpen(!modelPickerOpen); }}
            className="ci-model"
            style={{ width: '100%', justifyContent: 'flex-start' }}
          >
            {modelFavicon ? (
              <img src={modelFavicon} alt="" style={{ width: '12px', height: '12px', borderRadius: '2px', objectFit: 'contain' }} onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
            ) : (
              <Cpu size={12} />
            )}
            <span style={{ flex: 1, textAlign: 'left' }}>{modelDisplayName}</span>
            <span style={{ fontSize: '8px', padding: '1px 4px', borderRadius: '2px', background: effectiveModel ? 'rgba(192,80,30,0.15)' : 'rgba(90,122,74,0.15)', color: effectiveModel ? 'var(--orange)' : 'var(--green)' }}>
              {effectiveModel ? 'Manual' : 'Auto'}
            </span>
            <ChevronDown size={12} style={{ transform: modelPickerOpen ? 'rotate(180deg)' : '' }} />
          </button>
          {modelPickerOpen && (
            <ModelPicker
              recommended={modelCatalog || {}}
              searchResults={modelSearchResults || []}
              selectedModel={effectiveModel}
              onSelect={(modelId) => { setModel(modelId); setModelPickerOpen(false); }}
              onSearch={(query) => onSearchModels?.(query)}
              onClose={() => setModelPickerOpen(false)}
              anchorRef={modelBtnRef as any}
              showAutoRouter
            />
          )}
        </div>
      </FieldRow>

      {/* Tools — hidden for Manager because Manager delegates tasks to workers
          and does not execute tools directly */}
      {!mgr && (
      <FieldRow label="Tools" field="tools">
        <div style={{ maxHeight: '120px', overflowY: 'auto', border: '1px solid var(--line)', borderRadius: '3px', background: 'var(--paper)', padding: '4px' }}>
          {availableTools.length === 0 ? (
            <div style={{ fontSize: '10px', color: 'var(--ink3)', textAlign: 'center', padding: '8px' }}>ไม่มีเครื่องมือให้เลือก</div>
          ) : (
            availableTools.map(tool => {
              const checked = tools.includes(tool.name);
              return (
                <label
                  key={tool.name}
                  style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', padding: '4px 6px', cursor: 'pointer', borderRadius: '3px', background: checked ? 'rgba(192,80,30,0.06)' : 'transparent', marginBottom: '2px' }}
                >
                  <input type="checkbox" checked={checked} onChange={() => toggleTool(tool.name)} style={{ marginTop: '2px', accentColor: 'var(--orange)' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Wrench size={10} style={{ color: 'var(--ink3)' }} />
                      <span style={{ fontSize: '11px', color: 'var(--ink)', fontWeight: 500 }}>{tool.name}</span>
                    </div>
                    {tool.description && <div style={{ fontSize: '9px', color: 'var(--ink3)', marginTop: '1px' }}>{tool.description}</div>}
                  </div>
                </label>
              );
            })
          )}
        </div>
        {tools.length > 0 && (
          <div className="ad-tools" style={{ marginTop: '4px' }}>
            {tools.map(t => <span key={t} className="ad-tool">{t}</span>)}
          </div>
        )}
      </FieldRow>
      )}

      {/* Expertise */}
      <FieldRow label="Expertise" field="expertise">
        <input
          value={expertise.join(', ')}
          onChange={e => setExpertise(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
          placeholder="คั่นด้วยจุลภาค เช่น SEO, Marketing, Data Science"
          className={inputCls}
        />
      </FieldRow>

      {/* Personality */}
      <div className="ad-section">
        <div className="ad-lbl" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          Personality
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingLeft: '6px' }}>
          {['tone', 'communication_style', 'language'].map(key => (
            <div key={key}>
              <div style={{ fontSize: '10px', color: 'var(--ink3)', marginBottom: '1px', textTransform: 'capitalize', display: 'flex', alignItems: 'center', gap: '4px' }}>
                {key.replace('_', ' ')}
                <Tooltip field={`personality.${key}`} />
              </div>
              <input
                value={personality[key] || ''}
                onChange={e => setPersonality(prev => ({ ...prev, [key]: e.target.value }))}
                className={inputCls}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Brand Context */}
      <div className="ad-section">
        <div className="ad-lbl">Brand Context</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingLeft: '6px' }}>
          {['brand_name', 'guidelines', 'target_audience'].map(key => (
            <div key={key}>
              <div style={{ fontSize: '10px', color: 'var(--ink3)', marginBottom: '1px', textTransform: 'capitalize', display: 'flex', alignItems: 'center', gap: '4px' }}>
                {key.replace('_', ' ')}
                <Tooltip field={`brand.${key}`} />
              </div>
              <input
                value={brandContext[key] || ''}
                onChange={e => setBrandContext(prev => ({ ...prev, [key]: e.target.value }))}
                className={inputCls}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Worker-only settings — hidden for Manager because these are task
          execution parameters that only apply to agents that execute work */}
      {!mgr && (
      <>
      {/* Output Format */}
      <FieldRow label="Output Format" field="output_format">
        <textarea value={outputFormat} onChange={e => setOutputFormat(e.target.value)} rows={2} className={textareaCls} placeholder="เช่น [Hook] [Body] [CTA] [Hashtags]" />
      </FieldRow>

      {/* Quality Criteria */}
      <FieldRow label="Quality Criteria" field="quality_criteria">
        <textarea value={qualityCriteria} onChange={e => setQualityCriteria(e.target.value)} rows={3} className={textareaCls} placeholder="เช่น 1. ต้องมี Hook 2. ต้องมี CTA 3. ใช้ภาษาวัยรุ่น" />
      </FieldRow>

      {/* Review Iterations */}
      <FieldRow label="Review Iterations" field="review_iterations">
        <input type="number" min={1} max={10} value={reviewIterations} onChange={e => setReviewIterations(parseInt(e.target.value) || 3)} className={inputCls} />
      </FieldRow>

      {/* Max Iter */}
      <FieldRow label="Max Iterations" field="max_iter">
        <input type="number" min={1} max={100} value={maxIter} onChange={e => setMaxIter(parseInt(e.target.value) || 20)} className={inputCls} />
      </FieldRow>

      {/* Max Retry Limit */}
      <FieldRow label="Max Retry Limit" field="max_retry_limit">
        <input type="number" min={0} max={10} value={maxRetryLimit} onChange={e => setMaxRetryLimit(parseInt(e.target.value) || 3)} className={inputCls} />
      </FieldRow>

      {/* Allow Delegation */}
      <FieldRow label="Allow Delegation" field="allow_delegation">
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
          <input type="checkbox" checked={allowDelegation} onChange={e => setAllowDelegation(e.target.checked)} style={{ accentColor: 'var(--orange)' }} />
          <span style={{ fontSize: '11px', color: 'var(--ink2)' }}>{allowDelegation ? 'อนุญาต' : 'ไม่อนุญาต'}</span>
        </label>
      </FieldRow>
      </>
      )}

      {/* Learnings (read-only) */}
      <div className="ad-section">
        <div className="ad-lbl" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          Learnings
          <Tooltip field="learnings" />
        </div>
        <div style={{ fontSize: '9px', color: 'var(--ink3)', marginBottom: '4px' }}>บทเรียนที่ระบบบันทึกอัตโนมัติหลัง agent ทำงาน (ไม่สามารถแก้ไขได้)</div>
        {(() => {
          const learnings = (agent as any).learnings || [];
          if (learnings.length === 0) {
            return <div className="ad-val" style={{ color: 'var(--ink3)' }}>ยังไม่มีบทเรียน</div>;
          }
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              {learnings.map((l: any, i: number) => (
                <div key={i} style={{ fontSize: '10px', color: 'var(--ink2)', padding: '4px 6px', background: 'var(--cream)', border: '1px solid var(--line)', borderRadius: '3px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '2px' }}>
                    <span style={{ fontSize: '8px', padding: '1px 4px', borderRadius: '2px', background: 'rgba(192,80,30,0.15)', color: 'var(--orange)' }}>{l.type || 'lesson'}</span>
                    {l.rating && <span style={{ fontSize: '8px', color: 'var(--ink3)' }}>⭐ {l.rating}</span>}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--ink2)', wordBreak: 'break-word' }}>{l.lesson || String(l)}</div>
                </div>
              ))}
            </div>
          );
        })()}
      </div>

      {/* Actions */}
      <div className="ad-actions" style={{ marginTop: '8px' }}>
        {!mgr && (
          <button
            className="btn btn-no"
            onClick={() => { if (confirm(`Delete agent "${agent.name}"?`)) { onDelete(agent.id); } }}
          >
            🗑️ ลบ Agent
          </button>
        )}
        <div style={{ flex: 1 }} />
        <button className="btn btn-no" onClick={onCancel}>ปิด</button>
        <button className="btn btn-yes" onClick={handleSave}>
          <Check size={11} /> บันทึก
        </button>
      </div>
    </div>
  );
};

// ============================================================
// Agent Detail View (read-only display — full feature parity with AgentConfigModal view mode)
// ============================================================

const isAgentBusy = (agent: Agent) => {
  const s = (agent.status || '').toLowerCase();
  return s.includes('running') || s.includes('busy') || s.includes('waiting') || s.includes('review');
};

const AgentDetailView: React.FC<{
  agent: Agent;
  onEdit: () => void;
  onDelete: (agentId: string) => void;
}> = ({ agent, onEdit, onDelete }) => {
  const mgr = isManager(agent);
  const busy = isAgentBusy(agent);
  const expertise = (agent as any).expertise as string[] | undefined;
  const personality = (agent as any).personality as Record<string, string> | undefined;
  const brandContext = (agent as any).brand_context as Record<string, string> | undefined;
  const learnings = (agent as any).learnings as any[] | undefined;

  return (
    <div className="agent-detail">
      {/* Name */}
      <FieldRow label="ชื่อ" field="name">
        <DisplayValue value={agent.name} />
      </FieldRow>

      {/* Role */}
      <FieldRow label="Role" field="role">
        <DisplayValue value={agent.role} />
      </FieldRow>

      {/* Goal */}
      <FieldRow label="Goal" field="goal">
        <DisplayValue value={agent.goal || ''} multiline />
      </FieldRow>

      {/* Persona */}
      <FieldRow label="Persona" field="persona">
        <DisplayValue value={agent.persona || ''} multiline />
      </FieldRow>

      {/* Model */}
      <FieldRow label="Model" field="model">
        <div className="ad-val" style={{ color: agent.model ? 'var(--amber)' : 'var(--ink3)', fontFamily: 'var(--mono)', fontWeight: 600 }}>
          {agent.model || 'Auto (Free Router)'}
        </div>
      </FieldRow>

      {/* Tools — hidden for Manager because Manager delegates tasks and
          does not execute tools directly */}
      {!mgr && (
      <FieldRow label="Tools" field="tools">
        {agent.tools && agent.tools.length > 0 ? (
          <div className="ad-tools">
            {agent.tools.map(tool => <span key={tool} className="ad-tool">{tool}</span>)}
          </div>
        ) : (
          <DisplayValue value="" />
        )}
      </FieldRow>
      )}

      {/* Expertise */}
      <FieldRow label="Expertise" field="expertise">
        {expertise && expertise.length > 0 ? (
          <div className="ad-tools">
            {expertise.map(exp => <span key={exp} className="ad-tool">{exp}</span>)}
          </div>
        ) : (
          <DisplayValue value="" />
        )}
      </FieldRow>

      {/* Depends on — removed: this is a per-task runtime value set by the
          Secretary/Manager during planning, not a persistent agent config. */}

      {/* Personality */}
      <div className="ad-section">
        <div className="ad-lbl">Personality</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', paddingLeft: '6px' }}>
          {['tone', 'communication_style', 'language'].map(key => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ fontSize: '10px', color: 'var(--ink3)', textTransform: 'capitalize' }}>{key.replace('_', ' ')}:</span>
              <Tooltip field={`personality.${key}`} />
              <DisplayValue value={personality?.[key] || ''} />
            </div>
          ))}
        </div>
      </div>

      {/* Brand Context */}
      <div className="ad-section">
        <div className="ad-lbl">Brand Context</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', paddingLeft: '6px' }}>
          {['brand_name', 'guidelines', 'target_audience'].map(key => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ fontSize: '10px', color: 'var(--ink3)', textTransform: 'capitalize' }}>{key.replace('_', ' ')}:</span>
              <Tooltip field={`brand.${key}`} />
              <DisplayValue value={brandContext?.[key] || ''} />
            </div>
          ))}
        </div>
      </div>

      {/* Learnings */}
      <div className="ad-section">
        <div className="ad-lbl" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          Learnings
          <Tooltip field="learnings" />
        </div>
        <div style={{ fontSize: '9px', color: 'var(--ink3)', marginBottom: '4px' }}>บทเรียนที่ระบบบันทึกอัตโนมัติหลัง agent ทำงาน (ไม่สามารถแก้ไขได้)</div>
        {(!learnings || learnings.length === 0) ? (
          <DisplayValue value="" />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {learnings.map((l, i) => (
              <div key={i} style={{ fontSize: '10px', color: 'var(--ink2)', padding: '4px 6px', background: 'var(--cream)', border: '1px solid var(--line)', borderRadius: '3px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '2px' }}>
                  <span style={{ fontSize: '8px', padding: '1px 4px', borderRadius: '2px', background: 'rgba(192,80,30,0.15)', color: 'var(--orange)' }}>{l.type || 'lesson'}</span>
                  {l.rating && <span style={{ fontSize: '8px', color: 'var(--ink3)' }}>⭐ {l.rating}</span>}
                </div>
                <div style={{ fontSize: '10px', color: 'var(--ink2)', wordBreak: 'break-word' }}>{l.lesson || String(l)}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Worker-only fields — hidden for Manager because these are task
          execution parameters that only apply to agents that execute work */}
      {!mgr && (
      <>
      <FieldRow label="Output Format" field="output_format">
        <DisplayValue value={agent.output_format || ''} multiline />
      </FieldRow>

      <FieldRow label="Quality Criteria" field="quality_criteria">
        <DisplayValue value={agent.quality_criteria || ''} multiline />
      </FieldRow>

      <FieldRow label="Review Iterations" field="review_iterations">
        <DisplayValue value={agent.review_iterations != null ? String(agent.review_iterations) : ''} />
      </FieldRow>

      <FieldRow label="Max Iterations" field="max_iter">
        <DisplayValue value={agent.max_iter != null ? String(agent.max_iter) : ''} />
      </FieldRow>

      <FieldRow label="Max Retry Limit" field="max_retry_limit">
        <DisplayValue value={agent.max_retry_limit != null ? String(agent.max_retry_limit) : ''} />
      </FieldRow>

      <FieldRow label="Allow Delegation" field="allow_delegation">
        <DisplayValue value={agent.allow_delegation != null ? String(agent.allow_delegation) : ''} />
      </FieldRow>
      </>
      )}

      {/* Actions */}
      <div className="ad-actions">
        {busy ? (
          <div style={{ fontSize: '10px', color: 'var(--amber)', fontStyle: 'italic' }}>
            ⏳ Agent กำลังทำงานอยู่ — ไม่สามารถแก้ไขหรือลบได้
          </div>
        ) : (
          <>
            <button className="btn btn-warm" onClick={onEdit}>
              <Pencil size={11} /> แก้ไข
            </button>
            {!mgr && (
              <button
                className="btn btn-no"
                onClick={() => { if (confirm(`Delete agent "${agent.name}"?`)) onDelete(agent.id); }}
              >
                <Trash2 size={11} /> ลบ Agent
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// ============================================================
// Add Agent Form (inline — full feature parity with AgentFormModal)
// ============================================================

const AddAgentForm: React.FC<{
  availableTools: ToolCatalogEntry[];
  onSubmit: (data: any) => void;
  onCancel: () => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  onSearchModels?: (query: string) => void;
  onFetchModelCatalog?: () => void;
}> = ({ availableTools, onSubmit, onCancel, modelCatalog, modelSearchResults, onSearchModels, onFetchModelCatalog }) => {
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [goal, setGoal] = useState('');
  const [persona, setPersona] = useState('');
  const [model, setModel] = useState('');
  const [tools, setTools] = useState<string[]>([]);
  const [expertise, setExpertise] = useState<string[]>([]);
  const [personality, setPersonality] = useState<Record<string, string>>({});
  const [brandContext, setBrandContext] = useState<Record<string, string>>({});
  // Advanced fields — user can set these when creating an agent
  const [outputFormat, setOutputFormat] = useState('');
  const [qualityCriteria, setQualityCriteria] = useState('');
  const [reviewIterations, setReviewIterations] = useState(3);
  const [maxIter, setMaxIter] = useState(20);
  const [maxRetryLimit, setMaxRetryLimit] = useState(3);
  const [allowDelegation, setAllowDelegation] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const modelBtnRef = useRef<HTMLButtonElement>(null);

  const modelDisplayName = model ? findModelName(model, modelCatalog || {}, modelSearchResults || []) : 'Free Router';
  const modelProvider = getProvider(model);
  const modelFavicon = PROVIDER_FAVICONS[modelProvider];

  const applyTemplate = (templateId: string) => {
    setSelectedTemplate(templateId);
    if (!templateId) {
      setName(''); setRole(''); setGoal(''); setPersona(''); setTools([]); setModel('');
      setExpertise([]); setPersonality({}); setBrandContext({});
      // Reset advanced fields too — otherwise stale values from a previous
      // edit persist when switching templates, which is confusing for users.
      setOutputFormat(''); setQualityCriteria(''); setReviewIterations(3);
      setMaxIter(20); setMaxRetryLimit(3); setAllowDelegation(false);
      return;
    }
    const tmpl = TEMPLATES.find(t => t.id === templateId);
    if (!tmpl) return;
    setName(tmpl.spec.name);
    setRole(tmpl.spec.role);
    setGoal(tmpl.spec.goal);
    setPersona(tmpl.spec.persona);
    setTools(tmpl.spec.tools);
    setModel(tmpl.spec.model);
  };

  const toggleTool = (toolName: string) => {
    setTools(prev => prev.includes(toolName) ? prev.filter(t => t !== toolName) : [...prev, toolName]);
  };

  const handleSubmit = () => {
    if (!name.trim() || !role.trim()) return;
    onSubmit({
      name: name.trim(), role: role.trim(), goal: goal.trim(), persona: persona.trim(),
      tools: tools.join(', '), model, template_id: selectedTemplate,
      expertise, personality, brand_context: brandContext,
      output_format: outputFormat.trim(),
      quality_criteria: qualityCriteria.trim(),
      review_iterations: reviewIterations,
      max_iter: maxIter,
      max_retry_limit: maxRetryLimit,
      allow_delegation: allowDelegation,
    });
  };

  return (
    <div className="agent-detail" style={{ cursor: 'default', borderBottom: '2px solid var(--line)' }}>
      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--ink)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
        <Plus size={12} /> Add New Agent
      </div>

      {/* Templates */}
      {TEMPLATES.length > 0 && (
        <div className="ad-section">
          <div className="ad-lbl" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <LayoutTemplate size={10} /> Templates
          </div>
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
            <button
              onClick={() => applyTemplate('')}
              className={`btn ${!selectedTemplate ? 'btn-yes' : 'btn-no'}`}
              style={{ fontSize: '10px', padding: '3px 8px' }}
            >Blank</button>
            {TEMPLATES.map(t => (
              <button
                key={t.id}
                onClick={() => applyTemplate(t.id)}
                title={t.description}
                className={`btn ${selectedTemplate === t.id ? 'btn-yes' : 'btn-no'}`}
                style={{ fontSize: '10px', padding: '3px 8px' }}
              >{t.label}</button>
            ))}
          </div>
        </div>
      )}

      <FieldRow label="Name *" field="name">
        <input value={name} onChange={e => setName(e.target.value)} className={inputCls} placeholder="e.g. Research Agent" autoFocus />
      </FieldRow>

      <FieldRow label="Role *" field="role">
        <input value={role} onChange={e => setRole(e.target.value)} className={inputCls} placeholder="e.g. Data Analyst" />
      </FieldRow>

      <FieldRow label="Goal" field="goal">
        <input value={goal} onChange={e => setGoal(e.target.value)} className={inputCls} placeholder="e.g. Find and summarize information" />
      </FieldRow>

      <FieldRow label="Persona / Backstory" field="persona">
        <textarea value={persona} onChange={e => setPersona(e.target.value)} rows={3} className={textareaCls} placeholder="Describe the agent's personality and expertise..." />
      </FieldRow>

      {/* Tools */}
      <div className="ad-section">
        <div className="ad-lbl" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          🛠️ Tools
        </div>
        <div style={{ maxHeight: '100px', overflowY: 'auto', border: '1px solid var(--line)', borderRadius: '3px', background: 'var(--paper)', padding: '4px' }}>
          {availableTools.length === 0 ? (
            <div style={{ fontSize: '10px', color: 'var(--ink3)', textAlign: 'center', padding: '6px' }}>No tools available</div>
          ) : (
            availableTools.map(tool => {
              const checked = tools.includes(tool.name);
              return (
                <label key={tool.name} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', padding: '3px 6px', cursor: 'pointer', borderRadius: '3px', background: checked ? 'rgba(192,80,30,0.06)' : 'transparent', marginBottom: '2px' }}>
                  <input type="checkbox" checked={checked} onChange={() => toggleTool(tool.name)} style={{ marginTop: '2px', accentColor: 'var(--orange)' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Wrench size={10} style={{ color: 'var(--ink3)' }} />
                      <span style={{ fontSize: '11px', color: 'var(--ink)', fontWeight: 500 }}>{tool.name}</span>
                    </div>
                    {tool.description && <div style={{ fontSize: '9px', color: 'var(--ink3)' }}>{tool.description}</div>}
                  </div>
                </label>
              );
            })
          )}
        </div>
        {tools.length > 0 && (
          <div style={{ fontSize: '10px', color: 'var(--ink3)', marginTop: '2px' }}>{tools.length} tool(s) selected</div>
        )}
      </div>

      {/* Model */}
      <FieldRow label="Model" field="model">
        <div ref={modelBtnRef as any} style={{ position: 'relative' }}>
          <button
            onClick={() => { if (onFetchModelCatalog) onFetchModelCatalog(); setModelPickerOpen(!modelPickerOpen); }}
            className="ci-model"
            style={{ width: '100%', justifyContent: 'flex-start' }}
          >
            {modelFavicon ? (
              <img src={modelFavicon} alt="" style={{ width: '12px', height: '12px', borderRadius: '2px', objectFit: 'contain' }} onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
            ) : (
              <Cpu size={12} />
            )}
            <span style={{ flex: 1, textAlign: 'left' }}>{modelDisplayName}</span>
            <span style={{ fontSize: '8px', padding: '1px 4px', borderRadius: '2px', background: model ? 'rgba(192,80,30,0.15)' : 'rgba(90,122,74,0.15)', color: model ? 'var(--orange)' : 'var(--green)' }}>
              {model ? 'Manual' : 'Auto'}
            </span>
            <ChevronDown size={12} style={{ transform: modelPickerOpen ? 'rotate(180deg)' : '' }} />
          </button>
          {modelPickerOpen && (
            <ModelPicker
              recommended={modelCatalog || {}}
              searchResults={modelSearchResults || []}
              selectedModel={model}
              onSelect={(modelId) => { setModel(modelId); setModelPickerOpen(false); }}
              onSearch={(query) => onSearchModels?.(query)}
              onClose={() => setModelPickerOpen(false)}
              anchorRef={modelBtnRef as any}
              showAutoRouter
            />
          )}
        </div>
      </FieldRow>

      {/* Expertise */}
      <FieldRow label="Expertise" field="expertise">
        <input
          value={expertise.join(', ')}
          onChange={e => setExpertise(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
          placeholder="คั่นด้วยจุลภาค เช่น SEO, Marketing, Data Science"
          className={inputCls}
        />
      </FieldRow>

      {/* Personality */}
      <div className="ad-section">
        <div className="ad-lbl">Personality</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingLeft: '6px' }}>
          {['tone', 'communication_style', 'language'].map(key => (
            <div key={key}>
              <div style={{ fontSize: '10px', color: 'var(--ink3)', marginBottom: '1px', textTransform: 'capitalize', display: 'flex', alignItems: 'center', gap: '4px' }}>
                {key.replace('_', ' ')}
                <Tooltip field={`personality.${key}`} />
              </div>
              <input
                value={personality[key] || ''}
                onChange={e => setPersonality(prev => ({ ...prev, [key]: e.target.value }))}
                className={inputCls}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Brand Context */}
      <div className="ad-section">
        <div className="ad-lbl">Brand Context</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingLeft: '6px' }}>
          {['brand_name', 'guidelines', 'target_audience'].map(key => (
            <div key={key}>
              <div style={{ fontSize: '10px', color: 'var(--ink3)', marginBottom: '1px', textTransform: 'capitalize', display: 'flex', alignItems: 'center', gap: '4px' }}>
                {key.replace('_', ' ')}
                <Tooltip field={`brand.${key}`} />
              </div>
              <input
                value={brandContext[key] || ''}
                onChange={e => setBrandContext(prev => ({ ...prev, [key]: e.target.value }))}
                className={inputCls}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Advanced Fields */}
      <FieldRow label="Output Format" field="output_format">
        <textarea value={outputFormat} onChange={e => setOutputFormat(e.target.value)} rows={2} className={textareaCls} placeholder="e.g. Markdown report with headings" />
      </FieldRow>

      <FieldRow label="Quality Criteria" field="quality_criteria">
        <textarea value={qualityCriteria} onChange={e => setQualityCriteria(e.target.value)} rows={3} className={textareaCls} placeholder="e.g. Must include sources, no vague statements" />
      </FieldRow>

      <FieldRow label="Review Iterations" field="review_iterations">
        <input type="number" value={reviewIterations} onChange={e => setReviewIterations(Number(e.target.value))} className={inputCls} min={1} max={10} />
      </FieldRow>

      <FieldRow label="Max Iterations" field="max_iter">
        <input type="number" value={maxIter} onChange={e => setMaxIter(Number(e.target.value))} className={inputCls} min={1} max={50} />
      </FieldRow>

      <FieldRow label="Max Retry Limit" field="max_retry_limit">
        <input type="number" value={maxRetryLimit} onChange={e => setMaxRetryLimit(Number(e.target.value))} className={inputCls} min={0} max={10} />
      </FieldRow>

      <FieldRow label="Allow Delegation" field="allow_delegation">
        <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
          <input type="checkbox" checked={allowDelegation} onChange={e => setAllowDelegation(e.target.checked)} />
          <span style={{ fontSize: '10px', color: 'var(--ink2)' }}>Allow this agent to delegate tasks to other agents</span>
        </label>
      </FieldRow>

      <div className="ad-actions" style={{ marginTop: '8px' }}>
        <button className="btn btn-no" onClick={onCancel}>Cancel</button>
        <button
          className="btn btn-yes"
          onClick={handleSubmit}
          disabled={!name.trim() || !role.trim()}
          style={{ opacity: (!name.trim() || !role.trim()) ? 0.5 : 1 }}
        >
          <Check size={11} /> Create Agent
        </button>
      </div>
    </div>
  );
};

// ============================================================
// Main AgentsWindow
// ============================================================

export const AgentsWindow: React.FC<AgentsWindowProps> = ({
  agents, availableTools, onAddAgent, onConfigAgent, onDeleteAgent,
  modelCatalog, modelSearchResults, onSearchModels, onFetchModelCatalog, selectedModel,
}) => {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [editingAgent, setEditingAgent] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    setEditingAgent(false);
  }, [selectedAgent]);

  const handleSaveConfig = (data: any) => {
    onConfigAgent(data);
    setEditingAgent(false);
  };

  const handleDeleteAgent = (agentId: string) => {
    onDeleteAgent(agentId);
    setSelectedAgent(null);
    setEditingAgent(false);
  };

  const handleAddSubmit = (data: any) => {
    onAddAgent(data);
    setShowAddForm(false);
  };

  return (
    <div className="agents-body">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', borderBottom: '1px solid var(--line)', background: 'var(--cream)', position: 'sticky', top: 0, zIndex: 1 }}>
        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--ink)' }}>Agents ({agents.length})</span>
        {!showAddForm && (
          <button
            className="btn btn-yes"
            style={{ fontSize: '10px', padding: '3px 10px' }}
            onClick={() => { setShowAddForm(true); setSelectedAgent(null); }}
          >
            + Add Agent
          </button>
        )}
      </div>

      {/* Add Agent Form */}
      {showAddForm && (
        <AddAgentForm
          availableTools={availableTools}
          onSubmit={handleAddSubmit}
          onCancel={() => setShowAddForm(false)}
          modelCatalog={modelCatalog}
          modelSearchResults={modelSearchResults}
          onSearchModels={onSearchModels}
          onFetchModelCatalog={onFetchModelCatalog}
        />
      )}

      {/* Agent list */}
      {agents.length === 0 && !showAddForm ? (
        <div className="kcard-empty">
          <div style={{ fontSize: '24px', marginBottom: '6px' }}>⚙️</div>
          <div>No agents yet. Click "Add Agent" to create one.</div>
        </div>
      ) : (
        agents.map(agent => (
          <div key={agent.id}>
            <div
              className={`agent-row ${selectedAgent === agent.id ? 'selected' : ''}`}
              onClick={() => { setSelectedAgent(selectedAgent === agent.id ? null : agent.id); setEditingAgent(false); }}
            >
              <div className="ar-av" style={{ background: 'var(--cream2)' }}>
                {agentIcon(agent.name, agent.role)}
              </div>
              <div className="ar-body">
                <div className="ar-name">
                  {agent.name}
                  {isManager(agent) && (
                    <span style={{ fontSize: '8px', padding: '1px 5px', background: 'var(--orange)', color: '#fff', borderRadius: '2px', fontWeight: 700, marginLeft: '4px' }}>MANAGER</span>
                  )}
                </div>
                <div className="ar-role">{agent.role}</div>
              </div>
              <span className={`ar-stat ${statusClass(agent.status)}`}>{statusText(agent.status)}</span>
            </div>

            {/* Detail panel */}
            {selectedAgent === agent.id && (
              editingAgent ? (
                <AgentConfigForm
                  agent={agent}
                  availableTools={availableTools}
                  onSave={handleSaveConfig}
                  onCancel={() => setEditingAgent(false)}
                  onDelete={handleDeleteAgent}
                  modelCatalog={modelCatalog}
                  modelSearchResults={modelSearchResults}
                  onSearchModels={onSearchModels}
                  onFetchModelCatalog={onFetchModelCatalog}
                  selectedModel={selectedModel}
                />
              ) : (
                <AgentDetailView
                  agent={agent}
                  onEdit={() => setEditingAgent(true)}
                  onDelete={handleDeleteAgent}
                />
              )
            )}
          </div>
        ))
      )}
    </div>
  );
};
