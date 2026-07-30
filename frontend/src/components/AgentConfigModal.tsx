import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X, Cpu, ChevronDown, Info, Pencil, Check } from 'lucide-react';
import { ModelPicker, findModelName, getProvider, PROVIDER_FAVICONS, type ModelCatalogEntry } from './ModelPicker';
import type { Agent } from '../types/platform';

interface AgentConfigModalProps {
  open: boolean;
  agent: Agent | null;
  availableTools: Array<{ name: string; description: string }>;
  onClose: () => void;
  onSave: (data: { agent_id: string; name: string; role: string; goal: string; persona: string; model: string; tools: string[]; expertise?: string[]; personality?: Record<string, string>; brand_context?: Record<string, string>; output_format?: string; quality_criteria?: string; review_iterations?: number; max_iter?: number; max_retry_limit?: number; allow_delegation?: boolean }) => void;
  onAction?: (name: string, payload?: Record<string, any>) => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  onSearchModels?: (query: string) => void;
  onFetchModelCatalog?: () => void;
  selectedModel?: string;
}

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
  output_format: {
    desc: 'รูปแบบผลลัพธ์ที่ agent ต้องทำตาม กำหนดโครงสร้าง output ที่ชัดเจน',
    example: 'เช่น [Hook] [Body] [CTA] [Hashtags], หรือ JSON schema, หรือ markdown sections',
  },
  quality_criteria: {
    desc: 'เกณฑ์ที่ Manager ใช้ตรวจสอบคุณภาพผลงานของ agent ก่อนผ่าน',
    example: 'เช่น 1. ต้องมี Hook 2. ต้องมี CTA 3. ใช้ภาษาวัยรุ่น 4. ไม่เกิน 280 ตัวอักษร',
  },
  review_iterations: {
    desc: 'จำนวนครั้งขั้นต่ำที่ Manager ตรวจสอบผลงาน agent ถ้าไม่ผ่านจะส่งกลับให้แก้',
    example: 'เช่น 3 (ค่าเริ่มต้น), 5 (ตรวจเข้มข้น), 1 (ตรวจน้อย)',
  },
  max_iter: {
    desc: 'จำนวนรอบสูงสุดที่ agent คิดวนซ้ำได้ ค่ามาก = คิดละเอียด แต่ช้าและใช้ token มาก',
    example: 'เช่น 20 (ค่าเริ่มต้น), 5 (เร็ว กระชับ), 50 (คิดละเอียดมาก)',
  },
  max_retry_limit: {
    desc: 'จำนวนครั้งสูงสุดที่ agent ลองใหม่เมื่อเกิดข้อผิดพลาด',
    example: 'เช่น 3 (ค่าเริ่มต้น), 1 (ลองครั้งเดียว), 5 (พยายามมาก)',
  },
  allow_delegation: {
    desc: 'อนุญาตให้ agent มอบหมายงานให้ agent อื่นในทีมได้',
    example: 'เช่น false (ค่าเริ่มต้น — ทำเอง), true (สามารถมอบหมายได้)',
  },
  learnings: {
    desc: 'บทเรียนที่ agent บันทึกจากการทำงานก่อนหน้า ช่วยให้ทำงานได้ดีขึ้นในครั้งต่อไป',
    example: 'เช่น "ผู้ใช้ชอบบทความสั้นๆ", "ควรใส่ตัวอย่างในทุกหัวข้อ"',
  },
};

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
        className="inline-flex items-center cursor-help"
      >
        <Info className="w-3 h-3 text-text-3 hover:text-accent transition-colors" />
      </span>
      {show && pos && createPortal(
        <div
          className="fixed z-[9999] w-64 p-2.5 bg-bg border border-border rounded-lg shadow-xl pointer-events-none"
          style={{ left: Math.max(8, pos.x - 260), top: pos.y + 18 }}
        >
          <div className="text-[11px] text-text-2 leading-relaxed mb-1">{info.desc}</div>
          <div className="text-[10px] text-accent/80 italic">ตัวอย่าง: {info.example}</div>
        </div>,
        document.body
      )}
    </>
  );
}

function FieldRow({
  label,
  field,
  children,
}: {
  label: string;
  field: string;
  children: React.ReactNode;
}) {
  return (
    <div className="py-2.5 border-b border-border">
      <div className="flex items-center gap-1.5 mb-1">
        <span className="text-xs text-text-2">{label}</span>
        <Tooltip field={field} />
      </div>
      {children}
    </div>
  );
}

function DisplayValue({ value, multiline }: { value: string; multiline?: boolean }) {
  if (!value) return <span className="text-[11px] text-text-3">—</span>;
  return (
    <div className={`text-[11px] text-text ${multiline ? 'whitespace-pre-wrap break-words' : ''}`}>
      {value}
    </div>
  );
}

export const AgentConfigModal: React.FC<AgentConfigModalProps> = ({
  open,
  agent,
  availableTools,
  onClose,
  onSave,
  onAction,
  modelCatalog,
  modelSearchResults,
  onSearchModels,
  onFetchModelCatalog,
  selectedModel,
}) => {
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [goal, setGoal] = useState('');
  const [persona, setPersona] = useState('');
  const [model, setModel] = useState('');
  const [tools, setTools] = useState<string[]>([]);
  const [expertise, setExpertise] = useState<string[]>([]);
  const [personality, setPersonality] = useState<Record<string, string>>({});
  const [brandContext, setBrandContext] = useState<Record<string, string>>({});
  const [outputFormat, setOutputFormat] = useState('');
  const [qualityCriteria, setQualityCriteria] = useState('');
  const [reviewIterations, setReviewIterations] = useState(3);
  const [maxIter, setMaxIter] = useState(20);
  const [maxRetryLimit, setMaxRetryLimit] = useState(3);
  const [allowDelegation, setAllowDelegation] = useState(false);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const modelBtnRef = useRef<HTMLButtonElement>(null);

  const isManager = agent?.is_manager || agent?.role?.toLowerCase() === 'manager';
  const effectiveModel = isManager ? (selectedModel || model) : model;
  const modelProvider = getProvider(effectiveModel);
  const modelFavicon = PROVIDER_FAVICONS[modelProvider];
  const modelDisplayName = effectiveModel ? findModelName(effectiveModel, modelCatalog || {}, modelSearchResults || []) : 'Free Router';

  useEffect(() => {
    if (agent) {
      setName(agent.name || '');
      setRole(agent.role || '');
      setGoal(agent.goal || '');
      setPersona(agent.persona || '');
      const isMgr = agent.is_manager || agent.role?.toLowerCase() === 'manager';
      setModel(isMgr ? (selectedModel || agent.model || '') : (agent.model || ''));
      setTools(agent.tools || []);
      setExpertise((agent as any).expertise || []);
      setPersonality((agent as any).personality || {});
      setBrandContext((agent as any).brand_context || {});
      setOutputFormat((agent as any).output_format || '');
      setQualityCriteria((agent as any).quality_criteria || '');
      setReviewIterations((agent as any).review_iterations ?? 3);
      setMaxIter((agent as any).max_iter ?? 20);
      setMaxRetryLimit((agent as any).max_retry_limit ?? 3);
      setAllowDelegation((agent as any).allow_delegation ?? false);
      setIsEditing(false);
    }
  }, [agent, selectedModel]);

  const handleSave = () => {
    if (!agent) return;
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
    setIsEditing(false);
    onClose();
  };

  const toggleTool = (toolName: string) => {
    setTools((prev) =>
      prev.includes(toolName) ? prev.filter((t) => t !== toolName) : [...prev, toolName]
    );
  };

  if (!open || !agent) return null;

  const inputCls = "w-full px-2.5 py-1.5 bg-bg border border-border rounded-lg text-xs text-text focus:outline-none focus:border-accent";
  const textareaCls = inputCls + " resize-none";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-[480px] max-h-[85vh] overflow-auto bg-surface border border-border rounded-2xl shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-semibold text-text">ตั้งค่า Agent</h2>
          <div className="flex items-center gap-2">
            {!isEditing ? (
              <button
                onClick={() => setIsEditing(true)}
                className="flex items-center gap-1 px-2.5 py-1 bg-accent/10 text-accent rounded-lg text-xs font-medium hover:bg-accent/20 transition-colors"
              >
                <Pencil className="w-3 h-3" />
                แก้ไข
              </button>
            ) : (
              <button
                onClick={handleSave}
                className="flex items-center gap-1 px-2.5 py-1 bg-accent text-white rounded-lg text-xs font-medium hover:bg-accent-hover transition-colors"
              >
                <Check className="w-3 h-3" />
                บันทึก
              </button>
            )}
            <button onClick={onClose} className="p-1 text-text-3 hover:text-text transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
        <p className="text-xs text-text-3 mb-4">{agent.name} · {agent.role}</p>

        <div className="space-y-0">
          {/* Name */}
          <FieldRow label="ชื่อ" field="name">
            {isEditing ? (
              <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
            ) : (
              <DisplayValue value={name} />
            )}
          </FieldRow>

          {/* Role — locked to "Manager" for manager agents because backend expects
              this exact role to identify the manager; changing it would break
              team coordination logic (check_resources, model sync, etc.) */}
          <FieldRow label="Role" field="role">
            {isEditing && !isManager ? (
              <input value={role} onChange={(e) => setRole(e.target.value)} className={inputCls} />
            ) : (
              <DisplayValue value={role} />
            )}
          </FieldRow>

          {/* Goal */}
          <FieldRow label="Goal" field="goal">
            {isEditing ? (
              <textarea value={goal} onChange={(e) => setGoal(e.target.value)} rows={3} className={textareaCls} />
            ) : (
              <DisplayValue value={goal} multiline />
            )}
          </FieldRow>

          {/* Persona */}
          <FieldRow label="Persona" field="persona">
            {isEditing ? (
              <textarea value={persona} onChange={(e) => setPersona(e.target.value)} rows={3} className={textareaCls} />
            ) : (
              <DisplayValue value={persona} multiline />
            )}
          </FieldRow>

          {/* Model */}
          <FieldRow label="Model" field="model">
            {isManager && (
              <div className="text-[10px] text-text-3 px-2 py-1 rounded-md bg-surface-2 border border-border mb-1.5">
                ⚡ เชื่อมกับตัวเลือกโมเดลด้านบนของแชท — เปลี่ยนที่จุดใดจุดหนึ่งจะอัปเดตทั้งสองจุด
              </div>
            )}
            <div ref={modelBtnRef as any} className="relative">
              <button
                onClick={() => {
                  if (onFetchModelCatalog) onFetchModelCatalog();
                  setModelPickerOpen(!modelPickerOpen);
                }}
                className={"w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg border transition-colors text-left " + (modelPickerOpen ? "bg-accent/10 border-accent/40 text-text" : "bg-surface-2 border-border text-text-2 hover:text-text hover:border-accent/30")}
              >
                {modelFavicon ? (
                  <img src={modelFavicon} alt="" className="w-3.5 h-3.5 rounded shrink-0 object-contain" />
                ) : (
                  <Cpu className={"w-3.5 h-3.5 shrink-0" + (modelPickerOpen ? " text-accent" : "")} />
                )}
                <span className="text-xs font-medium text-text flex-1 truncate">{modelDisplayName}</span>
                <span className={"text-[9px] px-1.5 py-0.5 rounded-full shrink-0 " + (effectiveModel ? "bg-accent/15 text-accent" : "bg-emerald-500/15 text-emerald-500")}>
                  {effectiveModel ? "Manual" : "Auto"}
                </span>
                <ChevronDown className={"w-3.5 h-3.5 shrink-0 transition-transform" + (modelPickerOpen ? " rotate-180" : "")} />
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
              and does not execute tools directly; showing tool checkboxes would
              mislead users into thinking Manager can use them */}
          {!isManager && (
          <FieldRow label="Tools" field="tools">
            {isEditing ? (
              <div className="space-y-1.5">
                {availableTools.length === 0 && <span className="text-[11px] text-text-3">ไม่มีเครื่องมือให้เลือก</span>}
                {availableTools.map((tool) => (
                  <label key={tool.name} className="flex items-start gap-2 cursor-pointer hover:bg-surface-2 px-2 py-1 rounded-lg transition-colors">
                    <input
                      type="checkbox"
                      checked={tools.includes(tool.name)}
                      onChange={() => toggleTool(tool.name)}
                      className="mt-0.5 accent-accent"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-text font-medium">{tool.name}</div>
                      {tool.description && <div className="text-[10px] text-text-3">{tool.description}</div>}
                    </div>
                  </label>
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-1.5 flex-wrap">
                {tools.length === 0 && <span className="text-[11px] text-text-3">—</span>}
                {tools.map((tool) => (
                  <span key={tool} className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-2">{tool}</span>
                ))}
              </div>
            )}
          </FieldRow>
          )}

          {/* Expertise */}
          <FieldRow label="Expertise" field="expertise">
            {isEditing ? (
              <input
                value={expertise.join(', ')}
                onChange={(e) => setExpertise(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                placeholder="คั่นด้วยจุลภาค เช่น SEO, Marketing, Data Science"
                className={inputCls}
              />
            ) : (
              <div className="flex items-center gap-1.5 flex-wrap">
                {expertise.length === 0 && <span className="text-[11px] text-text-3">—</span>}
                {expertise.map((exp) => (
                  <span key={exp} className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-2">{exp}</span>
                ))}
              </div>
            )}
          </FieldRow>

          {/* Personality */}
          <div className="py-2.5 border-b border-border">
            <div className="flex items-center gap-1.5 mb-2">
              <span className="text-xs text-text-2">Personality</span>
            </div>
            <div className="space-y-2 pl-2">
              {['tone', 'communication_style', 'language'].map((key) => (
                <div key={key}>
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className="text-[11px] text-text-3 capitalize">{key.replace('_', ' ')}</span>
                    <Tooltip field={`personality.${key}`} />
                  </div>
                  {isEditing ? (
                    <input
                      value={personality[key] || ''}
                      onChange={(e) => setPersonality(prev => ({ ...prev, [key]: e.target.value }))}
                      className={inputCls}
                    />
                  ) : (
                    <DisplayValue value={personality[key] || ''} />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Brand Context */}
          <div className="py-2.5 border-b border-border">
            <div className="flex items-center gap-1.5 mb-2">
              <span className="text-xs text-text-2">Brand Context</span>
            </div>
            <div className="space-y-2 pl-2">
              {['brand_name', 'guidelines', 'target_audience'].map((key) => (
                <div key={key}>
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className="text-[11px] text-text-3 capitalize">{key.replace('_', ' ')}</span>
                    <Tooltip field={`brand.${key}`} />
                  </div>
                  {isEditing ? (
                    <input
                      value={brandContext[key] || ''}
                      onChange={(e) => setBrandContext(prev => ({ ...prev, [key]: e.target.value }))}
                      className={inputCls}
                    />
                  ) : (
                    <DisplayValue value={brandContext[key] || ''} />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Advanced settings — hidden for Manager because these are worker-level
              task execution settings; Manager only coordinates and delegates,
              so output_format/quality_criteria/review_iterations don't apply */}
          {!isManager && (
          <>
          <FieldRow label="Output Format" field="output_format">
            {isEditing ? (
              <textarea value={outputFormat} onChange={(e) => setOutputFormat(e.target.value)} rows={2} className={textareaCls} placeholder="เช่น [Hook] [Body] [CTA] [Hashtags]" />
            ) : (
              <DisplayValue value={outputFormat} multiline />
            )}
          </FieldRow>

          {/* Quality Criteria */}
          <FieldRow label="Quality Criteria" field="quality_criteria">
            {isEditing ? (
              <textarea value={qualityCriteria} onChange={(e) => setQualityCriteria(e.target.value)} rows={3} className={textareaCls} placeholder="เช่น 1. ต้องมี Hook 2. ต้องมี CTA 3. ใช้ภาษาวัยรุ่น" />
            ) : (
              <DisplayValue value={qualityCriteria} multiline />
            )}
          </FieldRow>

          {/* Review Iterations */}
          <FieldRow label="Review Iterations" field="review_iterations">
            {isEditing ? (
              <input type="number" min={1} max={10} value={reviewIterations} onChange={(e) => setReviewIterations(parseInt(e.target.value) || 3)} className={inputCls} />
            ) : (
              <DisplayValue value={String(reviewIterations)} />
            )}
          </FieldRow>

          {/* Max Iter */}
          <FieldRow label="Max Iterations" field="max_iter">
            {isEditing ? (
              <input type="number" min={1} max={100} value={maxIter} onChange={(e) => setMaxIter(parseInt(e.target.value) || 20)} className={inputCls} />
            ) : (
              <DisplayValue value={String(maxIter)} />
            )}
          </FieldRow>

          {/* Max Retry Limit */}
          <FieldRow label="Max Retry Limit" field="max_retry_limit">
            {isEditing ? (
              <input type="number" min={0} max={10} value={maxRetryLimit} onChange={(e) => setMaxRetryLimit(parseInt(e.target.value) || 3)} className={inputCls} />
            ) : (
              <DisplayValue value={String(maxRetryLimit)} />
            )}
          </FieldRow>

          {/* Allow Delegation */}
          <FieldRow label="Allow Delegation" field="allow_delegation">
            {isEditing ? (
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={allowDelegation} onChange={(e) => setAllowDelegation(e.target.checked)} className="accent-accent" />
                <span className="text-xs text-text-2">{allowDelegation ? 'อนุญาต' : 'ไม่อนุญาต'}</span>
              </label>
            ) : (
              <DisplayValue value={allowDelegation ? 'อนุญาต' : 'ไม่อนุญาต'} />
            )}
          </FieldRow>
          </>
          )}

          {/* Learnings (auto-generated, read-only) */}
          <div className="py-2.5 border-b border-border">
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-xs text-text-2">Learnings</span>
              <Tooltip field="learnings" />
            </div>
            <div className="text-[10px] text-text-3 mb-2">บทเรียนที่ระบบบันทึกอัตโนมัติหลัง agent ทำงาน (ไม่สามารถแก้ไขได้)</div>
            {(() => {
              const learnings = (agent as any).learnings || [];
              if (learnings.length === 0) {
                return <span className="text-[11px] text-text-3">ยังไม่มีบทเรียน</span>;
              }
              return (
                <div className="space-y-1.5">
                  {learnings.map((l: any, i: number) => (
                    <div key={i} className="text-[11px] text-text-2 px-2 py-1.5 rounded-lg bg-surface-2 border border-border">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent shrink-0">{l.type || 'lesson'}</span>
                        {l.rating && <span className="text-[9px] text-text-3">⭐ {l.rating}</span>}
                      </div>
                      <div className="text-[11px] text-text-2 break-words">{l.lesson || String(l)}</div>
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 mt-4 pt-3 border-t border-border">
          <button
            onClick={() => { onAction?.('delete_agent', { agent_id: agent.id }); onClose(); }}
            className="px-3 py-2 bg-danger/10 text-danger rounded-lg text-xs font-medium hover:bg-danger/20 transition-colors"
          >
            🗑 ลบ Agent
          </button>
          <div className="flex-1" />
          <button
            onClick={onClose}
            className="px-4 py-2 bg-surface-2 text-text-2 border border-border rounded-lg text-sm font-medium hover:text-text transition-colors"
          >
            ปิด
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            บันทึก
          </button>
        </div>
      </div>
    </div>
  );
};
