import { useState } from 'react';
import { Plus, Rocket, Pencil, Trash2, Bot, Search } from 'lucide-react';
import type { Agent, AgentFormData, AssignFormData, ToolCatalogEntry } from '../types/platform';
import { AgentFormModal } from './AgentFormModal';
import { AssignTaskModal } from './AssignTaskModal';

interface AgentSidebarProps {
  agents: Agent[];
  availableTools: ToolCatalogEntry[];
  onAddAgent: (data: AgentFormData) => void;
  onEditAgent: (data: AgentFormData) => void;
  onDeleteAgent: (agentId: string) => void;
  onAssignTask: (data: AssignFormData) => void;
}

const avatarColors = [
  'bg-blue-500/20 text-blue-400',
  'bg-green-500/20 text-green-400',
  'bg-purple-500/20 text-purple-400',
  'bg-orange-500/20 text-orange-400',
  'bg-pink-500/20 text-pink-400',
  'bg-cyan-500/20 text-cyan-400',
];

const getAvatarColor = (name: string) => {
  const hash = name.charCodeAt(0) + (name.charCodeAt(1) || 0);
  return avatarColors[hash % avatarColors.length];
};

export const AgentSidebar: React.FC<AgentSidebarProps> = ({
  agents,
  availableTools,
  onAddAgent,
  onEditAgent,
  onDeleteAgent,
  onAssignTask,
}) => {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'Idle' | 'Busy'>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [showAddModal, setShowAddModal] = useState(false);
  const [editAgent, setEditAgent] = useState<Agent | null>(null);
  const [assignAgent, setAssignAgent] = useState<Agent | null>(null);

  const handleDelete = (agentId: string, name: string) => {
    if (confirm(`Delete agent "${name}"?`)) {
      onDeleteAgent(agentId);
    }
  };

  const filtered = agents.filter((a) => {
    const matchesSearch =
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.role.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = filterStatus === 'all' || a.status === filterStatus;
    return matchesSearch && matchesStatus;
  });

  return (
    <>
      <aside className="w-72 bg-surface border-r border-border flex flex-col shrink-0">
        <div className="p-3 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-accent" />
            <h2 className="font-semibold text-sm">Agent Registry</h2>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="p-1.5 rounded-md bg-accent text-white hover:bg-accent-hover transition-colors"
            title="Add Agent"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        <div className="p-3 border-b border-border space-y-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search agents..."
              className="w-full bg-surface-2 border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-text placeholder:text-text-2 focus:outline-none focus:border-accent"
            />
          </div>
          <div className="flex gap-1">
            {(['all', 'Idle', 'Busy'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setFilterStatus(s)}
                className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  filterStatus === s
                    ? 'bg-accent text-white'
                    : 'bg-surface-2 text-text-2 hover:bg-border'
                }`}
              >
                {s === 'all' ? 'All' : s}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {filtered.length === 0 ? (
            <div className="text-sm text-text-2 text-center py-8">
              {agents.length === 0 ? 'No agents yet' : 'No matches found'}
            </div>
          ) : (
            filtered.map((agent) => {
              const isExpanded = expandedId === agent.id;
              return (
                <div
                  key={agent.id}
                  className="rounded-lg border border-border bg-surface-2 hover:border-accent/40 transition-colors"
                >
                  <div
                    className="p-3 cursor-pointer"
                    onClick={() => setExpandedId(isExpanded ? null : agent.id)}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <div
                          className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${getAvatarColor(agent.name)}`}
                        >
                          {agent.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div className="font-medium text-sm text-text">{agent.name}</div>
                          <div className="text-xs text-text-2">{agent.role}</div>
                        </div>
                      </div>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          agent.status === 'Idle'
                            ? 'bg-success/10 text-success'
                            : 'bg-warning/10 text-warning'
                        }`}
                      >
                        {agent.status}
                      </span>
                    </div>
                    {!isExpanded && agent.goal && (
                      <div className="text-xs text-text-2 truncate mt-1">{agent.goal}</div>
                    )}
                  </div>

                  {isExpanded && (
                    <div className="px-3 pb-3 space-y-2">
                      {agent.goal && (
                        <div className="text-xs text-text-2">
                          <span className="font-medium text-text">Goal:</span> {agent.goal}
                        </div>
                      )}
                      {agent.persona && (
                        <div className="text-xs text-text-2">
                          <span className="font-medium text-text">Persona:</span> {agent.persona}
                        </div>
                      )}
                      <div className="text-xs text-text-2">
                        <span className="font-medium text-text">Tools:</span>{' '}
                        {agent.tools.length ? agent.tools.join(', ') : '-'}
                      </div>
                      <div className="text-xs text-text-2">
                        <span className="font-medium text-text">Model:</span>{' '}
                        {agent.model || 'Auto (system default)'}
                      </div>
                    </div>
                  )}

                  <div className="flex gap-1 px-3 pb-2 border-t border-border/50 pt-2">
                    <button
                      onClick={() => setAssignAgent(agent)}
                      disabled={agent.status !== 'Idle'}
                      className="p-1.5 rounded-md hover:bg-border text-text-2 disabled:opacity-30 disabled:cursor-not-allowed"
                      title="Assign Task"
                    >
                      <Rocket className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setEditAgent(agent)}
                      className="p-1.5 rounded-md hover:bg-border text-text-2"
                      title="Edit"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDelete(agent.id, agent.name)}
                      className="p-1.5 rounded-md hover:bg-border text-danger"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>

      <AgentFormModal
        open={showAddModal}
        mode="add"
        availableTools={availableTools}
        onSubmit={onAddAgent}
        onClose={() => setShowAddModal(false)}
      />
      <AgentFormModal
        open={!!editAgent}
        mode="edit"
        agent={editAgent}
        availableTools={availableTools}
        onSubmit={onEditAgent}
        onClose={() => setEditAgent(null)}
      />
      <AssignTaskModal
        open={!!assignAgent}
        agent={assignAgent}
        onSubmit={onAssignTask}
        onClose={() => setAssignAgent(null)}
      />
    </>
  );
};
