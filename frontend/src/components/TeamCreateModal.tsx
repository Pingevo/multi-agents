import { useState, useRef } from 'react';
import { X, Cpu, ChevronDown, Plus, Trash2, Wrench, User, Users, LayoutTemplate } from 'lucide-react';
import { ModelPicker, PROVIDER_FAVICONS, getProvider, findModelName } from './ModelPicker';
import type { ModelCatalogEntry } from './ModelPicker';
import type { ToolCatalogEntry } from '../types/platform';

interface AgentEntry {
  name: string;
  role: string;
  goal: string;
  persona: string;
  tools: string[];
  model: string;
  template_id?: string;
  expertise: string[];
  personality: { tone: string; communication_style: string; language: string };
  brand_context: { brand_name: string; guidelines: string; target_audience: string };
  output_format: string;
  quality_criteria: string;
  review_iterations: number | null; // null = unlimited
  max_iter: number | null;          // null = unlimited
  max_retry_limit: number | null;   // null = unlimited
  allow_delegation: boolean;
}

interface AgentTemplate {
  id: string;
  label: string;
  description: string;
  spec: {
    name: string;
    role: string;
    goal: string;
    persona: string;
    tools: string[];
    model: string;
  };
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

interface TeamCreateModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (data: {
    name: string;
    description: string;
    manager_model: string;
    manager_persona: string;
    manager_goal: string;
    manager_expertise: string[];
    manager_personality: { tone: string; communication_style: string; language: string };
    manager_brand_context: { brand_name: string; guidelines: string; target_audience: string };
    agents: AgentEntry[];
  }) => void;
  onFetchModelCatalog?: () => void;
  onSearchModels?: (query: string) => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  selectedModel?: string;
  resolvedModel?: string;
  availableTools?: ToolCatalogEntry[];
}

export const TeamCreateModal: React.FC<TeamCreateModalProps> = ({
  open,
  onClose,
  onCreate,
  onFetchModelCatalog,
  onSearchModels,
  modelCatalog = {},
  modelSearchResults = [],
  selectedModel: externalSelectedModel,
  resolvedModel,
  availableTools = [],
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [managerModel, setManagerModel] = useState('');
  const [managerPersona, setManagerPersona] = useState('');
  const [managerGoal, setManagerGoal] = useState('');
  // Manager extra fields — same set as worker agents for consistency
  const [managerExpertise, setManagerExpertise] = useState<string[]>([]);
  const [managerPersonality, setManagerPersonality] = useState({ tone: '', communication_style: '', language: '' });
  const [managerBrandContext, setManagerBrandContext] = useState({ brand_name: '', guidelines: '', target_audience: '' });
  const [agents, setAgents] = useState<AgentEntry[]>([]);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [expandedAgent, setExpandedAgent] = useState<number | null>(null);
  const [agentModelPickerIdx, setAgentModelPickerIdx] = useState<number | null>(null);
  const inputBarRef = useRef<HTMLDivElement>(null);
  const agentModelRefs = useRef<(HTMLDivElement | null)[]>([]);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    // Validate: if ∞ unchecked, number must be filled
    const invalidAgent = agents.find(a =>
      a.role.trim() && (
        (a.review_iterations !== null && isNaN(a.review_iterations)) ||
        (a.max_iter !== null && isNaN(a.max_iter)) ||
        (a.max_retry_limit !== null && isNaN(a.max_retry_limit))
      )
    );
    if (invalidAgent) return;
    onCreate({
      name: name.trim(),
      description: description.trim(),
      manager_model: managerModel || 'auto',
      manager_persona: managerPersona.trim(),
      manager_goal: managerGoal.trim(),
      manager_expertise: managerExpertise,
      manager_personality: managerPersonality,
      manager_brand_context: managerBrandContext,
      agents: agents.filter(a => a.role.trim()),
    });
    setName('');
    setDescription('');
    setManagerModel('');
    setManagerPersona('');
    setManagerGoal('');
    setManagerExpertise([]);
    setManagerPersonality({ tone: '', communication_style: '', language: '' });
    setManagerBrandContext({ brand_name: '', guidelines: '', target_audience: '' });
    setAgents([]);
    setExpandedAgent(null);
    onClose();
  };

  const addAgent = () => {
    const newAgent: AgentEntry = {
      name: '', role: '', goal: '', persona: '', tools: [], model: '',
      expertise: [],
      personality: { tone: '', communication_style: '', language: '' },
      brand_context: { brand_name: '', guidelines: '', target_audience: '' },
      output_format: '', quality_criteria: '',
      review_iterations: null, max_iter: null, max_retry_limit: null, allow_delegation: false,
    };
    setAgents([...agents, newAgent]);
    setExpandedAgent(agents.length);
  };

  const addAgentFromTemplate = (template: AgentTemplate) => {
    const newAgent: AgentEntry = {
      name: template.spec.name,
      role: template.spec.role,
      goal: template.spec.goal,
      persona: template.spec.persona,
      tools: template.spec.tools,
      model: template.spec.model,
      template_id: template.id,
      expertise: [],
      personality: { tone: '', communication_style: '', language: '' },
      brand_context: { brand_name: '', guidelines: '', target_audience: '' },
      output_format: '', quality_criteria: '',
      review_iterations: null, max_iter: null, max_retry_limit: null, allow_delegation: false,
    };
    setAgents([...agents, newAgent]);
    setExpandedAgent(agents.length);
  };

  const removeAgent = (idx: number) => {
    setAgents(agents.filter((_, i) => i !== idx));
    setExpandedAgent(null);
  };

  const updateAgent = (idx: number, field: keyof AgentEntry, value: any) => {
    setAgents(agents.map((a, i) => i === idx ? { ...a, [field]: value } : a));
  };

  const toggleAgentTool = (idx: number, toolName: string) => {
    const agent = agents[idx];
    const tools = agent.tools.includes(toolName)
      ? agent.tools.filter(t => t !== toolName)
      : [...agent.tools, toolName];
    updateAgent(idx, 'tools', tools);
  };

  const handleOpenAgentModelPicker = (idx: number) => {
    if (agentModelPickerIdx === idx) {
      setAgentModelPickerIdx(null);
      return;
    }
    if (Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) {
      onFetchModelCatalog();
    }
    setAgentModelPickerIdx(idx);
  };

  const handleSelectAgentModel = (modelId: string) => {
    if (agentModelPickerIdx !== null) {
      updateAgent(agentModelPickerIdx, 'model', modelId);
    }
  };

  const handleOpenModelPicker = () => {
    if (modelPickerOpen) {
      setModelPickerOpen(false);
      return;
    }
    if (Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) {
      onFetchModelCatalog();
    }
    setModelPickerOpen(true);
  };

  const handleSelectModel = (modelId: string) => {
    setManagerModel(modelId);
  };

  const handleSearchModels = (query: string) => {
    if (onSearchModels) {
      onSearchModels(query);
    }
  };

  const displayModel = managerModel || externalSelectedModel || resolvedModel || '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-2xl bg-paper border border-line-2 rounded-retro-lg shadow-retro-lg flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-line shrink-0">
          <div>
            <h2 className="text-base font-semibold text-ink">สร้างทีมใหม่</h2>
            <p className="text-xs text-ink-3 mt-0.5">ตั้งค่าทีม, manager และ agent ได้ในที่เดียว</p>
          </div>
          <button onClick={onClose} className="p-1 text-ink-3 hover:text-ink transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="overflow-y-auto px-5 py-4 space-y-5 flex-1">

            {/* Section 1: Team Info */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-ink-2 uppercase tracking-wide">
                <Users className="w-3.5 h-3.5" /> ทีม
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-2 mb-1.5">ชื่อทีม *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="เช่น ทีมการตลาด"
                  autoFocus
                  className="w-full px-3 py-2 bg-cream border border-line rounded-retro text-sm text-ink placeholder-ink-3 focus:outline-none focus:ring-2 focus:ring-orange/50 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-2 mb-1.5">คำอธิบาย</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="ทีมนี้ทำอะไร?"
                  rows={2}
                  className="w-full px-3 py-2 bg-cream border border-line rounded-retro text-sm text-ink placeholder-ink-3 focus:outline-none focus:ring-2 focus:ring-orange/50 focus:border-transparent resize-none"
                />
              </div>
            </div>

            {/* Section 2: Manager Config */}
            <div className="space-y-3 border-t border-line pt-4">
              <div className="flex items-center gap-2 text-xs font-semibold text-ink-2 uppercase tracking-wide">
                <User className="w-3.5 h-3.5" /> Manager
              </div>
              <div ref={inputBarRef} className="relative">
                {modelPickerOpen && (
                  <ModelPicker
                    recommended={modelCatalog}
                    searchResults={modelSearchResults}
                    selectedModel={managerModel}
                    onSelect={handleSelectModel}
                    onSearch={handleSearchModels}
                    onClose={() => setModelPickerOpen(false)}
                    anchorRef={inputBarRef}
                  />
                )}
                <label className="block text-xs font-medium text-ink-2 mb-1.5">โมเดล</label>
                <button
                  type="button"
                  onClick={handleOpenModelPicker}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-retro border transition-colors text-left ${
                    modelPickerOpen
                      ? 'bg-orange/10 border-orange/40 text-ink'
                      : 'bg-cream border-line text-ink-2 hover:text-ink hover:border-line-2'
                  }`}
                >
                  {(() => {
                    const provider = getProvider(displayModel);
                    const favicon = PROVIDER_FAVICONS[provider];
                    if (favicon) {
                      return <img src={favicon} alt="" className="w-4 h-4 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                    }
                    return <Cpu className={`w-3.5 h-3.5 shrink-0 ${modelPickerOpen ? 'text-orange' : ''}`} />;
                  })()}
                  <span className="text-sm font-medium text-ink flex-1 truncate">
                    {displayModel ? findModelName(displayModel, modelCatalog, modelSearchResults) : 'Free Router'}
                  </span>
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full shrink-0 ${managerModel ? 'bg-orange/15 text-orange' : 'bg-green/15 text-green'}`}>
                    {managerModel ? 'Manual' : 'Auto'}
                  </span>
                  <ChevronDown className={`w-3.5 h-3.5 shrink-0 transition-transform ${modelPickerOpen ? 'rotate-180' : ''}`} />
                </button>
              </div>
              {/* Manager Goal removed — backend sets a default goal automatically
                  ("Coordinate the team to accomplish user tasks efficiently");
                  letting users override it with task-specific goals breaks team
                  coordination because Manager would try to do the work itself
                  instead of delegating */}
              <div>
                <label className="block text-xs font-medium text-ink-2 mb-1.5">Persona ของ Manager</label>
                <textarea
                  value={managerPersona}
                  onChange={(e) => setManagerPersona(e.target.value)}
                  placeholder="ค่าเริ่มต้น: ผู้จัดการโปรเจกต์ที่มีประสบการณ์ ประสานงานทีมได้มีประสิทธิภาพ"
                  rows={2}
                  className="w-full px-3 py-2 bg-cream border border-line rounded-retro text-sm text-ink placeholder-ink-3 focus:outline-none focus:ring-2 focus:ring-orange/50 focus:border-transparent resize-none"
                />
              </div>

              {/* Manager Expertise — same field as worker agents, lets user
                  specify what domains the Manager should understand when
                  coordinating and delegating */}
              <div>
                <label className="block text-xs font-medium text-ink-2 mb-1.5">Expertise ของ Manager (คั่นด้วยจุลภาค)</label>
                <input
                  type="text"
                  value={managerExpertise.join(', ')}
                  onChange={(e) => setManagerExpertise(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                  placeholder="เช่น Project Management, Marketing Strategy"
                  className="w-full px-3 py-2 bg-cream border border-line rounded-retro text-sm text-ink placeholder-ink-3 focus:outline-none focus:ring-2 focus:ring-orange/50 focus:border-transparent"
                />
              </div>

              {/* Manager Personality */}
              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-ink-2">Personality ของ Manager</label>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-[9px] text-ink-3 mb-0.5">Tone</label>
                    <input
                      type="text"
                      value={managerPersonality.tone}
                      onChange={(e) => setManagerPersonality({ ...managerPersonality, tone: e.target.value })}
                      placeholder="เช่น professional"
                      className="w-full px-2 py-1.5 bg-cream border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                    />
                  </div>
                  <div>
                    <label className="block text-[9px] text-ink-3 mb-0.5">Communication</label>
                    <input
                      type="text"
                      value={managerPersonality.communication_style}
                      onChange={(e) => setManagerPersonality({ ...managerPersonality, communication_style: e.target.value })}
                      placeholder="เช่น concise"
                      className="w-full px-2 py-1.5 bg-cream border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                    />
                  </div>
                  <div>
                    <label className="block text-[9px] text-ink-3 mb-0.5">Language</label>
                    <input
                      type="text"
                      value={managerPersonality.language}
                      onChange={(e) => setManagerPersonality({ ...managerPersonality, language: e.target.value })}
                      placeholder="เช่น th, en"
                      className="w-full px-2 py-1.5 bg-cream border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                    />
                  </div>
                </div>
              </div>

              {/* Manager Brand Context */}
              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-ink-2">Brand Context ของ Manager</label>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-[9px] text-ink-3 mb-0.5">Brand Name</label>
                    <input
                      type="text"
                      value={managerBrandContext.brand_name}
                      onChange={(e) => setManagerBrandContext({ ...managerBrandContext, brand_name: e.target.value })}
                      className="w-full px-2 py-1.5 bg-cream border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                    />
                  </div>
                  <div>
                    <label className="block text-[9px] text-ink-3 mb-0.5">Guidelines</label>
                    <input
                      type="text"
                      value={managerBrandContext.guidelines}
                      onChange={(e) => setManagerBrandContext({ ...managerBrandContext, guidelines: e.target.value })}
                      className="w-full px-2 py-1.5 bg-cream border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                    />
                  </div>
                  <div>
                    <label className="block text-[9px] text-ink-3 mb-0.5">Target Audience</label>
                    <input
                      type="text"
                      value={managerBrandContext.target_audience}
                      onChange={(e) => setManagerBrandContext({ ...managerBrandContext, target_audience: e.target.value })}
                      className="w-full px-2 py-1.5 bg-cream border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Section 3: Agents */}
            <div className="space-y-3 border-t border-line pt-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-semibold text-ink-2 uppercase tracking-wide">
                  <Wrench className="w-3.5 h-3.5" /> Agents ({agents.length})
                </div>
                <button
                  type="button"
                  onClick={addAgent}
                  className="flex items-center gap-1 px-2.5 py-1 bg-orange/10 text-orange rounded-retro text-xs font-medium hover:bg-orange/20 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" /> เพิ่ม Agent
                </button>
              </div>

              {/* Template buttons */}
              {TEMPLATES.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] text-ink-3 flex items-center gap-1">
                    <LayoutTemplate className="w-3 h-3" /> Templates:
                  </span>
                  {TEMPLATES.map((tmpl) => (
                    <button
                      key={tmpl.id}
                      type="button"
                      onClick={() => addAgentFromTemplate(tmpl)}
                      title={tmpl.description}
                      className="px-2.5 py-1 rounded-retro text-xs font-medium border border-line text-ink-2 hover:bg-orange/10 hover:border-orange/30 hover:text-orange transition-colors"
                    >
                      + {tmpl.label}
                    </button>
                  ))}
                </div>
              )}

              {agents.length === 0 && (
                <div className="text-center py-6 text-ink-3 text-xs border border-dashed border-line-2 rounded-retro">
                  ยังไม่มี agent — กด "เพิ่ม Agent" เพื่อสร้าง หรือข้ามไว้แล้วเพิ่มทีหลัง
                </div>
              )}

              {agents.map((agent, idx) => (
                <div key={idx} className="border border-line rounded-retro bg-cream overflow-hidden">
                  {/* Agent header — collapsed view */}
                  <div
                    className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-cream-2 transition-colors"
                    onClick={() => setExpandedAgent(expandedAgent === idx ? null : idx)}
                  >
                    <ChevronDown className={`w-3.5 h-3.5 text-ink-3 shrink-0 transition-transform ${expandedAgent === idx ? '' : '-rotate-90'}`} />
                    <span className="text-sm text-ink font-medium flex-1 truncate">
                      {agent.name || agent.role || `Agent ${idx + 1}`}
                    </span>
                    {agent.tools.length > 0 && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-orange/10 text-orange rounded-full shrink-0">
                        {agent.tools.length} tools
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); removeAgent(idx); }}
                      className="p-1 text-ink-3 hover:text-red transition-colors shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Agent detail — expanded view */}
                  {expandedAgent === idx && (
                    <div className="px-3 pb-3 space-y-2.5 border-t border-line pt-3">
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-[10px] text-ink-3 mb-0.5">ชื่อ (ว่าง = auto)</label>
                          <input
                            type="text"
                            value={agent.name}
                            onChange={(e) => updateAgent(idx, 'name', e.target.value)}
                            placeholder="เช่น Content Writer"
                            className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] text-ink-3 mb-0.5">Role *</label>
                          <input
                            type="text"
                            value={agent.role}
                            onChange={(e) => updateAgent(idx, 'role', e.target.value)}
                            placeholder="เช่น Data Analyst"
                            className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-[10px] text-ink-3 mb-0.5">เป้าหมาย</label>
                        <input
                          type="text"
                          value={agent.goal}
                          onChange={(e) => updateAgent(idx, 'goal', e.target.value)}
                          placeholder="เช่น ค้นหาและสรุปข้อมูล"
                          className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-ink-3 mb-0.5">Persona / Backstory</label>
                        <textarea
                          value={agent.persona}
                          onChange={(e) => updateAgent(idx, 'persona', e.target.value)}
                          placeholder="บุคลิกและความเชี่ยวชาญ..."
                          rows={2}
                          className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange resize-none"
                        />
                      </div>
                      <div ref={(el) => { agentModelRefs.current[idx] = el; }} className="relative">
                        {agentModelPickerIdx === idx && (
                          <ModelPicker
                            recommended={modelCatalog}
                            searchResults={modelSearchResults}
                            selectedModel={agent.model}
                            onSelect={handleSelectAgentModel}
                            onSearch={handleSearchModels}
                            onClose={() => setAgentModelPickerIdx(null)}
                            anchorRef={{ current: agentModelRefs.current[idx] }}
                          />
                        )}
                        <label className="block text-[10px] text-ink-3 mb-0.5">Model (ว่าง = auto)</label>
                        <button
                          type="button"
                          onClick={() => handleOpenAgentModelPicker(idx)}
                          className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-retro-sm border transition-colors text-left ${
                            agentModelPickerIdx === idx
                              ? 'bg-orange/10 border-orange/40 text-ink'
                              : 'bg-paper border-line text-ink-2 hover:text-ink'
                          }`}
                        >
                          {(() => {
                            const provider = getProvider(agent.model);
                            const favicon = PROVIDER_FAVICONS[provider];
                            if (favicon) {
                              return <img src={favicon} alt="" className="w-3.5 h-3.5 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                            }
                            return <Cpu className={`w-3 h-3 shrink-0 ${agentModelPickerIdx === idx ? 'text-orange' : ''}`} />;
                          })()}
                          <span className="text-xs font-medium text-ink flex-1 truncate">
                            {agent.model ? findModelName(agent.model, modelCatalog, modelSearchResults) : 'Free Router'}
                          </span>
                          <span className={`text-[8px] px-1 py-0.5 rounded-full shrink-0 ${agent.model ? 'bg-orange/15 text-orange' : 'bg-green/15 text-green'}`}>
                            {agent.model ? 'Manual' : 'Auto'}
                          </span>
                          <ChevronDown className={`w-3 h-3 shrink-0 transition-transform ${agentModelPickerIdx === idx ? 'rotate-180' : ''}`} />
                        </button>
                      </div>
                      <div>
                        <label className="block text-[10px] text-ink-3 mb-1">Tools</label>
                        <div className="grid grid-cols-2 gap-1 max-h-32 overflow-y-auto">
                          {availableTools.map((tool) => {
                            const checked = agent.tools.includes(tool.name);
                            return (
                              <label
                                key={tool.name}
                                className={`flex items-start gap-1.5 p-1.5 rounded-retro-sm cursor-pointer transition-colors text-[10px] ${
                                  checked ? 'bg-orange/10 border border-orange/30' : 'hover:bg-cream-2 border border-transparent'
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() => toggleAgentTool(idx, tool.name)}
                                  className="mt-0.5 accent-orange shrink-0"
                                />
                                <div className="min-w-0">
                                  <div className="text-ink font-medium">{tool.name}</div>
                                  <div className="text-ink-3 truncate">{tool.description}</div>
                                </div>
                              </label>
                            );
                          })}
                        </div>
                      </div>

                      {/* Expertise */}
                      <div>
                        <label className="block text-[10px] text-ink-3 mb-0.5">Expertise (คั่นด้วยจุลภาค)</label>
                        <input
                          type="text"
                          value={agent.expertise.join(', ')}
                          onChange={(e) => updateAgent(idx, 'expertise', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                          placeholder="เช่น SEO, Marketing, Data Science"
                          className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                        />
                      </div>

                      {/* Personality */}
                      <div className="space-y-1.5">
                        <label className="block text-[10px] text-ink-3">Personality</label>
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <label className="block text-[9px] text-ink-3 mb-0.5">Tone</label>
                            <input
                              type="text"
                              value={agent.personality.tone}
                              onChange={(e) => updateAgent(idx, 'personality', { ...agent.personality, tone: e.target.value })}
                              placeholder="เช่น professional"
                              className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                            />
                          </div>
                          <div>
                            <label className="block text-[9px] text-ink-3 mb-0.5">Communication</label>
                            <input
                              type="text"
                              value={agent.personality.communication_style}
                              onChange={(e) => updateAgent(idx, 'personality', { ...agent.personality, communication_style: e.target.value })}
                              placeholder="เช่น concise"
                              className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                            />
                          </div>
                          <div>
                            <label className="block text-[9px] text-ink-3 mb-0.5">Language</label>
                            <input
                              type="text"
                              value={agent.personality.language}
                              onChange={(e) => updateAgent(idx, 'personality', { ...agent.personality, language: e.target.value })}
                              placeholder="เช่น th, en"
                              className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                            />
                          </div>
                        </div>
                      </div>

                      {/* Brand Context */}
                      <div className="space-y-1.5">
                        <label className="block text-[10px] text-ink-3">Brand Context</label>
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <label className="block text-[9px] text-ink-3 mb-0.5">Brand Name</label>
                            <input
                              type="text"
                              value={agent.brand_context.brand_name}
                              onChange={(e) => updateAgent(idx, 'brand_context', { ...agent.brand_context, brand_name: e.target.value })}
                              className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                            />
                          </div>
                          <div>
                            <label className="block text-[9px] text-ink-3 mb-0.5">Guidelines</label>
                            <input
                              type="text"
                              value={agent.brand_context.guidelines}
                              onChange={(e) => updateAgent(idx, 'brand_context', { ...agent.brand_context, guidelines: e.target.value })}
                              className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                            />
                          </div>
                          <div>
                            <label className="block text-[9px] text-ink-3 mb-0.5">Target Audience</label>
                            <input
                              type="text"
                              value={agent.brand_context.target_audience}
                              onChange={(e) => updateAgent(idx, 'brand_context', { ...agent.brand_context, target_audience: e.target.value })}
                              className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                            />
                          </div>
                        </div>
                      </div>

                      {/* Output Format */}
                      <div>
                        <label className="block text-[10px] text-ink-3 mb-0.5">Output Format</label>
                        <input
                          type="text"
                          value={agent.output_format}
                          onChange={(e) => updateAgent(idx, 'output_format', e.target.value)}
                          placeholder="เช่น [Hook] [Body] [CTA] [Hashtags]"
                          className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                        />
                      </div>

                      {/* Quality Criteria */}
                      <div>
                        <label className="block text-[10px] text-ink-3 mb-0.5">Quality Criteria</label>
                        <input
                          type="text"
                          value={agent.quality_criteria}
                          onChange={(e) => updateAgent(idx, 'quality_criteria', e.target.value)}
                          placeholder="เช่น 1. ต้องมี Hook 2. ต้องมี CTA"
                          className="w-full px-2 py-1.5 bg-paper border border-line rounded-retro-sm text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-orange"
                        />
                      </div>

                      {/* Numeric settings — ∞ checked = unlimited (default), unchecked = must fill number */}
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <label className="flex items-center justify-between mb-0.5">
                            <span className="text-[10px] text-ink-3">Review Iterations</span>
                            <label className="flex items-center gap-1 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={agent.review_iterations === null}
                                onChange={(e) => updateAgent(idx, 'review_iterations', e.target.checked ? null : NaN)}
                                className="accent-orange w-2.5 h-2.5"
                              />
                              <span className="text-[9px] text-ink-3">∞ ไม่จำกัด</span>
                            </label>
                          </label>
                          <input
                            type="number"
                            min={1}
                            max={50}
                            value={agent.review_iterations ?? ''}
                            disabled={agent.review_iterations === null}
                            onChange={(e) => updateAgent(idx, 'review_iterations', parseInt(e.target.value))}
                            className={`w-full px-2 py-1.5 bg-paper border rounded-retro-sm text-xs text-ink focus:outline-none focus:border-orange disabled:opacity-40 ${
                              agent.review_iterations !== null && isNaN(agent.review_iterations) ? 'border-red-500' : 'border-line'
                            }`}
                          />
                        </div>
                        <div>
                          <label className="flex items-center justify-between mb-0.5">
                            <span className="text-[10px] text-ink-3">Max Iterations</span>
                            <label className="flex items-center gap-1 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={agent.max_iter === null}
                                onChange={(e) => updateAgent(idx, 'max_iter', e.target.checked ? null : NaN)}
                                className="accent-orange w-2.5 h-2.5"
                              />
                              <span className="text-[9px] text-ink-3">∞ ไม่จำกัด</span>
                            </label>
                          </label>
                          <input
                            type="number"
                            min={1}
                            max={500}
                            value={agent.max_iter ?? ''}
                            disabled={agent.max_iter === null}
                            onChange={(e) => updateAgent(idx, 'max_iter', parseInt(e.target.value))}
                            className={`w-full px-2 py-1.5 bg-paper border rounded-retro-sm text-xs text-ink focus:outline-none focus:border-orange disabled:opacity-40 ${
                              agent.max_iter !== null && isNaN(agent.max_iter) ? 'border-red-500' : 'border-line'
                            }`}
                          />
                        </div>
                        <div>
                          <label className="flex items-center justify-between mb-0.5">
                            <span className="text-[10px] text-ink-3">Max Retry</span>
                            <label className="flex items-center gap-1 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={agent.max_retry_limit === null}
                                onChange={(e) => updateAgent(idx, 'max_retry_limit', e.target.checked ? null : NaN)}
                                className="accent-orange w-2.5 h-2.5"
                              />
                              <span className="text-[9px] text-ink-3">∞ ไม่จำกัด</span>
                            </label>
                          </label>
                          <input
                            type="number"
                            min={0}
                            max={50}
                            value={agent.max_retry_limit ?? ''}
                            disabled={agent.max_retry_limit === null}
                            onChange={(e) => updateAgent(idx, 'max_retry_limit', parseInt(e.target.value))}
                            className={`w-full px-2 py-1.5 bg-paper border rounded-retro-sm text-xs text-ink focus:outline-none focus:border-orange disabled:opacity-40 ${
                              agent.max_retry_limit !== null && isNaN(agent.max_retry_limit) ? 'border-red-500' : 'border-line'
                            }`}
                          />
                        </div>
                      </div>

                      {/* Allow Delegation */}
                      <div>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={agent.allow_delegation}
                            onChange={(e) => updateAgent(idx, 'allow_delegation', e.target.checked)}
                            className="accent-orange"
                          />
                          <span className="text-[10px] text-ink-2">Allow Delegation</span>
                        </label>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center gap-2 p-4 border-t border-line shrink-0">
            <button
              type="submit"
              disabled={!name.trim()}
              className="flex-1 py-2 bg-orange text-white rounded-retro text-sm font-medium hover:bg-orange-light disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              สร้างทีม
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-cream-2 text-ink-2 border border-line rounded-retro text-sm font-medium hover:text-ink transition-colors"
            >
              ยกเลิก
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
