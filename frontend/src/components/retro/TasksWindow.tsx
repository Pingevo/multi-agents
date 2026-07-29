import { useState, useMemo } from 'react';
import {
  Loader2,
} from 'lucide-react';
import type { ChatMessage, AgentProgressEntry, PlanAgent, ResultAgent, PlanStatus, NotificationItem, TaskItem } from '../chatTypes';
import type { Agent, PendingApproval, ImageResult } from '../../types/platform';
import MarkdownRenderer from '../MarkdownRenderer';
import { Dialog } from './Dialog';
import { withMediaToken } from '../../utils/media';

// ============================================================
// Types
// ============================================================

interface TasksWindowProps {
  chatMessages: ChatMessage[];
  notifications: NotificationItem[];
  activeSessionId: string | null;
  onNavigate: (sessionId: string) => void;
  taskItems?: TaskItem[];
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
  onNavigate?: () => void;
}> = ({ agent, progress, pendingApprovals, imageResults, onNavigate }) => {
  const [showOutputDialog, setShowOutputDialog] = useState(false);
  const [dialogTab, setDialogTab] = useState<'output' | 'review'>('output');
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

      {/* Review summary for completed agents */}
      {isComplete && progress?.review_summary && (
        <div style={{ fontSize: '9px', color: 'var(--ink3)', marginTop: '2px' }}>
          {progress.review_summary.includes('หยุดโดยผู้ใช้') || progress.review_summary.includes('ยังไม่ตรวจ') || progress.review_summary.includes('Cancelled') ? (
            <span style={{ color: 'var(--amber)' }}>{'ยังไม่ตรวจสอบ'}</span>
          ) : (
            <span style={{ color: 'var(--green)' }}>{'ตรวจผ่าน'}</span>
          )}
          {' — '}{progress.review_summary}
        </div>
      )}
      {isComplete && progress?.review_history && progress.review_history.length > 1 && (
        <div style={{ fontSize: '9px', color: 'var(--ink3)', marginTop: '1px' }}>
          ตรวจ {progress.review_history.length} รอบ
        </div>
      )}


      {/* View output button — opens Dialog popup */}
      {hasOutput && (
        <button
          className="kcard-btn view"
          onClick={() => setShowOutputDialog(true)}
        >
          View
        </button>
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

      {/* Output Dialog popup */}
      <Dialog
        open={showOutputDialog}
        icon={agentIcon(agent.name)}
        title={`${agent.name} — ${dialogTab === 'output' ? 'Output' : 'Review History'}`}
        onClose={() => { setShowOutputDialog(false); setDialogTab('output'); }}
        footer={undefined}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Output tab */}
          {dialogTab === 'output' && progress?.output && (
            <div>
              <div style={{ fontSize: '10px', color: 'var(--ink3)', marginBottom: '4px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                Output{progress?.review_summary && <span style={{ color: 'var(--green)' }}> — {progress.review_summary}</span>}
                {progress?.review_history && progress.review_history.length > 0 && (
                  <button
                    className="kcard-btn"
                    style={{ fontSize: '10px', padding: '4px 12px' }}
                    onClick={() => setDialogTab('review')}
                  >
                    📋 ดูประวัติการตรวจ
                  </button>
                )}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--ink2)', background: 'var(--cream)', borderRadius: '3px', padding: '8px 10px', border: '1px solid var(--line)', maxHeight: '400px', overflowY: 'auto' }}>
                <MarkdownRenderer content={progress.output} />
              </div>
            </div>
          )}

          {/* Review History tab */}
          {dialogTab === 'review' && progress?.review_history && progress.review_history.length > 0 && (
            <div>
              <div style={{ marginBottom: '8px' }}>
                <button
                  className="kcard-btn"
                  style={{ fontSize: '10px', padding: '4px 12px' }}
                  onClick={() => setDialogTab('output')}
                >
                  📄 ดู Output
                </button>
              </div>
              {progress.review_history.map((rh, i) => (
                <div key={i} style={{ border: '1px solid var(--line)', borderRadius: '3px', padding: '6px 8px', marginBottom: '6px', background: 'var(--paper)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                    <span style={{ fontSize: '8px', padding: '1px 4px', borderRadius: '2px', fontWeight: 700, background: rh.status === 'approved' ? 'rgba(90,122,74,0.15)' : 'rgba(160,48,32,0.15)', color: rh.status === 'approved' ? 'var(--green)' : 'var(--red)' }}>
                      {rh.status === 'approved' ? 'PASS' : 'FAIL'}
                    </span>
                    <span style={{ fontSize: '10px', color: 'var(--ink2)', fontWeight: 500 }}>รอบที่ {rh.round}</span>
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--ink3)', marginBottom: '2px' }}>{rh.summary}</div>
                  {rh.feedback && (
                    <div style={{ fontSize: '10px', color: 'var(--red)', marginBottom: '2px' }}>Feedback: {rh.feedback}</div>
                  )}
                  {rh.output_preview && (
                    <div style={{ fontSize: '9px', color: 'var(--ink3)', background: 'var(--cream)', borderRadius: '2px', padding: '4px 6px', border: '1px solid var(--line)', maxHeight: '100px', overflowY: 'auto', marginTop: '4px', whiteSpace: 'pre-wrap' }}>
                      {rh.output_preview}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </Dialog>

      {/* Image approvals — click to navigate to chat */}
      {pendingApprovals.map(pa => (
        <div key={pa.approvalId} style={{ marginTop: '4px', cursor: 'pointer' }} onClick={() => onNavigate?.()}>
          {pa.approvalStatus === 'pending' && (
            <div style={{ fontSize: '10px', color: 'var(--ink2)', marginBottom: '2px' }}>{pa.mediaType === 'video' ? '🎬' : pa.mediaType === 'tts' ? '🔊' : pa.mediaType === 'stt' ? '�' : pa.mediaType === 'vision' ? '👁️' : '�️'} {pa.prompt} — <span style={{ color: 'var(--purple)' }}>คลิกเพื่ออนุมัติใน Chat</span></div>
          )}
          {pa.approvalStatus === 'error' && (
            <div style={{ fontSize: '10px', color: 'var(--red)', marginBottom: '2px' }}>⚠ {pa.imageError} — <span style={{ color: 'var(--amber)' }}>คลิกเพื่อ Retry ใน Chat</span></div>
          )}
          {pa.approvalStatus === 'approved' && (
            <div style={{ fontSize: '10px', color: 'var(--green)' }}>✓ Approved — generating...</div>
          )}
        </div>
      ))}

      {/* Image results — type-aware rendering: video→<video>, tts→<audio>, else→<img> */}
      {imageResults.map((ir, i) => (
        <div key={i} style={{ marginTop: '4px' }}>
          {ir.mediaType === 'video' ? (
            <video src={withMediaToken(ir.imageUrl)} controls style={{ width: '100%', borderRadius: '3px', border: '1px solid var(--line)' }} />
          ) : ir.mediaType === 'tts' ? (
            <audio src={withMediaToken(ir.imageUrl)} controls style={{ width: '100%' }} />
          ) : (
            <img src={withMediaToken(ir.imageUrl)} alt={ir.prompt} style={{ width: '100%', borderRadius: '3px', border: '1px solid var(--line)' }} />
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
  onNavigate?: () => void;
}> = ({ run, onNavigate }) => {
  const [collapsed, setCollapsed] = useState(false);

  const planAgentsAsAgents: Agent[] = useMemo(() =>
    run.planAgents.map((pa, idx) => ({
      id: `run${run.runIndex}-agent-${idx}`,
      name: pa.name, role: pa.role, goal: pa.goal || '',
      tools: pa.tools || [], depends_on: pa.depends_on || [],
      status: 'Idle' as const,
    })),
  [run.planAgents, run.runIndex]);

  const planAgentNames = useMemo(() => new Set(planAgentsAsAgents.map(a => a.name)), [planAgentsAsAgents]);

  const doneCount = useMemo(() => {
    if (!run.progress) return 0;
    return run.progress.filter(p => planAgentNames.has(p.name) && (p.status === 'complete' || p.status === 'error')).length;
  }, [run.progress, planAgentNames]);
  const totalCount = planAgentsAsAgents.length;

  const overallProgress = run.progress
    ? Math.round(run.progress.filter(p => planAgentNames.has(p.name)).reduce((sum, p) => sum + (p.status === 'complete' ? 100 : p.progress || 0), 0) / Math.max(totalCount, 1))
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
          {/* Pending plan — click to navigate to chat */}
          {run.planStatus === 'pending' && (
            <div className="kcard-plan-actions" style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '6px 10px', border: '1px solid rgba(200,146,32,0.3)', background: 'rgba(200,146,32,0.05)', borderRadius: '3px', fontSize: '11px', color: 'var(--amber)' }} onClick={() => onNavigate?.()}>
              คลิกเพื่ออนุมัติแผนใน Chat
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
                onNavigate={onNavigate}
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
        </div>
      )}
    </div>
  );
};

// ============================================================
// Main TasksWindow
// ============================================================

const isPending = (n: NotificationItem): boolean => {
  if (n.messageType === 'plan') return n.planStatus === 'pending';
  if (n.messageType === 'image_approval') return n.approvalStatus === 'pending' || n.approvalStatus === 'error';
  if (n.messageType === 'agent_review') return n.reviewStatus === 'pending';
  if (n.messageType === 'tuning_proposal') return n.tuningStatus !== 'confirmed' && n.tuningStatus !== 'rejected';
  return false;
};

const getNotifIcon = (n: NotificationItem): string => {
  if (n.messageType === 'plan') return '📋';
  // Type-aware icon — matches NotificationsWindow logic
  if (n.messageType === 'image_approval') {
    const mt = n.mediaType || 'image';
    if (mt === 'video') return '🎬';
    if (mt === 'tts') return '🔊';
    if (mt === 'stt') return '📝';
    if (mt === 'vision') return '👁️';
    return '🖼️';
  }
  if (n.messageType === 'agent_review') return '🔍';
  if (n.messageType === 'tuning_proposal') return '🔧';
  return '🔔';
};

const getNotifTitle = (n: NotificationItem): string => {
  if (n.messageType === 'plan') return 'Plan Approval';
  // Type-aware title — matches NotificationsWindow logic
  if (n.messageType === 'image_approval') {
    const mt = n.mediaType || 'image';
    if (mt === 'video') return 'Video Generation';
    if (mt === 'tts') return 'Text-to-Speech';
    if (mt === 'stt') return 'Audio Transcription';
    if (mt === 'vision') return 'Vision Analysis';
    return 'Image Generation';
  }
  if (n.messageType === 'agent_review') return 'Agent Review';
  if (n.messageType === 'tuning_proposal') return 'Tuning Proposal';
  return 'Notification';
};

export const TasksWindow: React.FC<TasksWindowProps> = ({
  chatMessages,
  notifications,
  activeSessionId,
  onNavigate,
  taskItems = [],
}) => {
  const runs = useMemo(() => buildRuns(chatMessages), [chatMessages]);

  // Pending notifications from OTHER sessions
  const otherSessionPending = useMemo(() =>
    notifications.filter(n => isPending(n) && n.sessionId !== activeSessionId),
    [notifications, activeSessionId]
  );

  // Group by session
  const otherSessions = useMemo(() => {
    const map = new Map<string, { title: string; items: NotificationItem[] }>();
    for (const n of otherSessionPending) {
      if (!map.has(n.sessionId)) {
        map.set(n.sessionId, { title: n.sessionTitle || 'Unknown', items: [] });
      }
      map.get(n.sessionId)!.items.push(n);
    }
    return Array.from(map.entries());
  }, [otherSessionPending]);

  // Build unified list: current session runs + taskItems from other sessions
  // Filter out taskItems that have a matching run in current session (same task, avoid duplicate display)
  const runInputs = new Set(runs.map(r => (r.userMessage || '').trim().slice(0, 60).toLowerCase()));
  const currentSessionTasks = taskItems.filter(t =>
    (!t.session_id || t.session_id === activeSessionId) &&
    !runInputs.has((t.input || '').trim().slice(0, 60).toLowerCase())
  );
  const otherSessionTasks = taskItems.filter(t => t.session_id && t.session_id !== activeSessionId);

  const hasContent = runs.length > 0 || otherSessions.length > 0 || taskItems.length > 0;

  if (!hasContent) {
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
    <div className="tasks-list" style={{ overflowY: 'auto', maxHeight: '100%' }}>
      {/* Current session runs — highlighted with amber left border */}
      {runs.map(run => (
        <div key={`run-${run.runIndex}`} style={{ borderLeft: '3px solid var(--amber)', paddingLeft: '6px', marginBottom: '6px' }}>
          <PlanFrame
            run={run}
            onNavigate={() => onNavigate(activeSessionId || '')}
          />
        </div>
      ))}

      {/* Current session task items — highlighted */}
      {currentSessionTasks.map(task => (
        <div key={`ct-${task.id}`} style={{ borderLeft: '3px solid var(--amber)', paddingLeft: '6px', marginBottom: '6px' }}>
          <div className="plan-frame" style={{ marginBottom: '0' }}>
            <div className="plan-frame-hdr">
              <span className="pf-ic">📋</span>
              <div className="pf-info">
                <div className="pf-title">{task.input?.slice(0, 60) || task.title?.slice(0, 60) || 'งานไม่มีชื่อ'}</div>
                <div className="pf-bar"><div className="pf-bar-fill" style={{ width: `${task.progress || 0}%` }} /></div>
              </div>
              <span className="pf-badge" style={{
                background: task.status === 'done' ? 'rgba(90,122,74,0.15)' : task.status === 'running' ? 'rgba(192,80,30,0.15)' : 'rgba(200,180,50,0.15)',
                color: task.status === 'done' ? 'var(--green)' : task.status === 'running' ? 'var(--orange)' : 'var(--amber)',
              }}>{task.status}</span>
            </div>
            {task.plan_agents && task.plan_agents.length > 0 && (
              <div className="plan-frame-body" style={{ padding: '4px 10px' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {task.plan_agents.map((a, i) => (
                    <span key={i} style={{ fontSize: '9px', padding: '1px 4px', borderRadius: '2px', background: 'var(--cream)', color: 'var(--ink2)' }}>{agentIcon(a.name)} {a.name}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Other session tasks — dimmed */}
      {otherSessionTasks.map(task => (
        <div key={`ot-${task.id}`} style={{ borderLeft: '3px solid var(--line)', paddingLeft: '6px', marginBottom: '6px', opacity: 0.6 }}>
          <div className="plan-frame" style={{ marginBottom: '0' }}>
            <div className="plan-frame-hdr">
              <span className="pf-ic">📋</span>
              <div className="pf-info">
                <div className="pf-title">{task.input?.slice(0, 60) || task.title?.slice(0, 60) || 'งานไม่มีชื่อ'}</div>
                <div className="pf-bar"><div className="pf-bar-fill" style={{ width: `${task.progress || 0}%` }} /></div>
              </div>
              <span className="pf-badge" style={{
                background: task.status === 'done' ? 'rgba(90,122,74,0.15)' : task.status === 'running' ? 'rgba(192,80,30,0.15)' : 'rgba(200,180,50,0.15)',
                color: task.status === 'done' ? 'var(--green)' : task.status === 'running' ? 'var(--orange)' : 'var(--amber)',
              }}>{task.status}</span>
            </div>
          </div>
        </div>
      ))}

      {/* Other sessions pending — compact */}
      {otherSessions.map(([sessionId, group]) => (
        <div key={sessionId} style={{ marginBottom: '6px' }}>
          {group.items.map(n => (
            <div
              key={n.id}
              className="plan-frame pending"
              style={{ cursor: 'pointer', marginBottom: '4px', opacity: 0.7 }}
              onClick={() => onNavigate(sessionId)}
            >
              <div className="plan-frame-hdr">
                <span className="pf-ic">{getNotifIcon(n)}</span>
                <div className="pf-info">
                  <div className="pf-title">{getNotifTitle(n)} — {group.title}</div>
                  <div className="pf-bar"><div className="pf-bar-fill" style={{ width: '0%' }} /></div>
                </div>
                <span className="pf-badge">รอดำเนินการ</span>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};
