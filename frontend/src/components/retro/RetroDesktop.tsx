import { useState, useCallback } from 'react';
import { WindowManagerProvider, useWindowManager } from './WindowManager';
import { RetroWindow } from './RetroWindow';
import { Taskbar } from './Taskbar';
import { StartMenu } from './StartMenu';
import { DesktopIcons } from './DesktopIcons';
import { ChatWindow } from './ChatWindow';
import { TasksWindow } from './TasksWindow';
import type { WindowId, PlanData } from './types';
import type { ChatMessage } from '../chatTypes';
import type { ChatSession } from '../ChatSidebar';

interface RetroDesktopProps {
  // Chat props
  chatMessages: ChatMessage[];
  chatSessions: ChatSession[];
  activeSessionId: string | null;
  isThinking: boolean;
  thinkingModel?: string;
  inputMode: 'chat' | 'plan';
  selectedModel?: string;
  resolvedModel?: string;
  isProcessing: boolean;
  onSendCommand: (message: string, attachments?: Array<{ url: string; name: string; mime: string }>) => void | Promise<void>;
  onStop?: () => void;
  onModeChange: (mode: 'chat' | 'plan') => void;
  onSessionSwitch: (sessionId: string) => void;
  onNewSession: () => void;
  onAction: (name: string, payload?: Record<string, any>) => void;
  // Tasks props
  plans: PlanData[];
}

const windowConfig: Record<WindowId, { title: string; icon: string; width: number; height: number }> = {
  chat: { title: 'Chat', icon: '💬', width: 720, height: 480 },
  tasks: { title: 'Tasks', icon: '📋', width: 600, height: 420 },
  agents: { title: 'Agents', icon: '🤖', width: 500, height: 380 },
  history: { title: 'History', icon: '📜', width: 500, height: 380 },
  schedule: { title: 'Schedule', icon: '⏰', width: 500, height: 380 },
  settings: { title: 'Settings', icon: '⚙️', width: 460, height: 340 },
};

const DesktopInner: React.FC<RetroDesktopProps> = (props) => {
  const { windows, activeWindowId, openWindow, closeWindow, focusWindow, minimizeWindow, moveWindow, resizeWindow } = useWindowManager();
  const [startMenuOpen, setStartMenuOpen] = useState(false);

  const handleOpenWindow = useCallback((id: WindowId) => {
    const cfg = windowConfig[id];
    openWindow(id, cfg.title, cfg.icon, cfg.width, cfg.height);
  }, [openWindow]);

  const renderWindowContent = (id: string) => {
    switch (id as WindowId) {
      case 'chat':
        return (
          <ChatWindow
            messages={props.chatMessages}
            sessions={props.chatSessions}
            activeSessionId={props.activeSessionId}
            isThinking={props.isThinking}
            thinkingModel={props.thinkingModel}
            inputMode={props.inputMode}
            selectedModel={props.selectedModel}
            resolvedModel={props.resolvedModel}
            onSend={props.onSendCommand}
            onStop={props.onStop}
            onModeChange={props.onModeChange}
            onSessionSwitch={props.onSessionSwitch}
            onNewSession={props.onNewSession}
            onAction={props.onAction}
            onViewTasks={() => handleOpenWindow('tasks')}
            isProcessing={props.isProcessing}
          />
        );
      case 'tasks':
        return <TasksWindow plans={props.plans} onAction={props.onAction} />;
      case 'agents':
        return <div className="p-4 text-ink-3 text-[12px]">Agents window — coming soon</div>;
      case 'history':
        return <div className="p-4 text-ink-3 text-[12px]">History window — coming soon</div>;
      case 'schedule':
        return <div className="p-4 text-ink-3 text-[12px]">Schedule window — coming soon</div>;
      case 'settings':
        return <div className="p-4 text-ink-3 text-[12px]">Settings window — coming soon</div>;
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
      />

      {/* Taskbar */}
      <Taskbar
        startMenuOpen={startMenuOpen}
        onToggleStartMenu={() => setStartMenuOpen(prev => !prev)}
        onOpenWindow={handleOpenWindow}
      />
    </div>
  );
};

export const RetroDesktop: React.FC<RetroDesktopProps> = (props) => (
  <WindowManagerProvider>
    <DesktopInner {...props} />
  </WindowManagerProvider>
);
