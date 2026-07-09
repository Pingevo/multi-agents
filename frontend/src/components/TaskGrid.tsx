import { useState } from 'react';
import { CheckCircle, XCircle, Loader2, Bot, Clock, CheckSquare, Trash2, ChevronDown, ChevronRight, ImageIcon } from 'lucide-react';
import type { Task, Plan } from '../types/platform';

interface TaskGridProps {
  tasks: Task[];
  currentPlan: Plan | null;
  onAcceptPlan: () => void;
  onRejectPlan: () => void;
  onCancelPlan: () => void;
  onDeleteTask?: (taskId: string) => void;
}

export const TaskGrid: React.FC<TaskGridProps> = ({
  tasks,
  currentPlan,
  onAcceptPlan,
  onRejectPlan,
  onCancelPlan,
  onDeleteTask,
}) => {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggleCollapsed = (taskId: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  const statusConfig: Record<string, { icon: React.ReactNode; className: string; label: string }> = {
    running: {
      icon: <Loader2 className="w-4 h-4 animate-spin" />,
      className: 'bg-accent/10 text-accent border-accent/20',
      label: 'Running',
    },
    complete: {
      icon: <CheckCircle className="w-4 h-4" />,
      className: 'bg-success/10 text-success border-success/20',
      label: 'Complete',
    },
    error: {
      icon: <XCircle className="w-4 h-4" />,
      className: 'bg-danger/10 text-danger border-danger/20',
      label: 'Error',
    },
    idle: {
      icon: <Bot className="w-4 h-4" />,
      className: 'bg-surface-2 text-text-2 border-border',
      label: 'Idle',
    },
  };

  return (
    <main className="flex-1 flex flex-col min-w-0 bg-bg">
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-text-2" />
          <h2 className="font-semibold text-sm text-text">Tasks & Projects</h2>
        </div>
        <div className="text-xs text-text-2">
          {tasks.filter((t) => t.status === 'running').length} running / {tasks.length} total
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {currentPlan && (
          <div className="mb-4 p-4 rounded-xl border border-accent/20 bg-surface">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-accent" />
                <h3 className="font-semibold text-sm">Plan Approval Required</h3>
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent">
                {currentPlan.agents.length} agent(s) · {currentPlan.plan_type === 'existing' ? 'Existing' : 'New'}
              </span>
            </div>
            <div className="text-sm text-text-2 mb-3">
              Task: <span className="text-text">{currentPlan.task_description}</span>
            </div>
            <div className="space-y-2 mb-3">
              {currentPlan.agents.map((agent, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-surface-2 border border-border">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono text-accent">#{idx + 1}</span>
                    <span className="text-sm font-medium text-text">{agent.name}</span>
                    <span className="text-xs text-text-2">— {agent.role}</span>
                  </div>
                  {agent.goal && (
                    <div className="text-xs text-text-2 ml-6">Goal: {agent.goal}</div>
                  )}
                  {agent.tools && agent.tools.length > 0 && (
                    <div className="text-xs text-text-2 ml-6">Tools: {agent.tools.join(', ')}</div>
                  )}
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                onClick={onAcceptPlan}
                className="px-3 py-1.5 rounded-md bg-accent text-white text-sm font-medium hover:bg-accent-hover"
              >
                Accept
              </button>
              <button
                onClick={onRejectPlan}
                className="px-3 py-1.5 rounded-md border border-border text-sm font-medium hover:bg-surface-2"
              >
                Reject
              </button>
              <button
                onClick={onCancelPlan}
                className="px-3 py-1.5 rounded-md border border-border text-sm font-medium hover:bg-surface-2 text-danger"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {tasks.length === 0 && !currentPlan ? (
            <div className="col-span-full flex flex-col items-center justify-center py-16 text-text-2">
              <Bot className="w-12 h-12 mb-3 opacity-30" />
              <p>No active tasks</p>
              <p className="text-sm mt-1">Type a command below or assign a task from the sidebar</p>
            </div>
          ) : (
            tasks.map((task) => {
              const config = statusConfig[task.status] || statusConfig.idle;
              const isCollapsed = collapsed.has(task.id);
              return (
                <div
                  key={task.id}
                  className="rounded-xl border border-border bg-surface flex flex-col overflow-hidden"
                >
                  <div className="flex items-start justify-between p-4">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => toggleCollapsed(task.id)}
                        className="text-text-2 hover:text-text transition-colors"
                        title={isCollapsed ? 'Expand' : 'Collapse'}
                      >
                        {isCollapsed ? (
                          <ChevronRight className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </button>
                      {config.icon}
                      <h3 className="font-medium text-sm text-text">{task.title}</h3>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full border ${config.className}`}>
                        {config.label}
                      </span>
                      {task.imageUrl && (
                        <span className="text-xs text-text-2 flex items-center gap-1" title="Image generated">
                          <ImageIcon className="w-3.5 h-3.5" />
                        </span>
                      )}
                      {onDeleteTask && (
                        <button
                          onClick={() => {
                            if (confirm(`Delete task "${task.title}"?`)) {
                              onDeleteTask(task.id);
                            }
                          }}
                          className="text-text-2 hover:text-danger transition-colors"
                          title="Delete task"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                  {!isCollapsed && (
                    <div className="px-4 pb-4 flex flex-col gap-3">
                      <div className="text-xs text-text-2">Agent: {task.agent}</div>
                      <div className="w-full bg-surface-2 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-accent h-full rounded-full transition-all duration-300"
                          style={{ width: `${task.progress}%` }}
                        />
                      </div>
                      <div className="text-xs text-text-2 text-right">{task.progress}%</div>
                      {task.agent_progress && task.agent_progress.length > 0 && (
                        <div className="space-y-1.5 pt-1 border-t border-border">
                          <div className="text-xs font-medium text-text-2 pt-1">Per-agent progress</div>
                          {task.agent_progress.map((agent, idx) => (
                            <div key={idx} className="flex items-center gap-2">
                              <span className="text-xs text-text min-w-0 truncate" style={{ maxWidth: '120px' }}>{agent.name}</span>
                              <div className="flex-1 bg-surface-2 rounded-full h-1.5 overflow-hidden min-w-[40px]">
                                <div
                                  className={`h-full rounded-full transition-all duration-300 ${
                                    agent.status === 'complete' ? 'bg-success' : agent.status === 'running' ? 'bg-accent' : 'bg-surface-2'
                                  }`}
                                  style={{ width: `${agent.progress}%` }}
                                />
                              </div>
                              <span className="text-xs text-text-2 w-8 text-right shrink-0">{agent.progress}%</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {task.images && task.images.length > 0 ? (
                        <div className="space-y-2">
                          {task.images.map((img, idx) => (
                            <div key={idx} className="rounded-lg border border-purple-400/20 overflow-hidden">
                              {img.mediaType === 'video' ? (
                                <video
                                  src={img.url}
                                  controls
                                  className="w-full max-w-md rounded-lg"
                                />
                              ) : (
                                <img
                                  src={img.url}
                                  alt={img.prompt || 'Generated image'}
                                  className="w-full max-w-md rounded-lg"
                                  loading="lazy"
                                />
                              )}
                              <p className="text-xs text-text-2 p-2 italic">"{img.prompt}"</p>
                            </div>
                          ))}
                        </div>
                      ) : task.imageUrl && (
                        <div className="rounded-lg border border-purple-400/20 overflow-hidden">
                          <img
                            src={task.imageUrl}
                            alt={task.imagePrompt || 'Generated image'}
                            className="w-full max-w-md rounded-lg"
                            loading="lazy"
                          />
                          <p className="text-xs text-text-2 p-2 italic">"{task.imagePrompt}"</p>
                        </div>
                      )}
                      {task.agent_outputs && task.agent_outputs.length > 0 ? (
                        <div className="space-y-2">
                          {task.agent_outputs.map((agentOut, idx) => (
                            <div key={idx} className="text-sm text-text bg-surface-2 p-3 rounded-lg max-h-96 overflow-y-auto whitespace-pre-wrap">
                              <div className="flex items-center gap-2 mb-1 pb-1 border-b border-border">
                                <Bot className="w-3 h-3 text-accent" />
                                <span className="text-xs font-medium text-accent">{agentOut.name}</span>
                                {agentOut.role && <span className="text-xs text-text-2">— {agentOut.role}</span>}
                              </div>
                              {agentOut.output}
                            </div>
                          ))}
                        </div>
                      ) : task.result && (
                        <div className="text-sm text-text bg-surface-2 p-3 rounded-lg max-h-96 overflow-y-auto whitespace-pre-wrap">
                          {task.result}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </main>
  );
};
