import { useState, useEffect, useRef } from 'react';
import { X, Cpu, ChevronDown } from 'lucide-react';
import { ModelPicker, findModelName, getProvider, PROVIDER_FAVICONS, type ModelCatalogEntry } from './ModelPicker';
import type { Agent } from '../types/platform';

interface AgentConfigModalProps {
  open: boolean;
  agent: Agent | null;
  availableTools: Array<{ name: string; description: string }>;
  onClose: () => void;
  onSave: (data: { agent_id: string; name: string; role: string; goal: string; persona: string; model: string; tools: string[]; expertise?: string[]; personality?: Record<string, string>; brand_context?: Record<string, string> }) => void;
  onAction?: (name: string, payload?: Record<string, any>) => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  onSearchModels?: (query: string) => void;
  onFetchModelCatalog?: () => void;
  selectedModel?: string;
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
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
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
    }
  }, [agent, selectedModel]);

  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

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
    });
    onClose();
  };

  const toggleTool = (toolName: string) => {
    setTools((prev) =>
      prev.includes(toolName) ? prev.filter((t) => t !== toolName) : [...prev, toolName]
    );
  };

  const startEdit = (field: string, value: string) => {
    setEditingField(field);
    setEditValue(value);
  };

  const saveEdit = (field: string) => {
    if (field === 'name') setName(editValue);
    else if (field === 'role') setRole(editValue);
    else if (field === 'goal') setGoal(editValue);
    else if (field === 'persona') setPersona(editValue);
    else if (field.startsWith('personality.')) setPersonality(prev => ({ ...prev, [field.slice(12)]: editValue }));
    else if (field.startsWith('brand.')) setBrandContext(prev => ({ ...prev, [field.slice(6)]: editValue }));
    setEditingField(null);
  };

  if (!open || !agent) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-[420px] max-h-[85vh] overflow-auto bg-surface border border-border rounded-2xl shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-semibold text-text">ตั้งค่า Agent</h2>
          <button onClick={onClose} className="p-1 text-text-3 hover:text-text transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <p className="text-xs text-text-3 mb-4">{agent.name} · {agent.role}</p>

        <div className="space-y-0">
          {/* Name */}
          <div className="flex items-center justify-between py-2.5 border-b border-border">
            <span className="text-xs text-text-2">ชื่อ</span>
            {editingField === 'name' ? (
              <div className="flex items-center gap-1.5">
                <input
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') saveEdit('name'); if (e.key === 'Escape') setEditingField(null); }}
                  className="px-2 py-1 bg-bg border border-border rounded text-xs text-text focus:outline-none focus:border-accent w-32 text-right"
                />
                <button onClick={() => saveEdit('name')} className="text-[10px] text-accent">บันทึก</button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-text">{name}</span>
                <button onClick={() => startEdit('name', name)} className="text-[10px] text-accent">แก้ไข</button>
              </div>
            )}
          </div>

          {/* Role */}
          <div className="flex items-center justify-between py-2.5 border-b border-border">
            <span className="text-xs text-text-2">Role</span>
            {editingField === 'role' ? (
              <div className="flex items-center gap-1.5">
                <input
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') saveEdit('role'); if (e.key === 'Escape') setEditingField(null); }}
                  className="px-2 py-1 bg-bg border border-border rounded text-xs text-text focus:outline-none focus:border-accent w-32 text-right"
                />
                <button onClick={() => saveEdit('role')} className="text-[10px] text-accent">บันทึก</button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-text">{role}</span>
                <button onClick={() => startEdit('role', role)} className="text-[10px] text-accent">แก้ไข</button>
              </div>
            )}
          </div>

          {/* Goal */}
          <div className="flex items-center justify-between py-2.5 border-b border-border">
            <span className="text-xs text-text-2">Goal</span>
            {editingField === 'goal' ? (
              <div className="flex items-center gap-1.5">
                <textarea
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  rows={2}
                  className="px-2 py-1 bg-bg border border-border rounded text-[11px] text-text focus:outline-none focus:border-accent w-48 text-right resize-none"
                />
                <button onClick={() => saveEdit('goal')} className="text-[10px] text-accent shrink-0">บันทึก</button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-text max-w-[200px] text-right truncate">{goal || '—'}</span>
                <button onClick={() => startEdit('goal', goal)} className="text-[10px] text-accent shrink-0">แก้ไข</button>
              </div>
            )}
          </div>

          {/* Persona */}
          <div className="flex items-center justify-between py-2.5 border-b border-border">
            <span className="text-xs text-text-2">Persona</span>
            {editingField === 'persona' ? (
              <div className="flex items-center gap-1.5">
                <textarea
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  rows={3}
                  className="px-2 py-1 bg-bg border border-border rounded text-[11px] text-text focus:outline-none focus:border-accent w-48 text-right resize-none"
                />
                <button onClick={() => saveEdit('persona')} className="text-[10px] text-accent shrink-0">บันทึก</button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-text max-w-[200px] text-right truncate">{persona || '—'}</span>
                <button onClick={() => startEdit('persona', persona)} className="text-[10px] text-accent shrink-0">แก้ไข</button>
              </div>
            )}
          </div>

          {/* Model */}
          <div className="py-2.5 border-b border-border">
            <span className="text-xs text-text-2 block mb-1">Model</span>
            {isManager && (
              <div className="text-[10px] text-text-3 px-2 py-1 rounded-md bg-surface-2 border border-border mb-1">
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
          </div>

          {/* Tools */}
          <div className="flex items-center justify-between py-2.5 border-b border-border">
            <span className="text-xs text-text-2">Tools</span>
            <div className="flex items-center gap-1.5 flex-wrap justify-end">
              {tools.map((tool) => (
                <span
                  key={tool}
                  className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-2 flex items-center gap-1"
                >
                  {tool}
                  <button
                    onClick={() => toggleTool(tool)}
                    className="text-text-3 hover:text-danger"
                  >✕</button>
                </span>
              ))}
              <button
                onClick={() => {
                  const available = availableTools.find(t => !tools.includes(t.name));
                  if (available) toggleTool(available.name);
                }}
                className="text-[10px] text-accent"
              >+ เพิ่ม</button>
            </div>
          </div>

          {/* Expertise */}
          <div className="py-2.5 border-b border-border">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-text-2">Expertise</span>
              <button
                onClick={() => {
                  const val = prompt('เพิ่ม expertise:');
                  if (val && val.trim()) setExpertise(prev => [...prev, val.trim()]);
                }}
                className="text-[10px] text-accent"
              >+ เพิ่ม</button>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {expertise.map((exp) => (
                <span key={exp} className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-2 flex items-center gap-1">
                  {exp}
                  <button onClick={() => setExpertise(prev => prev.filter(e => e !== exp))} className="text-text-3 hover:text-danger">✕</button>
                </span>
              ))}
              {expertise.length === 0 && <span className="text-[11px] text-text-3">—</span>}
            </div>
          </div>

          {/* Personality */}
          <div className="py-2.5 border-b border-border">
            <div className="text-xs text-text-2 mb-2">Personality</div>
            <div className="space-y-1.5">
              {['tone', 'communication_style', 'language'].map((key) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-[11px] text-text-3 capitalize">{key.replace('_', ' ')}</span>
                  {editingField === `personality.${key}` ? (
                    <div className="flex items-center gap-1.5">
                      <input
                        autoFocus
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') saveEdit(`personality.${key}`); if (e.key === 'Escape') setEditingField(null); }}
                        className="px-2 py-1 bg-bg border border-border rounded text-xs text-text focus:outline-none focus:border-accent w-32 text-right"
                      />
                      <button onClick={() => saveEdit(`personality.${key}`)} className="text-[10px] text-accent">บันทึก</button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-text max-w-[200px] text-right truncate">{personality[key] || '—'}</span>
                      <button onClick={() => startEdit(`personality.${key}`, personality[key] || '')} className="text-[10px] text-accent">แก้ไข</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Brand Context */}
          <div className="py-2.5 border-b border-border">
            <div className="text-xs text-text-2 mb-2">Brand Context</div>
            <div className="space-y-1.5">
              {['brand_name', 'guidelines', 'target_audience'].map((key) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-[11px] text-text-3 capitalize">{key.replace('_', ' ')}</span>
                  {editingField === `brand.${key}` ? (
                    <div className="flex items-center gap-1.5">
                      <input
                        autoFocus
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') saveEdit(`brand.${key}`); if (e.key === 'Escape') setEditingField(null); }}
                        className="px-2 py-1 bg-bg border border-border rounded text-xs text-text focus:outline-none focus:border-accent w-32 text-right"
                      />
                      <button onClick={() => saveEdit(`brand.${key}`)} className="text-[10px] text-accent">บันทึก</button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-text max-w-[200px] text-right truncate">{brandContext[key] || '—'}</span>
                      <button onClick={() => startEdit(`brand.${key}`, brandContext[key] || '')} className="text-[10px] text-accent">แก้ไข</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Learnings */}
          <div className="flex items-center justify-between py-2.5">
            <span className="text-xs text-text-2">Learnings</span>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-text-3">{(agent as any).learnings?.length || 0} entries</span>
              <button className="text-[10px] text-accent">ดู</button>
            </div>
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
