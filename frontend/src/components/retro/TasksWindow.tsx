import { useState } from 'react';
import type { PlanData } from './types';
import { Dialog } from './Dialog';

interface TasksWindowProps {
  plans: PlanData[];
  onAction: (name: string, payload?: Record<string, any>) => void;
}

export const TasksWindow: React.FC<TasksWindowProps> = ({ plans, onAction }) => {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [dialogState, setDialogState] = useState<{ open: boolean; title: string; icon: string; content: React.ReactNode }>({
    open: false, title: '', icon: '', content: null,
  });

  const toggleCollapse = (id: string) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const statusColor = (status: string) => {
    if (status === 'done') return 'bg-green';
    if (status === 'running') return 'bg-amber';
    return 'bg-red';
  };

  const badgeClass = (status: string) => {
    if (status === 'done') return 'text-green bg-green/10';
    if (status === 'running') return 'text-amber bg-amber/10';
    if (status === 'waiting') return 'text-red bg-red/10';
    return 'text-ink-3 bg-cream-2';
  };

  const renderCard = (agent: PlanData['agents'][0]) => {
    let action = null;
    if (agent.approval) {
      action = (
        <button
          className="text-[10px] px-3 py-1 border border-green bg-green text-white rounded-retro-sm font-bold hover:bg-green-light transition-colors flex-shrink-0"
          onClick={() => setDialogState({
            open: true,
            title: 'Image Approval',
            icon: '🎨',
            content: (
              <div className="flex flex-col gap-3">
                <p className="text-[12px] text-ink-2">Prompt: {agent.approval?.prompt}</p>
                <p className="text-[10px] text-ink-3 font-mono">Model: {agent.approval?.model}</p>
              </div>
            ),
          })}
        >
          Approve
        </button>
      );
    } else if (agent.output) {
      action = (
        <button
          className="text-[10px] px-3 py-1 border border-line-2 bg-paper text-orange rounded-retro-sm font-bold hover:bg-orange hover:text-white hover:border-orange transition-colors flex-shrink-0"
          onClick={() => setDialogState({
            open: true,
            title: agent.name,
            icon: agent.ic,
            content: (
              <div className="flex flex-col gap-2">
                <p className="text-[12px] text-ink leading-relaxed">{agent.output}</p>
                {agent.model && <p className="text-[10px] text-ink-3 font-mono">🤖 {agent.model} · ⏱️ {agent.duration || '—'}</p>}
              </div>
            ),
          })}
        >
          View
        </button>
      );
    }

    return (
      <div
        key={agent.name}
        className="flex items-center gap-2 bg-paper border border-line rounded-retro px-2.5 py-2 transition-colors hover:border-line-2 hover:shadow-retro"
      >
        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-sm border-2 flex-shrink-0 ${
          agent.stat === 'done' ? 'border-green bg-cream' :
          agent.stat === 'running' ? 'border-amber bg-cream' :
          agent.stat === 'waiting' ? 'border-red bg-cream' :
          'border-line-2 bg-cream opacity-50'
        }`}>
          {agent.ic}
        </div>
        <div className="flex-1 min-w-0 text-[11px] font-semibold text-ink truncate">{agent.name}</div>
        <span className={`text-[9px] font-semibold px-2 py-0.5 rounded-retro-sm flex-shrink-0 ${badgeClass(agent.stat)}`}>
          {agent.statText}
        </span>
        {action}
      </div>
    );
  };

  return (
    <div className="h-full overflow-y-auto p-3.5 flex flex-col gap-2.5">
      {plans.map(plan => {
        const doneCount = plan.agents.filter(a => a.stat === 'done').length;
        const totalCount = plan.agents.length;
        const isCollapsed = collapsed.has(plan.id);

        return (
          <div key={plan.id} className={`bg-paper border border-line rounded-retro overflow-hidden transition-colors hover:border-line-2`}>
            {/* Header */}
            <div
              className="flex items-center gap-2.5 px-3.5 py-2.5 cursor-pointer select-none bg-cream border-b border-line transition-colors hover:bg-cream-2"
              onClick={() => toggleCollapse(plan.id)}
            >
              <span className="text-xl flex-shrink-0">{plan.ic}</span>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-bold text-ink">{plan.title}</div>
                <div className="h-1 bg-line rounded-sm mt-1 overflow-hidden">
                  <div
                    className={`h-full rounded-sm transition-all ${statusColor(plan.status)}`}
                    style={{ width: `${plan.progress}%` }}
                  />
                </div>
              </div>
              <span className={`text-[9px] font-bold px-2.5 py-0.5 rounded-retro-sm flex-shrink-0 ${badgeClass(plan.status)}`}>
                {plan.statusText}
              </span>
              <span className="text-[10px] text-ink-3 font-mono flex-shrink-0">{doneCount}/{totalCount}</span>
              <span className="text-xs text-ink-3 flex-shrink-0">{isCollapsed ? '▸' : '▾'}</span>
            </div>

            {/* Body */}
            {!isCollapsed && (
              <div className="p-2.5 flex flex-col gap-1.5">
                {plan.status === 'pending' && (
                  <div className="flex gap-1.5 mb-1">
                    <button
                      className="flex-1 py-2 text-[11px] font-bold border border-red bg-paper text-red rounded-retro-sm hover:bg-red hover:text-white transition-colors"
                      onClick={() => onAction('plan_reject')}
                    >
                      Reject
                    </button>
                    <button
                      className="flex-1 py-2 text-[11px] font-bold border border-green bg-green text-white rounded-retro-sm hover:bg-green-light transition-colors"
                      onClick={() => onAction('plan_approve')}
                    >
                      Approve Plan
                    </button>
                  </div>
                )}
                {plan.agents.map(renderCard)}
              </div>
            )}
          </div>
        );
      })}

      <Dialog
        open={dialogState.open}
        icon={dialogState.icon}
        title={dialogState.title}
        onClose={() => setDialogState(prev => ({ ...prev, open: false }))}
        footer={
          <>
            <button
              className="px-4 py-1.5 text-[11px] font-bold border border-line-2 bg-paper text-ink-2 rounded-retro-sm hover:bg-cream-2 transition-colors"
              onClick={() => setDialogState(prev => ({ ...prev, open: false }))}
            >
              Close
            </button>
          </>
        }
      >
        {dialogState.content}
      </Dialog>
    </div>
  );
};
