import { useState, useRef, useEffect } from 'react';
import type { ChatMessage } from '../chatTypes';
import type { ChatSession } from '../ChatSidebar';
import { FeedUserMessage, FeedAgentMessage, FeedThinking, FeedProgress, ChatPlanCard, FeedResultBubbles } from './ChatFeed';

interface ChatWindowProps {
  messages: ChatMessage[];
  sessions: ChatSession[];
  activeSessionId: string | null;
  isThinking: boolean;
  thinkingModel?: string;
  inputMode: 'chat' | 'plan';
  selectedModel?: string;
  resolvedModel?: string;
  onSend: (message: string, attachments?: Array<{ url: string; name: string; mime: string }>) => void;
  onStop?: () => void;
  onModeChange: (mode: 'chat' | 'plan') => void;
  onSessionSwitch: (sessionId: string) => void;
  onNewSession: () => void;
  onAction: (name: string, payload?: Record<string, any>) => void;
  onViewTasks: () => void;
  isProcessing: boolean;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages, sessions, activeSessionId, isThinking, thinkingModel,
  inputMode, selectedModel, resolvedModel,
  onSend, onStop, onModeChange, onSessionSwitch, onNewSession, onAction,
  onViewTasks, isProcessing,
}) => {
  const [input, setInput] = useState('');
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages, isThinking]);

  const handleSend = () => {
    if (!input.trim() || isProcessing) return;
    onSend(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const renderMessage = (msg: ChatMessage) => {
    switch (msg.messageType) {
      case 'text':
        return msg.role === 'user'
          ? <FeedUserMessage key={msg.id} msg={msg} />
          : <FeedAgentMessage key={msg.id} avatar="🧠" name="Manager">{msg.content}</FeedAgentMessage>;

      case 'thinking':
        return <FeedThinking key={msg.id} model={msg.model} />;

      case 'plan':
        return (
          <ChatPlanCard
            key={msg.id}
            planAgents={msg.planAgents || []}
            taskDescription={msg.planTaskDescription || ''}
            planType={msg.planType}
            onApprove={() => onAction('plan_approve')}
            onReject={() => onAction('plan_reject')}
          />
        );

      case 'progress':
      case 'agent_progress':
        return (
          <FeedProgress
            key={msg.id}
            label={msg.progressLabel || 'กำลังทำงาน...'}
            onViewProgress={onViewTasks}
          />
        );

      case 'result':
        return (
          <FeedResultBubbles
            key={msg.id}
            agents={msg.resultAgents || []}
            summary={msg.resultSummary}
            isError={msg.resultError}
          />
        );

      case 'image_approval':
        return (
          <FeedAgentMessage key={msg.id} avatar="🎨" name={msg.agentName || 'Image Generator'}>
            <div className="flex flex-col gap-2">
              <span>รออนุมัติภาพ: {msg.imagePrompt}</span>
              <div className="flex gap-2">
                <button
                  className="text-[10px] px-3 py-1 border border-green bg-green text-white rounded-retro-sm font-bold hover:bg-green-light transition-colors"
                  onClick={() => onAction('image_approve', { approvalId: msg.approvalId })}
                >
                  Approve
                </button>
                <button
                  className="text-[10px] px-3 py-1 border border-red bg-paper text-red rounded-retro-sm font-bold hover:bg-red hover:text-white transition-colors"
                  onClick={() => onAction('image_reject', { approvalId: msg.approvalId })}
                >
                  Reject
                </button>
              </div>
            </div>
          </FeedAgentMessage>
        );

      case 'image_result':
        return (
          <FeedAgentMessage key={msg.id} avatar="🎨" name={msg.agentName || 'Image Generator'}>
            <img src={msg.imageUrl} alt={msg.imagePrompt} className="max-w-full rounded-retro mt-1 block" />
          </FeedAgentMessage>
        );

      default:
        return null;
    }
  };

  return (
    <div className="flex h-full">
      {/* Session sidebar */}
      <div className="w-44 flex flex-col border-r border-line bg-cream flex-shrink-0">
        <div className="px-3 py-2 text-[11px] font-bold text-ink-2 border-b border-line">Sessions</div>
        <button
          className="mx-2 my-1.5 px-2 py-1.5 text-[11px] text-ink-2 border border-dashed border-line-2 rounded-retro-sm hover:bg-cream-2 transition-colors text-left"
          onClick={onNewSession}
        >
          + New Session
        </button>
        <div className="flex-1 overflow-y-auto px-1.5 flex flex-col gap-0.5">
          {sessions.map(s => (
            <button
              key={s.id}
              className={`px-2 py-1.5 rounded-retro-sm text-left transition-colors ${
                activeSessionId === s.id
                  ? 'bg-paper border border-line text-ink font-semibold'
                  : 'text-ink-2 hover:bg-cream-2'
              }`}
              onClick={() => onSessionSwitch(s.id)}
            >
              <div className="text-[11px] truncate">{s.title}</div>
              <div className="text-[9px] text-ink-3 truncate">{s.updated_at}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {/* Feed */}
        <div
          ref={feedRef}
          className="flex-1 overflow-y-auto min-h-0 px-4 py-3 flex flex-col gap-2.5"
        >
          {messages.length === 0 && !isThinking && (
            <div className="flex items-center justify-center h-full text-ink-3 text-[12px]">
              พิมพ์คำสั่งถึงทีม...
            </div>
          )}
          {messages.map(renderMessage)}
          {isThinking && <FeedThinking model={thinkingModel} />}
        </div>

        {/* Input */}
        <div className="border-t border-line bg-cream px-3 py-2 flex-shrink-0">
          <div className="flex items-center justify-between mb-1.5">
            <div className="text-[10px] text-ink-3 font-mono">
              ⚡ {selectedModel || 'auto-router'}
              {resolvedModel && resolvedModel !== selectedModel && (
                <span className="text-green"> → {resolvedModel}</span>
              )}
            </div>
            <div className="flex gap-1">
              <button
                className={`px-2.5 py-0.5 text-[10px] rounded-retro-sm font-semibold transition-colors ${
                  inputMode === 'chat' ? 'bg-ink text-paper' : 'bg-paper text-ink-2 border border-line hover:bg-cream-2'
                }`}
                onClick={() => onModeChange('chat')}
              >
                💬 Chat
              </button>
              <button
                className={`px-2.5 py-0.5 text-[10px] rounded-retro-sm font-semibold transition-colors ${
                  inputMode === 'plan' ? 'bg-ink text-paper' : 'bg-paper text-ink-2 border border-line hover:bg-cream-2'
                }`}
                onClick={() => onModeChange('plan')}
              >
                ✨ Plan
              </button>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button className="w-7 h-7 border border-line-2 bg-paper rounded-retro-sm text-sm text-ink-2 hover:bg-cream-2 transition-colors flex items-center justify-center">+</button>
            <textarea
              className="flex-1 border border-line-2 bg-paper rounded-retro-sm px-2.5 py-1.5 text-[12px] text-ink resize-none outline-none focus:border-orange"
              rows={1}
              placeholder="พิมพ์คำสั่งถึงทีม..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            {isProcessing && onStop ? (
              <button
                className="px-3 py-1.5 border border-red bg-red text-white rounded-retro-sm text-[12px] font-bold hover:bg-red-light transition-colors"
                onClick={onStop}
              >
                ⏹
              </button>
            ) : (
              <button
                className="px-3 py-1.5 border border-orange bg-orange text-white rounded-retro-sm text-[12px] font-bold hover:bg-orange-light transition-colors"
                onClick={handleSend}
                disabled={!input.trim()}
              >
                ➤
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
