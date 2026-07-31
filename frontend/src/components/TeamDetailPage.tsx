import { useState, useCallback } from 'react';
import { ChevronLeft, ChevronRight, Plus, Settings, Trash2, Cpu } from 'lucide-react';
import { usePlatform } from '../context/PlatformContext';
import { formatResetDate } from '../utils/credits';
import { StoryboardArea } from './StoryboardArea';
import { ChatPanelRight } from './ChatPanelRight';
import { AgentConfigModal } from './AgentConfigModal';
import { AgentFormModal } from './AgentFormModal';
import type { ChatMessage, ActivityEntry } from './chatTypes';
import type { ChatSession } from './ChatSidebar';
import type { Team } from '../types/team';
import type { Agent } from '../types/platform';

function timeAgo(dateStr: string) {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (diff < 60) return 'เมื่อกี้';
  if (diff < 3600) return `${Math.floor(diff / 60)} นาทีที่แล้ว`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ชม. ที่แล้ว`;
  if (diff < 604800) return `${Math.floor(diff / 86400)} วันที่แล้ว`;
  return `${Math.floor(diff / 604800)} สัปดาห์ที่แล้ว`;
}

interface TeamDetailPageProps {
  team: Team;
  onBack: () => void;
  onDeleteTeam: (teamId: string) => void;
  onSendCommand: (message: string, attachments?: Array<{ url: string; name: string; mime: string }>) => void | Promise<void>;
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
  preloadedModelCatalog?: Record<string, any[]>;
  preloadedModelSearchResults?: any[];
  preloadedMediaCatalog?: Record<string, any[]>;
  preloadedMediaSearchResults?: any[];
  onMentionAgent?: (agentName: string) => void;
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
  preloadedModelCatalog,
  preloadedModelSearchResults,
  preloadedMediaCatalog,
  preloadedMediaSearchResults,
  onMentionAgent,
}) => {
  const { agents, current_plan, system_status, available_tools, credits } = usePlatform();
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [configAgentId, setConfigAgentId] = useState<string | null>(null);
  const configAgent = configAgentId ? agents.find(a => a.id === configAgentId) || null : null;
  const [mentionText, setMentionText] = useState('');
  const [showAddAgentModal, setShowAddAgentModal] = useState(false);

  const handleMentionAgent = useCallback((agentName: string) => {
    setMentionText(`@${agentName} `);
  }, []);

  const teamAgents = agents.filter((a) => team.agent_ids.includes(a.id));
  const managerAgent = teamAgents.find((a) => a.is_manager);
  const regularAgents = teamAgents.filter((a) => !a.is_manager);
  const statusText = connectionStatus === 'connected' ? system_status : 'Connecting...';

  const handleConfigAgent = useCallback((agent: Agent) => {
    setConfigAgentId(agent.id);
  }, []);

  const handleSaveConfig = useCallback((data: { agent_id: string; name: string; role: string; goal: string; persona: string; model: string; tools: string[] }) => {
    onAction('config_agent', data);
    // If this is a manager agent, sync model to top bar
    const agent = agents.find(a => a.id === data.agent_id);
    if (agent && (agent.is_manager || agent.role?.toLowerCase() === 'manager') && data.model) {
      onAction('set_selected_model', { model_id: data.model });
    }
  }, [onAction, agents]);

  return (
    <div className="h-full w-full flex flex-col bg-bg">
      {/* Top bar — match mockup */}
      <div className="flex items-center gap-4 px-5 py-2.5 bg-surface border-b border-border shrink-0">
        <button
          onClick={onBack}
          className="text-text-3 hover:text-text hover:bg-surface-2 rounded-md px-2 py-1 transition-colors text-lg"
        >
          ←
        </button>
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-purple-500 flex items-center justify-center text-sm font-bold text-white shrink-0">
          {team.name.charAt(0).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-sm font-semibold text-text truncate">{team.name}</h1>
          <p className="text-[11px] text-text-3 truncate">
            {team.description ? `${team.description} · ` : ''}{teamAgents.length} agents · {chatSessions.length} sessions
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Credits */}
          {credits && (
            <div className="flex items-center gap-1.5 text-xs text-text-2" title={`Daily: $${credits.usage_daily?.toFixed(4) ?? 0} | Weekly: $${credits.usage_weekly?.toFixed(4) ?? 0} | Monthly: $${credits.usage_monthly?.toFixed(4) ?? 0} | All-time: $${credits.usage?.toFixed(4) ?? 0}`}>
              {(() => {
                const isLow = (credits.limit_remaining ?? 0) < 1;
                if (credits.limit !== null && credits.limit > 0) {
                  // Show remaining/limit — previously showed used/limit which was confusing
                  const remaining = credits.limit_remaining ?? 0;
                  return (
                    <span className={isLow ? 'text-warning' : ''}>
                      ${remaining.toFixed(2)} / ${credits.limit?.toFixed(2) ?? '—'}
                      {credits.limit_reset && <span className="text-text-3 ml-1">(รีเซ็ต {formatResetDate(credits.limit_reset)})</span>}
                    </span>
                  );
                } else if (credits.is_free_tier) {
                  return <span className="text-warning">Free Tier</span>;
                } else {
                  return <span>${credits.usage?.toFixed(2) ?? '—'} used</span>;
                }
              })()}
            </div>
          )}
          {/* Status */}
          <div className="flex items-center gap-1.5 text-xs text-text-2">
            <div className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-success' : 'bg-warning'} ${connectionStatus === 'connected' ? '' : 'animate-pulse'}`} />
            <span>{statusText}</span>
          </div>
        </div>
      </div>

      {/* 3-column layout: Sessions+Agents | Chat | Storyboard */}
      <div className="flex-1 flex min-h-0 relative">
        {/* Left: Chat Sessions (top) + Agents (bottom) */}
        {!leftCollapsed && (
          <div className="w-[230px] bg-surface border-r border-border flex flex-col shrink-0">
            {/* Chat Sessions */}
            <div className="px-4 py-3 pb-2 flex items-center justify-between">
              <span className="text-xs font-semibold text-text-2">Chat Sessions</span>
              <button
                onClick={() => onAction('new_chat')}
                className="w-5 h-5 rounded bg-surface-2 text-text-3 hover:text-text hover:bg-surface-3 flex items-center justify-center transition-colors"
              >
                <Plus className="w-3 h-3" />
              </button>
            </div>
            <div className="overflow-y-auto px-2 pb-2 max-h-[35%]">
              {chatSessions.length === 0 ? (
                <p className="text-xs text-text-3 italic px-3 py-2 text-center">No sessions</p>
              ) : (
                chatSessions.map((session) => (
                  <div
                    key={session.id}
                    onClick={() => onAction('switch_chat', { session_id: session.id })}
                    className={`px-3 py-2 rounded-lg cursor-pointer mb-1 group ${activeSessionId === session.id ? 'bg-accent/15' : 'hover:bg-surface-2'}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-medium text-text truncate">{session.title}</div>
                        <div className="text-[10px] text-text-3 mt-0.5">{session.updated_at ? timeAgo(session.updated_at) : ''}</div>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); if (confirm('ลบแชทนี้?')) onAction('delete_chat', { session_id: session.id }); }}
                        className="text-text-3 opacity-0 group-hover:opacity-100 hover:text-danger transition-all shrink-0 ml-2"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Agents */}
            <div className="px-4 py-2 border-t border-border flex items-center justify-between">
              <span className="text-xs font-semibold text-text-2">Agents</span>
              <div className="flex items-center gap-1">
                <span className="text-[10px] text-text-3">{teamAgents.length}</span>
                <button
                  onClick={() => setShowAddAgentModal(true)}
                  className="p-1 rounded-md text-text-2 hover:text-accent hover:bg-surface-2 transition-colors"
                  title="Add Agent"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-2">
              {managerAgent && (
                <div
                  className="w-full text-left px-3 py-2.5 bg-accent/10 border border-accent/30 rounded-lg mb-1.5 hover:bg-accent/15 transition-colors group"
                >
                  <div className="flex items-center gap-1.5">
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${managerAgent.status === 'Busy' ? 'bg-warning' : 'bg-success'}`} />
                    <span className="text-xs font-semibold text-purple-400 truncate flex-1">{managerAgent.name}</span>
                    <span className="text-[8px] px-1 py-0.5 bg-accent/20 text-purple-400 rounded font-semibold">MGR</span>
                    {onMentionAgent && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleMentionAgent(managerAgent.name); }}
                        className="text-[10px] text-accent opacity-0 group-hover:opacity-100 hover:text-accent-light transition-opacity shrink-0"
                        title="Mention"
                      >@</button>
                    )}
                    <button onClick={() => handleConfigAgent(managerAgent)} className="shrink-0">
                      <Settings className="w-3 h-3 text-text-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </button>
                  </div>
                  <p className="text-[10px] text-text-3 ml-3.5 mt-0.5">{managerAgent.role}</p>
                  <div className="flex items-center gap-1 ml-3.5 mt-1">
                    <Cpu className="w-2.5 h-2.5 text-text-3" />
                    <span className="text-[9px] text-text-3">{selectedModel || managerAgent.model || 'auto'}</span>
                  </div>
                </div>
              )}
              {regularAgents.length === 0 && !managerAgent ? (
                <p className="text-xs text-text-3 italic px-3 py-4 text-center">
                  No agents yet.
                  <br />
                  Send a message to create some.
                </p>
              ) : (
                regularAgents.map((agent) => (
                  <div
                    key={agent.id}
                    className="w-full text-left px-3 py-2.5 bg-bg border border-border rounded-lg mb-1.5 hover:border-border-light transition-colors group"
                  >
                    <div className="flex items-center gap-1.5">
                      <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${agent.status === 'Busy' ? 'bg-warning' : 'bg-success'}`} />
                      <span className="text-xs font-semibold text-text truncate flex-1">{agent.name}</span>
                      {onMentionAgent && (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleMentionAgent(agent.name); }}
                          className="text-[10px] text-accent opacity-0 group-hover:opacity-100 hover:text-accent-light transition-opacity shrink-0"
                          title="Mention"
                        >@</button>
                      )}
                      <button onClick={() => handleConfigAgent(agent)} className="shrink-0">
                        <Settings className="w-3 h-3 text-text-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </button>
                    </div>
                    <p className="text-[10px] text-text-3 ml-3.5 mt-0.5">{agent.role}</p>
                    <div className="flex items-center gap-1 ml-3.5 mt-1">
                      <Cpu className="w-2.5 h-2.5 text-text-3" />
                      <span className="text-[9px] text-text-3">{agent.model || 'auto'}</span>
                    </div>
                    {agent.tools && agent.tools.length > 0 && (
                      <div className="flex flex-wrap gap-1 ml-3.5 mt-1">
                        {agent.tools.map((tool) => (
                          <span key={tool} className="text-[8px] px-1.5 py-0.5 bg-surface-2 rounded text-text-2">{tool}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Collapse toggle for left panel */}
        <button
          onClick={() => setLeftCollapsed(!leftCollapsed)}
          className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-4 h-12 bg-surface border border-border rounded-r flex items-center justify-center hover:bg-surface-2 transition-colors"
          style={{ left: leftCollapsed ? 0 : '230px' }}
        >
          {leftCollapsed ? <ChevronRight className="w-3 h-3 text-text-3" /> : <ChevronLeft className="w-3 h-3 text-text-3" />}
        </button>

        {/* Center: Chat */}
        <div className="flex-1 min-w-0 flex">
          <ChatPanelRight
              fillContainer
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
              onConfirmTuning={(proposals) => onAction('confirm_tuning', { proposals })}
              onRejectTuning={() => onAction('reject_tuning')}
              onApproveImage={(approvalId) => onAction('approve_image', { approval_id: approvalId })}
              onRejectImage={(approvalId) => onAction('reject_image', { approval_id: approvalId })}
              onRetryImage={(approvalId) => onAction('retry_image', { approval_id: approvalId })}
              onEditImagePrompt={(approvalId, newPrompt) => onAction('edit_image_prompt', { approval_id: approvalId, new_prompt: newPrompt })}
              onApproveAgentResult={(reviewId) => onAction('approve_agent_result', { review_id: reviewId })}
              onRejectAgentResult={(reviewId, feedback) => onAction('reject_agent_result', { review_id: reviewId, feedback })}
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
              preloadedModelCatalog={preloadedModelCatalog}
              preloadedModelSearchResults={preloadedModelSearchResults}
              preloadedMediaCatalog={preloadedMediaCatalog}
              preloadedMediaSearchResults={preloadedMediaSearchResults}
              mentionText={mentionText}
              onMentionConsumed={() => setMentionText('')}
            />
        </div>

        {/* Right: Storyboard (collapsible) */}
        {!rightCollapsed && (
          <div className="w-[380px] bg-surface border-l border-border flex flex-col shrink-0">
            <div className="px-4 py-2.5 border-b border-border shrink-0">
              <span className="text-xs font-semibold text-text-2">📊 Storyboard</span>
            </div>
            <div className="flex-1 min-w-0 overflow-hidden">
              <StoryboardArea
                chatMessages={chatMessages}
                onApproveImage={(approvalId) => onAction('approve_image', { approval_id: approvalId })}
                onRejectImage={(approvalId) => onAction('reject_image', { approval_id: approvalId })}
                onRetryImage={(approvalId) => onAction('retry_image', { approval_id: approvalId })}
                onEditImagePrompt={(approvalId, newPrompt) => onAction('edit_image_prompt', { approval_id: approvalId, new_prompt: newPrompt })}
                onRetryTask={() => onAction('retry_task')}
                onRateTask={(rating) => onAction('rate_task', { rating })}
                onSkipReview={(agentName) => onAction('skip_review', { agent_name: agentName })}
              />
            </div>
          </div>
        )}

        {/* Collapse toggle for right panel */}
        <button
          onClick={() => setRightCollapsed(!rightCollapsed)}
          className="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-4 h-12 bg-surface border border-border rounded-l flex items-center justify-center hover:bg-surface-2 transition-colors"
          style={{ right: rightCollapsed ? 0 : '23.75rem' }}
        >
          {rightCollapsed ? <ChevronLeft className="w-3 h-3 text-text-3" /> : <ChevronRight className="w-3 h-3 text-text-3" />}
        </button>
      </div>

      {/* Modals */}
      <AgentConfigModal
        open={!!configAgent}
        agent={configAgent}
        availableTools={available_tools || []}
        onClose={() => setConfigAgentId(null)}
        onSave={handleSaveConfig}
        onAction={onAction}
        modelCatalog={preloadedModelCatalog}
        modelSearchResults={preloadedModelSearchResults}
        onSearchModels={(query) => onAction('search_models', { query })}
        onFetchModelCatalog={() => onAction('fetch_model_catalog')}
        selectedModel={selectedModel}
      />

      <AgentFormModal
        open={showAddAgentModal}
        mode="add"
        availableTools={available_tools || []}
        onSubmit={(data) => {
          onAction('add_agent_form', { ...data, team_id: team.id });
          setShowAddAgentModal(false);
        }}
        onClose={() => setShowAddAgentModal(false)}
      />

    </div>
  );
};
