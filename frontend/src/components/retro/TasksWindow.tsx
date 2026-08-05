import { useState, useMemo, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import type { ChatMessage, AgentProgressEntry, PlanAgent, ResultAgent, PlanStatus, NotificationItem, TaskItem } from '../chatTypes';
import type { Agent, PendingApproval, ImageResult } from '../../types/platform';
import MarkdownRenderer from '../MarkdownRenderer';
import { withMediaToken } from '../../utils/media';
import { extractSourceUrls } from '../../utils/sources';

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
// Helpers (kept from original)
// ============================================================

const agentIcon = (name: string): string => {
  const n = name.toLowerCase();
  if (n.includes('analyst') || n.includes('product')) return '📊';
  if (n.includes('copy') || n.includes('writer') || n.includes('content')) return '✍️';
  if (n.includes('image') || n.includes('design') || n.includes('visual') || n.includes('artist') || n.includes('poster')) return '🎨';
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
    // Also extract from image_approval cards merged with image_result — App.tsx merges
    // image_result into image_approval cards (approvalStatus='generated', imageUrl set)
    // instead of adding image_result as a separate chatMessage, so buildRuns must check
    // both message types to populate imageResults during live sessions.
    if (msg.messageType === 'image_approval' && msg.approvalStatus === 'generated' && msg.imageUrl) {
      const alreadyAdded = currentRun.imageResults.some(ir => ir.approvalId === (msg.approvalId || ''));
      if (!alreadyAdded) {
        currentRun.imageResults.push({
          imageUrl: msg.imageUrl || '', prompt: msg.imagePrompt || '', approvalId: msg.approvalId || '',
          mediaType: msg.mediaType || 'image', agentName: msg.agentName || '',
        });
      }
    }
  }
  if (currentRun) runs.push(currentRun);
  const visible = runs.filter(r => r.planStatus !== 'rejected' && (r.planAgents.length > 0 || r.result));
  visible.forEach((r, i) => { r.runIndex = i; });
  if (visible.length > 0) visible[visible.length - 1].isLatest = true;
  return visible;
}

// Compute waves from depends_on — agents with no deps go in wave 0,
// agents depending on wave N agents go in wave N+1
function computeWaves(agents: { name: string; depends_on?: string[] }[]): { name: string; depends_on: string[] }[][] {
  const agentMap = new Map(agents.map(a => [a.name, a.depends_on || []]));
  const waves: { name: string; depends_on: string[] }[][] = [];
  const assigned = new Set<string>();

  for (let iter = 0; iter < agents.length; iter++) {
    const wave: { name: string; depends_on: string[] }[] = [];
    for (const a of agents) {
      if (assigned.has(a.name)) continue;
      const deps = a.depends_on || [];
      // Agent goes in this wave if all its deps are already assigned or not in our agent set
      if (deps.every(d => assigned.has(d) || !agentMap.has(d))) {
        wave.push({ name: a.name, depends_on: deps });
      }
    }
    if (wave.length === 0) break;
    wave.forEach(w => assigned.add(w.name));
    waves.push(wave);
  }
  // Any remaining agents (circular deps) go in last wave
  if (assigned.size < agents.length) {
    waves.push(agents.filter(a => !assigned.has(a.name)).map(a => ({ name: a.name, depends_on: a.depends_on || [] })));
  }
  return waves;
}

// Status helpers
const statusInfo = (status: string) => {
  const s = (status || '').toLowerCase();
  if (s.includes('stop')) return { cls: 'stopped', text: '⏹ ยกเลิก', color: 'var(--amber)' };
  if (s.includes('complete') || s.includes('done')) return { cls: 'done', text: '✓ Done', color: 'var(--green)' };
  if (s.includes('error')) return { cls: 'error', text: 'Error', color: 'var(--red)' };
  if (s.includes('running')) return { cls: 'running', text: 'Running', color: 'var(--amber)' };
  if (s.includes('waiting')) return { cls: 'waiting', text: 'Waiting', color: 'var(--purple)' };
  if (s.includes('review')) return { cls: 'review', text: 'Review', color: 'var(--blue)' };
  return { cls: 'pending', text: 'Pending', color: 'var(--ink3)' };
};

// ============================================================
// Left Panel: Task List Item
// ============================================================

const TaskListItem: React.FC<{
  icon: string;
  title: string;
  progress: number;
  statusText: string;
  statusCls: string;
  active: boolean;
  dimmed?: boolean;
  onClick: () => void;
}> = ({ icon, title, progress, statusText, statusCls, active, dimmed, onClick }) => (
  <div className={`tw-task-item${active ? ' active' : ''}${dimmed ? ' dimmed' : ''}`} onClick={onClick}>
    <span className="tw-ti-icon">{icon}</span>
    <div className="tw-ti-info">
      <div className="tw-ti-title">{title}</div>
      <div className="tw-ti-bar"><div className="tw-ti-bar-fill" style={{ width: `${progress}%` }} /></div>
    </div>
    <span className={`tw-ti-badge ${statusCls}`}>{statusText}</span>
  </div>
);

// ============================================================
// Center Panel: Flow Node (agent card in flow diagram)
// ============================================================

const FlowNode: React.FC<{
  agent: Agent;
  progress?: AgentProgressEntry;
  selected: boolean;
  onClick: () => void;
}> = ({ agent, progress, selected, onClick }) => {
  const rawStatus = progress?.status || 'pending';
  // If review_summary indicates a stop, override "complete" → "stopped" for display
  const wasStopped = progress?.reviewSummary?.includes('หยุดโดย') || progress?.review_summary?.includes('หยุดโดย');
  const status = (rawStatus === 'complete' && wasStopped) ? 'stopped' : rawStatus;
  const si = statusInfo(status);
  const pct = status === 'complete' ? 100 : status === 'error' ? 100 : status === 'stopped' ? 100 : progress?.progress || 0;
  const isComplete = status === 'complete';
  const isError = status === 'error';
  const isRunning = status === 'running';
  const isWaitingApproval = status === 'waiting_approval';
  const isAwaitingReview = status === 'awaiting_review';
  const deps = (agent as any).depends_on || [];

  return (
    <div className={`tw-node ${si.cls}${selected ? ' selected' : ''}`} onClick={onClick}>
      <div className="tw-node-av">{agentIcon(agent.name)}</div>
      <div className="tw-node-name">{agent.name}</div>
      <div className="tw-node-role">{agent.role}</div>
      <span className={`tw-node-status ${si.cls}`}>{si.text}</span>

      {/* Waiting for deps */}
      {deps.length > 0 && !isComplete && !isError && !isRunning && (
        <div className="tw-node-deps">⏳ รอ: {deps.join(', ')}</div>
      )}

      {/* Waiting approval */}
      {isWaitingApproval && (
        <div className="tw-node-waiting">รอผู้ใช้กด Generate</div>
      )}

      {/* Live reasoning preview — parity with Claude/ChatGPT visible thinking */}
      {isRunning && !isWaitingApproval && !isAwaitingReview && (
        <div className="tw-node-thinking">
          {progress?.thinking ? (
            <span className="tw-node-thinking-text">{progress.thinking.slice(-140)}</span>
          ) : progress?.tool_description ? (
            <span>{progress.tool_description}</span>
          ) : (
            <span className="tw-node-thinking-dots">
              <span className="animate-thinking" />
              <span className="animate-thinking" />
              <span className="animate-thinking" />
            </span>
          )}
        </div>
      )}

      {/* Awaiting review */}
      {isAwaitingReview && (
        <div className="tw-node-review">
          Manager กำลังตรวจ{progress?.review_round ? ` (รอบที่ ${progress.review_round})` : ''}...
          {progress?.review_summary && <div className="tw-node-review-sub">{progress.review_summary}</div>}
        </div>
      )}

      {/* Review summary for completed agents */}
      {isComplete && progress?.review_summary && (
        <div className="tw-node-review-done">
          {progress.review_summary.includes('หยุดโดย') || progress.review_summary.includes('ยังไม่ตรวจ') || progress.review_summary.includes('Cancelled') ? (
            <span style={{ color: 'var(--amber)' }}>ยังไม่ตรวจสอบ</span>
          ) : (
            <span style={{ color: 'var(--green)' }}>ตรวจผ่าน</span>
          )}
          {' — '}{progress.review_summary}
        </div>
      )}
      {isComplete && progress?.review_history && progress.review_history.length > 1 && (
        <div className="tw-node-review-count">ตรวจ {progress.review_history.length} รอบ</div>
      )}

      <div className="tw-node-prog">
        <div className="tw-node-prog-fill" style={{ width: `${pct}%`, background: si.color }} />
      </div>
    </div>
  );
};

// ============================================================
// Right Panel: Result Detail
// ============================================================

const ResultPanel: React.FC<{
  agent: Agent | null;
  progress?: AgentProgressEntry;
  imageResults: ImageResult[];
}> = ({ agent, progress, imageResults }) => {
  const [tab, setTab] = useState<'output' | 'review' | 'media' | 'info'>('output');
  const [expandedPreview, setExpandedPreview] = useState<number | null>(null);
  const [imageZoom, setImageZoom] = useState<string | null>(null);

  // Reset to output tab when agent changes
  useEffect(() => {
    setTab('output');
  }, [agent?.id]);

  if (!agent) {
    return (
      <div className="tw-result-empty">
        <div className="tw-rp-icon">👤</div>
        <div>คลิก agent ในแผนผังเพื่อดูผลลัพธ์</div>
      </div>
    );
  }

  const rawStatus = progress?.status || 'pending';
  const wasStopped = progress?.reviewSummary?.includes('หยุดโดย') || progress?.review_summary?.includes('หยุดโดย');
  const status = (rawStatus === 'complete' && wasStopped) ? 'stopped' : rawStatus;
  const si = statusInfo(status);
  const pct = status === 'complete' ? 100 : status === 'error' ? 100 : status === 'stopped' ? 100 : progress?.progress || 0;

  const hasOutput = !!progress?.output;
  const hasReview = !!(progress?.review_history && progress.review_history.length > 0);
  const hasMedia = imageResults.length > 0;

  return (
    <>
      {/* Lightbox overlay — in-app full-screen image viewer */}
      {imageZoom && (
        <div className="tw-lightbox" onClick={() => setImageZoom(null)}>
          <img src={imageZoom} alt="Zoomed" />
        </div>
      )}

    <div className="tw-result-content">
      {/* Tab bar */}
      <div className="tw-rp-tabs">
        <button className={`tw-rp-tab${tab === 'output' ? ' active' : ''}`} onClick={() => setTab('output')}>
          Output{hasOutput && <span className="tw-rp-tab-badge has">✓</span>}
        </button>
        <button className={`tw-rp-tab${tab === 'review' ? ' active' : ''}`} onClick={() => setTab('review')}>
          Review{hasReview && <span className="tw-rp-tab-badge has">{progress?.review_history?.length}</span>}
        </button>
        <button className={`tw-rp-tab${tab === 'media' ? ' active' : ''}`} onClick={() => setTab('media')}>
          Media{hasMedia && <span className="tw-rp-tab-badge has">{imageResults.length}</span>}
        </button>
        <button className={`tw-rp-tab${tab === 'info' ? ' active' : ''}`} onClick={() => setTab('info')}>
          Info
        </button>
      </div>

      {/* Agent header — compact row */}
      <div className="tw-rp-hdr">
        <div className="tw-rp-av">{agentIcon(agent.name)}</div>
        <div className="tw-rp-name">{agent.name}</div>
        <div className="tw-rp-role">· {agent.role}</div>
        <span className={`tw-rp-status ${si.cls}`}>{si.text}</span>
      </div>

      {/* Tab content */}
      {tab === 'output' && (
        <>
          {/* Progress */}
          <div className="tw-rp-section">
            <div className="tw-rp-lbl">Progress</div>
            <div className="tw-rp-prog-bar"><div className="tw-rp-prog-fill" style={{ width: `${pct}%`, background: si.color }} /></div>
            <div className="tw-rp-prog-text">{pct}%</div>
          </div>

          {/* Output */}
          {hasOutput ? (
            <div className="tw-rp-section">
              <div className="tw-rp-lbl">Output</div>
              {progress?.review_summary && (
                <div style={{ fontSize: '10px', marginBottom: '4px' }}>
                  {status === 'complete' ? (
                    progress.review_summary.includes('หยุดโดย') || progress.review_summary.includes('ยังไม่ตรวจ') || progress.review_summary.includes('Cancelled')
                      ? <span style={{ color: 'var(--amber)' }}>ยังไม่ตรวจสอบ</span>
                      : <span style={{ color: 'var(--green)' }}>ตรวจผ่าน</span>
                  ) : (
                    <span style={{ color: 'var(--amber)' }}>Feedback</span>
                  )}
                  {' — '}{progress.review_summary}
                </div>
              )}
              <div className="tw-rp-output">
                <MarkdownRenderer content={progress!.output!} />
              </div>
              {(() => {
                const chips = extractSourceUrls(progress!.output);
                if (chips.length === 0) return null;
                return (
                  <div className="tw-rp-sources">
                    <span className="tw-rp-sources-lbl">แหล่งข้อมูล</span>
                    <div className="tw-rp-chips">
                      {chips.map((c, i) => (
                        <a
                          key={i}
                          className="tw-rp-chip"
                          href={c.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={c.url}
                        >
                          {c.label}
                        </a>
                      ))}
                    </div>
                  </div>
                );
              })()}
            </div>
          ) : isRunning ? (
            <div className="tw-rp-section">
              <div className="tw-rp-lbl">Thinking</div>
              {/* Tool context — single line above the streaming reasoning */}
              {progress?.tool_description && (
                <div className="tw-rp-tool-desc">{progress.tool_description}</div>
              )}
              {progress?.thinking ? (
                <div className="tw-rp-thinking">{progress.thinking}</div>
              ) : (
                <div className="tw-rp-thinking-waiting">
                  <span className="tw-rp-thinking-dots">
                    {[0, 0.2, 0.4].map((d, i) => (
                      <span key={i} className="animate-thinking" style={{ animationDelay: `${d}s` }} />
                    ))}
                  </span>
                  กำลังคิด...
                </div>
              )}
            </div>
          ) : (
            <div className="tw-rp-section">
              <div className="tw-rp-lbl">Output</div>
              <div className="tw-rp-empty">ยังไม่มี output</div>
            </div>
          )}
        </>
      )}

      {tab === 'review' && (
        hasReview ? (
          <div className="tw-rp-section">
            <div className="tw-rp-lbl">Review History ({progress!.review_history!.length} รอบ)</div>
            {progress!.review_history!.map((rh, i) => (
              <div key={i} className="tw-rp-review-item">
                <div className="tw-rp-review-hdr">
                  <span className={`tw-rp-review-badge ${rh.status === 'approved' ? 'pass' : 'fail'}`}>
                    {rh.status === 'approved' ? 'PASS' : 'FAIL'}
                  </span>
                  <span className="tw-rp-review-round">รอบที่ {rh.round}</span>
                </div>
                <div className="tw-rp-review-summary">{rh.summary}</div>
                {rh.feedback && <div className="tw-rp-review-feedback">Feedback: {rh.feedback}</div>}
                {rh.output_preview && (
                  <div
                    className={`tw-rp-review-preview${expandedPreview === i ? ' expanded' : ''}`}
                    onClick={() => setExpandedPreview(expandedPreview === i ? null : i)}
                    title="Click to expand/collapse"
                  >{rh.output_preview}</div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="tw-rp-section">
            <div className="tw-rp-lbl">Review History</div>
            <div style={{ fontSize: '10px', color: 'var(--ink3)', fontStyle: 'italic' }}>ไม่มีประวัติการตรวจ</div>
          </div>
        )
      )}

      {tab === 'media' && (
        hasMedia ? (
          <div className="tw-rp-section">
            <div className="tw-rp-lbl">Media Results ({imageResults.length})</div>
            <div className="tw-rp-media-grid">
            {imageResults.map((ir, i) => (
              <div key={i} className="tw-rp-media-item">
                {ir.mediaType === 'video' ? (
                  <video src={withMediaToken(ir.imageUrl)} controls className="tw-rp-media-el" />
                ) : ir.mediaType === 'tts' ? (
                  <audio src={withMediaToken(ir.imageUrl)} controls style={{ width: '100%' }} />
                ) : (
                  <img
                    src={withMediaToken(ir.imageUrl)}
                    alt={ir.prompt}
                    className="tw-rp-media-el"
                    onClick={() => setImageZoom(withMediaToken(ir.imageUrl))}
                  />
                )}
                <div className="tw-rp-media-prompt" title={ir.prompt}>{ir.prompt}</div>
              </div>
            ))}
            </div>
          </div>
        ) : (
          <div className="tw-rp-section">
            <div className="tw-rp-lbl">Media Results</div>
            <div style={{ fontSize: '10px', color: 'var(--ink3)', fontStyle: 'italic' }}>ไม่มีสื่อที่สร้าง</div>
          </div>
        )
      )}

      {tab === 'info' && (
        <>
          {/* Progress */}
          <div className="tw-rp-section">
            <div className="tw-rp-lbl">Progress</div>
            <div className="tw-rp-prog-bar"><div className="tw-rp-prog-fill" style={{ width: `${pct}%`, background: si.color }} /></div>
            <div className="tw-rp-prog-text">{pct}%</div>
          </div>

          {/* Goal */}
          {agent.goal && (
            <div className="tw-rp-section">
              <div className="tw-rp-lbl">Goal</div>
              <div className="tw-rp-val">{agent.goal}</div>
            </div>
          )}

          {/* Tools */}
          {agent.tools && agent.tools.length > 0 && (
            <div className="tw-rp-section">
              <div className="tw-rp-lbl">Tools</div>
              <div className="tw-rp-tools">
                {agent.tools.map(t => <span key={t} className="tw-rp-tool">{t}</span>)}
              </div>
            </div>
          )}
        </>
      )}
    </div>
    </>
  );
};

// ============================================================
// Notification helpers (kept from original)
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

// ============================================================
// Main TasksWindow — 3-panel layout
// ============================================================

export const TasksWindow: React.FC<TasksWindowProps> = ({
  chatMessages,
  notifications,
  activeSessionId,
  onNavigate,
  taskItems = [],
}) => {
  const runs = useMemo(() => buildRuns(chatMessages), [chatMessages]);
  const [selectedRunIdx, setSelectedRunIdx] = useState<number>(-1);
  const [selectedAgentName, setSelectedAgentName] = useState<string | null>(null);

  // Auto-select latest run when runs change
  useEffect(() => {
    if (runs.length > 0 && (selectedRunIdx < 0 || selectedRunIdx >= runs.length)) {
      setSelectedRunIdx(runs.length - 1);
    }
  }, [runs, selectedRunIdx]);

  // Other session pending notifications
  const otherSessionPending = useMemo(() =>
    notifications.filter(n => isPending(n) && n.sessionId !== activeSessionId),
    [notifications, activeSessionId]
  );

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

  // Task items filtering (same logic as original)
  const runInputs = new Set(runs.map(r => (r.userMessage || '').trim().slice(0, 60).toLowerCase()));
  const currentSessionTasks = taskItems.filter(t =>
    (!t.session_id || t.session_id === activeSessionId) &&
    !runInputs.has((t.input || '').trim().slice(0, 60).toLowerCase())
  );
  const otherSessionTasks = taskItems.filter(t => t.session_id && t.session_id !== activeSessionId);

  const hasContent = runs.length > 0 || otherSessions.length > 0 || taskItems.length > 0;

  // Selected run data
  const selectedRun = selectedRunIdx >= 0 && selectedRunIdx < runs.length ? runs[selectedRunIdx] : null;

  // Compute waves for selected run
  const waves = useMemo(() => {
    if (!selectedRun) return [];
    const agents = selectedRun.planAgents.map(pa => ({ name: pa.name, depends_on: pa.depends_on || [] }));
    return computeWaves(agents);
  }, [selectedRun]);

  // Convert plan agents to Agent[] for lookup
  const planAgentsMap = useMemo(() => {
    if (!selectedRun) return new Map<string, Agent>();
    const m = new Map<string, Agent>();
    selectedRun.planAgents.forEach((pa, idx) => {
      m.set(pa.name, {
        id: `run${selectedRun.runIndex}-agent-${idx}`,
        name: pa.name, role: pa.role, goal: pa.goal || '',
        tools: pa.tools || [], depends_on: pa.depends_on || [],
        status: 'Idle' as const,
      });
    });
    return m;
  }, [selectedRun]);

  // Selected agent data
  const selectedAgent = selectedAgentName ? planAgentsMap.get(selectedAgentName) || null : null;
  const selectedAgentProgress = selectedAgentName && selectedRun?.progress
    ? selectedRun.progress.find(p => p.name === selectedAgentName)
    : undefined;

  // Image results for selected agent
  const selectedAgentImages = useMemo(() => {
    if (!selectedRun || !selectedAgentName) return [];
    const agentApprovals = selectedRun.pendingApprovals.filter(pa => pa.agentName.toLowerCase() === selectedAgentName.toLowerCase());
    const agentApprovalIds = new Set(agentApprovals.map(pa => pa.approvalId));
    return selectedRun.imageResults.filter(ir => {
      if (ir.agentName && ir.agentName.toLowerCase() === selectedAgentName.toLowerCase()) return true;
      if (!ir.agentName && agentApprovalIds.has(ir.approvalId)) return true;
      return false;
    });
  }, [selectedRun, selectedAgentName]);

  // Reset agent selection when run changes
  useEffect(() => {
    setSelectedAgentName(null);
  }, [selectedRunIdx]);

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

  // Compute overall progress for selected run
  let runOverallProgress = 0;
  let runStatusText = '';
  let runStatusCls = '';
  let runFrameIcon = '📝';
  if (selectedRun) {
    const planAgentNames = new Set(selectedRun.planAgents.map(a => a.name));
    const totalCount = selectedRun.planAgents.length;
    runOverallProgress = selectedRun.progress
      ? Math.round(selectedRun.progress.filter(p => planAgentNames.has(p.name)).reduce((sum, p) => sum + (p.status === 'complete' ? 100 : p.progress || 0), 0) / Math.max(totalCount, 1))
      : selectedRun.result ? 100 : 0;
    const wasStopped = selectedRun.progress?.some(p => p.reviewSummary?.includes('หยุดโดย') || p.review_summary?.includes('หยุดโดย'));
    const frameStatus = selectedRun.planStatus === 'pending' ? 'pending' : selectedRun.result ? (wasStopped ? 'stopped' : 'done') : 'running';
    runStatusText = selectedRun.planStatus === 'pending' ? 'รออนุมัติ' : selectedRun.result ? (selectedRun.result.error ? 'Error' : wasStopped ? 'ยกเลิก' : 'เสร็จสิ้น') : runOverallProgress > 0 ? `${runOverallProgress}%` : 'เริ่ม...';
    runStatusCls = frameStatus;
    runFrameIcon = selectedRun.planType === 'create_agents' ? '🤖' : '📝';
  }

  const hasWaitingApproval = selectedRun?.progress?.some(ap => ap.status === 'waiting_approval');
  const hasAwaitingReview = selectedRun?.progress?.some(ap => ap.status === 'awaiting_review');
  const allComplete = selectedRun?.progress && selectedRun.planAgents.length > 0 && selectedRun.planAgents.every(a => {
    const p = selectedRun.progress!.find(ap => ap.name === a.name);
    return p?.status === 'complete' || p?.status === 'error';
  });

  return (
    <div className="tw-layout">
      {/* ===== LEFT: Task List ===== */}
      <div className="tw-task-list">
        {runs.map((run, idx) => {
          const planAgentNames = new Set(run.planAgents.map(a => a.name));
          const totalCount = run.planAgents.length;
          const prog = run.progress
            ? Math.round(run.progress.filter(p => planAgentNames.has(p.name)).reduce((sum, p) => sum + (p.status === 'complete' ? 100 : p.progress || 0), 0) / Math.max(totalCount, 1))
            : run.result ? 100 : 0;
          const runWasStopped = run.progress?.some(p => p.reviewSummary?.includes('หยุดโดย') || p.review_summary?.includes('หยุดโดย'));
          const st = run.planStatus === 'pending' ? 'pending' : run.result ? (runWasStopped ? 'stopped' : 'done') : 'running';
          const stText = run.planStatus === 'pending' ? 'รอ' : run.result ? (run.result.error ? 'Error' : runWasStopped ? 'ยกเลิก' : 'Done') : `${prog}%`;
          return (
            <TaskListItem
              key={`run-${run.runIndex}`}
              icon={run.planType === 'create_agents' ? '🤖' : '📝'}
              title={run.userMessage || `Run ${run.runIndex + 1}`}
              progress={prog}
              statusText={stText}
              statusCls={st}
              active={idx === selectedRunIdx}
              onClick={() => setSelectedRunIdx(idx)}
            />
          );
        })}

        {/* Current session task items */}
        {currentSessionTasks.map(task => (
          <div key={`ct-${task.id}`}>
            <TaskListItem
              icon="📋"
              title={task.input?.slice(0, 50) || task.title?.slice(0, 50) || 'งานไม่มีชื่อ'}
              progress={task.progress || 0}
              statusText={task.status === 'stopped' ? 'ยกเลิก' : task.status === 'done' ? 'เสร็จสิ้น' : task.status === 'running' ? 'กำลังทำงาน' : 'รออนุมัติ'}
              statusCls={task.status === 'done' ? 'done' : task.status === 'stopped' ? 'stopped' : task.status === 'running' ? 'running' : 'pending'}
              active={false}
              onClick={() => {}}
            />
            {task.plan_agents && task.plan_agents.length > 0 && (
              <div className="tw-ti-agents">
                {task.plan_agents.map((a, i) => (
                  <span key={i} className="tw-ti-agent-tag">{agentIcon(a.name)} {a.name}</span>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Other session tasks — dimmed */}
        {otherSessionTasks.map(task => (
          <TaskListItem
            key={`ot-${task.id}`}
            icon="📋"
            title={task.input?.slice(0, 50) || task.title?.slice(0, 50) || 'งานไม่มีชื่อ'}
            progress={task.progress || 0}
            statusText={task.status || 'pending'}
            statusCls={task.status === 'done' ? 'done' : task.status === 'running' ? 'running' : 'pending'}
            active={false}
            dimmed
            onClick={() => task.session_id && onNavigate(task.session_id)}
          />
        ))}

        {/* Other sessions pending notifications */}
        {otherSessions.map(([sessionId, group]) => (
          <div key={sessionId}>
            {group.items.map(n => (
              <TaskListItem
                key={n.id}
                icon={getNotifIcon(n)}
                title={`${getNotifTitle(n)} — ${group.title}`}
                progress={0}
                statusText="รอ"
                statusCls="pending"
                active={false}
                dimmed
                onClick={() => onNavigate(sessionId)}
              />
            ))}
          </div>
        ))}
      </div>

      {/* ===== CENTER: Flow View ===== */}
      <div className="tw-flow">
        {selectedRun ? (
          <>
            {/* Task header */}
            <div className="tw-flow-header">
              <span className="tw-flow-icon">{runFrameIcon}</span>
              <div className="tw-flow-info">
                <div className="tw-flow-title">{selectedRun.userMessage || `Run ${selectedRun.runIndex + 1}`}</div>
                <div className="tw-flow-bar"><div className="tw-flow-bar-fill" style={{ width: `${runOverallProgress}%` }} /></div>
              </div>
              <span className={`tw-flow-badge ${runStatusCls}`}>{runStatusText}</span>
              {selectedRun.planAgents.length > 0 && (
                <span className="tw-flow-count">
                  {selectedRun.progress?.filter(p => selectedRun.planAgents.some(a => a.name === p.name) && (p.status === 'complete' || p.status === 'error')).length || 0}/{selectedRun.planAgents.length}
                </span>
              )}
            </div>

            {/* Pending plan — click to navigate to chat */}
            {selectedRun.planStatus === 'pending' && (
              <div className="tw-flow-banner pending" onClick={() => onNavigate(activeSessionId || '')}>
                คลิกเพื่ออนุมัติแผนใน Chat
              </div>
            )}

            {/* Wave-based flow diagram */}
            {waves.map((wave, waveIdx) => {
              const isLast = waveIdx === waves.length - 1;
              const isSynthesis = isLast && wave.length === 1 && wave[0].name.toLowerCase().includes('manager');
              return (
                <div key={waveIdx}>
                  <div className="tw-wave-label">
                    {isSynthesis ? 'Synthesis' : `Wave ${waveIdx + 1}`}
                  </div>
                  <div className="tw-nodes">
                    {wave.map(w => {
                      const agent = planAgentsMap.get(w.name);
                      if (!agent) return null;
                      const prog = selectedRun.progress?.find(p => p.name === w.name);
                      return (
                        <FlowNode
                          key={w.name}
                          agent={agent}
                          progress={prog}
                          selected={selectedAgentName === w.name}
                          onClick={() => setSelectedAgentName(w.name)}
                        />
                      );
                    })}
                  </div>
                  {!isLast && <div className="tw-connector" />}
                </div>
              );
            })}

            {/* Status banners */}
            {hasWaitingApproval && !selectedRun.result && (
              <div className="tw-flow-banner waiting">
                รอผู้ใช้กด Generate เพื่อสร้างภาพ/วิดีโอ
              </div>
            )}
            {hasAwaitingReview && !selectedRun.result && (
              <div className="tw-flow-banner review">
                Manager กำลังตรวจผลงานของ agent...
              </div>
            )}
            {allComplete && !selectedRun.result && !hasWaitingApproval && !hasAwaitingReview && (
              <div className="tw-flow-banner synthesizing">
                <Loader2 size={12} className="animate-spin" /> {(() => {
                  const mgr = selectedRun.progress?.find(p => p.name === 'Manager');
                  if (mgr && mgr.progress && mgr.progress > 0) {
                    return `${mgr.current_task || 'Manager กำลังสรุปผล...'} (${mgr.progress}%)`;
                  }
                  return 'Combining all agent outputs...';
                })()}
              </div>
            )}
          </>
        ) : (
          <div className="tw-flow-empty">
            <div style={{ fontSize: '24px', marginBottom: '6px' }}>🔀</div>
            <div>เลือก task จากรายการด้านซ้าย</div>
          </div>
        )}
      </div>

      {/* ===== RIGHT: Result Panel ===== */}
      <div className="tw-result">
        <ResultPanel
          agent={selectedAgent}
          progress={selectedAgentProgress}
          imageResults={selectedAgentImages}
        />
      </div>
    </div>
  );
};
