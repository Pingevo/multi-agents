import { useState, useMemo } from 'react';
import {
  CheckCircle, XCircle, Loader2,
} from 'lucide-react';
import type { ChatMessage, AgentProgressEntry, PlanAgent, ResultAgent, PlanStatus } from '../chatTypes';
import type { Agent, PendingApproval, ImageResult } from '../../types/platform';
import MarkdownRenderer from '../MarkdownRenderer';

// ============================================================
// Types
// ============================================================

interface TasksWindowProps {
  chatMessages: ChatMessage[];
  onApproveImage?: (approvalId: string) => void;
  onRejectImage?: (approvalId: string) => void;
  onRetryImage?: (approvalId: string) => void;
  onEditImagePrompt?: (approvalId: string, newPrompt: string) => void;
  onRetryTask?: () => void;
  onRateTask?: (rating: number) => void;
  onSkipReview?: (agentName: string) => void;
}

interface StoryboardRun {
  runIndex: number;
  userMessage: string;
  planAgents: PlanAgent[];
  planStatus: PlanStatus;
  planType: string;
  progress?: AgentProgressEntry[];
  result?: { summary: string; agents: ResultAgent[]; error: boolean };
  pendingApprovals: PendingApproval[];
  imageResults: ImageResult[];
  isLatest: boolean;
}

// ============================================================
// Helpers
// ============================================================

const agentIcon = (name: string): string => {
  const n = name.toLowerCase();
  if (n.includes('analyst') || n.includes('product')) return '📊';
  if (n.includes('copy') || n.includes('writer')) return '✍️';
  if (n.includes('image') || n.includes('design') || n.includes('visual') || n.includes('artist')) return '🎨';
  if (n.includes('seo') || n.includes('search')) return '🔍';
  if (n.includes('manager')) return '🧠';
  if (n.includes('video')) return '🎬';
  return '🤖';
};

function buildRuns(chatMessages: ChatMessage[]): StoryboardRun[] {
  const runs: StoryboardRun[] = [];
  let currentRun: StoryboardRun | null = null;
  for (let i = 0; i < chatMessages.length; i++) {
    const msg = chatMessages[i];
    if (msg.role === 'user' && msg.messageType !== 'image_approval' && msg.messageType !== 'image_result') {
      if (currentRun) runs.push(currentRun);
      currentRun = { runIndex: runs.length, userMessage: msg.content, planAgents: [], planStatus: 'pending', planType: 'new', pendingApprovals: [], imageResults: [], isLatest: false };
    }
    if (!currentRun) continue;
    if (msg.messageType === 'plan' && msg.planAgents) {
      currentRun.planAgents = msg.planAgents;
      currentRun.planStatus = msg.planStatus || 'pending';
      currentRun.planType = msg.planType || 'new';
    }
    if (msg.messageType === 'agent_progress' && msg.agentProgressList) {
      currentRun.progress = msg.agentProgressList;
    }
    if (msg.messageType === 'result') {
      currentRun.result = { summary: msg.resultSummary || '', agents: msg.resultAgents || [], error: msg.resultError || false };
    }
    if (msg.messageType === 'image_approval' && (msg.approvalStatus === 'pending' || msg.approvalStatus === 'error' || msg.approvalStatus === 'approved')) {
      const existingIdx = currentRun.pendingApprovals.findIndex(pa => pa.approvalId === (msg.approvalId || ''));
      const entry = {
        approvalId: msg.approvalId || '', prompt: msg.imagePrompt || '', agentName: msg.agentName || '',
        mediaType: msg.mediaType || 'image', duration: msg.duration || 0, model: msg.model || '',
        approvalStatus: msg.approvalStatus || 'pending', imageError: msg.imageError || '',
      };
      if (existingIdx >= 0) currentRun.pendingApprovals[existingIdx] = entry;
      else currentRun.pendingApprovals.push(entry);
    }
    if (msg.messageType === 'image_result' && msg.imageUrl) {
      currentRun.imageResults.push({
        imageUrl: msg.imageUrl || '', prompt: msg.imagePrompt || '', approvalId: msg.approvalId || '',
        mediaType: msg.mediaType || 'image', agentName: msg.agentName || '',
      });
    }
  }
  if (currentRun) runs.push(currentRun);
  const visible = runs.filter(r => r.planStatus !== 'rejected' && (r.planAgents.length > 0 || r.result));
  visible.forEach((r, i) => { r.runIndex = i; });
  if (visible.length > 0) visible[visible.length - 1].isLatest = true;
  return visible;
}

// ============================================================
// Agent Card (kcard)
// ============================================================

const TaskAgentCard: React.FC<{
  agent: Agent;
  progress?: AgentProgressEntry;
  pendingApprovals: PendingApproval[];
  imageResults: ImageResult[];
  onApproveImage?: (id: string) => void;
  onRejectImage?: (id: string) => void;
  onRetryImage?: (id: string) => void;
  onSkipReview?: (name: string) => void;
}> = ({ agent, progress, pendingApprovals, imageResults, onApproveImage, onRejectImage, onRetryImage, onSkipReview }) => {
  const [showOutput, setShowOutput] = useState(false);
  const status = progress?.status || 'pending';
  const hasOutput = !!progress?.output;
  const isComplete = status === 'complete';
  const isError = status === 'error';
  const isRunning = status === 'running';
  const isWaitingApproval = status === 'waiting_approval';
  const isAwaitingReview = status === 'awaiting_review';

  const statClass = isComplete ? 'done' : isError ? 'error' : isRunning ? 'running' : isWaitingApproval ? 'waiting' : isAwaitingReview ? 'review' : 'idle';
  const statText = isComplete ? 'เสร็จแล้ว' : isError ? 'Error' : isRunning ? `กำลังทำงาน ${progress?.progress || 0}%` : isWaitingApproval ? 'รออนุมัติ' : isAwaitingReview ? 'กำลังตรวจ' : 'รอคิว';

  return (
    <div className="kcard">
      <div className={`kcard-av ${statClass}`}>{agentIcon(agent.name)}</div>
      <div className="kcard-name">{agent.name}</div>
      <span className={`kcard-badge ${statClass}`}>{statText}</span>

      {/* Model + duration */}
      {progress?.model && (
        <div style={{ fontSize: '9px', color: 'var(--ink3)', fontFamily: 'var(--mono)', marginTop: '2px' }}>
          🤖 {progress.model}
        </div>
      )}

      {/* Current task */}
      {progress?.current_task && !isComplete && !isError && (
        <div style={{ fontSize: '10px', color: 'var(--ink3)', fontStyle: 'italic', marginTop: '2px' }}>{progress.current_task}</div>
      )}

      {/* Current tool */}
      {progress?.current_tool && (
        <div style={{ fontSize: '10px', color: 'var(--orange)', marginTop: '2px' }}>⚡ {progress.tool_description || progress.current_tool}</div>
      )}

      {/* Thinking */}
      {progress?.thinking && (
        <div style={{ fontSize: '10px', color: 'var(--ink3)', marginTop: '2px', fontStyle: 'italic' }}>💭 {progress.thinking}</div>
      )}

      {/* Waiting for deps */}
      {(() => {
        const deps = (agent as any).depends_on || [];
        if (deps.length === 0 || isComplete || isError || isRunning) return null;
        const depProgress = deps.filter(() => progress?.status === 'pending');
        if (depProgress.length === 0 && isRunning) return null;
        return (
          <div style={{ fontSize: '10px', color: 'var(--amber)', marginTop: '2px' }}>
            ⏳ รอ: {deps.join(', ')}
          </div>
        );
      })()}

      {/* Waiting approval */}
      {isWaitingApproval && (
        <div style={{ fontSize: '10px', color: 'var(--purple)', marginTop: '2px' }}>รอผู้ใช้กด Generate</div>
      )}

      {/* Awaiting review */}
      {isAwaitingReview && (
        <div style={{ fontSize: '10px', color: 'var(--amber)', marginTop: '2px' }}>
          Manager กำลังตรวจ{progress?.review_round ? ` (รอบที่ ${progress.review_round})` : ''}...
          {progress?.review_summary && <div style={{ fontSize: '9px', color: 'var(--ink3)', marginTop: '1px' }}>{progress.review_summary}</div>}
        </div>
      )}

      {/* Skip review button */}
      {onSkipReview && hasOutput && !isComplete && !isError && (
        <button
          className="kcard-btn"
          style={{ background: 'rgba(200,146,32,0.1)', color: 'var(--amber)', borderColor: 'rgba(200,146,32,0.3)' }}
          onClick={() => onSkipReview(agent.name)}
        >
          หยุดตรวจ
        </button>
      )}

      {/* Completed output */}
      {isComplete && hasOutput && (
        <div style={{ marginTop: '4px' }}>
          <button
            onClick={() => setShowOutput(!showOutput)}
            style={{ fontSize: '9px', color: 'var(--ink3)', cursor: 'pointer', background: 'none', border: 'none' }}
          >
            {showOutput ? '▼ ซ่อน output' : '▶ ดู output'}
            {progress?.review_summary && <span style={{ color: 'var(--green)' }}> — {progress.review_summary}</span>}
          </button>
          {showOutput && (
            <div style={{ fontSize: '10px', color: 'var(--ink2)', background: 'var(--cream)', borderRadius: '3px', padding: '6px 8px', border: '1px solid var(--line)', maxHeight: '120px', overflowY: 'auto', marginTop: '2px' }}>
              <MarkdownRenderer content={progress?.output || ''} />
            </div>
          )}
        </div>
      )}

      {/* Progress bar */}
      {(isRunning || isComplete || isError) && (
        <div style={{ marginTop: '4px' }}>
          <div style={{ width: '100%', height: '3px', background: 'var(--line)', borderRadius: '2px', overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                borderRadius: '2px',
                transition: 'width 0.5s',
                width: `${isComplete ? 100 : isError ? 100 : progress?.progress || 0}%`,
                background: isComplete ? 'var(--green)' : isError ? 'var(--red)' : isWaitingApproval ? 'var(--purple)' : isAwaitingReview ? 'var(--amber)' : 'var(--orange)',
              }}
            />
          </div>
        </div>
      )}

      {/* Review history */}
      {progress?.review_history && progress.review_history.length > 0 && (
        <div style={{ marginTop: '4px', fontSize: '9px', color: 'var(--ink3)' }}>
          {progress.review_history.map((rh, i) => (
            <div key={i} style={{ padding: '2px 0' }}>
              <span style={{ color: rh.status === 'approved' ? 'var(--green)' : 'var(--red)' }}>
                รอบ {rh.round}: {rh.status === 'approved' ? '✓' : '✕'} {rh.summary}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Image approvals */}
      {pendingApprovals.map(pa => (
        <div key={pa.approvalId} style={{ marginTop: '4px' }}>
          {pa.approvalStatus === 'pending' && (
            <>
              <div style={{ fontSize: '10px', color: 'var(--ink2)', marginBottom: '2px' }}>🖼️ {pa.prompt}</div>
              <div style={{ display: 'flex', gap: '4px' }}>
                <button className="kcard-btn reject" onClick={() => onRejectImage?.(pa.approvalId)}>Reject</button>
                <button className="kcard-btn approve" onClick={() => onApproveImage?.(pa.approvalId)}>Generate</button>
              </div>
            </>
          )}
          {pa.approvalStatus === 'error' && (
            <>
              <div style={{ fontSize: '10px', color: 'var(--red)', marginBottom: '2px' }}>⚠ {pa.imageError}</div>
              <button className="kcard-btn" style={{ background: 'rgba(200,146,32,0.1)', color: 'var(--amber)' }} onClick={() => onRetryImage?.(pa.approvalId)}>🔄 Retry</button>
            </>
          )}
          {pa.approvalStatus === 'approved' && (
            <div style={{ fontSize: '10px', color: 'var(--green)' }}>✓ Approved — generating...</div>
          )}
        </div>
      ))}

      {/* Image results */}
      {imageResults.map((ir, i) => (
        <div key={i} style={{ marginTop: '4px' }}>
          {ir.mediaType === 'video' ? (
            <video src={ir.imageUrl} controls style={{ width: '100%', borderRadius: '3px', border: '1px solid var(--line)' }} />
          ) : (
            <img src={ir.imageUrl} alt={ir.prompt} style={{ width: '100%', borderRadius: '3px', border: '1px solid var(--line)' }} />
          )}
          <div style={{ fontSize: '9px', color: 'var(--ink3)', marginTop: '2px' }}>{ir.prompt}</div>
        </div>
      ))}
    </div>
  );
};

// ============================================================
// Plan Frame (one per run)
// ============================================================

const PlanFrame: React.FC<{
  run: StoryboardRun;
  onApproveImage?: (id: string) => void;
  onRejectImage?: (id: string) => void;
  onRetryImage?: (id: string) => void;
  onEditImagePrompt?: (id: string, p: string) => void;
  onSkipReview?: (name: string) => void;
}> = ({ run, onApproveImage, onRejectImage, onRetryImage, onSkipReview }) => {
  const [collapsed, setCollapsed] = useState(false);

  const planAgentsAsAgents: Agent[] = useMemo(() =>
    run.planAgents.map((pa, idx) => ({
      id: `run${run.runIndex}-agent-${idx}`,
      name: pa.name, role: pa.role, goal: pa.goal || '',
      tools: pa.tools || [], depends_on: pa.depends_on || [],
      status: 'Idle' as const,
    })),
  [run.planAgents, run.runIndex]);

  const doneCount = useMemo(() => {
    if (!run.progress) return 0;
    return run.progress.filter(p => p.status === 'complete' || p.status === 'error').length;
  }, [run.progress]);
  const totalCount = planAgentsAsAgents.length;

  const overallProgress = run.progress
    ? Math.round(run.progress.reduce((sum, p) => sum + (p.status === 'complete' ? 100 : p.progress || 0), 0) / Math.max(totalCount, 1))
    : run.result ? 100 : 0;

  const frameStatus = run.planStatus === 'pending' ? 'pending' : run.result ? 'done' : 'running';
  const statusText = run.planStatus === 'pending' ? 'รออนุมัติ' : run.result ? (run.result.error ? 'Error' : 'เสร็จสิ้น') : overallProgress > 0 ? `กำลังทำงาน ${overallProgress}%` : 'เริ่ม...';
  const frameIcon = run.planType === 'create_agents' ? '🤖' : '📝';

  const hasWaitingApproval = run.progress?.some(ap => ap.status === 'waiting_approval');
  const hasAwaitingReview = run.progress?.some(ap => ap.status === 'awaiting_review');
  const allComplete = run.progress && planAgentsAsAgents.length > 0 && planAgentsAsAgents.every(a => {
    const p = run.progress!.find(ap => ap.name === a.name);
    return p?.status === 'complete' || p?.status === 'error';
  });

  return (
    <div className={`plan-frame ${frameStatus}`}>
      <div className="plan-frame-hdr" onClick={() => setCollapsed(!collapsed)}>
        <span className="pf-ic">{frameIcon}</span>
        <div className="pf-info">
          <div className="pf-title">{run.userMessage || `Run ${run.runIndex + 1}`}</div>
          <div className="pf-bar"><div className="pf-bar-fill" style={{ width: `${overallProgress}%` }} /></div>
        </div>
        <span className="pf-badge">{statusText}</span>
        <span className="pf-count">{doneCount}/{totalCount}</span>
        <span className="pf-toggle">{collapsed ? '▸' : '▾'}</span>
      </div>
      {!collapsed && (
        <div className="plan-frame-body">
          {/* Pending plan actions */}
          {run.planStatus === 'pending' && (
            <div className="kcard-plan-actions">
              <button className="kcard-btn reject">Reject</button>
              <button className="kcard-btn approve">Approve Plan</button>
            </div>
          )}

          {/* Agent cards */}
          {planAgentsAsAgents.map(agent => {
            const nodeProgress = run.progress?.find(p => p.name === agent.name);
            const agentApprovals = run.pendingApprovals.filter(pa => pa.agentName.toLowerCase() === agent.name.toLowerCase());
            const agentApprovalIds = new Set(agentApprovals.map(pa => pa.approvalId));
            const agentImages = run.imageResults.filter(ir => {
              if (ir.agentName && ir.agentName.toLowerCase() === agent.name.toLowerCase()) return true;
              if (!ir.agentName && agentApprovalIds.has(ir.approvalId)) return true;
              return false;
            });
            return (
              <TaskAgentCard
                key={agent.id || agent.name}
                agent={agent}
                progress={nodeProgress}
                pendingApprovals={agentApprovals}
                imageResults={agentImages}
                onApproveImage={onApproveImage}
                onRejectImage={onRejectImage}
                onRetryImage={onRetryImage}
                onSkipReview={onSkipReview}
              />
            );
          })}

          {/* Waiting for user */}
          {hasWaitingApproval && !run.result && (
            <div style={{ padding: '6px 10px', border: '1px solid rgba(106,74,122,0.3)', background: 'rgba(106,74,122,0.05)', borderRadius: '3px', fontSize: '11px', color: 'var(--purple)', marginBottom: '6px' }}>
              รอผู้ใช้กด Generate เพื่อสร้างภาพ/วิดีโอ
            </div>
          )}

          {/* Manager reviewing */}
          {hasAwaitingReview && !run.result && (
            <div style={{ padding: '6px 10px', border: '1px solid rgba(200,146,32,0.3)', background: 'rgba(200,146,32,0.05)', borderRadius: '3px', fontSize: '11px', color: 'var(--amber)', marginBottom: '6px' }}>
              Manager กำลังตรวจผลงานของ agent...
            </div>
          )}

          {/* Synthesizing */}
          {allComplete && !run.result && !hasWaitingApproval && !hasAwaitingReview && (
            <div style={{ padding: '6px 10px', border: '1px solid rgba(58,107,138,0.3)', background: 'rgba(58,107,138,0.05)', borderRadius: '3px', fontSize: '11px', color: 'var(--blue)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Loader2 size={12} className="animate-spin" /> Combining all agent outputs...
            </div>
          )}

          {/* Final result */}
          {run.result && (
            <div className="card" style={{ borderLeft: `4px solid ${run.result.error ? 'var(--red)' : 'var(--green)'}` }}>
              <div className="card-hdr">
                {run.result.error ? <XCircle size={14} style={{ color: 'var(--red)' }} /> : <CheckCircle size={14} style={{ color: 'var(--green)' }} />}
                <span>{run.result.error ? 'Error' : 'Completed'}</span>
              </div>
              <div className="card-body">
                <MarkdownRenderer content={run.result.summary} />
              </div>
              {run.result.agents.length > 0 && (
                <div className="result-agents">
                  {run.result.agents.map((agent, i) => (
                    <div key={i} className="result-agent">
                      <div className="ra-hdr">
                        <div className="ra-av">{agentIcon(agent.name)}</div>
                        <span>{agent.name}</span>
                      </div>
                      <div className="ra-body open">
                        <MarkdownRenderer content={agent.output} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ============================================================
// Main TasksWindow
// ============================================================

export const TasksWindow: React.FC<TasksWindowProps> = ({
  chatMessages,
  onApproveImage, onRejectImage, onRetryImage, onEditImagePrompt,
  onSkipReview,
}) => {
  const runs = useMemo(() => buildRuns(chatMessages), [chatMessages]);

  if (runs.length === 0) {
    return (
      <div className="tasks-list">
        <div className="kcard-empty">
          <div style={{ fontSize: '24px', marginBottom: '6px' }}>📋</div>
          <div>Send a message to start</div>
        </div>
      </div>
    );
  }

  return (
    <div className="tasks-list">
      {runs.map(run => (
        <PlanFrame
          key={run.runIndex}
          run={run}
          onApproveImage={onApproveImage}
          onRejectImage={onRejectImage}
          onRetryImage={onRetryImage}
          onEditImagePrompt={onEditImagePrompt}
          onSkipReview={onSkipReview}
        />
      ))}
    </div>
  );
};
