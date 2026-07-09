import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  MiniMap,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type NodeChange,
  type EdgeChange,
  type NodeProps,
  Handle,
  Position,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Loader2, CheckCircle, XCircle, Bot, User, Zap, Image, Video, PenTool, Eye, ChevronDown, ChevronUp, Rocket, Pencil, Trash2, Cpu } from 'lucide-react';
import type { Agent, Task, Plan } from '../types/platform';
import type { AgentProgressEntry } from './ChatPanel';

// ============================================================
// Custom Node Types
// ============================================================

const nodeIcons: Record<string, React.ReactNode> = {
  image: <Image className="w-4 h-4" />,
  video: <Video className="w-4 h-4" />,
  copywriter: <PenTool className="w-4 h-4" />,
  default: <Bot className="w-4 h-4" />,
};

const getAgentIcon = (name: string) => {
  const lower = name.toLowerCase();
  if (lower.includes('image') || lower.includes('visual')) return nodeIcons.image;
  if (lower.includes('video')) return nodeIcons.video;
  if (lower.includes('copy') || lower.includes('writer') || lower.includes('content')) return nodeIcons.copywriter;
  return nodeIcons.default;
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

export interface AgentNodeData {
  agent: Agent;
  progress?: AgentProgressEntry;
  task?: Task;
  isSelected?: boolean;
  planPending?: boolean;
  pendingApprovals?: PendingApproval[];
  imageResults?: ImageResult[];
  onApproveImage?: (approvalId: string) => void;
  onRejectImage?: (approvalId: string) => void;
  onEditImagePrompt?: (approvalId: string, newPrompt: string) => void;
  onNodeClick?: (agent: Agent) => void;
  onEdit?: (agent: Agent) => void;
  onAssignTask?: (agent: Agent) => void;
  onDelete?: (agentId: string) => void;
}

const AgentNodeComponent: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as AgentNodeData;
  const { agent, progress, task, isSelected, planPending, pendingApprovals, imageResults, onApproveImage, onRejectImage, onEditImagePrompt, onNodeClick, onEdit, onAssignTask, onDelete } = nodeData;
  const [showOutput, setShowOutput] = useState(false);

  const status = progress?.status || 'pending';
  const isRunning = status === 'running';
  const isComplete = status === 'complete';
  const isError = status === 'error';
  const progressPercent = progress?.progress || 0;
  const hasOutput = !!progress?.output && progress.output.length > 0;
  const hasMedia = !!(task?.images && task.images.length > 0) || !!task?.imageUrl;
  const canAct = agent.status === 'Idle' || isComplete;

  const glowClass = isRunning
    ? 'border-accent/50 animate-pulse-glow'
    : isComplete
    ? 'border-success/40'
    : isError
    ? 'border-danger/40'
    : planPending
    ? 'border-accent/30 border-dashed'
    : 'border-border';

  return (
    <div
      className={`relative group rounded-xl border-2 ${glowClass} bg-gradient-to-br ${getAvatarColor(agent.name)} p-3 min-w-52 max-w-md transition-all hover:border-accent/60 ${
        isSelected ? 'ring-2 ring-accent/50' : ''
      }`}
    >
      <Handle type="target" position={Position.Top} className="!w-2 !h-2 !bg-accent !border-none" />

      <div
        className="flex items-start gap-3 mb-2 cursor-pointer"
        onClick={() => onNodeClick?.(agent)}
      >
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
          ) : (
            <div className="w-4 h-4 rounded-full border-2 border-text-3" />
          )}
        </div>
      </div>

      {isRunning && (
        <div className="text-xs text-text-2 mb-2 bg-surface/60 rounded-md p-2 backdrop-blur-sm border border-border/30">
          <div className="flex items-center gap-1.5 mb-1">
            <Loader2 className="w-3 h-3 text-accent animate-spin shrink-0" />
            <span className="text-text-2 font-medium">Thinking...</span>
          </div>
          {progress?.current_task && (
            <div className="text-[10px] text-text-3 italic">
              {progress.current_task}
            </div>
          )}
          {progress?.current_tool && (
            <div className="text-[10px] text-accent mt-1 flex items-center gap-1">
              <Zap className="w-2.5 h-2.5" />
              {progress.tool_description || progress.current_tool}
            </div>
          )}
        </div>
      )}

      {progressPercent > 0 && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-text-2">{isComplete ? 'Done' : isRunning ? 'Working' : 'Pending'}</span>
            <span className="text-text-2">{progressPercent}%</span>
          </div>
          <div className="w-full bg-surface-3 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isComplete ? 'bg-success' : isError ? 'bg-danger' : 'bg-gradient-to-r from-accent to-accent-light'
              }`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {agent.goal && (
        <div className="mt-1.5 text-[10px] text-text-2">
          {agent.goal}
        </div>
      )}

      {agent.tools.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {agent.tools.slice(0, 3).map((tool, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface/60 text-text-2 backdrop-blur-sm">
              {tool}
            </span>
          ))}
          {agent.tools.length > 3 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface/60 text-text-2">
              +{agent.tools.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Media preview */}
      {hasMedia && (
        <div className="mt-2 border-t border-border/30 pt-2">
          <div className="text-[10px] text-text-2 mb-1 flex items-center gap-1">
            <Image className="w-2.5 h-2.5" /> Media output
          </div>
          {task?.images && task.images.length > 0 ? (
            <div className="space-y-1">
              {task.images.map((img, i) => (
                <div key={i} className="rounded-md overflow-hidden border border-border/30">
                  {img.mediaType === 'video' ? (
                    <video src={img.url} controls className="w-full" />
                  ) : (
                    <img src={img.url} alt={img.prompt} className="w-full" loading="lazy" />
                  )}
                </div>
              ))}
            </div>
          ) : task?.imageUrl && (
            <div className="rounded-md overflow-hidden border border-border/30">
              <img src={task.imageUrl} alt={task.imagePrompt || ''} className="w-full" loading="lazy" />
            </div>
          )}
        </div>
      )}

      {/* Output preview — always visible when output exists */}
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
          {pendingApprovals.map((pa) => (
            <div key={pa.approvalId} className="rounded-lg border border-purple-400/30 bg-purple-500/5 p-2">
              <div className="flex items-center gap-1 text-[10px] text-purple-400 mb-1">
                {pa.mediaType === 'video' ? <Video className="w-2.5 h-2.5" /> : <Image className="w-2.5 h-2.5" />}
                <span className="font-medium">{pa.mediaType === 'video' ? 'Video' : 'Image'} Approval</span>
                {pa.duration > 0 && <span className="text-text-3">({pa.duration}s)</span>}
              </div>
              <div className="text-xs text-text-2 italic mb-2">"{pa.prompt}"</div>
              {pa.model && (
                <div className="flex items-center gap-1 text-[10px] text-text-2 mb-2">
                  <Cpu className="w-2.5 h-2.5 shrink-0" />
                  <span>Model: <span className="text-text font-mono">{pa.model}</span></span>
                </div>
              )}
              <div className="flex gap-1.5 flex-wrap">
                <button
                  onClick={(e) => { e.stopPropagation(); onApproveImage?.(pa.approvalId); }}
                  className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-purple-500 text-white hover:bg-purple-600 transition-colors"
                >
                  {pa.mediaType === 'video' ? '🎬' : '🖼️'} Generate
                </button>
                {onEditImagePrompt && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      const newPrompt = prompt('Edit prompt:', pa.prompt);
                      if (newPrompt) onEditImagePrompt(pa.approvalId, newPrompt);
                    }}
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
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Generated media results */}
      {imageResults && imageResults.length > 0 && (
        <div className="mt-2 border-t border-border/30 pt-2 space-y-1">
          <div className="text-[10px] text-text-2 mb-1 flex items-center gap-1">
            <Image className="w-2.5 h-2.5" /> Generated media
          </div>
          {imageResults.map((ir) => (
            <div key={ir.approvalId} className="rounded-md overflow-hidden border border-border/30">
              {ir.mediaType === 'video' ? (
                <video src={ir.imageUrl} controls className="w-full" />
              ) : (
                <img src={ir.imageUrl} alt={ir.prompt} className="w-full" loading="lazy" />
              )}
            </div>
          ))}
        </div>
      )}

      {/* Quick actions on hover */}
      <div className="mt-2 border-t border-border/30 pt-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {onAssignTask && (
          <button
            onClick={(e) => { e.stopPropagation(); onAssignTask(agent); }}
            disabled={!canAct}
            className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent hover:bg-accent/20 disabled:opacity-30 transition-colors"
            title="Assign Task"
          >
            <Rocket className="w-2.5 h-2.5" /> Task
          </button>
        )}
        {onEdit && (
          <button
            onClick={(e) => { e.stopPropagation(); onEdit(agent); }}
            className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-surface/60 text-text-2 hover:text-text transition-colors"
            title="Edit"
          >
            <Pencil className="w-2.5 h-2.5" />
          </button>
        )}
        {onDelete && (
          <button
            onClick={(e) => { e.stopPropagation(); if (confirm(`Delete agent "${agent.name}"?`)) onDelete(agent.id); }}
            className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-surface/60 text-text-2 hover:text-danger transition-colors"
            title="Delete"
          >
            <Trash2 className="w-2.5 h-2.5" />
          </button>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!w-2 !h-2 !bg-accent !border-none" />
    </div>
  );
};

interface SystemNodeData {
  label: string;
  sublabel?: string;
  icon: 'user' | 'manager' | 'output';
  isThinking?: boolean;
  taskCount?: number;
  taskDescription?: string;
  resultSummary?: string;
  resultAgents?: { name: string; role: string; output: string }[];
  resultError?: boolean;
}

const SystemNodeComponent: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as SystemNodeData;
  const { label, sublabel, icon, isThinking, taskCount, taskDescription, resultSummary, resultAgents, resultError } = nodeData;
  const [expandedAgent, setExpandedAgent] = useState<number | null>(null);

  const borderClass = icon === 'output'
    ? (resultError ? 'border-danger/40' : 'border-success/30')
    : 'border-accent/30';
  const bgClass = icon === 'output'
    ? (resultError ? 'from-danger/15 to-danger/5' : 'from-success/15 to-success/5')
    : 'from-accent/20 to-accent-light/10';

  return (
    <div className={`rounded-xl border-2 ${borderClass} bg-gradient-to-br ${bgClass} p-4 min-w-48 max-w-lg ${isThinking ? 'animate-pulse-glow' : ''}`}>
      {icon !== 'user' && <Handle type="target" position={Position.Top} className="!w-2 !h-2 !bg-accent !border-none" />}
      <div className="flex items-center gap-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
          icon === 'output' ? 'bg-success/20' : 'bg-accent/20'
        }`}>
          {icon === 'user' ? (
            <User className="w-4 h-4 text-accent" />
          ) : icon === 'output' ? (
            <CheckCircle className="w-4 h-4 text-success" />
          ) : (
            <Bot className="w-4 h-4 text-accent" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-text">{label}</div>
          <div className="text-xs text-text-2">
            {icon === 'output' ? (resultSummary || (taskCount && taskCount > 0 ? `${taskCount} task(s) completed` : 'Waiting...')) : sublabel || ''}
          </div>
        </div>
        {isThinking && <Loader2 className="w-4 h-4 text-accent animate-spin shrink-0" />}
      </div>
      {/* Show task description on manager node */}
      {icon === 'manager' && taskDescription && (
        <div className="mt-2 text-[10px] text-text-2 bg-surface/40 rounded-md p-1.5 backdrop-blur-sm">
          {taskDescription}
        </div>
      )}
      {/* Show result details on output node — per-agent cards */}
      {icon === 'output' && resultAgents && resultAgents.length > 0 && (
        <div className="mt-2 space-y-2">
          {resultAgents.map((ra, i) => {
            const isExpanded = expandedAgent === i;
            const outputLen = ra.output?.length || 0;
            return (
              <div key={i} className="border-t border-border/30 pt-2">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-md bg-surface/60 flex items-center justify-center shrink-0">
                    {getAgentIcon(ra.name)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-text truncate">{ra.name}</div>
                    <div className="text-[10px] text-text-2 truncate">{ra.role}</div>
                  </div>
                </div>
                <div
                  className="text-xs text-text-2 mt-1.5 whitespace-pre-wrap bg-surface/40 rounded-md p-2 border border-border/20"
                  style={{ display: isExpanded ? 'block' : '-webkit-box', WebkitLineClamp: isExpanded ? 'unset' : 3, WebkitBoxOrient: 'vertical', overflow: isExpanded ? 'auto' : 'hidden' }}
                >
                  {ra.output}
                </div>
                {outputLen > 150 && (
                  <button
                    onClick={(e) => { e.stopPropagation(); setExpandedAgent(isExpanded ? null : i); }}
                    className="flex items-center gap-1 text-[10px] text-text-2 hover:text-text transition-colors mt-1"
                  >
                    {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    {isExpanded ? 'Show less' : 'Show more'}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
      {icon !== 'output' && <Handle type="source" position={Position.Bottom} className="!w-2 !h-2 !bg-accent !border-none" />}
    </div>
  );
};

const nodeTypes = {
  agent: AgentNodeComponent,
  system: SystemNodeComponent,
};

// ============================================================
// Canvas Area (inner component with react-flow context)
// ============================================================

export interface PendingApproval {
  approvalId: string;
  prompt: string;
  agentName: string;
  mediaType: string;
  duration: number;
  model?: string;
  approvalStatus?: string;
  imageError?: string;
}

export interface ImageResult {
  imageUrl: string;
  prompt: string;
  approvalId: string;
  mediaType: string;
  agentName: string;
}

interface CanvasAreaInnerProps {
  agents: Agent[];
  agentProgress?: AgentProgressEntry[];
  latestUserMessage?: string;
  runningTasks: number;
  completedTasks: number;
  currentPlan?: Plan | null;
  planPending?: boolean;
  isProcessing?: boolean;
  tasks?: Task[];
  resultData?: { summary: string; agents: { name: string; role: string; output: string }[]; error: boolean } | null;
  pendingApprovals?: PendingApproval[];
  imageResults?: ImageResult[];
  onApproveImage?: (approvalId: string) => void;
  onRejectImage?: (approvalId: string) => void;
  onEditImagePrompt?: (approvalId: string, newPrompt: string) => void;
  onNodeClick: (agent: Agent) => void;
  onEdit?: (agent: Agent) => void;
  onAssignTask?: (agent: Agent) => void;
  onDelete?: (agentId: string) => void;
  selectedAgentId?: string;
  canvasState?: { nodes: Node[]; edges: Edge[] };
  onCanvasStateChange?: (nodes: Node[], edges: Edge[]) => void;
}

const CanvasAreaInner: React.FC<CanvasAreaInnerProps> = ({
  agents,
  agentProgress,
  latestUserMessage,
  runningTasks,
  completedTasks,
  currentPlan,
  planPending = false,
  isProcessing = false,
  tasks = [],
  resultData = null,
  pendingApprovals = [],
  imageResults = [],
  onApproveImage,
  onRejectImage,
  onEditImagePrompt,
  onNodeClick,
  onEdit,
  onAssignTask,
  onDelete,
  selectedAgentId,
  canvasState,
  onCanvasStateChange: _onCanvasStateChange,
}) => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const isDraggingRef = useRef(false);

  // Stable refs for callbacks — prevents data-update effect from firing on every render
  const callbacksRef = useRef({ onNodeClick, onEdit, onAssignTask, onDelete, onApproveImage, onRejectImage, onEditImagePrompt });
  callbacksRef.current = { onNodeClick, onEdit, onAssignTask, onDelete, onApproveImage, onRejectImage, onEditImagePrompt };

  // Sync from external canvasState (e.g. when switching sessions)
  // Only apply when switching sessions, not on every render
  const lastCanvasStateRef = useRef<string>('');
  useEffect(() => {
    const stateKey = canvasState ? `${canvasState.nodes.length}-${canvasState.edges.length}` : 'empty';
    if (canvasState && lastCanvasStateRef.current !== stateKey) {
      lastCanvasStateRef.current = stateKey;
      lastStructureKeyRef.current = ''; // force rebuild
      setNodes(canvasState.nodes);
      setEdges(canvasState.edges);
    } else if (!canvasState && lastCanvasStateRef.current !== 'empty') {
      lastCanvasStateRef.current = 'empty';
      lastStructureKeyRef.current = '';
      setNodes([]);
      setEdges([]);
    }
  }, [canvasState]);

  // Auto-arrange: only rebuild topology when plan/agent structure changes
  const planKey = currentPlan ? `${currentPlan.task_description}-${currentPlan.agents.length}` : 'no-plan';
  const structureKey = `${planKey}-${agents.length}`;
  const lastStructureKeyRef = useRef<string>('');

  useEffect(() => {
    // Don't rebuild if user is actively dragging
    if (isDraggingRef.current) return;
    // Only rebuild when structure changes (new plan, different agent count)
    if (lastStructureKeyRef.current === structureKey && nodes.length > 0) return;
    lastStructureKeyRef.current = structureKey;

    // Auto-arrange from plan or agents
    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];

    // Determine which agents to show: prefer plan agents, fall back to registry
    const planAgents = currentPlan?.agents || agents;
    const taskDesc = currentPlan?.task_description || '';

    // Layout: vertical (top to bottom)
    // User → Manager → [Agents fan-out] → Output
    const centerX = 300;
    const agentCount = planAgents.length;

    // User node (top)
    newNodes.push({
      id: 'user-node',
      type: 'system',
      position: { x: centerX - 112, y: 0 },
      data: { label: 'User', sublabel: latestUserMessage || 'Type a message...', icon: 'user' },
    });

    // Manager node (below user)
    newNodes.push({
      id: 'manager-node',
      type: 'system',
      position: { x: centerX - 112, y: 140 },
      data: {
        label: 'Manager',
        sublabel: 'Orchestrator',
        icon: 'manager',
        isThinking: runningTasks > 0,
        taskDescription: taskDesc,
      },
    });

    // Output node (bottom) — generous spacing to avoid overlap with expanded agent nodes
    const cols = Math.min(agentCount, 4);
    const agentRows = Math.ceil(agentCount / cols);
    const outputY = 300 + agentRows * 320 + 60;
    newNodes.push({
      id: 'output-node',
      type: 'system',
      position: { x: centerX - 112, y: outputY },
      data: { label: 'Output', icon: 'output', taskCount: completedTasks, resultSummary: resultData?.summary, resultAgents: resultData?.agents, resultError: resultData?.error },
    });

    // Edges: User → Manager
    newEdges.push({
      id: 'e-user-manager',
      source: 'user-node',
      target: 'manager-node',
      animated: runningTasks > 0,
      label: runningTasks > 0 ? 'Processing...' : 'Request',
      labelStyle: { fontSize: 10, fill: '#8b8fa3' },
      labelBgStyle: { fill: '#1e1f2b' },
      style: { stroke: runningTasks > 0 ? '#6366f1' : '#3a3d4a', strokeWidth: 2 },
    });

    // Agent nodes — fan-out below manager in a row
    const spacing = 280;
    const startX = centerX - 112 - ((cols - 1) * spacing) / 2;

    planAgents.forEach((agent, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      const agentId = agent.id || `plan-${idx}`;
      const agentTask = tasks.find((t) => t.agent === agent.name);
      const nodeProgress = agentProgress?.find((p) => p.name === agent.name);
      const agentApprovals = pendingApprovals.filter((pa) => pa.agentName.toLowerCase() === agent.name.toLowerCase());
      const agentImages = imageResults.filter((ir) => ir.agentName.toLowerCase() === agent.name.toLowerCase());

      newNodes.push({
        id: `agent-${agentId}`,
        type: 'agent',
        position: { x: startX + col * spacing, y: 300 + row * 320 },
        data: {
          agent,
          progress: nodeProgress,
          task: agentTask,
          isSelected: selectedAgentId === agentId,
          planPending,
          pendingApprovals: agentApprovals,
          imageResults: agentImages,
          onApproveImage: callbacksRef.current.onApproveImage,
          onRejectImage: callbacksRef.current.onRejectImage,
          onEditImagePrompt: callbacksRef.current.onEditImagePrompt,
          onNodeClick: callbacksRef.current.onNodeClick,
          onEdit: callbacksRef.current.onEdit,
          onAssignTask: callbacksRef.current.onAssignTask,
          onDelete: callbacksRef.current.onDelete,
        },
      });

      // Manager → Agent
      const agentStatus = nodeProgress?.status || 'pending';
      newEdges.push({
        id: `e-manager-${agentId}`,
        source: 'manager-node',
        target: `agent-${agentId}`,
        animated: agentStatus === 'running',
        label: agentStatus === 'running' ? 'Running...' : agentStatus === 'complete' ? 'Done' : agentStatus === 'error' ? 'Error' : 'Assigned',
        labelStyle: { fontSize: 10, fill: agentStatus === 'running' ? '#6366f1' : agentStatus === 'complete' ? '#22c55e' : agentStatus === 'error' ? '#ef4444' : '#8b8fa3' },
        labelBgStyle: { fill: '#1e1f2b' },
        style: { stroke: agentStatus === 'running' ? '#6366f1' : agentStatus === 'complete' ? '#22c55e' : agentStatus === 'error' ? '#ef4444' : '#3a3d4a', strokeWidth: 2 },
      });

      // Agent → Output
      newEdges.push({
        id: `e-${agentId}-output`,
        source: `agent-${agentId}`,
        target: 'output-node',
        animated: agentStatus === 'complete',
        label: agentStatus === 'complete' ? 'Delivered' : agentStatus === 'running' ? 'Working...' : 'Pending',
        labelStyle: { fontSize: 10, fill: agentStatus === 'complete' ? '#22c55e' : agentStatus === 'running' ? '#6366f1' : '#8b8fa3' },
        labelBgStyle: { fill: '#1e1f2b' },
        style: { stroke: agentStatus === 'complete' ? '#22c55e' : agentStatus === 'running' ? '#6366f1' : '#3a3d4a', strokeWidth: 2 },
      });
    });

    // Dependency edges: agent → agent (based on depends_on)
    planAgents.forEach((agent, idx) => {
      const agentId = agent.id || `plan-${idx}`;
      const deps = (agent as any).depends_on || [];
      if (deps.length > 0) {
        deps.forEach((depName: string) => {
          // Find the source agent by name
          const sourceIdx = planAgents.findIndex((a) => a.name.toLowerCase() === depName.toLowerCase());
          if (sourceIdx >= 0) {
            const sourceId = planAgents[sourceIdx].id || `plan-${sourceIdx}`;
            const sourceProgress = agentProgress?.find((p) => p.name.toLowerCase() === depName.toLowerCase());
            const sourceStatus = sourceProgress?.status || 'pending';
            newEdges.push({
              id: `e-dep-${sourceId}-${agentId}`,
              source: `agent-${sourceId}`,
              target: `agent-${agentId}`,
              animated: sourceStatus === 'running',
              label: sourceStatus === 'complete' ? 'Received' : sourceStatus === 'running' ? 'Waiting...' : 'Depends on',
              labelStyle: { fontSize: 10, fill: sourceStatus === 'complete' ? '#22c55e' : sourceStatus === 'running' ? '#f59e0b' : '#8b8fa3' },
              labelBgStyle: { fill: '#1e1f2b' },
              style: { stroke: sourceStatus === 'complete' ? '#22c55e' : sourceStatus === 'running' ? '#f59e0b' : '#6b7280', strokeWidth: 2, strokeDasharray: sourceStatus === 'complete' ? undefined : '5 5' },
            });
          }
        });
      }
    });

    setNodes(newNodes);
    setEdges(newEdges);
  }, [structureKey, currentPlan, agents, nodes.length]);

  // Enrich node data during render (no setNodes/setEdges — preserves drag positions)
  const enrichedNodes = useMemo(() => {
    return nodes.map((node) => {
      if (node.type === 'agent' && node.id.startsWith('agent-')) {
        const agentId = node.id.replace('agent-', '');
        const agent = agents.find((a) => a.id === agentId) ||
          (currentPlan?.agents || []).find((a) => (a.id || '') === agentId);
        if (agent) {
          const nodeProgress = agentProgress?.find((p) => p.name === agent.name);
          const agentTask = tasks.find((t) => t.agent === agent.name);
          return {
            ...node,
            data: {
              ...node.data,
              agent,
              progress: nodeProgress,
              task: agentTask,
              isSelected: selectedAgentId === agentId,
              planPending,
              pendingApprovals: pendingApprovals.filter((pa) => pa.agentName.toLowerCase() === agent.name.toLowerCase()),
              imageResults: imageResults.filter((ir) => ir.agentName.toLowerCase() === agent.name.toLowerCase()),
              onApproveImage: callbacksRef.current.onApproveImage,
              onRejectImage: callbacksRef.current.onRejectImage,
              onEditImagePrompt: callbacksRef.current.onEditImagePrompt,
              onNodeClick: callbacksRef.current.onNodeClick,
              onEdit: callbacksRef.current.onEdit,
              onAssignTask: callbacksRef.current.onAssignTask,
              onDelete: callbacksRef.current.onDelete,
            },
          };
        }
      }
      if (node.id === 'manager-node') {
        return {
          ...node,
          data: {
            ...node.data,
            isThinking: runningTasks > 0,
            taskDescription: currentPlan?.task_description || node.data.taskDescription,
          },
        };
      }
      if (node.id === 'user-node') {
        return {
          ...node,
          data: { ...node.data, sublabel: latestUserMessage || 'Type a message...' },
        };
      }
      if (node.id === 'output-node') {
        return {
          ...node,
          data: { ...node.data, taskCount: completedTasks, resultSummary: resultData?.summary, resultAgents: resultData?.agents, resultError: resultData?.error },
        };
      }
      return node;
    });
  }, [nodes, agents, agentProgress, latestUserMessage, runningTasks, completedTasks, selectedAgentId, currentPlan, tasks, planPending, resultData, pendingApprovals, imageResults]);

  // Enrich edge labels/styles during render (no setEdges — preserves edge state)
  const enrichedEdges = useMemo(() => {
    if (edges.length === 0) return edges;
    return edges.map((edge) => {
      if (edge.id === 'e-user-manager') {
        return {
          ...edge,
          animated: runningTasks > 0,
          label: runningTasks > 0 ? 'Processing...' : 'Request',
          style: { stroke: runningTasks > 0 ? '#6366f1' : '#3a3d4a', strokeWidth: 2 },
        };
      }
      if (edge.id.startsWith('e-manager-')) {
        const agentId = edge.id.replace('e-manager-', '');
        const agent = agents.find((a) => a.id === agentId) ||
          (currentPlan?.agents || []).find((a) => (a.id || '') === agentId);
        const agentStatus = agentProgress?.find((p) => p.name === agent?.name)?.status || 'pending';
        return {
          ...edge,
          animated: agentStatus === 'running',
          label: agentStatus === 'running' ? 'Running...' : agentStatus === 'complete' ? 'Done' : agentStatus === 'error' ? 'Error' : 'Assigned',
          labelStyle: { fontSize: 10, fill: agentStatus === 'running' ? '#6366f1' : agentStatus === 'complete' ? '#22c55e' : agentStatus === 'error' ? '#ef4444' : '#8b8fa3' },
          labelBgStyle: { fill: '#1e1f2b' },
          style: { stroke: agentStatus === 'running' ? '#6366f1' : agentStatus === 'complete' ? '#22c55e' : agentStatus === 'error' ? '#ef4444' : '#3a3d4a', strokeWidth: 2 },
        };
      }
      if (edge.id.includes('-output')) {
        const agentId = edge.id.replace('-output', '').replace('e-', '');
        const agent = agents.find((a) => a.id === agentId) ||
          (currentPlan?.agents || []).find((a) => (a.id || '') === agentId);
        const agentStatus = agentProgress?.find((p) => p.name === agent?.name)?.status || 'pending';
        return {
          ...edge,
          animated: agentStatus === 'complete',
          label: agentStatus === 'complete' ? 'Delivered' : agentStatus === 'running' ? 'Working...' : 'Pending',
          labelStyle: { fontSize: 10, fill: agentStatus === 'complete' ? '#22c55e' : agentStatus === 'running' ? '#6366f1' : '#8b8fa3' },
          labelBgStyle: { fill: '#1e1f2b' },
          style: { stroke: agentStatus === 'complete' ? '#22c55e' : agentStatus === 'running' ? '#6366f1' : '#3a3d4a', strokeWidth: 2 },
        };
      }
      // Dependency edges (agent → agent)
      if (edge.id.startsWith('e-dep-')) {
        // Extract source agent name from the edge source node
        const sourceNodeId = edge.source.replace('agent-', '');
        const sourceAgent = agents.find((a) => a.id === sourceNodeId) ||
          (currentPlan?.agents || []).find((a) => (a.id || '') === sourceNodeId);
        const sourceStatus = agentProgress?.find((p) => p.name === sourceAgent?.name)?.status || 'pending';
        return {
          ...edge,
          animated: sourceStatus === 'running',
          label: sourceStatus === 'complete' ? 'Received' : sourceStatus === 'running' ? 'Waiting...' : 'Depends on',
          labelStyle: { fontSize: 10, fill: sourceStatus === 'complete' ? '#22c55e' : sourceStatus === 'running' ? '#f59e0b' : '#8b8fa3' },
          labelBgStyle: { fill: '#1e1f2b' },
          style: { stroke: sourceStatus === 'complete' ? '#22c55e' : sourceStatus === 'running' ? '#f59e0b' : '#6b7280', strokeWidth: 2, strokeDasharray: sourceStatus === 'complete' ? undefined : '5 5' },
        };
      }
      return edge;
    });
  }, [edges, agents, agentProgress, runningTasks, currentPlan]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      // Allow position changes (drag) and selection
      setNodes((prev) => applyNodeChanges(changes, prev));
    },
    []
  );

  const onNodeDragStart = useCallback(() => {
    isDraggingRef.current = true;
  }, []);

  const onNodeDragStop = useCallback(() => {
    isDraggingRef.current = false;
  }, []);

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdges((prev) => applyEdgeChanges(changes, prev));
    },
    []
  );

  const onConnect = useCallback(
    (_connection: any) => {},
    []
  );

  const hasContent = !!currentPlan || (!isProcessing && agents.length > 0 && (latestUserMessage || runningTasks > 0 || completedTasks > 0));

  if (!hasContent) {
    return (
      <div className="flex-1 flex items-center justify-center bg-bg">
        <div className="flex flex-col items-center text-text-2">
          {isProcessing ? (
            <>
              <Loader2 className="w-12 h-12 mb-3 text-accent animate-spin" />
              <p className="text-sm">AI is thinking...</p>
              <p className="text-xs mt-1">Planning will appear here shortly</p>
            </>
          ) : (
            <>
              <Bot className="w-12 h-12 mb-3 opacity-30" />
              <p className="text-sm">Canvas is empty</p>
              <p className="text-xs mt-1">Type a message in chat to get started</p>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 h-full">
      <ReactFlow
        nodes={enrichedNodes}
        edges={enrichedEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        onNodeDragStart={onNodeDragStart}
        onNodeDragStop={onNodeDragStop}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        className="bg-bg"
        defaultEdgeOptions={{
          style: { stroke: '#6366f1', strokeWidth: 2 },
        }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#2a2d3a" />
        <MiniMap
          className="!bg-surface !border-border"
          nodeColor={(node) => {
            if (node.type === 'system') return '#6366f1';
            return '#8b5cf6';
          }}
        />
      </ReactFlow>
    </div>
  );
};

// ============================================================
// Canvas Area (wrapped with ReactFlowProvider)
// ============================================================

export interface CanvasAreaProps extends CanvasAreaInnerProps {}

export const CanvasArea: React.FC<CanvasAreaProps> = (props) => (
  <ReactFlowProvider>
    <CanvasAreaInner {...props} />
  </ReactFlowProvider>
);
