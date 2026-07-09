import { useState, useMemo } from 'react';
import {
  Loader2, CheckCircle, XCircle, Bot, User as UserIcon, Zap, Image as ImageIcon,
  Video, PenTool, ChevronDown, ChevronUp, Pencil, Brain,
  ArrowRight, GitBranch, Cpu, Download, RotateCw,
} from 'lucide-react';
import type { Agent } from '../types/platform';
import type { ChatMessage, AgentProgressEntry, PlanAgent, ResultAgent, PlanStatus } from './ChatPanel';
import type { PendingApproval, ImageResult } from './CanvasArea';
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

const avatarColors = [
  'from-blue-500/20 to-blue-600/10 text-blue-400',
  'from-green-500/20 to-green-600/10 text-green-400',
  'from-purple-500/20 to-purple-600/10 text-purple-400',
  'from-orange-500/20 to-orange-600/10 text-orange-400',
  'from-pink-500/20 to-pink-600/10 text-pink-400',
  'from-cyan-500/20 to-cyan-600/10 text-cyan-400',
];

const getAvatarColor = (name: string) => {
  const hash = name.charCodeAt(0) + (name.charCodeAt(1) || 0);
  return avatarColors[hash % avatarColors.length];
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
}> = ({ agent, progress, pendingApprovals, imageResults, onApproveImage, onRejectImage, onRetryImage, onEditImagePrompt }) => {
  const [showOutput, setShowOutput] = useState(false);

  const status = progress?.status || 'pending';
  const isRunning = status === 'running';
  const isComplete = status === 'complete';
  const isError = status === 'error';
  const isWaiting = status === 'pending' && ((agent as any).depends_on?.length || 0) > 0;
  const progressPercent = progress?.progress || 0;
  const hasOutput = !!progress?.output && progress.output.length > 0;

  const borderClass = isRunning
    ? 'border-accent/50'
    : isComplete
    ? 'border-success/40'
    : isError
    ? 'border-danger/40'
    : isWaiting
    ? 'border-warning/30'
    : 'border-border';

  return (
    <div className={`relative group rounded-xl border-2 ${borderClass} bg-gradient-to-br ${getAvatarColor(agent.name)} p-3 min-w-[240px] flex-1 transition-all hover:border-accent/60`}>
      {/* Header */}
      <div className="flex items-start gap-3 mb-2">
        <div className="w-9 h-9 rounded-lg bg-surface/80 flex items-center justify-center shrink-0 backdrop-blur-sm">
          {getAgentIcon(agent.name)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-text">{agent.name}</div>
          <div className="text-xs text-text-2">{agent.role}</div>
          {progress?.model && (
            <div className="flex items-center gap-1 text-[9px] text-text-3 mt-0.5">
              <Cpu className="w-2 h-2 shrink-0" />
              <span className="truncate max-w-[120px]" title={progress.model}>{progress.model}</span>
            </div>
          )}
        </div>
        <div className="shrink-0">
          {isRunning ? (
            <Loader2 className="w-4 h-4 text-accent animate-spin" />
          ) : isComplete ? (
            <CheckCircle className="w-4 h-4 text-success" />
          ) : isError ? (
            <XCircle className="w-4 h-4 text-danger" />
          ) : isWaiting ? (
            <div className="text-[10px] text-warning font-medium px-1.5 py-0.5 rounded bg-warning/10">Waiting</div>
          ) : (
            <div className="w-4 h-4 rounded-full border-2 border-text-3" />
          )}
        </div>
      </div>

      {/* Thinking indicator */}
      {isRunning && (
        <div className="text-xs text-text-2 mb-2 bg-surface/60 rounded-md p-2 backdrop-blur-sm border border-border/30">
          <div className="flex items-center gap-1.5 mb-1">
            <Loader2 className="w-3 h-3 text-accent animate-spin shrink-0" />
            <span className="text-text-2 font-medium">Thinking...</span>
          </div>
          {progress?.current_task && (
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
        <div className="text-[11px] text-warning bg-warning/5 rounded-md p-2 border border-warning/20 flex items-center gap-1.5">
          <GitBranch className="w-3 h-3 shrink-0" />
          <span>Waiting for: {((agent as any).depends_on || []).join(', ')}</span>
        </div>
      )}

      {/* Progress bar */}
      {progressPercent > 0 && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-text-2">{isComplete ? 'Done' : isRunning ? 'Working' : 'Pending'}</span>
            <span className="text-text-2">{progressPercent}%</span>
          </div>
          <div className="w-full bg-surface-3 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${isComplete ? 'bg-success' : isError ? 'bg-danger' : 'bg-gradient-to-r from-accent to-accent-light'}`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Goal */}
      {agent.goal && <div className="mt-1.5 text-[10px] text-text-2">{agent.goal}</div>}

      {/* Tools */}
      {agent.tools.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {agent.tools.slice(0, 3).map((tool, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface/60 text-text-2 backdrop-blur-sm">{tool}</span>
          ))}
          {agent.tools.length > 3 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface/60 text-text-2">+{agent.tools.length - 3}</span>
          )}
        </div>
      )}

      {/* Media preview — handled by imageResults below */}

      {/* Output */}
      {hasOutput && (
        <div className="mt-2 border-t border-border/30 pt-2">
          <div
            className="text-xs text-text-2 bg-surface/60 rounded-md p-2 backdrop-blur-sm border border-border/30 max-h-40 overflow-y-auto whitespace-pre-wrap"
            style={{ display: showOutput ? 'block' : '-webkit-box', WebkitLineClamp: showOutput ? 'unset' : 4, WebkitBoxOrient: 'vertical', overflow: showOutput ? 'auto' : 'hidden' }}
          >
            {progress?.output}
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); setShowOutput(!showOutput); }}
            className="flex items-center gap-1 text-[10px] text-text-2 hover:text-text transition-colors mt-1"
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
            return (
            <div key={pa.approvalId} className={`rounded-lg p-2 ${isApprovalError ? 'border border-danger/40 bg-danger/5' : 'border border-purple-400/30 bg-purple-500/5'}`}>
              <div className={`flex items-center gap-1 text-[10px] mb-1 ${isApprovalError ? 'text-danger' : 'text-purple-400'}`}>
                {pa.mediaType === 'video' ? <Video className="w-2.5 h-2.5" /> : <ImageIcon className="w-2.5 h-2.5" />}
                <span className="font-medium">{isApprovalError ? `${pa.mediaType === 'video' ? 'Video' : 'Image'} Failed` : `${pa.mediaType === 'video' ? 'Video' : 'Image'} Approval`}</span>
                {pa.duration > 0 && <span className="text-text-3">({pa.duration}s)</span>}
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

      {/* Loading state for approved but not yet generated media */}
      {pendingApprovals && pendingApprovals.some((pa) => pa.approvalStatus === 'approved') && (
        <div className="mt-2 border-t border-border/30 pt-2 space-y-2">
          {pendingApprovals.filter((pa) => pa.approvalStatus === 'approved').map((pa) => {
            const hasResult = imageResults?.some((ir) => ir.approvalId === pa.approvalId);
            if (hasResult) return null;
            return (
              <div key={pa.approvalId} className="rounded-lg border border-purple-400/30 bg-purple-500/5 p-2">
                <div className="flex items-center gap-1.5 text-[10px] text-purple-400 mb-2">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span className="font-medium">Generating {pa.mediaType === 'video' ? 'video' : 'image'}...</span>
                </div>
                <div className="w-full aspect-video rounded-md bg-surface-2 flex items-center justify-center">
                  <Loader2 className="w-6 h-6 text-text-3 animate-spin" />
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
  <div className="flex items-center justify-center gap-2 my-2 flex-wrap">
    <span className="text-[11px] text-text-2">{from}</span>
    <ArrowRight className="w-3 h-3 text-warning" />
    <span className="text-[11px] text-text-2">{to}</span>
    {status === 'sent' && <span className="text-[10px] text-success">✓ sent</span>}
    {status === 'waiting' && <span className="text-[10px] text-warning">waiting...</span>}
    {status === 'active' && (
      <div className="w-8 h-0.5 bg-warning animate-pulse" style={{ background: 'repeating-linear-gradient(90deg, #f59e0b 0, #f59e0b 4px, transparent 4px, transparent 8px)' }} />
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

    if (msg.messageType === 'image_approval' && (msg.approvalStatus === 'pending' || msg.approvalStatus === 'error')) {
      currentRun.pendingApprovals.push({
        approvalId: msg.approvalId || '',
        prompt: msg.imagePrompt || '',
        agentName: msg.agentName || '',
        mediaType: msg.mediaType || 'image',
        duration: msg.duration || 0,
        model: msg.model || '',
        approvalStatus: msg.approvalStatus || 'pending',
        imageError: msg.imageError || '',
      });
    }

    if (msg.messageType === 'image_result' && msg.imageUrl) {
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

  // Filter out rejected runs — they should not appear in storyboard
  const visible = runs.filter(r => r.planStatus !== 'rejected');

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
}> = ({ run, onApproveImage, onRejectImage, onRetryImage, onEditImagePrompt }) => {
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

  return (
    <>
      {/* Run separator for non-first runs */}
      {run.runIndex > 0 && (
        <div className="relative pl-10 mb-4 mt-6">
          <div className="absolute left-0 top-0 w-8 h-8 rounded-full bg-surface-2 border-2 border-border flex items-center justify-center">
            <ArrowRight className="w-3.5 h-3.5 text-text-3 rotate-90" />
          </div>
          <div className="text-[10px] text-text-3 uppercase tracking-wide">Run {run.runIndex + 1}</div>
        </div>
      )}

      {/* User Request */}
      <div className="relative pl-10 mb-5 storyboard-fade-in">
        <div className="absolute left-0 top-1 w-8 h-8 rounded-full bg-success/20 border-2 border-success/40 flex items-center justify-center">
          <UserIcon className="w-3.5 h-3.5 text-success" />
        </div>
        <div className="rounded-xl border border-border bg-surface p-3">
          <div className="text-[10px] text-text-3 uppercase tracking-wide mb-1">User Request</div>
          <div className="text-sm text-text font-medium">{run.userMessage}</div>
        </div>
      </div>

      {/* Manager Plan */}
      {run.planAgents.length > 0 && (
        <div className="relative pl-10 mb-5 storyboard-fade-in">
          <div className="absolute left-0 top-1 w-8 h-8 rounded-full bg-accent/20 border-2 border-accent/40 flex items-center justify-center">
            <Brain className="w-3.5 h-3.5 text-accent" />
          </div>
          <div className={`rounded-xl border bg-surface p-3 ${planPending ? 'border-accent/30 border-dashed' : 'border-accent/20'}`}>
            <div className="text-[10px] text-text-3 uppercase tracking-wide mb-1">Manager — Plan</div>
            <div className="text-sm text-text font-medium mb-2">
              {planPending ? 'Awaiting Approval' : `${run.planAgents.length} agents, ${waves.length} wave${waves.length > 1 ? 's' : ''}`}
            </div>
            <div className="text-xs text-text-2 bg-bg/50 rounded-lg p-2.5 border border-border/50 space-y-1.5">
              {waves.map((wave, wi) => (
                <div key={wi}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-text-3 font-medium text-[11px]">Wave {wi + 1}</span>
                    {wave.agents.map(({ agent }, ai) => (
                      <span key={ai} className="text-[11px] px-2 py-0.5 rounded-full bg-surface-2 text-text-2">{agent.name}</span>
                    ))}
                    {wave.dependsOn.length > 0 && (
                      <span className="text-[10px] text-warning flex items-center gap-1">
                        <ArrowRight className="w-2.5 h-2.5" />depends on {wave.dependsOn.join(', ')}
                      </span>
                    )}
                    {wave.agents.length > 1 && wave.dependsOn.length > 0 && (
                      <span className="text-[10px] text-text-3">(parallel within wave)</span>
                    )}
                  </div>
                  {wi < waves.length - 1 && <div className="text-text-3 text-[10px] ml-3 my-0.5">↓</div>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Wave-by-wave execution */}
      {waves.map((wave, waveIdx) => {
        const waveStarted = wave.agents.some(({ agent }) => {
          const p = run.progress?.find((ap) => ap.name === agent.name);
          return p?.status === 'running' || p?.status === 'complete' || p?.status === 'error';
        });

        return (
          <div key={waveIdx}>
            {waveIdx > 0 && waveStarted && (
              <div className="pl-10 mb-2">
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

            {wave.upstreamWaveIndices.length > 1 && (
              <div className="pl-10 mb-2 text-[11px] text-warning flex items-center gap-1.5">
                <GitBranch className="w-3 h-3" />Convergence: waits for {wave.dependsOn.length} upstream agents
              </div>
            )}

            <div className="relative pl-10 mb-5 storyboard-fade-in">
              <div className="absolute left-[3px] top-1 w-[13px] h-[13px] rounded-full border-2 border-text-3 flex items-center justify-center">
                <div className="w-1 h-1 rounded-full bg-text-3" />
              </div>
              <div className="text-[10px] text-text-3 uppercase tracking-wide mb-2 flex items-center gap-2">
                <span>Wave {waveIdx + 1}</span>
                <span className="bg-surface-2 px-1.5 py-0.5 rounded text-text-2 normal-case tracking-normal">
                  {wave.agents.length} agent{wave.agents.length > 1 ? 's' : ''}
                </span>
                {wave.agents.length > 1 && wave.dependsOn.length > 0 && <span className="text-text-3 normal-case tracking-normal">parallel</span>}
                {wave.dependsOn.length === 0 && waveIdx === 0 && <span className="text-text-3 normal-case tracking-normal">no dependencies</span>}
              </div>
              <div className={`flex gap-3 flex-wrap ${wave.agents.length > 1 ? 'flex-row' : ''}`}>
                {wave.agents.map(({ agent }) => {
                  const nodeProgress = run.progress?.find((p) => p.name === agent.name);
                  const agentApprovals = run.pendingApprovals.filter((pa) => pa.agentName.toLowerCase() === agent.name.toLowerCase());
                  const agentImages = run.imageResults.filter((ir) => ir.agentName.toLowerCase() === agent.name.toLowerCase());
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
                    />
                  );
                })}
              </div>
            </div>
          </div>
        );
      })}

      {/* Manager Synthesizing */}
      {allComplete && !run.result && (
        <div className="relative pl-10 mb-5 storyboard-fade-in">
          <div className="absolute left-0 top-1 w-8 h-8 rounded-full bg-accent/20 border-2 border-accent/40 flex items-center justify-center">
            <Brain className="w-3.5 h-3.5 text-accent animate-pulse" />
          </div>
          <div className="rounded-xl border border-accent/30 bg-accent/5 p-3">
            <div className="text-[10px] text-text-3 uppercase tracking-wide mb-1">Manager — Synthesizing</div>
            <div className="flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />
              <span className="text-sm text-text-2">Combining all agent outputs...</span>
            </div>
          </div>
        </div>
      )}

      {/* Final Result */}
      {run.result && (
        <div className="relative pl-10 mb-5 storyboard-fade-in">
          <div className="absolute left-0 top-1 w-8 h-8 rounded-full bg-success/20 border-2 border-success/40 flex items-center justify-center">
            <CheckCircle className="w-3.5 h-3.5 text-success" />
          </div>
          <div className={`rounded-xl border p-3 ${run.result.error ? 'border-danger/30 bg-danger/5' : 'border-success/30 bg-success/5'}`}>
            <div className="text-[10px] text-text-3 uppercase tracking-wide mb-1">Final Result</div>
            <div className="text-sm text-text font-medium mb-2">{run.result.summary}</div>
            {run.result.agents && run.result.agents.length > 0 && (
              <div className="space-y-1.5 mt-2">
                {run.result.agents.map((ra, i) => (
                  <div key={i} className="flex gap-2 items-start py-1.5 border-t border-border/30 first:border-t-0">
                    <div className="text-xs font-semibold text-text-2 min-w-[120px] shrink-0">{ra.name}</div>
                    <div className="text-xs text-text-3 flex-1">{ra.output}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
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
      <div className="max-w-3xl mx-auto relative">
        <div className="absolute left-[15px] top-0 bottom-0 w-0.5 bg-border" />
        {runs.map((run) => (
          <RunTimeline
            key={run.runIndex}
            run={run}
            onApproveImage={onApproveImage}
            onRejectImage={onRejectImage}
            onRetryImage={onRetryImage}
            onEditImagePrompt={onEditImagePrompt}
          />
        ))}
      </div>
    </div>
  );
};
