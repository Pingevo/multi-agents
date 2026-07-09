import { useState } from 'react';
import { Bot, Plus, Search, Image, Video, PenTool, Wrench } from 'lucide-react';
import type { Agent, Plan } from '../types/platform';

interface AgentPaletteProps {
  agents: Agent[];
  currentPlan: Plan | null;
  onAddAgent: () => void;
  onSelectAgent: (agent: Agent) => void;
  selectedAgentId?: string;
}

const paletteIcons: Record<string, React.ReactNode> = {
  image: <Image className="w-3.5 h-3.5" />,
  video: <Video className="w-3.5 h-3.5" />,
  copywriter: <PenTool className="w-3.5 h-3.5" />,
  default: <Bot className="w-3.5 h-3.5" />,
};

const getAgentIcon = (name: string) => {
  const lower = name.toLowerCase();
  if (lower.includes('image') || lower.includes('visual')) return paletteIcons.image;
  if (lower.includes('video')) return paletteIcons.video;
  if (lower.includes('copy') || lower.includes('writer') || lower.includes('content')) return paletteIcons.copywriter;
  return paletteIcons.default;
};

const avatarColors = [
  'text-blue-400 bg-blue-500/10',
  'text-green-400 bg-green-500/10',
  'text-purple-400 bg-purple-500/10',
  'text-orange-400 bg-orange-500/10',
  'text-pink-400 bg-pink-500/10',
  'text-cyan-400 bg-cyan-500/10',
];

const getAvatarColor = (name: string) => {
  const hash = name.charCodeAt(0) + (name.charCodeAt(1) || 0);
  return avatarColors[hash % avatarColors.length];
};

export const AgentPalette: React.FC<AgentPaletteProps> = ({
  agents,
  currentPlan,
  onAddAgent,
  onSelectAgent,
  selectedAgentId,
}) => {
  const [search, setSearch] = useState('');

  const existingNames = new Set(agents.map((a) => a.name));
  const suggestedAgents = currentPlan?.agents.filter((a) => !existingNames.has(a.name)) || [];

  const filtered = agents.filter((a) =>
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    a.role.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="w-56 shrink-0 border-r border-border bg-surface flex flex-col">
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-text-2 uppercase tracking-wider">Agents</span>
          <button
            onClick={onAddAgent}
            className="p-1 rounded-md text-text-2 hover:text-accent hover:bg-surface-2 transition-colors"
            title="Add Agent"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="relative">
          <Search className="w-3 h-3 text-text-3 absolute left-2 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search agents..."
            className="w-full bg-surface-2 border border-border rounded-md pl-7 pr-2 py-1 text-xs text-text placeholder:text-text-3 focus:outline-none focus:border-accent"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {suggestedAgents.length > 0 && (
          <div className="mb-2">
            <div className="text-[10px] font-semibold text-accent uppercase tracking-wider px-1 mb-1 flex items-center gap-1">
              <Wrench className="w-2.5 h-2.5" />
              AI Suggested
            </div>
            {suggestedAgents.map((agent, idx) => (
              <div
                key={`suggested-${idx}`}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('application/agent', JSON.stringify(agent));
                  e.dataTransfer.effectAllowed = 'move';
                }}
                className="flex items-center gap-2 px-2 py-1.5 rounded-md cursor-grab hover:bg-surface-2 transition-colors group border border-accent/20 bg-accent/5"
                title="Drag to canvas"
              >
                <div className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 ${getAvatarColor(agent.name)}`}>
                  {getAgentIcon(agent.name)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-text truncate">{agent.name}</div>
                  <div className="text-[10px] text-text-2 truncate">{agent.role}</div>
                </div>
                <span className="text-[9px] px-1 py-0.5 rounded-full bg-accent/10 text-accent shrink-0">New</span>
              </div>
            ))}
          </div>
        )}

        <div className="text-[10px] font-semibold text-text-2 uppercase tracking-wider px-1 mb-1">
          Existing ({filtered.length})
        </div>
        {filtered.length === 0 ? (
          <div className="text-xs text-text-3 text-center py-4">
            {search ? 'No matches' : 'No agents yet'}
          </div>
        ) : (
          filtered.map((agent) => (
            <div
              key={agent.id}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/agent', JSON.stringify(agent));
                e.dataTransfer.effectAllowed = 'move';
              }}
              onClick={() => onSelectAgent(agent)}
              className={`flex items-center gap-2 px-2 py-1.5 rounded-md cursor-grab transition-colors group ${
                selectedAgentId === agent.id
                  ? 'bg-accent/10 text-text'
                  : 'text-text-2 hover:bg-surface-2'
              }`}
            >
              <div className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 ${getAvatarColor(agent.name)}`}>
                {getAgentIcon(agent.name)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-text truncate">{agent.name}</div>
                <div className="text-[10px] text-text-2 truncate">{agent.role}</div>
              </div>
              <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                agent.status === 'Idle' ? 'bg-success' : 'bg-warning'
              }`} />
            </div>
          ))
        )}
      </div>
    </div>
  );
};
