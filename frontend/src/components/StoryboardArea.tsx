import { useState, useMemo } from 'react';
import {
  Loader2, CheckCircle, XCircle, Bot, Zap, Image as ImageIcon,
  Video, PenTool, ChevronDown, ChevronUp, Pencil, Brain,
  GitBranch, Cpu, Download, RotateCw, Copy,
} from 'lucide-react';
import type { Agent, PendingApproval, ImageResult } from '../types/platform';
import type { ChatMessage, AgentProgressEntry, PlanAgent, ResultAgent, PlanStatus } from './chatTypes';
import { displayModelId } from './ModelPicker';

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
            <div className="text-sm text-text whitespace-pre-wrap leading-relaxed">
              {result.summary}
            </div>
          </div>
        )}
      </div>
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
  isCreated?: boolean;
}> = ({ agent, progress, pendingApprovals, imageResults, onApproveImage, onRejectImage, onRetryImage, onEditImagePrompt, isCreated }) => {
  const [showOutput, setShowOutput] = useState(false);

  const status = progress?.status || 'pending';
  const isRunning = status === 'running';
  const isComplete = status === 'complete';
  const isError = status === 'error';
  const isWaitingApproval = status === 'waiting_approval';
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

      {/* Progress bar */}
      {progressPercent > 0 && (
        <div className="mb-2">
          <div className="w-full bg-surface-2 rounded-full h-1 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${isComplete ? 'bg-success' : isError ? 'bg-danger' : isWaitingApproval ? 'bg-purple-400' : 'bg-gradient-to-r from-warning to-amber-500'}`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Output */}
      {hasOutput && (
        <div className="mt-1.5">
          <div
            className="text-[11px] text-text-3 bg-bg rounded-md p-2 max-h-32 overflow-y-auto whitespace-pre-wrap"
            style={{ display: showOutput ? 'block' : '-webkit-box', WebkitLineClamp: showOutput ? 'unset' : 3, WebkitBoxOrient: 'vertical', overflow: showOutput ? 'auto' : 'hidden' }}
          >
            {progress?.output}
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); setShowOutput(!showOutput); }}
            className="flex items-center gap-1 text-[10px] text-text-3 hover:text-text transition-colors mt-1"
          >
            {showOutput ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {showOutput ? 'Show less' : 'Show more'}
          </button>
        </div>
      )}

      {/* Pending media approvals */}
      {pendingApprovals && pendingApprovals.length > 0 && (
        <div className="mt-2 border-t border-border/30 pt-2 space-y-2">
          {pendingApprovals.map((pa) => {
            const isApprovalError = pa.approvalStatus === 'error';
            const isApproved = pa.approvalStatus === 'approved';
            const hasResult = imageResults?.some((ir) => ir.approvalId === pa.approvalId);
            return (
            <div key={pa.approvalId} className={`rounded-lg p-2 ${isApprovalError ? 'border border-danger/40 bg-danger/5' : isApproved ? 'border border-purple-400/40 bg-purple-500/10' : 'border border-purple-400/30 bg-purple-500/5'}`}>
              <div className={`flex items-center gap-1 text-[10px] mb-1 ${isApprovalError ? 'text-danger' : 'text-purple-400'}`}>
                {pa.mediaType === 'video' ? <Video className="w-2.5 h-2.5" /> : <ImageIcon className="w-2.5 h-2.5" />}
                <span className="font-medium">{isApprovalError ? `${pa.mediaType === 'video' ? 'Video' : 'Image'} Failed` : isApproved ? (hasResult ? `${pa.mediaType === 'video' ? 'Video' : 'Image'} Generated` : `Generating ${pa.mediaType === 'video' ? 'Video' : 'Image'}`) : `${pa.mediaType === 'video' ? 'Video' : 'Image'} Approval`}</span>
                {pa.duration > 0 && <span className="text-text-3">({pa.duration}s)</span>}
                {isApproved && !hasResult && <Loader2 className="w-3 h-3 animate-spin ml-auto" />}
              </div>
              <div className="text-xs text-text-2 italic mb-2">"{pa.prompt}"</div>
              {pa.model && (
                <div className="flex items-center gap-1 text-[10px] text-text-2 mb-2">
                  <Cpu className="w-2.5 h-2.5 shrink-0" />
                  <span>Model: <span className="text-text font-mono">{displayModelId(pa.model)}</span></span>
                </div>
              )}
              {isApprovalError && pa.imageError && (
                <div className="text-[10px] text-danger bg-danger/10 rounded px-1.5 py-1 mb-2 border border-danger/20">
                  ⚠️ {pa.imageError}
                </div>
              )}
              {isApproved && !hasResult && (
                <div className="w-full aspect-video rounded-md bg-surface-2 flex items-center justify-center mb-2">
                  <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
                </div>
              )}
              {hasResult && (
                <div className="text-[10px] text-success flex items-center gap-1 mb-1">
                  <CheckCircle className="w-3 h-3" /> Generated successfully
                </div>
              )}
              <div className="flex gap-1.5 flex-wrap">
                {isApprovalError ? (
                  <>
                    <button
                      onClick={(e) => { e.stopPropagation(); onRetryImage?.(pa.approvalId); }}
                      className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-purple-500 text-white hover:bg-purple-600 transition-colors"
                    >
                      🔄 Retry
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); onRejectImage?.(pa.approvalId); }}
                      className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-surface-2 text-text-2 border border-border hover:bg-surface-3 transition-colors"
                    >
                      ❌ Cancel
                    </button>
                  </>
                ) : isApproved ? (
                  hasResult ? (
                    <span className="text-[10px] text-success italic">✅ สร้างภาพเสร็จแล้ว</span>
                  ) : (
                    <span className="text-[10px] text-text-3 italic">กำลังสร้างภาพ... กรุณารอ</span>
                  )
                ) : (
                  <>
                    <button
                      onClick={(e) => { e.stopPropagation(); onApproveImage?.(pa.approvalId); }}
                      className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-purple-500 text-white hover:bg-purple-600 transition-colors"
                    >
                      {pa.mediaType === 'video' ? '🎬' : '🖼️'} Generate
                    </button>
                    {onEditImagePrompt && (
                      <button
                        onClick={(e) => { e.stopPropagation(); const newPrompt = prompt('Edit prompt:', pa.prompt); if (newPrompt) onEditImagePrompt(pa.approvalId, newPrompt); }}
                        className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-surface-2 text-text-2 border border-border hover:bg-surface-3 transition-colors"
                      >
                        <Pencil className="w-2.5 h-2.5" /> Edit
                      </button>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); onRejectImage?.(pa.approvalId); }}
                      className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-surface-2 text-text-2 border border-border hover:bg-surface-3 transition-colors"
                    >
                      ❌ Cancel
                    </button>
                  </>
                )}
              </div>
            </div>
            );
          })}
        </div>
      )}

      {/* Generated media results */}
      {imageResults && imageResults.length > 0 && (
        <div className="mt-2 border-t border-border/30 pt-2 space-y-2">
          <div className="text-[10px] text-text-2 mb-1 flex items-center gap-1">
            <ImageIcon className="w-2.5 h-2.5" /> Generated media
          </div>
          {imageResults.map((ir) => (
            <div key={ir.approvalId} className="rounded-md overflow-hidden border border-border/30">
              {ir.mediaType === 'video' ? (
                <video src={ir.imageUrl} controls className="w-full" />
              ) : (
                <img src={ir.imageUrl} alt={ir.prompt} className="w-full" loading="lazy" />
              )}
              <div className="flex items-center gap-1.5 p-1.5 bg-surface-2 border-t border-border/30">
                {onRetryImage && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onRetryImage(ir.approvalId); }}
                    className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
                    title="Regenerate"
                  >
                    <RotateCw className="w-2.5 h-2.5" /> Regenerate
                  </button>
                )}
                {onEditImagePrompt && (
                  <button
                    onClick={(e) => { e.stopPropagation(); const newPrompt = prompt('Edit prompt:', ir.prompt); if (newPrompt) onEditImagePrompt(ir.approvalId, newPrompt); }}
                    className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-surface-3 text-text-2 hover:bg-surface-2 border border-border/50 transition-colors"
                    title="Edit prompt"
                  >
                    <Pencil className="w-2.5 h-2.5" /> Edit
                  </button>
                )}
                <a
                  href={ir.imageUrl}
                  download
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-surface-3 text-text-2 hover:bg-surface-2 border border-border/50 transition-colors ml-auto"
                  title="Download"
                >
                  <Download className="w-2.5 h-2.5" /> Download
                </a>
              </div>
            </div>
          ))}
        </div>
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
  const visible = runs.filter(r => r.planStatus !== 'rejected' && (r.planAgents.length > 0 || r.result));

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
}> = ({ run, onApproveImage, onRejectImage, onRetryImage, onEditImagePrompt, onRetryTask, onRateTask }) => {
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
            return p?.status === 'running' || p?.status === 'complete' || p?.status === 'error' || p?.status === 'waiting_approval';
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

        {/* Manager Synthesizing */}
        {allComplete && !run.result && !hasWaitingApproval && (
          <div className="mb-3 px-3 py-2 rounded-lg border border-accent/30 bg-accent/5">
            <div className="text-[10px] text-text-3 uppercase tracking-wide mb-1">Manager — Synthesizing</div>
            <div className="flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />
              <span className="text-xs text-text-2">Combining all agent outputs...</span>
            </div>
          </div>
        )}

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
          />
        ))}
      </div>
    </div>
  );
};
