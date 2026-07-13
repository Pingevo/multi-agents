import { useState, useEffect, useRef } from 'react';
import { X, Save, Cpu, ChevronDown } from 'lucide-react';
import { ModelPicker, type ModelCatalogEntry } from './ModelPicker';
import type { Agent } from '../types/platform';

interface AgentConfigModalProps {
  open: boolean;
  agent: Agent | null;
  availableTools: Array<{ name: string; description: string }>;
  onClose: () => void;
  onSave: (data: { agent_id: string; name: string; role: string; goal: string; persona: string; model: string; tools: string[] }) => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  onSearchModels?: (query: string) => void;
  onFetchModelCatalog?: () => void;
}

function findModelName(modelId: string, catalog: Record<string, ModelCatalogEntry[]> | undefined): string {
  if (!modelId || !catalog) return modelId || 'auto';
  for (const category of Object.values(catalog)) {
    const found = category.find((m) => m.id === modelId);
    if (found) return found.name;
  }
  return modelId;
}

export const AgentConfigModal: React.FC<AgentConfigModalProps> = ({
  open,
  agent,
  availableTools,
  onClose,
  onSave,
  modelCatalog,
  modelSearchResults,
  onSearchModels,
  onFetchModelCatalog,
}) => {
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [goal, setGoal] = useState('');
  const [persona, setPersona] = useState('');
  const [model, setModel] = useState('');
  const [tools, setTools] = useState<string[]>([]);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const modelBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (agent) {
      setName(agent.name || '');
      setRole(agent.role || '');
      setGoal(agent.goal || '');
      setPersona(agent.persona || '');
      setModel(agent.model || '');
      setTools(agent.tools || []);
    }
  }, [agent]);

  if (!open || !agent) return null;

  const handleSave = () => {
    onSave({
      agent_id: agent.id,
      name: name.trim(),
      role: role.trim(),
      goal: goal.trim(),
      persona: persona.trim(),
      model,
      tools,
    });
    onClose();
  };

  const toggleTool = (toolName: string) => {
    setTools((prev) =>
      prev.includes(toolName) ? prev.filter((t) => t !== toolName) : [...prev, toolName]
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-lg max-h-[85vh] overflow-auto bg-surface border border-border rounded-2xl shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text">
            Configure {agent.is_manager ? 'Manager' : 'Agent'}
          </h2>
          <button onClick={onClose} className="p-1 text-text-3 hover:text-text transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-text-2 mb-1.5">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-2 mb-1.5">Role</label>
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-2 mb-1.5">Goal</label>
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/50 resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-2 mb-1.5">Persona / Backstory</label>
            <textarea
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/50 resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-2 mb-1.5">Model</label>
            <button
              ref={modelBtnRef}
              onClick={() => {
                if (onFetchModelCatalog) onFetchModelCatalog();
                setModelPickerOpen(true);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text hover:border-accent/50 transition-colors"
            >
              <Cpu className="w-4 h-4 text-text-2" />
              <span className={`flex-1 text-left truncate ${model ? 'text-text' : 'text-text-3'}`}>
                {model ? findModelName(model, modelCatalog) : 'auto'}
              </span>
              {model && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-success/15 text-success font-medium">Manual</span>
              )}
              {!model && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-success/15 text-success font-medium">Auto</span>
              )}
              <ChevronDown className="w-3 h-3 text-text-2" />
            </button>
            {modelPickerOpen && modelBtnRef.current && (
              <ModelPicker
                recommended={modelCatalog || {}}
                searchResults={modelSearchResults || []}
                selectedModel={model}
                onSelect={(modelId) => { setModel(modelId); setModelPickerOpen(false); }}
                onSearch={(query) => onSearchModels?.(query)}
                onClose={() => setModelPickerOpen(false)}
                anchorRef={modelBtnRef}
                showAutoRouter
              />
            )}
            {model && (
              <button
                onClick={() => setModel('')}
                className="text-[10px] text-text-3 hover:text-text mt-1"
              >
                Reset to auto
              </button>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-text-2 mb-1.5">Tools / Capabilities</label>
            <div className="flex flex-wrap gap-2">
              {availableTools.map((tool) => (
                <button
                  key={tool.name}
                  onClick={() => toggleTool(tool.name)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
                    tools.includes(tool.name)
                      ? 'bg-accent/15 text-accent border-accent/30'
                      : 'bg-surface-2 text-text-2 border-border hover:border-accent/30'
                  }`}
                  title={tool.description}
                >
                  {tool.name}
                </button>
              ))}
              {availableTools.length === 0 && (
                <span className="text-xs text-text-3">No tools available</span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <button
              onClick={handleSave}
              className="flex-1 flex items-center justify-center gap-2 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
            >
              <Save className="w-4 h-4" />
              Save Changes
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-surface-2 text-text-2 border border-border rounded-lg text-sm font-medium hover:text-text transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
