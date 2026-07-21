import { useState, useCallback, useEffect, useRef } from 'react';
import '/retro-mockup.css';
import { WindowManagerProvider, useWindowManager } from './WindowManager';
import { RetroWindow } from './RetroWindow';
import { Taskbar } from './Taskbar';
import { StartMenu } from './StartMenu';
import { DesktopIcons } from './DesktopIcons';
import { AgentsWindow } from './AgentsWindow';
import { HistoryWindow } from './HistoryWindow';
import { ScheduleWindow } from './ScheduleWindow';
import { SettingsWindow } from './SettingsWindow';
import { ChatWindow } from './ChatWindow';
import { TasksWindow } from './TasksWindow';
import { NotificationsWindow } from './NotificationsWindow';
import type { WindowId } from './types';
import type { ChatMessage, ActivityEntry, HistoryTaskLog, NotificationItem, TaskItem } from '../chatTypes';
import type { ChatSession } from '../ChatSidebar';
import type { Agent, Plan } from '../../types/platform';
import type { Team } from '../../types/team';
import type { ModelCatalogEntry } from '../ModelPicker';

interface RetroDesktopProps {
  // Team
  team: Team;
  onBack: () => void;
  onDeleteTeam: (teamId: string) => void;
  // Chat
  chatMessages: ChatMessage[];
  notifications: NotificationItem[];
  chatSessions: ChatSession[];
  activeSessionId: string | null;
  activityLog: ActivityEntry[];
  isProcessing: boolean;
  isThinking: boolean;
  thinkingText?: string;
  thinkingDuration?: number | null;
  inputMode: 'chat' | 'plan';
  selectedModel?: string;
  resolvedModel?: string;
  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  systemStatus?: string;
  onSendCommand: (message: string, attachments?: Array<{ url: string; name: string; mime: string }>) => void | Promise<void>;
  onStop?: () => void;
  onModeChange: (mode: 'chat' | 'plan') => void;
  onAction: (name: string, payload?: Record<string, any>) => void;
  // Platform state
  agents: Agent[];
  currentPlan: Plan | null;
  availableTools: Array<{ name: string; description: string }>;
  credits: any;
  historyLogs: HistoryTaskLog[];
  onFetchHistory: () => void;
  // Model catalog
  modelCatalog: Record<string, ModelCatalogEntry[]>;
  modelSearchResults: ModelCatalogEntry[];
  mediaCatalog: Record<string, ModelCatalogEntry[]>;
  mediaSearchResults: ModelCatalogEntry[];
  taskItems?: TaskItem[];
}

const windowConfig: Record<WindowId, { title: string; icon: string; width: number; height: number }> = {
  chat: { title: 'Chat', icon: '💬', width: 720, height: 480 },
  tasks: { title: 'Tasks', icon: '📋', width: 600, height: 420 },
  agents: { title: 'Agents', icon: '🤖', width: 500, height: 380 },
  history: { title: 'History', icon: '📜', width: 500, height: 380 },
  schedule: { title: 'Schedule', icon: '⏰', width: 500, height: 380 },
  settings: { title: 'Settings', icon: '⚙️', width: 460, height: 340 },
  notifications: { title: 'Notifications', icon: '🔔', width: 480, height: 400 },
};

const DesktopInner: React.FC<RetroDesktopProps> = (props) => {
  const { windows, activeWindowId, openWindow, closeWindow, focusWindow, minimizeWindow, moveWindow, resizeWindow } = useWindowManager();
  const [startMenuOpen, setStartMenuOpen] = useState(false);

  // Toast notifications — fire on real-time chat events
  const [toasts, setToasts] = useState<{ id: string; text: string; icon: string }[]>([]);
  const seenMsgIdsRef = useRef<Set<string>>(new Set());
  const seenNotifIdsRef = useRef<Set<string>>(new Set());

  const pushToast = useCallback((id: string, icon: string, text: string) => {
    setToasts(prev => [...prev, { id, icon, text }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  }, []);

  // Watch chatMessages — only fire toast when exactly 1 new message appears (real-time event).
  // Multiple new messages at once = session switch / history load → skip all.
  useEffect(() => {
    const newMsgs: typeof props.chatMessages = [];
    for (const msg of props.chatMessages) {
      const key = `msg-${msg.id}`;
      if (!seenMsgIdsRef.current.has(key)) newMsgs.push(msg);
    }
    // Mark all as seen
    for (const msg of props.chatMessages) seenMsgIdsRef.current.add(`msg-${msg.id}`);

    // Only fire if exactly 1 new message (real-time event)
    if (newMsgs.length !== 1) return;
    const msg = newMsgs[0];
    const key = `msg-${msg.id}`;

    if (msg.messageType === 'plan' && msg.planStatus === 'pending') {
      pushToast(key, '📋', 'แผนงานรออนุมัติ');
    } else if (msg.messageType === 'result') {
      pushToast(key, msg.resultError ? '❌' : '✅', msg.resultError ? 'งานเกิดข้อผิดพลาด' : 'งานเสร็จสิ้นแล้ว');
    } else if (msg.messageType === 'image_approval' && msg.approvalStatus === 'pending') {
      pushToast(key, '🖼️', 'รูปภาพรออนุมัติ');
    } else if (msg.messageType === 'agent_review' && msg.reviewStatus === 'pending') {
      pushToast(key, '🔍', 'ผลงาน agent รอตรวจสอบ');
    } else if (msg.messageType === 'tuning_proposal') {
      pushToast(key, '🔧', 'ข้อเสนอแนะการปรับแต่ง');
    }
  }, [props.chatMessages, pushToast]);

  // Watch notifications — same logic: only fire if exactly 1 new notification appears
  useEffect(() => {
    const pending = props.notifications.filter(n =>
      n.sessionId !== props.activeSessionId && (
        (n.messageType === 'plan' && n.planStatus === 'pending') ||
        (n.messageType === 'image_approval' && (n.approvalStatus === 'pending' || n.approvalStatus === 'error')) ||
        (n.messageType === 'agent_review' && n.reviewStatus === 'pending') ||
        (n.messageType === 'tuning_proposal' && n.tuningStatus !== 'confirmed' && n.tuningStatus !== 'rejected')
      )
    );

    const newNotifs: typeof pending = [];
    for (const n of pending) {
      const key = `notif-${n.messageType}-${n.id || n.sessionId || ''}-${n.timestamp || ''}`;
      if (!seenNotifIdsRef.current.has(key)) newNotifs.push(n);
    }
    // Mark all as seen
    for (const n of pending) {
      const key = `notif-${n.messageType}-${n.id || n.sessionId || ''}-${n.timestamp || ''}`;
      seenNotifIdsRef.current.add(key);
    }

    // Only fire if exactly 1 new notification (real-time event)
    if (newNotifs.length !== 1) return;
    const n = newNotifs[0];
    const key = `notif-${n.messageType}-${n.id || n.sessionId || ''}-${n.timestamp || ''}`;
    let icon = '🔔';
    let text = 'การแจ้งเตือนใหม่';
    if (n.messageType === 'plan') { icon = '📋'; text = 'แผนงานรออนุมัติ'; }
    else if (n.messageType === 'image_approval') { icon = '🖼️'; text = 'รูปภาพรออนุมัติ'; }
    else if (n.messageType === 'agent_review') { icon = '🔍'; text = 'ผลงาน agent รอตรวจสอบ'; }
    else if (n.messageType === 'tuning_proposal') { icon = '🔧'; text = 'ข้อเสนอแนะการปรับแต่ง'; }
    if (n.sessionTitle) text += ` — ${n.sessionTitle}`;
    pushToast(key, icon, text);
  }, [props.notifications, props.activeSessionId, pushToast]);

  // Auto-open chat window on mount
  useEffect(() => {
    handleOpenWindow('chat');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleOpenWindow = useCallback((id: WindowId) => {
    const cfg = windowConfig[id];
    openWindow(id, cfg.title, cfg.icon, cfg.width, cfg.height);
  }, [openWindow]);

  const handleSessionSwitch = useCallback((sessionId: string) => {
    props.onAction('switch_chat', { session_id: sessionId });
  }, [props.onAction]);

  const handleNewSession = useCallback(() => {
    props.onAction('new_chat');
  }, [props.onAction]);

  const handleRenameChat = useCallback((sessionId: string, title: string) => {
    props.onAction('rename_chat', { session_id: sessionId, title });
  }, [props.onAction]);

  const handleDeleteChat = useCallback((sessionId: string) => {
    props.onAction('delete_chat', { session_id: sessionId });
  }, [props.onAction]);

  const handleFetchModelCatalog = useCallback(() => {
    props.onAction('fetch_model_catalog');
  }, [props.onAction]);

  const handleSearchModels = useCallback((query: string) => {
    props.onAction('search_models', { query });
  }, [props.onAction]);

  const handleSelectModel = useCallback((modelId: string) => {
    props.onAction('set_selected_model', { model_id: modelId });
  }, [props.onAction]);

  const handleChangeAgentModel = useCallback((agentName: string, modelId: string) => {
    props.onAction('change_agent_model', { agent_name: agentName, model_id: modelId });
  }, [props.onAction]);

  const handleChangeManagerModel = useCallback((modelId: string) => {
    props.onAction('change_manager_model', { model_id: modelId });
  }, [props.onAction]);

  const handleChangeMediaModel = useCallback((mediaType: 'imageModel' | 'videoModel' | 'searchModel' | 'ttsModel' | 'sttModel' | 'visionModel', modelId: string) => {
    props.onAction('change_media_model', { media_type: mediaType, model_id: modelId });
  }, [props.onAction]);

  const handleFetchMediaCatalog = useCallback((mediaType: string) => {
    props.onAction('fetch_media_catalog', { media_type: mediaType });
  }, [props.onAction]);

  const handleAcceptPlan = useCallback(() => {
    props.onAction('accept_plan');
  }, [props.onAction]);

  const handleRejectPlan = useCallback(() => {
    props.onAction('reject_plan');
  }, [props.onAction]);

  const handleConfirmTuning = useCallback((proposals: any[]) => {
    props.onAction('confirm_tuning', { proposals });
  }, [props.onAction]);

  const handleRejectTuning = useCallback(() => {
    props.onAction('reject_tuning');
  }, [props.onAction]);

  const handleApproveImage = useCallback((approvalId: string, model?: string) => {
    props.onAction('approve_image', { approval_id: approvalId, model });
  }, [props.onAction]);

  const handleRejectImage = useCallback((approvalId: string) => {
    props.onAction('reject_image', { approval_id: approvalId });
  }, [props.onAction]);

  const handleRetryImage = useCallback((approvalId: string) => {
    props.onAction('retry_image', { approval_id: approvalId });
  }, [props.onAction]);

  const handleEditImagePrompt = useCallback((approvalId: string, newPrompt: string) => {
    props.onAction('retry_image', { approval_id: approvalId, prompt: newPrompt });
  }, [props.onAction]);

  const handleApproveAgentResult = useCallback((reviewId: string) => {
    props.onAction('approve_agent_result', { review_id: reviewId });
  }, [props.onAction]);

  const handleRejectAgentResult = useCallback((reviewId: string, feedback: string) => {
    props.onAction('reject_agent_result', { review_id: reviewId, feedback });
  }, [props.onAction]);

  const handleSaveAgentConfig = useCallback((data: any) => {
    props.onAction('config_agent', data);
  }, [props.onAction]);

  const handleAddAgent = useCallback((data: any) => {
    props.onAction('add_agent', data);
  }, [props.onAction]);

  const handleDeleteAgent = useCallback((agentId: string) => {
    props.onAction('delete_agent', { agent_id: agentId });
  }, [props.onAction]);

  const renderWindowContent = (id: string) => {
    switch (id as WindowId) {
      case 'chat':
        return (
          <ChatWindow
            messages={props.chatMessages}
            activityLog={props.activityLog}
            isProcessing={props.isProcessing}
            chatSessions={props.chatSessions}
            activeSessionId={props.activeSessionId}
            onSend={props.onSendCommand}
            onStop={props.onStop}
            onNewChat={handleNewSession}
            onSwitchChat={handleSessionSwitch}
            onRenameChat={handleRenameChat}
            onDeleteChat={handleDeleteChat}
            onAcceptPlan={handleAcceptPlan}
            onRejectPlan={handleRejectPlan}
            onConfirmTuning={handleConfirmTuning}
            onRejectTuning={handleRejectTuning}
            onApproveImage={handleApproveImage}
            onRejectImage={handleRejectImage}
            onRetryImage={handleRetryImage}
            onEditImagePrompt={handleEditImagePrompt}
            onApproveAgentResult={handleApproveAgentResult}
            onRejectAgentResult={handleRejectAgentResult}
            onFetchModelCatalog={handleFetchModelCatalog}
            onFetchMediaCatalog={handleFetchMediaCatalog}
            onSearchModels={handleSearchModels}
            onSelectModel={handleSelectModel}
            onChangeAgentModel={handleChangeAgentModel}
            onChangeManagerModel={handleChangeManagerModel}
            onChangeMediaModel={handleChangeMediaModel}
            selectedModel={props.selectedModel}
            resolvedModel={props.resolvedModel}
            thinkingText={props.thinkingText}
            thinkingDuration={props.thinkingDuration}
            isThinking={props.isThinking}
            inputMode={props.inputMode}
            onModeChange={props.onModeChange}
            disabled={props.isProcessing}
            preloadedModelCatalog={props.modelCatalog}
            preloadedModelSearchResults={props.modelSearchResults}
            preloadedMediaCatalog={props.mediaCatalog}
            preloadedMediaSearchResults={props.mediaSearchResults}
            onViewTasks={() => handleOpenWindow('tasks')}
          />
        );
      case 'tasks':
        return (
          <TasksWindow
            chatMessages={props.chatMessages}
            notifications={props.notifications}
            activeSessionId={props.activeSessionId}
            taskItems={props.taskItems}
            onNavigate={(sessionId) => {
              props.onAction('switch_chat', { session_id: sessionId });
              handleOpenWindow('chat');
            }}
          />
        );
      case 'agents':
        return (
          <AgentsWindow
            agents={props.agents}
            availableTools={props.availableTools}
            onAddAgent={handleAddAgent}
            onConfigAgent={handleSaveAgentConfig}
            onDeleteAgent={handleDeleteAgent}
            modelCatalog={props.modelCatalog}
            modelSearchResults={props.modelSearchResults}
            onSearchModels={handleSearchModels}
            onFetchModelCatalog={handleFetchModelCatalog}
            selectedModel={props.selectedModel}
          />
        );
      case 'history':
        return <HistoryWindow historyLogs={props.historyLogs} onFetchHistory={props.onFetchHistory} />;
      case 'schedule':
        return <ScheduleWindow />;
      case 'settings':
        return (
          <SettingsWindow
            credits={props.credits}
            connectionStatus={props.connectionStatus}
            systemStatus={props.systemStatus}
            team={props.team}
            onBack={props.onBack}
            onDeleteTeam={props.onDeleteTeam}
          />
        );
      case 'notifications':
        return (
          <NotificationsWindow
            notifications={props.notifications}
            onNavigate={(sessionId, windowId) => {
              props.onAction('switch_chat', { session_id: sessionId });
              handleOpenWindow(windowId);
            }}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div
      className="fixed inset-0 overflow-hidden"
      style={{
        background: '#e8dcc8',
        backgroundImage: 'radial-gradient(circle at 20% 30%, rgba(192,80,30,.03) 0%, transparent 50%), radial-gradient(circle at 80% 70%, rgba(58,107,138,.03) 0%, transparent 50%)',
      }}
    >
      {/* Desktop icons */}
      <DesktopIcons onOpenWindow={handleOpenWindow} />

      {/* Windows */}
      {windows.map(w => (
        <RetroWindow
          key={w.id}
          id={w.id}
          title={w.title}
          icon={w.icon}
          x={w.x}
          y={w.y}
          width={w.width}
          height={w.height}
          zIndex={w.zIndex}
          active={activeWindowId === w.id}
          minimized={w.minimized}
          onFocus={() => focusWindow(w.id)}
          onClose={() => closeWindow(w.id)}
          onMinimize={() => minimizeWindow(w.id)}
          onMove={(x, y) => moveWindow(w.id, x, y)}
          onResize={(width, height) => resizeWindow(w.id, width, height)}
        >
          {renderWindowContent(w.id)}
        </RetroWindow>
      ))}

      {/* Start menu */}
      <StartMenu
        open={startMenuOpen}
        onClose={() => setStartMenuOpen(false)}
        onOpenWindow={handleOpenWindow}
        onBack={props.onBack}
      />

      {/* Taskbar */}
      <Taskbar
        startMenuOpen={startMenuOpen}
        onToggleStartMenu={() => setStartMenuOpen(prev => !prev)}
        onOpenWindow={handleOpenWindow}
        credits={props.credits}
        notificationCount={props.notifications.filter(n =>
          (n.messageType === 'plan' && n.planStatus === 'pending') ||
          (n.messageType === 'image_approval' && (n.approvalStatus === 'pending' || n.approvalStatus === 'error')) ||
          (n.messageType === 'agent_review' && n.reviewStatus === 'pending') ||
          (n.messageType === 'tuning_proposal' && n.tuningStatus !== 'confirmed' && n.tuningStatus !== 'rejected')
        ).length}
      />

      {/* Toast notifications */}
      {toasts.length > 0 && (
        <div style={{
          position: 'fixed',
          bottom: '48px',
          right: '12px',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          maxWidth: '320px',
        }}>
          {toasts.map(t => (
            <div
              key={t.id}
              onClick={() => { handleOpenWindow('notifications'); setToasts(prev => prev.filter(tt => tt.id !== t.id)); }}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
                padding: '8px 12px',
                background: 'var(--cream, #f5f0e8)',
                border: '1px solid var(--line, #c8b89a)',
                borderRadius: '4px',
                boxShadow: '2px 2px 8px rgba(0,0,0,0.15)',
                fontSize: '11px',
                color: 'var(--ink, #3a3a3a)',
                cursor: 'pointer',
                animation: 'slideIn 0.3s ease',
              }}
            >
              <span style={{ fontSize: '14px', flexShrink: 0 }}>{t.icon}</span>
              <span>{t.text}</span>
            </div>
          ))}
        </div>
      )}

    </div>
  );
};

export const RetroDesktop: React.FC<RetroDesktopProps> = (props) => (
  <WindowManagerProvider>
    <DesktopInner {...props} />
  </WindowManagerProvider>
);
