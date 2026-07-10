import { X, Pencil, Trash2, Rocket, Bot, Wrench } from 'lucide-react';
import type { Agent, ToolCatalogEntry } from '../types/platform';
import type { AgentProgressEntry } from './chatTypes';

interface DetailPanelProps {
  agent: Agent | null;
  progress?: AgentProgressEntry;
  availableTools: ToolCatalogEntry[];
  onClose: () => void;
  onEdit: (agent: Agent) => void;
  onDelete: (agentId: string) => void;
  onAssignTask: (agent: Agent) => void;
}

export const DetailPanel: React.FC<DetailPanelProps> = ({
  agent,
  progress,
  onClose,
  onEdit,
  onDelete,
  onAssignTask,
}) => {
  if (!agent) return null;

  const status = progress?.status || 'pending';
  const isRunning = status === 'running';
  const isComplete = status === 'complete';

  return (
    <div className="w-56 shrink-0 border-r border-border bg-surface flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border">
        <div className="flex items-center gap-2">
          <button
            onClick={onClose}
            className="p-1 rounded-md text-text-2 hover:text-text hover:bg-surface-2 transition-colors"
            title="Back to agents"
          >
            <X className="w-3.5 h-3.5" />
          </button>
          <h3 className="font-semibold text-xs text-text">Agent Details</h3>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {/* Agent identity */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-accent shrink-0" />
            <div className="text-sm font-semibold text-text truncate">{agent.name}</div>
          </div>
          <div className="text-xs text-text-2">{agent.role}</div>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
              isRunning ? 'bg-accent/10 text-accent' :
              isComplete ? 'bg-success/10 text-success' :
              agent.status === 'Idle' ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'
            }`}>
              {isRunning ? 'Running' : isComplete ? 'Complete' : agent.status}
            </span>
            {progress?.progress !== undefined && progress.progress > 0 && (
              <span className="text-[10px] text-text-2">{progress.progress}%</span>
            )}
          </div>
        </div>

        {/* Progress bar */}
        {progress?.progress !== undefined && progress.progress > 0 && (
          <div>
            <div className="w-full bg-surface-2 rounded-full h-1.5 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  isComplete ? 'bg-success' : 'bg-gradient-to-r from-accent to-accent-light'
                }`}
                style={{ width: `${progress.progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Current tool */}
        {isRunning && progress?.current_tool && (
          <div className="p-2 rounded-lg bg-surface-2 border border-accent/20">
            <div className="flex items-center gap-1.5 mb-1">
              <Wrench className="w-2.5 h-2.5 text-accent" />
              <span className="text-[10px] font-medium text-accent">Current Tool</span>
            </div>
            <div className="text-[11px] text-text">{progress.tool_description || progress.current_tool}</div>
          </div>
        )}

        {/* Output preview */}
        {progress?.output && (
          <div>
            <div className="text-[10px] font-medium text-text-2 mb-1">Output Preview</div>
            <div className="text-[11px] text-text-2 bg-surface-2 rounded-lg p-2 max-h-48 overflow-y-auto whitespace-pre-wrap border border-border">
              {progress.output}
            </div>
          </div>
        )}

        {/* Goal */}
        {agent.goal && (
          <div>
            <div className="text-[10px] font-medium text-text-2 mb-1">Goal</div>
            <div className="text-xs text-text bg-surface-2 rounded-lg p-2 border border-border">
              {agent.goal}
            </div>
          </div>
        )}

        {/* Persona */}
        {agent.persona && (
          <div>
            <div className="text-[10px] font-medium text-text-2 mb-1">Persona</div>
            <div className="text-xs text-text-2 bg-surface-2 rounded-lg p-2 border border-border">
              {agent.persona}
            </div>
          </div>
        )}

        {/* Tools */}
        <div>
          <div className="text-[10px] font-medium text-text-2 mb-1">Tools & Capabilities</div>
          <div className="flex flex-wrap gap-1">
            {agent.tools.length > 0 ? (
              agent.tools.map((tool, i) => (
                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/10 text-accent flex items-center gap-0.5">
                  <Wrench className="w-2 h-2" />
                  {tool}
                </span>
              ))
            ) : (
              <span className="text-[10px] text-text-3">No tools assigned</span>
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="border-t border-border p-2 flex gap-1.5">
        <button
          onClick={() => onAssignTask(agent)}
          disabled={agent.status !== 'Idle' && !isComplete}
          className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg bg-accent text-white text-[10px] font-medium hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <Rocket className="w-3 h-3" />
          Assign Task
        </button>
        <button
          onClick={() => onEdit(agent)}
          className="p-1.5 rounded-lg border border-border text-text-2 hover:text-text hover:bg-surface-2 transition-colors"
          title="Edit Agent"
        >
          <Pencil className="w-3 h-3" />
        </button>
        <button
          onClick={() => { if (confirm(`Delete agent "${agent.name}"?`)) onDelete(agent.id); }}
          className="p-1.5 rounded-lg border border-border text-text-2 hover:text-danger hover:bg-surface-2 transition-colors"
          title="Delete Agent"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
};
