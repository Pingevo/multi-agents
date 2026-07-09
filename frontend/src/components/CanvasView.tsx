import { useState } from 'react';
import { Bot, CheckCircle, Clock, Trash2, ChevronDown, ChevronRight, ImageIcon } from 'lucide-react';
import type { Agent, Task, Plan, ToolCatalogEntry, AgentProgress } from '../types/platform';
import { AgentNode, UserNode, ManagerNode, OutputNode } from './AgentNode';
import type { AgentProgressEntry } from './ChatPanel';

interface CanvasViewProps {
  agents: Agent[];
  tasks: Task[];
  currentPlan: Plan | null;
  agentProgress?: AgentProgressEntry[];
  availableTools: ToolCatalogEntry[];
  onAddAgent: (data: any) => void;
  onEditAgent: (data: any) => void;
  onDeleteAgent: (id: string) => void;
  onAssignTask: (data: any) => void;
  onAcceptPlan: () => void;
  onRejectPlan: () => void;
  onCancelPlan: () => void;
  onDeleteTask: (taskId: string) => void;
  onSelectAgent: (agent: Agent) => void;
  selectedAgentId?: string;
  latestUserMessage?: string;
}

export const CanvasView: React.FC<CanvasViewProps> = ({
  agents,
  tasks,
  currentPlan,
  agentProgress,
  availableTools,
  onAcceptPlan,
  onRejectPlan,
  onCancelPlan,
  onDeleteTask,
  onSelectAgent,
  selectedAgentId,
  latestUserMessage,
}) => {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const getProgressForAgent = (agentName: string): AgentProgressEntry | undefined => {
    return agentProgress?.find((p) => p.name === agentName);
  };

  const toggleCollapsed = (taskId: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  const runningTasks = tasks.filter((t) => t.status === 'running').length;
  const completedTasks = tasks.filter((t) => t.status === 'complete').length;

  return (
    <div className="flex-1 flex min-w-0 bg-bg overflow-hidden">
      {/* Canvas area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Plan approval banner */}
        {currentPlan && (
          <div className="mx-6 mt-4 p-4 rounded-xl border border-accent/30 bg-surface/80 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-accent" />
                <h3 className="font-semibold text-sm text-text">Plan Approval Required</h3>
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent">
                {currentPlan.agents.length} agent(s) · {currentPlan.plan_type === 'existing' ? 'Existing' : 'New'}
              </span>
            </div>
            <div className="text-sm text-text-2 mb-3">
              Task: <span className="text-text">{currentPlan.task_description}</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={onAcceptPlan}
                className="px-3 py-1.5 rounded-md bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
              >
                Accept
              </button>
              <button
                onClick={onRejectPlan}
                className="px-3 py-1.5 rounded-md border border-border text-sm font-medium hover:bg-surface-2 text-text-2 transition-colors"
              >
                Reject
              </button>
              <button
                onClick={onCancelPlan}
                className="px-3 py-1.5 rounded-md border border-border text-sm font-medium hover:bg-surface-2 text-danger transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Node graph */}
        <div className="flex-1 flex flex-col items-center justify-center p-8 gap-6">
          {/* Row 1: User → Manager → Output */}
          <div className="flex items-center gap-8">
            <UserNode label={latestUserMessage || 'Type a message below'} />
            <ConnectionLine />
            <ManagerNode isThinking={runningTasks > 0} />
            <ConnectionLine />
            <OutputNode taskCount={completedTasks} />
          </div>

          {/* Branch lines to workers */}
          {agents.length > 0 && (
            <div className="flex flex-col items-center gap-2">
              <div className="w-px h-6 bg-border-light" />
              <div className="w-32 h-px bg-border-light" />
            </div>
          )}

          {/* Row 2: Worker agents */}
          {agents.length > 0 && (
            <div className="flex flex-wrap justify-center gap-4 max-w-3xl">
              {agents.map((agent) => (
                <AgentNode
                  key={agent.id}
                  agent={agent}
                  progress={getProgressForAgent(agent.name)}
                  onClick={() => onSelectAgent(agent)}
                  isSelected={selectedAgentId === agent.id}
                />
              ))}
            </div>
          )}

          {agents.length === 0 && !currentPlan && (
            <div className="flex flex-col items-center justify-center py-16 text-text-2">
              <Bot className="w-12 h-12 mb-3 opacity-30" />
              <p className="text-sm">No agents yet</p>
              <p className="text-xs mt-1">Type a message below to let the AI plan your team</p>
            </div>
          )}
        </div>

        {/* Task list at bottom */}
        {tasks.length > 0 && (
          <div className="border-t border-border p-4 space-y-2 max-h-64 overflow-y-auto">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-text-2" />
              <h3 className="font-semibold text-sm text-text">Tasks</h3>
              <span className="text-xs text-text-2 ml-auto">
                {runningTasks} running / {tasks.length} total
              </span>
            </div>
            {tasks.map((task) => {
              const isCollapsed = collapsed.has(task.id);
              const statusColor =
                task.status === 'running' ? 'text-accent' :
                task.status === 'complete' ? 'text-success' :
                task.status === 'error' ? 'text-danger' : 'text-text-2';
              return (
                <div key={task.id} className="rounded-lg border border-border bg-surface overflow-hidden">
                  <div className="flex items-center justify-between p-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => toggleCollapsed(task.id)}
                        className="text-text-2 hover:text-text transition-colors"
                      >
                        {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                      <span className={`text-sm font-medium ${statusColor}`}>{task.title}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        task.status === 'running' ? 'bg-accent/10 text-accent' :
                        task.status === 'complete' ? 'bg-success/10 text-success' :
                        task.status === 'error' ? 'bg-danger/10 text-danger' :
                        'bg-surface-2 text-text-2'
                      }`}>
                        {task.status}
                      </span>
                      {task.images && task.images.length > 0 && (
                        <span className="text-xs text-text-2 flex items-center gap-1">
                          <ImageIcon className="w-3.5 h-3.5" /> {task.images.length}
                        </span>
                      )}
                      <button
                        onClick={() => { if (confirm(`Delete task "${task.title}"?`)) onDeleteTask(task.id); }}
                        className="text-text-2 hover:text-danger transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  {!isCollapsed && (
                    <div className="px-3 pb-3 space-y-2">
                      <div className="w-full bg-surface-2 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
                            task.status === 'complete' ? 'bg-success' : 'bg-gradient-to-r from-accent to-accent-light'
                          }`}
                          style={{ width: `${task.progress}%` }}
                        />
                      </div>
                      {task.agent_progress && task.agent_progress.length > 0 && (
                        <div className="space-y-1 pt-1">
                          {task.agent_progress.map((ap: AgentProgress, idx: number) => (
                            <div key={idx} className="flex items-center gap-2">
                              <span className="text-xs text-text min-w-0 truncate" style={{ maxWidth: '120px' }}>{ap.name}</span>
                              <div className="flex-1 bg-surface-2 rounded-full h-1 overflow-hidden min-w-[40px]">
                                <div
                                  className={`h-full rounded-full transition-all duration-300 ${
                                    ap.status === 'complete' ? 'bg-success' : ap.status === 'running' ? 'bg-accent' : 'bg-surface-3'
                                  }`}
                                  style={{ width: `${ap.progress}%` }}
                                />
                              </div>
                              <span className="text-xs text-text-2 w-8 text-right shrink-0">{ap.progress}%</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {task.images && task.images.length > 0 && (
                        <div className="grid grid-cols-2 gap-2 pt-2">
                          {task.images.map((img, idx) => (
                            <div key={idx} className="rounded-lg border border-border overflow-hidden">
                              {img.mediaType === 'video' ? (
                                <video src={img.url} controls className="w-full rounded-lg" />
                              ) : (
                                <img src={img.url} alt={img.prompt || 'Generated'} className="w-full rounded-lg" loading="lazy" />
                              )}
                              <p className="text-xs text-text-2 p-1.5 italic truncate">"{img.prompt}"</p>
                            </div>
                          ))}
                        </div>
                      )}
                      {task.agent_outputs && task.agent_outputs.length > 0 ? (
                        <div className="space-y-1.5 pt-1">
                          {task.agent_outputs.map((out, idx) => (
                            <div key={idx} className="text-xs text-text bg-surface-2 p-2 rounded-lg max-h-48 overflow-y-auto whitespace-pre-wrap">
                              <div className="flex items-center gap-2 mb-1 pb-1 border-b border-border">
                                <Bot className="w-3 h-3 text-accent" />
                                <span className="font-medium text-accent">{out.name}</span>
                                {out.role && <span className="text-text-2">— {out.role}</span>}
                              </div>
                              {out.output}
                            </div>
                          ))}
                        </div>
                      ) : task.result && (
                        <div className="text-xs text-text bg-surface-2 p-2 rounded-lg max-h-48 overflow-y-auto whitespace-pre-wrap">
                          {task.result}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

const ConnectionLine: React.FC = () => (
  <div className="flex items-center shrink-0">
    <div className="w-8 h-px bg-gradient-to-r from-accent/40 to-accent/20" />
    <div className="w-1.5 h-1.5 rounded-full bg-accent/40" />
  </div>
);
