import { useState, useCallback } from 'react';
import { ArrowLeft, ChevronLeft, ChevronRight, Settings, Trash2, Users } from 'lucide-react';
import { usePlatform } from '../context/PlatformContext';
import { StoryboardArea } from './StoryboardArea';
import { ChatPanelRight } from './ChatPanelRight';
import { AgentConfigModal } from './AgentConfigModal';
import type { ChatMessage, ActivityEntry } from './chatTypes';
import type { ChatSession } from './ChatSidebar';
import type { Team } from '../types/team';
import type { Agent } from '../types/platform';

interface TeamDetailPageProps {
  team: Team;
  onBack: () => void;
  onDeleteTeam: (teamId: string) => void;
  onSendCommand: (message: string, attachment?: { url: string; name: string; mime: string }) => void | Promise<void>;
  onStop?: () => void;
  onAction: (name: string, payload?: Record<string, any>) => void;
  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  chatMessages: ChatMessage[];
  activityLog: ActivityEntry[];
  isProcessing: boolean;
  chatSessions: ChatSession[];
  activeSessionId: string | null;
  selectedModel?: string;
  resolvedModel?: string;
  thinkingText?: string;
  thinkingDuration?: number | null;
  isThinking?: boolean;
  inputMode?: 'chat' | 'plan';
  onModeChange?: (mode: 'chat' | 'plan') => void;
}

export const TeamDetailPage: React.FC<TeamDetailPageProps> = ({
  team,
  onBack,
  onDeleteTeam,
  onSendCommand,
  onStop,
  onAction,
  connectionStatus,
  chatMessages,
  activityLog,
  isProcessing,
  chatSessions,
  activeSessionId,
  selectedModel,
  resolvedModel,
  thinkingText,
  thinkingDuration,
  isThinking,
  inputMode,
  onModeChange,
}) => {
  const { agents, current_plan, system_status, available_tools, credits } = usePlatform();
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [configAgent, setConfigAgent] = useState<Agent | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const teamAgents = agents.filter((a) => team.agent_ids.includes(a.id));
  const statusText = connectionStatus === 'connected' ? system_status : 'Connecting...';

  const handleConfigAgent = useCallback((agent: Agent) => {
    setConfigAgent(agent);
  }, []);

  const handleSaveConfig = useCallback((data: { agent_id: string; name: string; role: string; goal: string; persona: string; model: string; tools: string[] }) => {
    onAction('config_agent', data);
  }, [onAction]);

  return (
    <div className="h-full w-full flex flex-col bg-bg">
      {/* Top bar with team info + back */}
      <div className="h-12 bg-surface border-b border-border flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1 text-xs text-text-2 hover:text-text transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Teams
          </button>
          <div className="w-px h-5 bg-border" />
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-accent" />
            <h1 className="text-sm font-semibold text-text">{team.name}</h1>
            {team.description && (
              <span className="text-xs text-text-3 hidden md:inline">— {team.description}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Credits */}
          {credits && (
            <div className="flex items-center gap-1.5 text-xs text-text-2" title={`Daily: $${credits.usage_daily?.toFixed(4) ?? 0} | Monthly: $${credits.usage_monthly?.toFixed(4) ?? 0}`}>
              <span className={credits.limit_remaining !== null && credits.limit_remaining < 1 ? 'text-warning' : ''}>
                {credits.limit !== null && credits.limit > 0
                  ? `$${credits.usage?.toFixed(2) ?? '0'} / $${credits.limit?.toFixed(2) ?? '—'}`
                  : credits.is_free_tier
                  ? 'Free Tier'
                  : `$${credits.usage?.toFixed(2) ?? '—'} used`}
              </span>
            </div>
          )}
          {/* Status */}
          <div className="flex items-center gap-1.5 text-xs text-text-2">
            <div className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-success' : 'bg-warning'} ${connectionStatus === 'connected' ? '' : 'animate-pulse'}`} />
            <span>{statusText}</span>
          </div>
          {/* Delete team */}
          {confirmDelete ? (
            <div className="flex items-center gap-1">
              <button
                onClick={() => { onDeleteTeam(team.id); }}
                className="px-2 py-1 bg-error text-white text-[10px] rounded font-medium"
              >
                Confirm Delete
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="px-2 py-1 bg-surface-2 text-text-2 text-[10px] rounded font-medium border border-border"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="p-1.5 text-text-3 hover:text-error transition-colors"
              title="Delete team"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* 3-column layout: Agent list | Storyboard | Chat */}
      <div className="flex-1 flex min-h-0 relative">
        {/* Left: Agent list */}
        {!leftCollapsed && (
          <div className="w-56 bg-surface border-r border-border flex flex-col shrink-0">
            <div className="px-3 py-2 border-b border-border flex items-center justify-between">
              <span className="text-[10px] font-medium text-text-3 uppercase tracking-wide">Agents</span>
              <span className="text-[10px] text-text-3">{teamAgents.length}</span>
            </div>
            <div className="flex-1 overflow-auto py-1">
              {teamAgents.length === 0 ? (
                <p className="text-xs text-text-3 italic px-3 py-4 text-center">
                  No agents yet.
                  <br />
                  Send a message to create some.
                </p>
              ) : (
                teamAgents.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => handleConfigAgent(agent)}
                    className="w-full text-left px-3 py-2 hover:bg-surface-2 transition-colors group"
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-accent/50 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-text truncate">{agent.name}</p>
                        <p className="text-[10px] text-text-3 truncate">{agent.role}</p>
                      </div>
                      <Settings className="w-3 h-3 text-text-3 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        )}

        {/* Collapse toggle for left panel */}
        <button
          onClick={() => setLeftCollapsed(!leftCollapsed)}
          className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-4 h-12 bg-surface border border-border rounded-r flex items-center justify-center hover:bg-surface-2 transition-colors"
          style={{ left: leftCollapsed ? 0 : '14rem' }}
        >
          {leftCollapsed ? <ChevronRight className="w-3 h-3 text-text-3" /> : <ChevronLeft className="w-3 h-3 text-text-3" />}
        </button>

        {/* Middle: Storyboard */}
        <div className="flex-1 min-w-0 overflow-hidden">
          <StoryboardArea
            chatMessages={chatMessages}
            onApproveImage={(approvalId) => onAction('approve_image', { approval_id: approvalId })}
            onRejectImage={(approvalId) => onAction('reject_image', { approval_id: approvalId })}
            onRetryImage={(approvalId) => onAction('retry_image', { approval_id: approvalId })}
            onEditImagePrompt={(approvalId, newPrompt) => onAction('edit_image_prompt', { approval_id: approvalId, new_prompt: newPrompt })}
          />
        </div>

        {/* Right: Chat panel */}
        {!rightCollapsed && (
          <div className="w-[420px] bg-surface border-l border-border flex flex-col shrink-0">
            <ChatPanelRight
              messages={chatMessages}
              activityLog={activityLog}
              isProcessing={isProcessing}
              chatSessions={chatSessions}
              activeSessionId={activeSessionId}
              onSend={onSendCommand}
              onStop={onStop}
              onNewChat={() => onAction('new_chat')}
              onSwitchChat={(id) => onAction('switch_chat', { session_id: id })}
              onRenameChat={(id, title) => onAction('rename_chat', { session_id: id, title })}
              onDeleteChat={(id) => onAction('delete_chat', { session_id: id })}
              onAcceptPlan={() => onAction('accept_plan')}
              onRejectPlan={() => onAction('reject_plan')}
              onConfirmTuning={() => onAction('confirm_tuning')}
              onRejectTuning={() => onAction('reject_tuning')}
              onApproveImage={(approvalId) => onAction('approve_image', { approval_id: approvalId })}
              onRejectImage={(approvalId) => onAction('reject_image', { approval_id: approvalId })}
              onRetryImage={(approvalId) => onAction('retry_image', { approval_id: approvalId })}
              onEditImagePrompt={(approvalId, newPrompt) => onAction('edit_image_prompt', { approval_id: approvalId, new_prompt: newPrompt })}
              onFetchModelCatalog={() => onAction('fetch_model_catalog')}
              onFetchMediaCatalog={(mediaType) => onAction('fetch_media_catalog', { media_type: mediaType })}
              onSearchModels={(query) => onAction('search_models', { query })}
              onSelectModel={(modelId) => onAction('set_selected_model', { model_id: modelId })}
              onChangeAgentModel={(agentName, modelId) => onAction('change_agent_model', { agent_name: agentName, model_id: modelId })}
              onChangeManagerModel={(modelId) => onAction('change_manager_model', { model_id: modelId })}
              onChangeMediaModel={(mediaType, modelId) => onAction('change_media_model', { media_type: mediaType, model_id: modelId })}
              selectedModel={selectedModel}
              resolvedModel={resolvedModel}
              thinkingText={thinkingText}
              thinkingDuration={thinkingDuration}
              isThinking={isThinking}
              inputMode={inputMode}
              onModeChange={onModeChange}
              disabled={connectionStatus !== 'connected' || isProcessing || !!current_plan}
            />
          </div>
        )}

        {/* Collapse toggle for right panel */}
        <button
          onClick={() => setRightCollapsed(!rightCollapsed)}
          className="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-4 h-12 bg-surface border border-border rounded-l flex items-center justify-center hover:bg-surface-2 transition-colors"
          style={{ right: rightCollapsed ? 0 : '26.25rem' }}
        >
          {rightCollapsed ? <ChevronLeft className="w-3 h-3 text-text-3" /> : <ChevronRight className="w-3 h-3 text-text-3" />}
        </button>
      </div>

      {/* Modals */}
      <AgentConfigModal
        open={!!configAgent}
        agent={configAgent}
        availableTools={available_tools || []}
        onClose={() => setConfigAgent(null)}
        onSave={handleSaveConfig}
      />
    </div>
  );
};
