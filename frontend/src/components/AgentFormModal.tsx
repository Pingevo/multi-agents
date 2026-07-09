import { useState, useEffect } from 'react';
import { X, Wrench } from 'lucide-react';
import type { Agent, AgentFormData, ToolCatalogEntry } from '../types/platform';

interface AgentFormModalProps {
  open: boolean;
  mode: 'add' | 'edit';
  agent?: Agent | null;
  availableTools: ToolCatalogEntry[];
  onSubmit: (data: AgentFormData) => void;
  onClose: () => void;
}

export const AgentFormModal: React.FC<AgentFormModalProps> = ({
  open,
  mode,
  agent,
  availableTools,
  onSubmit,
  onClose,
}) => {
  const [form, setForm] = useState<AgentFormData>({
    name: '',
    role: '',
    goal: '',
    persona: '',
    tools: '',
    model: '',
  });

  useEffect(() => {
    if (open) {
      if (mode === 'edit' && agent) {
        setForm({
          agent_id: agent.id,
          name: agent.name,
          role: agent.role,
          goal: agent.goal || '',
          persona: agent.persona || '',
          tools: agent.tools.join(', '),
          model: agent.model || '',
        });
      } else {
        setForm({ name: '', role: '', goal: '', persona: '', tools: '', model: '' });
      }
    }
  }, [open, mode, agent]);

  const selectedTools = form.tools ? form.tools.split(',').map((t) => t.trim()).filter(Boolean) : [];

  const toggleTool = (toolName: string) => {
    const next = selectedTools.includes(toolName)
      ? selectedTools.filter((t) => t !== toolName)
      : [...selectedTools, toolName];
    setForm({ ...form, tools: next.join(', ') });
  };

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.role.trim()) return;
    onSubmit(form);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-full max-w-md bg-surface rounded-xl border border-border shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="font-semibold text-sm text-text">
            {mode === 'add' ? 'Add New Agent' : 'Edit Agent'}
          </h2>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-surface-2 text-text-2">
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-3">
          <div>
            <label className="block text-xs text-text-2 mb-1">Name *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Research Agent"
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-2 focus:outline-none focus:border-accent"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs text-text-2 mb-1">Role *</label>
            <input
              type="text"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              placeholder="e.g. Data Analyst"
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-2 focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <label className="block text-xs text-text-2 mb-1">Goal</label>
            <input
              type="text"
              value={form.goal}
              onChange={(e) => setForm({ ...form, goal: e.target.value })}
              placeholder="e.g. Find and summarize information"
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-2 focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <label className="block text-xs text-text-2 mb-1">Persona / Backstory</label>
            <textarea
              value={form.persona}
              onChange={(e) => setForm({ ...form, persona: e.target.value })}
              placeholder="Describe the agent's personality and expertise..."
              rows={3}
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-2 focus:outline-none focus:border-accent resize-none"
            />
          </div>
          <div>
            <label className="block text-xs text-text-2 mb-1.5">Tools</label>
            <div className="space-y-1.5 max-h-40 overflow-y-auto rounded-lg border border-border bg-surface-2 p-2">
              {availableTools.length === 0 ? (
                <div className="text-xs text-text-2 py-2 text-center">No tools available</div>
              ) : (
                availableTools.map((tool) => {
                  const checked = selectedTools.includes(tool.name);
                  return (
                    <label
                      key={tool.name}
                      className={`flex items-start gap-2 p-2 rounded-md cursor-pointer transition-colors ${
                        checked ? 'bg-accent/10 border border-accent/30' : 'hover:bg-border/50 border border-transparent'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleTool(tool.name)}
                        className="mt-0.5 accent-accent"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <Wrench className="w-3 h-3 text-text-2 shrink-0" />
                          <span className="text-sm text-text font-medium">{tool.name}</span>
                        </div>
                        <p className="text-xs text-text-2 mt-0.5">{tool.description}</p>
                      </div>
                    </label>
                  );
                })
              )}
            </div>
            {selectedTools.length > 0 && (
              <p className="text-xs text-text-2 mt-1">{selectedTools.length} tool(s) selected</p>
            )}
          </div>
          <div>
            <label className="block text-xs text-text-2 mb-1">Model</label>
            <input
              type="text"
              value={form.model || ''}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              placeholder="e.g. openrouter/auto (leave empty for system default)"
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-2 focus:outline-none focus:border-accent"
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={!form.name.trim() || !form.role.trim()}
              className="flex-1 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors"
            >
              {mode === 'add' ? 'Create Agent' : 'Save Changes'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-surface-2 text-text-2"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
