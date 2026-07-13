import { useState, useCallback, useEffect } from 'react';
import { usePlatform } from '../context/PlatformContext';
import { Header } from './Header';
import { AgentPalette } from './AgentPalette';
import { StoryboardArea } from './StoryboardArea';
import { ChatPanelRight } from './ChatPanelRight';
import { DetailPanel } from './DetailPanel';
import { AgentFormModal } from './AgentFormModal';
import { AssignTaskModal } from './AssignTaskModal';
import type { ChatMessage, ActivityEntry, AgentProgressEntry } from './chatTypes';
import type { ChatSession } from './ChatSidebar';
import type { Agent } from '../types/platform';
import type { Node, Edge } from '@xyflow/react';

interface MainLayoutProps {
  onSendCommand: (message: string, attachment?: { url: string; name: string; mime: string }) => void | Promise<void>;
  onStop?: () => void;
  onAction: (name: string, payload?: Record<string, any>) => void;
  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  chatMessages: ChatMessage[];
  activityLog: ActivityEntry[];
  isProcessing: boolean;
  chatSessions: ChatSession[];
  activeSessionId: string | null;
  canvasStateFromBackend?: any;
  selectedModel?: string;
  resolvedModel?: string;
  thinkingText?: string;
  thinkingDuration?: number | null;
  isThinking?: boolean;
  inputMode?: 'chat' | 'plan';
  onModeChange?: (mode: 'chat' | 'plan') => void;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  onSendCommand,
  onStop,
  onAction,
  connectionStatus,
  chatMessages,
  activityLog,
  isProcessing,
  chatSessions,
  activeSessionId,
  canvasStateFromBackend,
  selectedModel,
  resolvedModel,
  thinkingText,
  thinkingDuration,
  isThinking,
  inputMode,
  onModeChange,
}) => {
  const { agents, current_plan, system_status, available_tools, credits } = usePlatform();
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editAgent, setEditAgent] = useState<Agent | null>(null);
  const [assignAgent, setAssignAgent] = useState<Agent | null>(null);
  const [canvasStates, setCanvasStates] = useState<Record<string, { nodes: Node[]; edges: Edge[] }>>({});

  // Sync canvas state from backend when switching sessions
  useEffect(() => {
    if (canvasStateFromBackend && activeSessionId) {
      setCanvasStates((prev) => ({
        ...prev,
        [activeSessionId]: {
          nodes: canvasStateFromBackend.nodes || [],
          edges: canvasStateFromBackend.edges || [],
        },
      }));
    }
  }, [canvasStateFromBackend, activeSessionId]);

  const statusText = connectionStatus === 'connected' ? system_status : 'Connecting...';

  const latestProgress: AgentProgressEntry[] | undefined = (() => {
    // Find the last agent_progress message, last plan message, and last user message
    let lastProgressIdx = -1;
    let lastPlanOrUserIdx = -1;
    for (let i = chatMessages.length - 1; i >= 0; i--) {
      const msg = chatMessages[i];
      if (lastProgressIdx === -1 && msg.messageType === 'agent_progress' && msg.agentProgressList) {
        lastProgressIdx = i;
      }
      if (lastPlanOrUserIdx === -1 && (msg.messageType === 'plan' || msg.role === 'user')) {
        lastPlanOrUserIdx = i;
        break;
      }
    }

    // If a plan or user message appears AFTER the last progress, the progress is stale
    if (lastPlanOrUserIdx > lastProgressIdx && lastPlanOrUserIdx !== -1) {
      return undefined;
    }

    if (lastProgressIdx >= 0) {
      return chatMessages[lastProgressIdx].agentProgressList;
    }
    return undefined;
  })();

  const handleSelectAgent = (agent: Agent) => {
    setSelectedAgent(selectedAgent?.id === agent.id ? null : agent);
  };

  const handleEditAgent = (agent: Agent) => {
    setEditAgent(agent);
    setSelectedAgent(null);
  };

  const handleDeleteAgent = (agentId: string) => {
    onAction('delete_agent', { agent_id: agentId });
    setSelectedAgent(null);
  };

  const handleAssignTask = (agent: Agent) => {
    setAssignAgent(agent);
    setSelectedAgent(null);
  };

  const handleApproveImage = useCallback((approvalId: string) => {
    onAction('approve_image', { approval_id: approvalId });
  }, [onAction]);

  const handleRejectImage = useCallback((approvalId: string) => {
    onAction('reject_image', { approval_id: approvalId });
  }, [onAction]);

  const handleRetryImage = useCallback((approvalId: string) => {
    onAction('retry_image', { approval_id: approvalId });
  }, [onAction]);

  const handleEditImagePrompt = useCallback((approvalId: string, newPrompt: string) => {
    onAction('edit_image_prompt', { approval_id: approvalId, new_prompt: newPrompt });
  }, [onAction]);

  const selectedProgress = selectedAgent
    ? latestProgress?.find((p) => p.name === selectedAgent.name)
    : undefined;

  return (
    <div className="h-full w-full flex flex-col bg-bg">
      <Header
        systemStatus={statusText}
        credits={credits}
      />

      <div className="flex-1 flex min-h-0 relative">
        {selectedAgent ? (
          <DetailPanel
            agent={selectedAgent}
            progress={selectedProgress}
            availableTools={available_tools || []}
            onClose={() => setSelectedAgent(null)}
            onEdit={handleEditAgent}
            onDelete={handleDeleteAgent}
            onAssignTask={handleAssignTask}
          />
        ) : (
          <AgentPalette
            agents={agents}
            currentPlan={current_plan}
            onAddAgent={() => setShowAddModal(true)}
            onSelectAgent={handleSelectAgent}
            selectedAgentId={selectedAgent?.id || null}
          />
        )}

        <StoryboardArea
          chatMessages={chatMessages}
          onApproveImage={handleApproveImage}
          onRejectImage={handleRejectImage}
          onRetryImage={handleRetryImage}
          onEditImagePrompt={handleEditImagePrompt}
        />

        <ChatPanelRight
          messages={chatMessages}
          activityLog={activityLog}
          isProcessing={isProcessing}
          chatSessions={chatSessions}
          activeSessionId={activeSessionId}
          onSend={onSendCommand}
          onStop={onStop}
          onNewChat={() => { setCanvasStates({}); onAction('new_chat'); }}
          onSwitchChat={(id) => onAction('switch_chat', { session_id: id })}
          onRenameChat={(id, title) => onAction('rename_chat', { session_id: id, title })}
          onDeleteChat={(id) => {
            setCanvasStates((prev) => {
              const next = { ...prev };
              delete next[id];
              return next;
            });
            onAction('delete_chat', { session_id: id });
          }}
          onAcceptPlan={() => onAction('accept_plan')}
          onRejectPlan={() => onAction('reject_plan')}
          onConfirmTuning={() => onAction('confirm_tuning')}
          onRejectTuning={() => onAction('reject_tuning')}
          onApproveImage={(approvalId) => onAction('approve_image', { approval_id: approvalId })}
          onRejectImage={(approvalId) => onAction('reject_image', { approval_id: approvalId })}
          onRetryImage={(approvalId) => onAction('retry_image', { approval_id: approvalId })}
          onEditImagePrompt={(approvalId, newPrompt) =>
            onAction('edit_image_prompt', { approval_id: approvalId, new_prompt: newPrompt })
          }
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

      {/* Modals */}
      <AgentFormModal
        open={showAddModal}
        mode="add"
        availableTools={available_tools || []}
        onSubmit={(data) => onAction('add_agent_form', data)}
        onClose={() => setShowAddModal(false)}
      />
      <AgentFormModal
        open={!!editAgent}
        mode="edit"
        agent={editAgent}
        availableTools={available_tools || []}
        onSubmit={(data) => onAction('edit_agent_form', data)}
        onClose={() => setEditAgent(null)}
      />
      <AssignTaskModal
        open={!!assignAgent}
        agent={assignAgent}
        onSubmit={(data) => onAction('assign_task_form', data)}
        onClose={() => setAssignAgent(null)}
      />
    </div>
  );
};
