import { useState, useEffect, useCallback } from 'react';
import {
  Plus, Trash2, Clock, FileText, Calendar, Play, Pause, X, Save,
} from 'lucide-react';

export interface TaskTemplate {
  id: string;
  name: string;
  prompt: string;
  mode: string;
  created_at: string;
}

export interface ScheduledTask {
  id: string;
  name: string;
  prompt: string;
  interval_hours: number;
  mode: string;
  last_run: string | null;
  next_run: string;
  created_at: string;
  active: boolean;
}

interface TemplatesPanelProps {
  onAction: (name: string, payload?: Record<string, any>) => void;
  onUseTemplate?: (prompt: string) => void;
  visible: boolean;
  onClose: () => void;
}

export const TemplatesPanel: React.FC<TemplatesPanelProps> = ({
  onAction, onUseTemplate, visible, onClose,
}) => {
  const [tab, setTab] = useState<'templates' | 'scheduling'>('templates');
  const [templates, setTemplates] = useState<TaskTemplate[]>([]);
  const [scheduled, setScheduled] = useState<ScheduledTask[]>([]);
  const [showAddTemplate, setShowAddTemplate] = useState(false);
  const [showAddSchedule, setShowAddSchedule] = useState(false);
  const [newTplName, setNewTplName] = useState('');
  const [newTplPrompt, setNewTplPrompt] = useState('');
  const [newSchedName, setNewSchedName] = useState('');
  const [newSchedPrompt, setNewSchedPrompt] = useState('');
  const [newSchedInterval, setNewSchedInterval] = useState('24');

  const refreshTemplates = useCallback(() => {
    onAction('list_task_templates');
  }, [onAction]);

  const refreshScheduled = useCallback(() => {
    onAction('list_scheduled_tasks');
  }, [onAction]);

  useEffect(() => {
    if (visible) {
      refreshTemplates();
      refreshScheduled();
    }
  }, [visible, refreshTemplates, refreshScheduled]);

  // Listen for template/scheduled data in chat messages
  useEffect(() => {
    if (!visible) return;
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (!detail) return;
      if (detail.type === 'task_templates') {
        setTemplates(detail.templates || []);
      } else if (detail.type === 'scheduled_tasks') {
        setScheduled(detail.tasks || []);
      }
    };
    window.addEventListener('chat-data', handler);
    return () => window.removeEventListener('chat-data', handler);
  }, [visible]);

  if (!visible) return null;

  const handleSaveTemplate = () => {
    if (!newTplPrompt.trim()) return;
    onAction('save_task_template', { name: newTplName || 'Untitled', prompt: newTplPrompt, mode: 'plan' });
    setNewTplName('');
    setNewTplPrompt('');
    setShowAddTemplate(false);
    setTimeout(refreshTemplates, 500);
  };

  const handleSaveSchedule = () => {
    if (!newSchedPrompt.trim()) return;
    onAction('add_scheduled_task', {
      name: newSchedName || 'Scheduled Task',
      prompt: newSchedPrompt,
      interval_hours: parseFloat(newSchedInterval) || 24,
      mode: 'plan',
    });
    setNewSchedName('');
    setNewSchedPrompt('');
    setNewSchedInterval('24');
    setShowAddSchedule(false);
    setTimeout(refreshScheduled, 500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-[480px] max-h-[80vh] bg-surface rounded-xl border border-border shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-accent" />
            <h2 className="text-sm font-semibold text-text">Templates & Scheduling</h2>
          </div>
          <button onClick={onClose} className="text-text-3 hover:text-text transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border">
          <button
            onClick={() => setTab('templates')}
            className={`flex-1 px-4 py-2 text-xs font-medium transition-colors ${
              tab === 'templates' ? 'text-accent border-b-2 border-accent' : 'text-text-3 hover:text-text'
            }`}
          >
            <FileText className="w-3 h-3 inline mr-1" />
            Templates ({templates.length})
          </button>
          <button
            onClick={() => setTab('scheduling')}
            className={`flex-1 px-4 py-2 text-xs font-medium transition-colors ${
              tab === 'scheduling' ? 'text-accent border-b-2 border-accent' : 'text-text-3 hover:text-text'
            }`}
          >
            <Calendar className="w-3 h-3 inline mr-1" />
            Scheduled ({scheduled.length})
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {tab === 'templates' && (
            <div className="space-y-2">
              {showAddTemplate ? (
                <div className="p-3 rounded-lg bg-bg border border-accent/30 space-y-2">
                  <input
                    type="text"
                    placeholder="Template name..."
                    value={newTplName}
                    onChange={(e) => setNewTplName(e.target.value)}
                    className="w-full px-2 py-1.5 text-xs bg-surface-2 border border-border rounded text-text focus:outline-none focus:border-accent"
                  />
                  <textarea
                    placeholder="Task prompt..."
                    value={newTplPrompt}
                    onChange={(e) => setNewTplPrompt(e.target.value)}
                    rows={3}
                    className="w-full px-2 py-1.5 text-xs bg-surface-2 border border-border rounded text-text focus:outline-none focus:border-accent resize-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={handleSaveTemplate}
                      className="flex items-center gap-1 px-2 py-1 text-[10px] bg-accent text-white rounded hover:bg-accent/80 transition-colors"
                    >
                      <Save className="w-3 h-3" /> Save
                    </button>
                    <button
                      onClick={() => setShowAddTemplate(false)}
                      className="px-2 py-1 text-[10px] bg-surface-2 text-text-2 rounded hover:bg-surface-3 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowAddTemplate(true)}
                  className="w-full flex items-center justify-center gap-1 py-2 text-xs text-accent border border-dashed border-accent/30 rounded-lg hover:bg-accent/5 transition-colors"
                >
                  <Plus className="w-3 h-3" /> New Template
                </button>
              )}

              {templates.length === 0 && !showAddTemplate ? (
                <p className="text-xs text-text-3 italic text-center py-8">
                  No templates yet. Create one to reuse common task prompts.
                </p>
              ) : (
                templates.map((tpl) => (
                  <div
                    key={tpl.id}
                    className="p-3 rounded-lg bg-bg border border-border hover:border-accent/30 transition-colors group"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-text truncate">{tpl.name}</div>
                        <div className="text-[10px] text-text-3 mt-0.5 line-clamp-2">{tpl.prompt}</div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {onUseTemplate && (
                          <button
                            onClick={() => { onUseTemplate(tpl.prompt); onClose(); }}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
                            title="Use this template"
                          >
                            Use
                          </button>
                        )}
                        <button
                          onClick={() => { onAction('delete_task_template', { template_id: tpl.id }); setTimeout(refreshTemplates, 500); }}
                          className="text-text-3 hover:text-danger transition-colors"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {tab === 'scheduling' && (
            <div className="space-y-2">
              {showAddSchedule ? (
                <div className="p-3 rounded-lg bg-bg border border-accent/30 space-y-2">
                  <input
                    type="text"
                    placeholder="Task name..."
                    value={newSchedName}
                    onChange={(e) => setNewSchedName(e.target.value)}
                    className="w-full px-2 py-1.5 text-xs bg-surface-2 border border-border rounded text-text focus:outline-none focus:border-accent"
                  />
                  <textarea
                    placeholder="Task prompt to run on schedule..."
                    value={newSchedPrompt}
                    onChange={(e) => setNewSchedPrompt(e.target.value)}
                    rows={3}
                    className="w-full px-2 py-1.5 text-xs bg-surface-2 border border-border rounded text-text focus:outline-none focus:border-accent resize-none"
                  />
                  <div className="flex items-center gap-2">
                    <label className="text-[10px] text-text-3">Every</label>
                    <input
                      type="number"
                      min="0.5"
                      step="0.5"
                      value={newSchedInterval}
                      onChange={(e) => setNewSchedInterval(e.target.value)}
                      className="w-16 px-2 py-1 text-xs bg-surface-2 border border-border rounded text-text focus:outline-none focus:border-accent"
                    />
                    <label className="text-[10px] text-text-3">hours</label>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleSaveSchedule}
                      className="flex items-center gap-1 px-2 py-1 text-[10px] bg-accent text-white rounded hover:bg-accent/80 transition-colors"
                    >
                      <Save className="w-3 h-3" /> Schedule
                    </button>
                    <button
                      onClick={() => setShowAddSchedule(false)}
                      className="px-2 py-1 text-[10px] bg-surface-2 text-text-2 rounded hover:bg-surface-3 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowAddSchedule(true)}
                  className="w-full flex items-center justify-center gap-1 py-2 text-xs text-accent border border-dashed border-accent/30 rounded-lg hover:bg-accent/5 transition-colors"
                >
                  <Plus className="w-3 h-3" /> New Scheduled Task
                </button>
              )}

              {scheduled.length === 0 && !showAddSchedule ? (
                <p className="text-xs text-text-3 italic text-center py-8">
                  No scheduled tasks. Create one to run tasks automatically on a recurring basis.
                </p>
              ) : (
                scheduled.map((task) => (
                  <div
                    key={task.id}
                    className="p-3 rounded-lg bg-bg border border-border hover:border-accent/30 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3 h-3 text-text-3 shrink-0" />
                          <span className="text-xs font-medium text-text truncate">{task.name}</span>
                          {task.active ? (
                            <span className="text-[8px] px-1 py-0.5 rounded bg-success/20 text-success font-semibold">ACTIVE</span>
                          ) : (
                            <span className="text-[8px] px-1 py-0.5 rounded bg-surface-2 text-text-3 font-semibold">PAUSED</span>
                          )}
                        </div>
                        <div className="text-[10px] text-text-3 mt-0.5 line-clamp-2">{task.prompt}</div>
                        <div className="text-[9px] text-text-3 mt-1 flex items-center gap-2">
                          <span>Every {task.interval_hours}h</span>
                          {task.last_run && <span>Last: {new Date(task.last_run).toLocaleDateString()}</span>}
                          {task.next_run && <span>Next: {new Date(task.next_run).toLocaleDateString()}</span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => { onAction('toggle_scheduled_task', { task_id: task.id }); setTimeout(refreshScheduled, 500); }}
                          className="text-text-3 hover:text-accent transition-colors"
                          title={task.active ? 'Pause' : 'Resume'}
                        >
                          {task.active ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                        </button>
                        <button
                          onClick={() => { onAction('delete_scheduled_task', { task_id: task.id }); setTimeout(refreshScheduled, 500); }}
                          className="text-text-3 hover:text-danger transition-colors"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
