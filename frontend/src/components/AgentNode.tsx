import { Loader2, CheckCircle, XCircle, Bot, User, Zap, Image, Video, PenTool } from 'lucide-react';
import type { Agent } from '../types/platform';
import type { AgentProgressEntry } from './ChatPanel';

interface AgentNodeProps {
  agent: Agent;
  progress?: AgentProgressEntry;
  onClick: () => void;
  isSelected?: boolean;
}

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

export const AgentNode: React.FC<AgentNodeProps> = ({ agent, progress, onClick, isSelected }) => {
  const status = progress?.status || 'pending';
  const isRunning = status === 'running';
  const isComplete = status === 'complete';
  const isError = status === 'error';
  const progressPercent = progress?.progress || 0;

  const glowClass = isRunning
    ? 'border-accent/50 animate-pulse-glow'
    : isComplete
    ? 'border-success/40'
    : isError
    ? 'border-danger/40'
    : 'border-border';

  return (
    <button
      onClick={onClick}
      className={`relative group rounded-xl border-2 ${glowClass} bg-gradient-to-br ${getAvatarColor(agent.name)} p-4 w-52 text-left transition-all hover:border-accent/60 hover:scale-[1.02] ${
        isSelected ? 'ring-2 ring-accent/50' : ''
      }`}
    >
      <div className="flex items-start gap-3 mb-2">
        <div className="w-9 h-9 rounded-lg bg-surface/80 flex items-center justify-center shrink-0 backdrop-blur-sm">
          {getAgentIcon(agent.name)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-text truncate">{agent.name}</div>
          <div className="text-xs text-text-2 truncate">{agent.role}</div>
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

      {isRunning && progress?.current_tool && (
        <div className="text-xs text-text-2 mb-2 truncate">
          <Zap className="w-3 h-3 inline mr-1 text-accent" />
          {progress.tool_description || progress.current_tool}
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
    </button>
  );
};

export const UserNode: React.FC<{ label: string }> = ({ label }) => (
  <div className="rounded-xl border-2 border-accent/30 bg-gradient-to-br from-accent/20 to-accent-light/10 p-4 w-52">
    <div className="flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-accent/20 flex items-center justify-center shrink-0">
        <User className="w-4 h-4 text-accent" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-text">User</div>
        <div className="text-xs text-text-2 truncate">{label || 'Waiting for input...'}</div>
      </div>
    </div>
  </div>
);

export const ManagerNode: React.FC<{ isThinking?: boolean; isSelected?: boolean; onClick?: () => void }> = ({ isThinking, isSelected, onClick }) => (
  <button
    onClick={onClick}
    className={`rounded-xl border-2 ${isThinking ? 'border-accent/50 animate-pulse-glow' : 'border-accent/30'} bg-gradient-to-br from-accent/20 to-accent-light/10 p-4 w-52 text-left transition-all hover:border-accent/60 hover:scale-[1.02] ${
      isSelected ? 'ring-2 ring-accent/50' : ''
    }`}
  >
    <div className="flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-accent/20 flex items-center justify-center shrink-0">
        <Bot className="w-4 h-4 text-accent" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-text">Manager</div>
        <div className="text-xs text-text-2">Orchestrator</div>
      </div>
      {isThinking && <Loader2 className="w-4 h-4 text-accent animate-spin shrink-0" />}
    </div>
  </button>
);

export const OutputNode: React.FC<{ taskCount: number; onClick?: () => void; isSelected?: boolean }> = ({ taskCount, onClick, isSelected }) => (
  <button
    onClick={onClick}
    className={`rounded-xl border-2 border-success/30 bg-gradient-to-br from-success/15 to-success/5 p-4 w-52 text-left transition-all hover:border-success/50 hover:scale-[1.02] ${
      isSelected ? 'ring-2 ring-success/40' : ''
    }`}
  >
    <div className="flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-success/20 flex items-center justify-center shrink-0">
        <CheckCircle className="w-4 h-4 text-success" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-text">Output</div>
        <div className="text-xs text-text-2">{taskCount} task(s) completed</div>
      </div>
    </div>
  </button>
);
