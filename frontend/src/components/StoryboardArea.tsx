import { useState, useMemo } from 'react';
import {
  Loader2, CheckCircle, XCircle, Bot, Zap, Image as ImageIcon,
  Video, PenTool, ChevronDown, ChevronUp, Pencil, Brain,
  GitBranch, Cpu, Download, RotateCw, Copy, Eye, ChevronRight,
} from 'lucide-react';
import type { Agent, PendingApproval, ImageResult } from '../types/platform';
import type { ChatMessage, AgentProgressEntry, PlanAgent, ResultAgent, PlanStatus } from './chatTypes';
import { displayModelId } from './ModelPicker';
import MarkdownRenderer from './MarkdownRenderer';

// ============================================================
// Types
// ============================================================

interface StoryboardProps {
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

const getAgentIcon = (name: string): React.ReactNode => {
  const lower = name.toLowerCase();
  if (lower.includes('image') || lower.includes('visual') || lower.includes('artist')) return <ImageIcon className="w-4 h-4" />;
  if (lower.includes('video')) return <Video className="w-4 h-4" />;
  if (lower.includes('copy') || lower.includes('writer') || lower.includes('content')) return <PenTool className="w-4 h-4" />;
  if (lower.includes('review') || lower.includes('qa')) return <CheckCircle className="w-4 h-4" />;
  if (lower.includes('plan') || lower.includes('strateg')) return <Brain className="w-4 h-4" />;
  return <Bot className="w-4 h-4" />;
};

interface WaveGroup {
  waveIndex: number;
  agents: { agent: Agent; specIndex: number }[];
  dependsOn: string[];
  upstreamWaveIndices: number[];
}

function computeWaves(agents: Agent[]): WaveGroup[] {
  const nameToAgent = new Map<string, Agent>();
  agents.forEach((a) => nameToAgent.set(a.name.toLowerCase(), a));

  const depsMap = new Map<string, string[]>();
  agents.forEach((a) => {
    const deps = (a as any).depends_on || [];
    depsMap.set(
      a.name.toLowerCase(),
      (Array.isArray(deps) ? deps : []).filter((d: string) => nameToAgent.has(d.toLowerCase()))
    );
  });

  const waves: WaveGroup[] = [];
  const completed = new Set<string>();
  const remaining = new Set(agents.map((a) => a.name.toLowerCase()));

  while (remaining.size > 0) {
    const waveAgents: { agent: Agent; specIndex: number }[] = [];
    const waveNames: string[] = [];

    agents.forEach((agent, idx) => {
      const key = agent.name.toLowerCase();
      if (completed.has(key)) return;
      const deps = depsMap.get(key) || [];
      if (deps.every((d) => completed.has(d.toLowerCase()))) {
        waveAgents.push({ agent, specIndex: idx });
        waveNames.push(key);
      }
    });

    if (waveAgents.length === 0) {
      // circular dependency — force remaining into one wave
      agents.forEach((agent, idx) => {
        const key = agent.name.toLowerCase();
        if (!completed.has(key)) {
          waveAgents.push({ agent, specIndex: idx });
          waveNames.push(key);
        }
      });
    }

    const upstreamWaves = new Set<number>();
    waveAgents.forEach(({ agent }) => {
      const deps = depsMap.get(agent.name.toLowerCase()) || [];
      deps.forEach((dep) => {
        for (let wi = 0; wi < waves.length; wi++) {
          if (waves[wi].agents.some((a) => a.agent.name.toLowerCase() === dep.toLowerCase())) {
            upstreamWaves.add(wi);
          }
        }
      });
    });

    const dependsOn: string[] = [];
    waveAgents.forEach(({ agent }) => {
      const deps = depsMap.get(agent.name.toLowerCase()) || [];
      deps.forEach((d) => {
        if (!dependsOn.includes(d)) dependsOn.push(d);
      });
    });

    waves.push({
      waveIndex: waves.length,
      agents: waveAgents,
      dependsOn,
      upstreamWaveIndices: Array.from(upstreamWaves),
    });

    waveNames.forEach((n) => {
      completed.add(n);
      remaining.delete(n);
    });
  }

  return waves;
}

// ============================================================
// Final Result Card
// ============================================================

const FinalResultCard: React.FC<{
  result: { summary: string; agents?: ResultAgent[]; error?: boolean };
  agentCount: number;
  onRetry?: () => void;
}> = ({ result, agentCount, onRetry }) => {
  const [expanded, setExpanded] = useState(true);
  const [copied, setCopied] = useState(false);
  const isError = result.error || false;

  const handleCopy = () => {
    navigator.clipboard.writeText(result.summary);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    let content = `# Task Result\n\nGenerated: ${new Date().toLocaleString()}\nAgents: ${agentCount}\n\n---\n\n${result.summary}`;
    if (result.agents && result.agents.length > 0) {
      content += '\n\n---\n\n## Agent Outputs\n\n';
      for (const a of result.agents) {
        content += `### ${a.name} (${a.role})\n\n${a.output || 'N/A'}\n\n`;
      }
    }
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `task-result-${timestamp}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mb-3 storyboard-fade-in">
      <div className={`rounded-[10px] border overflow-hidden ${
        isError ? 'border-danger/40' : 'border-success/40'
      }`}>
        {/* Header bar */}
        <div
          className={`flex items-center justify-between px-3 py-2 cursor-pointer select-none ${
            isError ? 'bg-danger/5' : 'bg-gradient-to-r from-success/10 to-accent/10'
          }`}
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center gap-2">
            {isError ? (
              <XCircle className="w-3.5 h-3.5 text-danger shrink-0" />
            ) : (
              <CheckCircle className="w-3.5 h-3.5 text-success shrink-0" />
            )}
            <span className="font-semibold text-xs text-text">
              {isError ? 'Generation Failed' : 'Final Result'}
            </span>
            {!isError && agentCount > 0 && (
              <span className="text-[10px] text-text-3 bg-surface-2 px-1.5 py-0.5 rounded">
                {agentCount} agent{agentCount > 1 ? 's' : ''}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={(e) => { e.stopPropagation(); handleCopy(); }}
              className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded text-text-3 hover:text-text hover:bg-surface-2 transition-colors"
            >
              {copied ? <CheckCircle className="w-3 h-3 text-success" /> : <Copy className="w-3 h-3" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            {!isError && (
              <button
                onClick={(e) => { e.stopPropagation(); handleDownload(); }}
                className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded text-text-3 hover:text-text hover:bg-surface-2 transition-colors"
              >
                <Download className="w-3 h-3" />
                Download
              </button>
            )}
            {isError && onRetry && (
              <button
                onClick={(e) => { e.stopPropagation(); onRetry(); }}
                className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded text-accent hover:text-accent-light hover:bg-accent/10 transition-colors"
              >
                <RotateCw className="w-3 h-3" />
                Retry
              </button>
            )}
            {expanded ? <ChevronUp className="w-3.5 h-3.5 text-text-3" /> : <ChevronDown className="w-3.5 h-3.5 text-text-3" />}
          </div>
        </div>
        {/* Content */}
        {expanded && (
          <div className="p-3 bg-bg">
            <MarkdownRenderer content={result.summary} className="text-sm" />
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================
// Review History (collapsible per-round)
// ============================================================

const ReviewHistory: React.FC<{
  history: NonNullable<AgentProgressEntry['review_history']>;
}> = ({ history }) => {
  const [expandedRounds, setExpandedRounds] = useState<Set<number>>(new Set());

  const toggleRound = (round: number) => {
    setExpandedRounds((prev) => {
      const next = new Set(prev);
      if (next.has(round)) next.delete(round);
      else next.add(round);
      return next;
    });
  };

  return (
    <div className="mb-2 space-y-1">
      <div className="text-[9px] text-text-3 uppercase tracking-wide font-medium">Review History</div>
      {history.map((entry) => {
        const isExpanded = expandedRounds.has(entry.round);
        const isApproved = entry.status === 'approved';
        return (
          <div key={entry.round} className="rounded-md border border-border/40 bg-surface/40 overflow-hidden">
            <button
              onClick={() => toggleRound(entry.round)}
              className="w-full flex items-center gap-1.5 px-2 py-1.5 hover:bg-surface-2 transition-colors"
            >
              {isExpanded ? <ChevronDown className="w-2.5 h-2.5 text-text-2 shrink-0" /> : <ChevronUp className="w-2.5 h-2.5 text-text-2 shrink-0" style={{ transform: 'rotate(90deg)' }} />}
              <span className={`text-[8px] px-1 rounded font-semibold ${isApproved ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'}`}>
                {isApproved ? 'PASS' : 'FAIL'}
              </span>
              <span className="text-[10px] text-text-2 font-medium">รอบที่ {entry.round}</span>
              <span className="text-[9px] text-text-3 truncate flex-1 text-left">{entry.summary}</span>
            </button>
            {isExpanded && (
              <div className="px-2 pb-2 space-y-1.5">
                <div className="text-[9px] text-text-3">
                  <span className="font-medium text-text-2">Summary:</span> {entry.summary}
                </div>
                {entry.feedback && (
                  <div className="text-[9px] text-red-400/70">
                    <span className="font-medium">Feedback:</span> {entry.feedback}
                  </div>
                )}
                {entry.output_preview && (
                  <div className="text-[9px] text-text-3 bg-surface-2/50 rounded p-1.5 max-h-32 overflow-y-auto whitespace-pre-wrap leading-relaxed border border-border/20">
                    {entry.output_preview}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

// ============================================================
// Agent Card
// ============================================================

const AgentCard: React.FC<{
  agent: Agent;
  progress?: AgentProgressEntry;
  pendingApprovals?: PendingApproval[];
  imageResults?: ImageResult[];
  onApproveImage?: (approvalId: string) => void;
  onRejectImage?: (approvalId: string) => void;
  onRetryImage?: (approvalId: string) => void;
  onEditImagePrompt?: (approvalId: string, newPrompt: string) => void;
  onSkipReview?: (agentName: string) => void;
  isCreated?: boolean;
}> = ({ agent, progress, pendingApprovals, imageResults, onApproveImage, onRejectImage, onRetryImage, onEditImagePrompt, onSkipReview, isCreated }) => {
  const [showOutput, setShowOutput] = useState(false);

  const status = progress?.status || 'pending';
  const isRunning = status === 'running';
  const isComplete = status === 'complete';
  const isError = status === 'error';
  const isWaitingApproval = status === 'waiting_approval';
  const isAwaitingReview = status === 'awaiting_review';
  const isWaiting = status === 'pending' && ((agent as any).depends_on?.length || 0) > 0;
  const progressPercent = progress?.progress || 0;
  const hasOutput = !!progress?.output && progress.output.length > 0;

  const borderClass = isRunning
    ? 'border-warning/50'
    : isComplete
    ? 'border-success/40'
    : isError
    ? 'border-danger/40'
    : isWaitingApproval
    ? 'border-purple-400/40'
    : isAwaitingReview
    ? 'border-amber-400/50'
    : isWaiting
    ? 'border-warning/30'
    : 'border-border';

  const statusBadge = isRunning ? (
    <span className="text-[8px] px-1.5 py-0.5 rounded bg-warning/20 text-warning font-semibold">RUN</span>
  ) : isComplete ? (
    <span className="text-[8px] px-1.5 py-0.5 rounded bg-success/20 text-success font-semibold">DONE</span>
  ) : isError ? (
    <span className="text-[8px] px-1.5 py-0.5 rounded bg-danger/20 text-danger font-semibold">ERR</span>
  ) : isWaitingApproval ? (
    <span className="text-[8px] px-1.5 py-0.5 rounded bg-purple-400/20 text-purple-400 font-semibold">WAIT</span>
  ) : isAwaitingReview ? (
    <span className="text-[8px] px-1.5 py-0.5 rounded bg-amber-400/20 text-amber-400 font-semibold">REVIEW</span>
  ) : isCreated ? (
    <span className="text-[8px] px-1.5 py-0.5 rounded bg-success/20 text-success font-semibold">CREATED</span>
  ) : (
    <span className="text-[8px] px-1.5 py-0.5 rounded bg-surface-2 text-text-3 font-semibold">IDLE</span>
  );

  return (
    <div className={`rounded-[10px] border bg-bg p-3 w-full transition-all ${borderClass}`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-1.5">
        <div className="w-[26px] h-[26px] rounded-lg bg-surface-2 flex items-center justify-center shrink-0 text-[13px]">
          {getAgentIcon(agent.name)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] font-semibold text-text truncate">{agent.name}</div>
          <div className="text-[9px] text-text-3">{agent.role}</div>
        </div>
        {statusBadge}
      </div>

      {/* Thinking/Running indicator */}
      {isRunning && (
        <div className="text-[10px] text-text-2 mb-2 bg-surface/60 rounded-md p-2 border border-border/30">
          {progress?.review_feedback && (
            <div className="text-[9px] text-red-400/80 mb-1.5 bg-red-500/5 rounded p-1.5 border border-red-400/20">
              <div className="font-medium mb-0.5">Manager feedback (รอบที่ {progress.review_round || 1}):</div>
              <div className="text-text-3">{progress.review_summary}</div>
            </div>
          )}
          {progress?.delegated_by && progress.delegated_by.length > 0 && (
            <div className="text-[9px] text-accent/80 mb-1 flex items-center gap-1">
              <GitBranch className="w-2.5 h-2.5" />
              <span>Receives from: {progress.delegated_by.join(', ')}</span>
            </div>
          )}
          <div className="flex items-center gap-1.5 mb-1">
            <Loader2 className="w-3 h-3 text-accent animate-spin shrink-0" />
            <span className="text-text-2 font-medium">Working...</span>
          </div>
          {progress?.thinking && (
            <div className="text-[10px] text-text-3 italic mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap leading-relaxed">
              {progress.thinking}
            </div>
          )}
          {!progress?.thinking && progress?.current_task && (
            <div className="text-[10px] text-text-3 italic">{progress.current_task}</div>
          )}
          {progress?.current_tool && (
            <div className="text-[10px] text-accent mt-1 flex items-center gap-1">
              <Zap className="w-2.5 h-2.5" />
              {progress.tool_description || progress.current_tool}
            </div>
          )}
        </div>
      )}

      {/* Waiting indicator */}
      {isWaiting && (
        <div className="text-[10px] text-warning bg-warning/5 rounded-md p-2 border border-warning/20 flex items-center gap-1.5 mb-2">
          <GitBranch className="w-3 h-3 shrink-0" />
          <span>Waiting for: {((agent as any).depends_on || []).join(', ')}</span>
        </div>
      )}

      {/* Waiting for approval */}
      {isWaitingApproval && (
        <div className="text-[10px] text-purple-400 mb-2 bg-purple-500/5 rounded-md p-2 border border-purple-400/20 flex items-center gap-1.5">
          <PenTool className="w-3 h-3 shrink-0" />
          <span>รอผู้ใช้กด Generate</span>
        </div>
      )}

      {/* Awaiting review */}
      {isAwaitingReview && (
        <div className="text-[10px] text-amber-400 mb-2 bg-amber-500/5 rounded-md p-2 border border-amber-400/20">
          <div className="flex items-center gap-1.5 mb-1">
            <Eye className="w-3 h-3 shrink-0" />
            <span>Manager กำลังตรวจ{progress?.review_round ? ` (รอบที่ ${progress.review_round})` : ''}...</span>
          </div>
          {progress?.review_summary && (
            <div className="text-[9px] text-amber-300/80 mt-1">
              {progress.review_summary}
            </div>
          )}
          {hasOutput && !progress?.review_summary && (
            <div className="text-[9px] text-text-3 line-clamp-3 mt-1">
              {progress?.output}
            </div>
          )}
        </div>
      )}

      {/* Skip review button — visible whenever agent has output and is not yet complete */}
      {onSkipReview && hasOutput && !isComplete && !isError && (
        <button
          onClick={() => onSkipReview(agent.name)}
          className="mb-2 text-[9px] px-2 py-1 rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 border border-amber-400/30 transition-colors font-medium"
        >
          หยุดตรวจ — ใช้ output นี้
        </button>
      )}

      {/* Completed output — collapsible, visible after agent is done */}
      {isComplete && hasOutput && (
        <div className="mb-2">
          <button
            onClick={() => setShowOutput(!showOutput)}
            className="flex items-center gap-1 text-[9px] text-text-3 hover:text-text-2 transition-colors mb-1"
          >
            {showOutput ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            <span>{showOutput ? 'ซ่อน output' : 'ดู output'}</span>
            {progress?.review_summary && (
              <span className="ml-1 text-success/70">— {progress.review_summary}</span>
            )}
          </button>
          {showOutput && (
            <div className="text-[10px] text-text-2 bg-surface/60 rounded-md p-2 border border-border/30 max-h-48 overflow-y-auto leading-relaxed">
              <MarkdownRenderer content={progress?.output || ''} className="text-[10px]" />
            </div>
          )}
        </div>
      )}

      {/* Progress bar */}
      {progressPercent > 0 && (
        <div className="mb-2">
          <div className="w-full bg-surface-2 rounded-full h-1 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${isComplete ? 'bg-success' : isError ? 'bg-danger' : isWaitingApproval ? 'bg-purple-400' : isAwaitingReview ? 'bg-amber-400' : 'bg-gradient-to-r from-warning to-amber-500'}`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Review History */}
      {progress?.review_history && progress.review_history.length > 0 && (
        <ReviewHistory history={progress.review_history} />
      )}

    </div>
  );
};

// ============================================================
// Handoff Arrow
// ============================================================

const HandoffArrow: React.FC<{ from: string; to: string; status: 'sent' | 'waiting' | 'active' }> = ({ from, to, status }) => (
  <div className="flex items-center gap-1.5 text-[11px]">
    <span className="text-warning">→</span>
    <span className="text-text-2">{from} → {to}</span>
    {status === 'sent' && <span className="text-[10px] text-success">✓ sent</span>}
    {status === 'waiting' && <span className="text-[10px] text-warning">waiting...</span>}
    {status === 'active' && (
      <div className="w-8 h-0.5 animate-pulse" style={{ background: 'repeating-linear-gradient(90deg, #fbbf24 0, #fbbf24 4px, transparent 4px, transparent 8px)' }} />
    )}
  </div>
);

// ============================================================
// Run builder — derives runs from chatMessages
// ============================================================

function buildRuns(chatMessages: ChatMessage[]): StoryboardRun[] {
  const runs: StoryboardRun[] = [];
  let currentRun: StoryboardRun | null = null;
  for (let i = 0; i < chatMessages.length; i++) {
    const msg = chatMessages[i];

    // Start a new run on user message
    if (msg.role === 'user' && msg.messageType !== 'image_approval' && msg.messageType !== 'image_result') {
      if (currentRun) runs.push(currentRun);
      currentRun = {
        runIndex: runs.length,
        userMessage: msg.content,
        planAgents: [],
        planStatus: 'pending',
        planType: 'new',
        pendingApprovals: [],
        imageResults: [],
        isLatest: false,
      };
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
      currentRun.result = {
        summary: msg.resultSummary || '',
        agents: msg.resultAgents || [],
        error: msg.resultError || false,
      };
    }

    if (msg.messageType === 'image_approval' && (msg.approvalStatus === 'pending' || msg.approvalStatus === 'error' || msg.approvalStatus === 'approved')) {
      // Replace existing entry with same approvalId, or add new
      const existingIdx = currentRun.pendingApprovals.findIndex((pa) => pa.approvalId === (msg.approvalId || ''));
      const entry = {
        approvalId: msg.approvalId || '',
        prompt: msg.imagePrompt || '',
        agentName: msg.agentName || '',
        mediaType: msg.mediaType || 'image',
        duration: msg.duration || 0,
        model: msg.model || '',
        approvalStatus: msg.approvalStatus || 'pending',
        imageError: msg.imageError || '',
      };
      if (existingIdx >= 0) {
        currentRun.pendingApprovals[existingIdx] = entry;
      } else {
        currentRun.pendingApprovals.push(entry);
      }
    }

    if (msg.messageType === 'image_result' && msg.imageUrl) {
      console.log('[STORYBOARD] image_result found:', { imageUrl: msg.imageUrl, approvalId: msg.approvalId, agentName: msg.agentName, mediaType: msg.mediaType });
      currentRun.imageResults.push({
        imageUrl: msg.imageUrl || '',
        prompt: msg.imagePrompt || '',
        approvalId: msg.approvalId || '',
        mediaType: msg.mediaType || 'image',
        agentName: msg.agentName || '',
      });
    }
  }

  if (currentRun) runs.push(currentRun);

  // Filter out rejected runs and runs with no plan agents (plain chat messages)
  const visible = runs.filter(r => r.planStatus !== 'rejected' && r.planStatus !== 'discarded' && (r.planAgents.length > 0 || r.result));

  // Re-index so run numbers start from 1 sequentially
  visible.forEach((r, i) => { r.runIndex = i; });

  // Mark last visible run as latest
  if (visible.length > 0) visible[visible.length - 1].isLatest = true;

  return visible;
}

// ============================================================
// Single Run renderer
// ============================================================

const RunTimeline: React.FC<{
  run: StoryboardRun;
  onApproveImage?: (approvalId: string) => void;
  onRejectImage?: (approvalId: string) => void;
  onRetryImage?: (approvalId: string) => void;
  onEditImagePrompt?: (approvalId: string, newPrompt: string) => void;
  onRetryTask?: () => void;
  onRateTask?: (rating: number) => void;
  onSkipReview?: (agentName: string) => void;
}> = ({ run, onApproveImage, onRejectImage, onRetryImage, onEditImagePrompt, onRetryTask, onRateTask, onSkipReview }) => {
  const planPending = run.planStatus === 'pending';

  // Convert PlanAgent[] to Agent[] for wave computation
  const planAgentsAsAgents: Agent[] = useMemo(() =>
    run.planAgents.map((pa, idx) => ({
      id: `run${run.runIndex}-agent-${idx}`,
      name: pa.name,
      role: pa.role,
      goal: pa.goal || '',
      tools: pa.tools || [],
      depends_on: pa.depends_on || [],
      status: 'Idle' as const,
    })),
  [run.planAgents, run.runIndex]);

  const waves = useMemo(() => computeWaves(planAgentsAsAgents), [planAgentsAsAgents]);

  const allComplete = useMemo(() => {
    if (!run.progress || planAgentsAsAgents.length === 0) return false;
    return planAgentsAsAgents.every((a) => {
      const p = run.progress!.find((ap) => ap.name === a.name);
      return p?.status === 'complete' || p?.status === 'error';
    });
  }, [run.progress, planAgentsAsAgents]);

  const hasWaitingApproval = useMemo(() => {
    if (!run.progress) return false;
    return run.progress.some((ap) => ap.status === 'waiting_approval');
  }, [run.progress]);

  const hasAwaitingReview = useMemo(() => {
    if (!run.progress) return false;
    return run.progress.some((ap) => ap.status === 'awaiting_review');
  }, [run.progress]);

  return (
    <>
      {/* Run separator for non-first runs */}
      {run.runIndex > 0 && (
        <div className="mb-4 mt-6 text-[10px] text-text-3 uppercase tracking-wide">
          Run {run.runIndex + 1}
        </div>
      )}

      {/* Run block */}
      <div className="mb-6">
        {/* User Request */}
        <div className="flex items-center gap-2 mb-3">
          <div className="w-[22px] h-[22px] rounded-full bg-accent flex items-center justify-center text-[10px] font-semibold text-white shrink-0">U</div>
          <span className="text-xs font-medium text-text">{run.userMessage}</span>
        </div>

        {/* Manager Plan summary */}
        {run.planAgents.length > 0 && (
          <div className={`mb-3 px-3 py-2 rounded-lg border ${run.planType === 'create_agents' ? 'bg-success/5 border-success/20' : 'bg-surface border-accent/20'}`}>
            <div className="text-[10px] text-text-3 uppercase tracking-wide mb-1">
              {run.planType === 'create_agents' ? 'Agent Creation' : 'Manager — Plan'}
            </div>
            <div className="text-xs text-text-2">
              {planPending ? 'Awaiting Approval' : run.planType === 'create_agents'
                ? `${run.planAgents.length} agent${run.planAgents.length > 1 ? 's' : ''} created`
                : `${run.planAgents.length} agents, ${waves.length} wave${waves.length > 1 ? 's' : ''}`}
            </div>
          </div>
        )}

        {/* Wave-by-wave execution */}
        {waves.map((wave, waveIdx) => {
          const waveStarted = wave.agents.some(({ agent }) => {
            const p = run.progress?.find((ap) => ap.name === agent.name);
            return p?.status === 'running' || p?.status === 'complete' || p?.status === 'error' || p?.status === 'waiting_approval' || p?.status === 'awaiting_review';
          });

          return (
            <div key={waveIdx}>
              {/* Handoff arrow */}
              {waveIdx > 0 && waveStarted && (
                <div className="flex items-center gap-2 mb-2 ml-2">
                  {wave.dependsOn.map((dep) => {
                    const depProgress = run.progress?.find((ap) => ap.name.toLowerCase() === dep.toLowerCase());
                    const depStatus = depProgress?.status || 'pending';
                    const handoffStatus = depStatus === 'complete' ? 'sent' : depStatus === 'running' ? 'active' : 'waiting';
                    return (
                      <HandoffArrow key={dep} from={dep} to={wave.agents.map((a) => a.agent.name).join(' + ')} status={handoffStatus as 'sent' | 'waiting' | 'active'} />
                    );
                  })}
                </div>
              )}

              {/* Wave label */}
              <div className="flex items-center gap-1.5 mb-1.5 pl-5 relative">
                <div className="absolute left-1 top-0.5 w-2 h-2 rounded-full border-2 border-border-light" />
                <span className="text-[10px] text-text-3 uppercase tracking-wide">Wave {waveIdx + 1}</span>
                <span className="text-[10px] bg-surface-2 px-1.5 py-0.5 rounded text-text-2 normal-case tracking-normal">
                  {wave.agents.length} agent{wave.agents.length > 1 ? 's' : ''}
                </span>
              </div>

              {/* Agent cards row */}
              <div className="flex gap-2.5 flex-wrap pl-5 ml-[7px] border-l border-dashed border-border mb-3">
                {wave.agents.map(({ agent }) => {
                  const nodeProgress = run.progress?.find((p) => p.name === agent.name);
                  const agentApprovals = run.pendingApprovals.filter((pa) => pa.agentName.toLowerCase() === agent.name.toLowerCase());
                  const agentApprovalIds = new Set(agentApprovals.map(pa => pa.approvalId));
                  const agentImages = run.imageResults.filter((ir) => {
                    if (ir.agentName && ir.agentName.toLowerCase() === agent.name.toLowerCase()) return true;
                    if (!ir.agentName && agentApprovalIds.has(ir.approvalId)) return true;
                    return false;
                  });
                  return (
                    <AgentCard
                      key={agent.id || agent.name}
                      agent={agent}
                      progress={nodeProgress}
                      pendingApprovals={agentApprovals}
                      imageResults={agentImages}
                      onApproveImage={onApproveImage}
                      onRejectImage={onRejectImage}
                      onRetryImage={onRetryImage}
                      onEditImagePrompt={onEditImagePrompt}
                      onSkipReview={onSkipReview}
                      isCreated={run.planType === 'create_agents' && !planPending}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}

        {/* Waiting for user to generate images */}
        {hasWaitingApproval && !run.result && (
          <div className="mb-3 px-3 py-2 rounded-lg border border-purple-400/30 bg-purple-500/5">
            <div className="text-[10px] text-text-3 uppercase tracking-wide mb-1">Awaiting User Action</div>
            <span className="text-xs text-text-2">รอผู้ใช้กด Generate เพื่อสร้างภาพ/วิดีโอ</span>
          </div>
        )}

        {/* Manager reviewing */}
        {hasAwaitingReview && !run.result && (
          <div className="mb-3 px-3 py-2 rounded-lg border border-amber-400/30 bg-amber-500/5">
            <div className="text-[10px] text-text-3 uppercase tracking-wide mb-1">Manager Review</div>
            <span className="text-xs text-text-2">Manager กำลังตรวจผลงานของ agent...</span>
          </div>
        )}

        {/* Manager Synthesizing */}
        {allComplete && !run.result && !hasWaitingApproval && !hasAwaitingReview && (
          <div className="mb-3 px-3 py-2 rounded-lg border border-accent/30 bg-accent/5">
            <div className="text-[10px] text-text-3 uppercase tracking-wide mb-1">Manager — Synthesizing</div>
            <div className="flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />
              <span className="text-xs text-text-2">Combining all agent outputs...</span>
            </div>
          </div>
        )}

        {/* Manager Review Output — shown when Manager progress entry is complete */}
        {(() => {
          const managerProgress = run.progress?.find((p) => p.name === 'Manager' && p.status === 'complete');
          if (!managerProgress || !run.result) return null;
          return (
            <div className="mb-3">
              <div className="rounded-[10px] border border-accent/40 bg-accent/5 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-[26px] h-[26px] rounded-lg bg-accent/20 flex items-center justify-center shrink-0 text-[13px]">
                    <Brain className="w-3.5 h-3.5 text-accent" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] font-semibold text-text">Manager</div>
                    <div className="text-[9px] text-text-3">Project Manager</div>
                  </div>
                  <span className="text-[8px] px-1.5 py-0.5 rounded bg-accent/20 text-accent font-semibold">REVIEW</span>
                </div>
                <div className="text-[10px] text-text-2 max-h-64 overflow-y-auto leading-relaxed">
                  <MarkdownRenderer content={managerProgress.output || ''} className="text-[10px]" />
                </div>
              </div>
            </div>
          );
        })()}

        {/* Final Result */}
        {run.result && (
          <FinalResultCard result={run.result} agentCount={run.planAgents.length} onRetry={onRetryTask} />
        )}
      </div>
    </>
  );
};

// ============================================================
// Main Storyboard Component
// ============================================================

export const StoryboardArea: React.FC<StoryboardProps> = ({
  chatMessages,
  onApproveImage,
  onRejectImage,
  onRetryImage,
  onEditImagePrompt,
  onRetryTask,
  onRateTask,
  onSkipReview,
}) => {
  const runs = useMemo(() => buildRuns(chatMessages), [chatMessages]);

  if (runs.length === 0) {
    return (
      <div className="h-full w-full flex items-center justify-center bg-bg">
        <div className="text-center">
          <Bot className="w-12 h-12 text-text-3 mx-auto mb-3" />
          <div className="text-text-2 text-sm">Send a message to start</div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex-1 overflow-y-auto bg-bg p-4">
      <div className="max-w-3xl mx-auto">
        {runs.map((run) => (
          <RunTimeline
            key={run.runIndex}
            run={run}
            onApproveImage={onApproveImage}
            onRejectImage={onRejectImage}
            onRetryImage={onRetryImage}
            onEditImagePrompt={onEditImagePrompt}
            onRetryTask={onRetryTask}
            onRateTask={onRateTask}
            onSkipReview={onSkipReview}
          />
        ))}
      </div>
    </div>
  );
};
