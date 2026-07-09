import { useState, useEffect } from 'react';
import { X, Rocket } from 'lucide-react';
import type { Agent, AssignFormData } from '../types/platform';

interface AssignTaskModalProps {
  open: boolean;
  agent: Agent | null;
  onSubmit: (data: AssignFormData) => void;
  onClose: () => void;
}

export const AssignTaskModal: React.FC<AssignTaskModalProps> = ({
  open,
  agent,
  onSubmit,
  onClose,
}) => {
  const [task, setTask] = useState('');

  useEffect(() => {
    if (open) setTask('');
  }, [open]);

  if (!open || !agent) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim()) return;
    onSubmit({ agent_id: agent.id, task: task.trim() });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-full max-w-md bg-surface rounded-xl border border-border shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Rocket className="w-4 h-4 text-accent" />
            <h2 className="font-semibold text-sm text-text">Assign Task</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-surface-2 text-text-2">
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-3">
          <div className="flex items-center gap-2 p-3 rounded-lg bg-surface-2">
            <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-accent text-xs font-bold">
              {agent.name.charAt(0).toUpperCase()}
            </div>
            <div>
              <div className="text-sm font-medium text-text">{agent.name}</div>
              <div className="text-xs text-text-2">{agent.role}</div>
            </div>
            <span
              className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${
                agent.status === 'Idle'
                  ? 'bg-success/10 text-success'
                  : 'bg-warning/10 text-warning'
              }`}
            >
              {agent.status}
            </span>
          </div>
          <div>
            <label className="block text-xs text-text-2 mb-1">Task Description *</label>
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="Describe the task you want to assign..."
              rows={4}
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-2 focus:outline-none focus:border-accent resize-none"
              autoFocus
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={!task.trim() || agent.status !== 'Idle'}
              className="flex-1 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors"
            >
              {agent.status !== 'Idle' ? 'Agent is Busy' : 'Assign & Run'}
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
