import { useEffect, useRef, useState } from 'react';
import { Bot, User, Loader2, CheckSquare, CheckCircle, XCircle, ChevronDown, ChevronRight, Wrench, Image, Pencil, Search, PenTool, Eye, Brain } from 'lucide-react';

export interface PlanAgent {
  name: string;
  role: string;
  goal?: string;
  tools?: string[];
  depends_on?: string[];
  is_existing?: boolean;
  model?: string;
}

export interface ResultAgent {
  name: string;
  role: string;
  output: string;
}

export type ChatMessageType = 'text' | 'plan' | 'plan_validation_error' | 'progress' | 'result' | 'image_approval' | 'image_result' | 'agent_progress' | 'model_catalog' | 'thinking' | 'thinking_done' | 'audio_result' | 'transcription_result' | 'video_result' | 'file_result';

export type PlanStatus = 'pending' | 'approved' | 'rejected';

export type ImageApprovalStatus = 'pending' | 'approved' | 'rejected' | 'error';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  messageType?: ChatMessageType;
  planAgents?: PlanAgent[];
  planTaskDescription?: string;
  planType?: string;
  planStatus?: PlanStatus;
  progressId?: string;
  progressPercent?: number;
  progressLabel?: string;
  agentProgressTaskId?: string;
  agentProgressOverall?: number;
  agentProgressList?: AgentProgressEntry[];
  resultAgents?: ResultAgent[];
  resultSummary?: string;
  resultError?: boolean;
  imagePrompt?: string;
  approvalId?: string;
  agentName?: string;
  approvalStatus?: ImageApprovalStatus;
  imageUrl?: string;
  mediaType?: string;
  duration?: number;
  model?: string;
  imageError?: string;
  modelCatalogRecommended?: Record<string, any[]>;
  modelCatalogSearchResults?: any[];
  modelCatalogSelected?: string;
  modelCatalogResolved?: string;
  catalogType?: string;
  imageModel?: string;
  videoModel?: string;
  searchModel?: string;
  ttsModel?: string;
  sttModel?: string;
  visionModel?: string;
  hasImageTool?: boolean;
  hasVideoTool?: boolean;
  hasSearchTool?: boolean;
  hasTtsTool?: boolean;
  hasSttTool?: boolean;
  hasVisionTool?: boolean;
  audioUrl?: string;
  audioPrompt?: string;
  voice?: string;
  transcriptionText?: string;
  videoUrl?: string;
  videoPrompt?: string;
  fileUrl?: string;
  fileName?: string;
  fileMime?: string;
  attachmentUrl?: string;  // For user message attachments
  attachmentName?: string;
  attachmentMime?: string;
}

export interface AgentProgressEntry {
  name: string;
  role: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  progress: number;
  output?: string;
  current_task?: string;
  current_tool?: string;
  tool_description?: string;
  model?: string;
}

export interface ActivityEntry {
  id: string;
  text: string;
  timestamp: number;
  status: 'current' | 'completed';
}

interface ChatPanelProps {
  messages: ChatMessage[];
  activityLog: ActivityEntry[];
  isProcessing: boolean;
  onAcceptPlan?: () => void;
  onRejectPlan?: () => void;
  onApproveImage?: (approvalId: string) => void;
  onRejectImage?: (approvalId: string) => void;
  onEditImagePrompt?: (approvalId: string, newPrompt: string) => void;
}

const PlanCard: React.FC<{
  agents: PlanAgent[];
  taskDescription: string;
  planType: string;
  planStatus: PlanStatus;
  onAccept?: () => void;
  onReject?: () => void;
}> = ({ agents, taskDescription, planType, planStatus, onAccept, onReject }) => {
  const isPending = planStatus === 'pending';
  return (
    <div className={`rounded-xl border bg-surface/80 backdrop-blur-sm overflow-hidden ${isPending ? 'border-accent/30' : 'border-border'}`}>
      <div className="flex items-center justify-between px-4 py-2.5 bg-accent/5 border-b border-accent/20">
        <div className="flex items-center gap-2">
          <CheckSquare className="w-4 h-4 text-accent" />
          <span className="font-semibold text-sm text-text">
            {planStatus === 'approved' ? 'Plan Approved' : planStatus === 'rejected' ? 'Plan Rejected' : 'Plan Approval Required'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {planStatus === 'approved' && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-success/10 text-success flex items-center gap-1">
              <CheckCircle className="w-3 h-3" /> Approved
            </span>
          )}
          {planStatus === 'rejected' && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-danger/10 text-danger flex items-center gap-1">
              <XCircle className="w-3 h-3" /> Rejected
            </span>
          )}
          <span className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent">
            {agents.length} agent(s) · {planType === 'existing' ? 'Existing' : 'New'}
          </span>
        </div>
      </div>
      <div className="p-4 space-y-3">
        <div className="text-sm text-text-2">
          Task: <span className="text-text">{taskDescription}</span>
        </div>
        <div className="space-y-2">
          {agents.map((agent, idx) => (
            <div key={idx} className="p-3 rounded-lg bg-surface-2 border border-border/50">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono text-accent">#{idx + 1}</span>
                <span className="text-sm font-medium text-text">{agent.name}</span>
                <span className="text-xs text-text-2">— {agent.role}</span>
                {agent.is_existing ? (
                  <span className="text-xs px-1.5 py-0.5 rounded-full bg-success/10 text-success">Existing</span>
                ) : (
                  <span className="text-xs px-1.5 py-0.5 rounded-full bg-accent/10 text-accent">New</span>
                )}
              </div>
              {agent.goal && (
                <div className="text-xs text-text-2 ml-6">Goal: {agent.goal}</div>
              )}
              {agent.tools && agent.tools.length > 0 && (
                <div className="text-xs text-text-2 ml-6 flex items-center gap-1 flex-wrap">
                  <span className="text-text-2">Capabilities:</span>
                  {agent.tools.map((cap, i) => {
                    const isTool = cap === 'search_web' || cap === 'generate_image';
                    return (
                      <span
                        key={i}
                        className={`px-1.5 py-0.5 rounded-full text-xs ${
                          isTool
                            ? 'bg-accent/10 text-accent'
                            : 'bg-surface-3 text-text-2'
                        }`}
                      >
                        {isTool && <Wrench className="w-2.5 h-2.5 inline mr-0.5" />}
                        {cap}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
        {isPending && (
          <div className="flex gap-2">
            <button
              onClick={onAccept}
              className="px-4 py-1.5 rounded-md bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
            >
              ✅ Approve
            </button>
            <button
              onClick={onReject}
              className="px-4 py-1.5 rounded-md border border-border text-sm font-medium hover:bg-surface-2 transition-colors"
            >
              ❌ Reject
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const ProgressCard: React.FC<{ percent: number; label: string }> = ({ percent, label }) => {
  const isDone = percent >= 100;
  return (
    <div className="rounded-xl border border-border bg-surface/80 backdrop-blur-sm p-4">
      <div className="flex items-center gap-2 mb-2">
        {isDone ? (
          <CheckCircle className="w-4 h-4 text-success" />
        ) : (
          <Loader2 className="w-4 h-4 text-accent animate-spin" />
        )}
        <span className="text-sm text-text">{label}</span>
        <span className="text-xs text-text-2 ml-auto">{percent}%</span>
      </div>
      <div className="w-full bg-surface-2 rounded-full h-2 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${isDone ? 'bg-success' : 'bg-accent'}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
};

const toolIcon = (toolName: string) => {
  if (toolName === 'search_web') return <Search className="w-3.5 h-3.5 text-accent shrink-0" />;
  if (toolName === 'generate_image') return <Image className="w-3.5 h-3.5 text-purple-400 shrink-0" />;
  if (toolName === 'write_code') return <PenTool className="w-3.5 h-3.5 text-blue-400 shrink-0" />;
  return <Wrench className="w-3.5 h-3.5 text-text-2 shrink-0" />;
};

const AgentStatusRow: React.FC<{
  agent: AgentProgressEntry;
  index: number;
  showOutput: boolean;
  onToggleOutput: () => void;
}> = ({ agent, index, showOutput, onToggleOutput }) => {
  const isRunning = agent.status === 'running';
  const isComplete = agent.status === 'complete';
  const isError = agent.status === 'error';
  const hasTool = isRunning && !!agent.current_tool;
  const hasOutput = !!agent.output && agent.output.length > 0;

  return (
    <div className={`rounded-lg border overflow-hidden transition-colors ${
      isRunning ? 'border-accent/30 bg-accent/5' :
      isComplete ? 'border-success/20 bg-success/5' :
      isError ? 'border-danger/30 bg-danger/5' :
      'border-border bg-surface-2'
    }`}>
      <div className="flex items-center gap-2 px-3 py-2">
        <span className="text-xs font-mono text-text-2 shrink-0">#{index + 1}</span>
        {isRunning ? (
          <Loader2 className="w-3.5 h-3.5 text-accent animate-spin shrink-0" />
        ) : isComplete ? (
          <CheckCircle className="w-3.5 h-3.5 text-success shrink-0" />
        ) : isError ? (
          <XCircle className="w-3.5 h-3.5 text-danger shrink-0" />
        ) : (
          <div className="w-3.5 h-3.5 rounded-full border border-text-2/40 shrink-0" />
        )}
        <span className="text-sm font-medium text-text truncate">{agent.name}</span>
        <span className="text-xs text-text-2 hidden sm:inline truncate">— {agent.role}</span>
        {isComplete && (
          <span className="text-xs px-1.5 py-0.5 rounded-full bg-success/10 text-success shrink-0 ml-auto">Done</span>
        )}
        {isRunning && hasTool && (
          <span className="text-xs px-1.5 py-0.5 rounded-full bg-accent/10 text-accent shrink-0 ml-auto animate-pulse">Working</span>
        )}
        {isRunning && !hasTool && (
          <span className="text-xs px-1.5 py-0.5 rounded-full bg-accent/10 text-accent shrink-0 ml-auto">Thinking...</span>
        )}
      </div>

      {isRunning && agent.current_task && (
        <div className="px-3 pb-2 flex items-start gap-1.5">
          <Brain className="w-3 h-3 text-text-2 shrink-0 mt-0.5" />
          <span className="text-xs text-text-2 line-clamp-2">{agent.current_task}</span>
        </div>
      )}

      {hasTool && (
        <div className="px-3 pb-2 flex items-center gap-1.5">
          {toolIcon(agent.current_tool!)}
          <span className="text-xs text-text line-clamp-1">{agent.tool_description || agent.current_tool}</span>
        </div>
      )}

      {hasOutput && (
        <div className="px-3 pb-2">
          <button
            onClick={onToggleOutput}
            className="flex items-center gap-1 text-xs text-text-2 hover:text-text transition-colors"
          >
            <Eye className="w-3 h-3" />
            {showOutput ? 'Hide' : 'Preview'} output
          </button>
          {showOutput && (
            <div className="mt-1.5 text-xs text-text-2 bg-surface-3 rounded-md p-2 max-h-96 overflow-y-auto whitespace-pre-wrap">
              {agent.output}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const AgentProgressCard: React.FC<{
  overallPercent: number;
  agents: AgentProgressEntry[];
}> = ({ agents }) => {
  const allDone = agents.every((a) => a.status === 'complete');
  const runningCount = agents.filter((a) => a.status === 'running').length;
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());

  const toggleOutput = (agentName: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(agentName)) next.delete(agentName);
      else next.add(agentName);
      return next;
    });
  };

  return (
    <div className="rounded-xl border border-border bg-surface/80 backdrop-blur-sm p-4 space-y-3">
      <div className="flex items-center gap-2">
        {allDone ? (
          <CheckCircle className="w-4 h-4 text-success" />
        ) : (
          <Loader2 className="w-4 h-4 text-accent animate-spin" />
        )}
        <span className="text-sm font-medium text-text">
          {allDone ? 'All agents complete' : `${runningCount} agent(s) working...`}
        </span>
      </div>
      <div className="space-y-2">
        {agents.map((agent, idx) => (
          <AgentStatusRow
            key={agent.name}
            agent={agent}
            index={idx}
            showOutput={expandedAgents.has(agent.name)}
            onToggleOutput={() => toggleOutput(agent.name)}
          />
        ))}
      </div>
    </div>
  );
};

const ResultAgentCard: React.FC<{ agent: ResultAgent; index: number }> = ({ agent, index }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-lg bg-surface-2 border border-border/50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-surface-3 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-text-2 shrink-0" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-text-2 shrink-0" />
        )}
        <span className="text-xs font-mono text-accent">#{index + 1}</span>
        <span className="text-sm font-medium text-text">{agent.name}</span>
        <span className="text-xs text-text-2 truncate">— {agent.role}</span>
      </button>
      {expanded && (
        <div className="px-3 pb-3 text-sm text-text whitespace-pre-wrap max-h-64 overflow-y-auto">
          {agent.output}
        </div>
      )}
    </div>
  );
};

const ResultCard: React.FC<{
  summary: string;
  agents?: ResultAgent[];
  isError?: boolean;
}> = ({ summary, agents, isError }) => (
  <div className={`rounded-xl border overflow-hidden backdrop-blur-sm ${isError ? 'border-danger/30 bg-surface/80' : 'border-success/30 bg-surface/80'}`}>
    <div className={`flex items-center gap-2 px-4 py-2.5 border-b ${isError ? 'bg-danger/5 border-danger/20' : 'bg-success/5 border-success/20'}`}>
      {isError ? (
        <XCircle className="w-4 h-4 text-danger" />
      ) : (
        <CheckCircle className="w-4 h-4 text-success" />
      )}
      <span className="font-semibold text-sm text-text">{summary}</span>
    </div>
    {agents && agents.length > 0 && (
      <div className="p-3 space-y-2">
        {agents.map((agent, idx) => (
          <ResultAgentCard key={idx} agent={agent} index={idx} />
        ))}
      </div>
    )}
  </div>
);

const ImageApprovalCard: React.FC<{
  prompt: string;
  agentName: string;
  approvalStatus: ImageApprovalStatus;
  mediaType?: string;
  duration?: number;
  onApprove?: () => void;
  onReject?: () => void;
}> = ({ prompt, agentName, approvalStatus, mediaType = 'image', duration = 0, onApprove, onReject }) => {
  const isPending = approvalStatus === 'pending';
  const isVideo = mediaType === 'video';
  const icon = isVideo ? '🎬' : '🖼️';
  const label = isVideo ? 'Video' : 'Image';
  return (
    <div className={`rounded-xl border bg-surface/80 backdrop-blur-sm overflow-hidden ${isPending ? 'border-purple-400/30' : 'border-border'}`}>
      <div className="flex items-center justify-between px-4 py-2.5 bg-purple-500/5 border-b border-purple-400/20">
        <div className="flex items-center gap-2">
          <Image className="w-4 h-4 text-purple-400" />
          <span className="font-semibold text-sm text-text">
            {approvalStatus === 'approved' ? `${label} Generated` : approvalStatus === 'rejected' ? `${label} Rejected` : `${label} Generation Approval`}
          </span>
        </div>
        {agentName && <span className="text-xs text-text-2">by {agentName}</span>}
      </div>
      <div className="p-4 space-y-3">
        <div className="text-sm text-text-2">
          Prompt: <span className="text-text italic">"{prompt}"</span>
          {isVideo && duration > 0 && <span className="ml-2 text-xs text-text-3">({duration}s)</span>}
        </div>
        {isPending && (
          <div className="flex gap-2">
            <button
              onClick={onApprove}
              className="px-4 py-1.5 rounded-md bg-purple-500 text-white text-sm font-medium hover:bg-purple-600 transition-colors"
            >
              {icon} Generate
            </button>
            <button
              onClick={onReject}
              className="px-4 py-1.5 rounded-md bg-surface-2 text-text-2 text-sm font-medium border border-border hover:bg-surface-3 transition-colors"
            >
              ❌ Cancel
            </button>
          </div>
        )}
        {approvalStatus === 'approved' && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-success/10 text-success flex items-center gap-1 w-fit">
            <CheckCircle className="w-3 h-3" /> Approved
          </span>
        )}
        {approvalStatus === 'rejected' && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-danger/10 text-danger flex items-center gap-1 w-fit">
            <XCircle className="w-3 h-3" /> Cancelled
          </span>
        )}
      </div>
    </div>
  );
};

const ImageResultCard: React.FC<{
  imageUrl: string;
  prompt: string;
  approvalId?: string;
  mediaType?: string;
  onEditPrompt?: (approvalId: string, newPrompt: string) => void;
}> = ({ imageUrl, prompt, approvalId, mediaType = 'image', onEditPrompt }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedPrompt, setEditedPrompt] = useState(prompt);
  const [loadError, setLoadError] = useState(false);
  const isVideo = mediaType === 'video';
  const isPlaceholder = imageUrl.includes('placeholder_');
  return (
    <div className="rounded-xl border border-purple-400/30 bg-surface/80 backdrop-blur-sm overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-purple-500/5 border-b border-purple-400/20">
        <Image className="w-4 h-4 text-purple-400" />
        <span className="font-semibold text-sm text-text">{isVideo ? 'Generated Video' : 'Generated Image'}</span>
        {approvalId && onEditPrompt && (
          <div className="ml-auto flex items-center gap-3">
            <button
              onClick={() => onEditPrompt?.(approvalId, prompt)}
              className="text-text-2 hover:text-purple-400 transition-colors text-xs font-medium"
              title="Regenerate with same prompt"
            >
              🔄
            </button>
            <button
              onClick={() => setIsEditing(!isEditing)}
              className="text-text-2 hover:text-purple-400 transition-colors"
              title="Edit prompt"
            >
              <Pencil className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
      <div className="p-3">
        {loadError || isPlaceholder ? (
          <div className="w-full max-w-md rounded-lg border border-border bg-surface-2 p-6 text-center">
            <p className="text-sm text-text-2">
              {isVideo ? '🎬' : '🖼️'} {isVideo ? 'Video' : 'Image'} generation pending paid tier
            </p>
            <p className="text-xs text-text-3 mt-1">Configure OpenRouter credits to generate real media</p>
          </div>
        ) : isVideo ? (
          <video
            src={imageUrl}
            controls
            className="w-full max-w-md rounded-lg border border-border"
            onError={() => setLoadError(true)}
          />
        ) : (
          <img
            src={imageUrl}
            alt={prompt}
            className="w-full max-w-md rounded-lg border border-border"
            loading="lazy"
            onError={() => setLoadError(true)}
          />
        )}
        <p className="text-xs text-text-2 mt-2 italic">"{prompt}"</p>
        {isEditing && (
          <div className="mt-3 space-y-2">
            <textarea
              value={editedPrompt}
              onChange={(e) => setEditedPrompt(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-2 p-2 text-sm text-text focus:outline-none focus:border-purple-400"
              rows={3}
            />
            <div className="flex gap-2">
              <button
                onClick={() => {
                  onEditPrompt?.(approvalId || '', editedPrompt);
                  setIsEditing(false);
                }}
                className="px-3 py-1.5 rounded-md bg-purple-500 text-white text-sm font-medium hover:bg-purple-600 transition-colors"
              >
                🔄 Regenerate
              </button>
              <button
                onClick={() => setIsEditing(false)}
                className="px-3 py-1.5 rounded-md border border-border text-sm font-medium hover:bg-surface-2 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  activityLog,
  isProcessing,
  onAcceptPlan,
  onRejectPlan,
  onApproveImage,
  onRejectImage,
  onEditImagePrompt,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, activityLog, isProcessing]);

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-bg">
      <div className="p-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-accent" />
          <h2 className="font-semibold text-sm text-text">Conversation</h2>
        </div>
        <div className="text-xs text-text-2">{messages.length} messages</div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && activityLog.length === 0 && !isProcessing ? (
          <div className="flex flex-col items-center justify-center py-16 text-text-2">
            <Bot className="w-12 h-12 mb-3 opacity-30" />
            <p>No conversation yet</p>
            <p className="text-sm mt-1">Type a message below to start chatting</p>
          </div>
        ) : (
          <>
            {messages.map((msg) => {
              const msgType = msg.messageType || 'text';

              if (msgType === 'plan' && msg.planAgents) {
                return (
                  <div key={msg.id} className="flex gap-2 flex-row">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                      <Bot className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex-1 max-w-[85%]">
                      <PlanCard
                        agents={msg.planAgents}
                        taskDescription={msg.planTaskDescription || ''}
                        planType={msg.planType || 'new'}
                        planStatus={msg.planStatus || 'pending'}
                        onAccept={onAcceptPlan}
                        onReject={onRejectPlan}
                      />
                    </div>
                  </div>
                );
              }

              if (msgType === 'progress') {
                return (
                  <div key={msg.id} className="flex gap-2 flex-row">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                      <Bot className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex-1 max-w-[85%]">
                      <ProgressCard
                        percent={msg.progressPercent || 0}
                        label={msg.progressLabel || 'Processing...'}
                      />
                    </div>
                  </div>
                );
              }

              if (msgType === 'agent_progress' && msg.agentProgressList) {
                return (
                  <div key={msg.id} className="flex gap-2 flex-row">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                      <Bot className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex-1 max-w-[85%]">
                      <AgentProgressCard
                        overallPercent={msg.agentProgressOverall || 0}
                        agents={msg.agentProgressList}
                      />
                    </div>
                  </div>
                );
              }

              if (msgType === 'result') {
                return (
                  <div key={msg.id} className="flex gap-2 flex-row">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                      <Bot className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex-1 max-w-[85%]">
                      <ResultCard
                        summary={msg.resultSummary || 'Done'}
                        agents={msg.resultAgents}
                        isError={msg.resultError}
                      />
                    </div>
                  </div>
                );
              }

              // image_approval and image_result are now shown on canvas agent nodes, not in chat
              if (msgType === 'image_approval' || msgType === 'image_result') {
                return null;
              }

              // Default: text message
              return (
                <div
                  key={msg.id}
                  className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
                >
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                      msg.role === 'user'
                        ? 'bg-accent text-white'
                        : 'bg-surface-2 text-text-2'
                    }`}
                  >
                    {msg.role === 'user' ? (
                      <User className="w-3.5 h-3.5" />
                    ) : (
                      <Bot className="w-3.5 h-3.5" />
                    )}
                  </div>
                  <div
                    className={`max-w-[75%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                      msg.role === 'user'
                        ? 'bg-accent text-white'
                        : 'bg-surface/80 backdrop-blur-sm border border-border text-text'
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              );
            })}
            {(activityLog.length > 0 || isProcessing) && (
              <div className="flex flex-col gap-1.5 pl-9">
                {activityLog.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-center gap-2 text-xs text-text-2"
                  >
                    {entry.status === 'current' ? (
                      <Loader2 className="w-3 h-3 text-accent animate-spin shrink-0" />
                    ) : (
                      <CheckCircle className="w-3 h-3 text-success shrink-0" />
                    )}
                    <span>{entry.text}</span>
                  </div>
                ))}
                {isProcessing && activityLog.length === 0 && (
                  <div className="flex items-center gap-2 text-xs text-text-2">
                    <Loader2 className="w-3 h-3 text-accent animate-spin shrink-0" />
                    <span>Processing...</span>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
