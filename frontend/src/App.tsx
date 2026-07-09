import { useEffect, useCallback, useState, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { PlatformProvider, usePlatform } from './context/PlatformContext';
import { MainLayout } from './components/MainLayout';
import type { ChatMessage, ActivityEntry, PlanAgent } from './components/ChatPanel';
import type { ChatSession } from './components/ChatSidebar';
import type { ChatReplyEnvelope, ChatReplyPayload, ChatReplyPlan } from './schemas/messages';
import type { Agent, Plan } from './types/platform';

const planAgentsToAgents = (planAgents: PlanAgent[]): Agent[] =>
  planAgents.map((pa, idx) => ({
    id: pa.is_existing ? pa.name.toLowerCase().replace(/\s+/g, '-') : `plan-${idx}`,
    name: pa.name,
    role: pa.role,
    goal: pa.goal || '',
    tools: pa.tools || [],
    depends_on: pa.depends_on || [],
    status: 'Idle',
  }));

const BACKEND_URL = 'http://localhost:8000';
const SOCKET_PATH = '/ws/socket.io';

const generateUUIDv4 = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

const parseStateMessage = (message: any) => {
  const text = message?.output || message?.content || '';
  if (!text) return null;
  try {
    const parsed = JSON.parse(text);
    if (parsed.type === 'platform_state') {
      return parsed.payload;
    }
  } catch {
    return null;
  }
  return null;
};

const parseChatReply = (message: any): Omit<ChatMessage, 'id' | 'timestamp'> | null => {
  const text = message?.output || message?.content || '';
  if (!text) return null;
  try {
    const parsed: ChatReplyEnvelope = JSON.parse(text);
    if (parsed.type === 'chat_reply') {
      const p = parsed.payload as ChatReplyPayload;
      const msgType = p.messageType;

      if (msgType === 'plan') {
        const planP = p as ChatReplyPlan;
        return {
          role: 'assistant',
          content: '',
          messageType: 'plan',
          planAgents: planP.planAgents || [],
          planTaskDescription: planP.planTaskDescription || '',
          planType: planP.planType || 'new',
          planStatus: 'pending',
          imageModel: planP.imageModel || '',
          videoModel: planP.videoModel || '',
          searchModel: planP.searchModel || '',
          ttsModel: planP.ttsModel || '',
          sttModel: planP.sttModel || '',
          visionModel: planP.visionModel || '',
          hasImageTool: planP.hasImageTool || false,
          hasVideoTool: planP.hasVideoTool || false,
          hasSearchTool: planP.hasSearchTool || false,
          hasTtsTool: planP.hasTtsTool || false,
          hasSttTool: planP.hasSttTool || false,
          hasVisionTool: planP.hasVisionTool || false,
        };
      }

      if (msgType === 'progress') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'progress',
          progressId: p.progressId || '',
          progressPercent: p.progressPercent || 0,
          progressLabel: p.progressLabel || 'Processing...',
        };
      }

      if (msgType === 'agent_progress') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'agent_progress',
          agentProgressTaskId: p.taskId || '',
          agentProgressOverall: p.overallProgress || 0,
          agentProgressList: p.agents || [],
        };
      }

      if (msgType === 'result') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'result',
          resultSummary: p.resultSummary || 'Done',
          resultAgents: p.resultAgents || [],
          resultError: p.resultError || false,
        };
      }

      if (msgType === 'image_approval') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'image_approval',
          imagePrompt: p.imagePrompt || '',
          approvalId: p.approvalId || '',
          agentName: p.agentName || '',
          mediaType: (p as any).mediaType || 'image',
          duration: (p as any).duration || 0,
          model: (p as any).model || '',
          approvalStatus: (p as any).approvalStatus || 'pending',
          imageError: (p as any).imageError || '',
        };
      }

      if (msgType === 'image_result') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'image_result',
          imageUrl: p.imageUrl || '',
          imagePrompt: p.imagePrompt || '',
          approvalId: p.approvalId || '',
          mediaType: (p as any).mediaType || 'image',
          agentName: (p as any).agentName || '',
        };
      }

      if (msgType === 'model_catalog') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'model_catalog',
          modelCatalogRecommended: (p as any).recommended || {},
          modelCatalogSearchResults: (p as any).searchResults || [],
          modelCatalogSelected: (p as any).selectedModel || '',
          modelCatalogResolved: (p as any).resolvedModel || '',
          catalogType: (p as any).catalogType || 'text',
        };
      }

      if (msgType === 'thinking') {
        return {
          role: 'assistant',
          content: (p as any).chunk || '',
          messageType: 'thinking',
        };
      }

      if (msgType === 'thinking_done') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'thinking_done',
        };
      }

      if (msgType === 'plan_validation_error') {
        return {
          role: 'assistant',
          content: (p as any).message || '',
          messageType: 'plan_validation_error',
        };
      }

      if (msgType === 'audio_result') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'audio_result',
          audioUrl: (p as any).audioUrl || '',
          audioPrompt: (p as any).audioPrompt || '',
          voice: (p as any).voice || '',
          agentName: (p as any).agentName || '',
          model: (p as any).model || '',
        };
      }

      if (msgType === 'transcription_result') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'transcription_result',
          transcriptionText: (p as any).transcriptionText || '',
          audioUrl: (p as any).audioUrl || '',
          agentName: (p as any).agentName || '',
          model: (p as any).model || '',
        };
      }

      if (msgType === 'video_result') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'video_result',
          videoUrl: (p as any).videoUrl || '',
          videoPrompt: (p as any).videoPrompt || '',
          agentName: (p as any).agentName || '',
          model: (p as any).model || '',
        };
      }

      if (msgType === 'file_result') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'file_result',
          fileUrl: (p as any).fileUrl || '',
          fileName: (p as any).fileName || '',
          fileMime: (p as any).fileMime || '',
          agentName: (p as any).agentName || '',
        };
      }

      // Default: text reply
      return {
        role: 'assistant',
        content: (p as any).message || '',
        messageType: 'text',
      };
    }
  } catch {
    return null;
  }
  return null;
};

const parseChatSessionMessage = (message: any): { sessions: ChatSession[]; currentSessionId: string } | { messages: ChatMessage[]; canvasState: any } | null => {
  const text = message?.output || message?.content || '';
  if (!text) return null;
  try {
    const parsed = JSON.parse(text);
    if (parsed.type === 'chat_reply') {
      const p = parsed.payload || {};
      const msgType = p.messageType || 'text';

      if (msgType === 'chat_sessions') {
        return { sessions: p.sessions || [], currentSessionId: p.currentSessionId || '' };
      }

      if (msgType === 'chat_history') {
        const msgs = p.messages || [];
        const messages = msgs.map((m: any) => ({
          id: generateUUIDv4(),
          timestamp: Date.now(),
          role: m.role || 'assistant',
          content: m.content || '',
          messageType: m.messageType || 'text',
          planAgents: m.planAgents,
          planTaskDescription: m.planTaskDescription,
          planType: m.planType,
          planStatus: m.planStatus || 'pending',
          progressId: m.progressId,
          progressPercent: m.progressPercent,
          progressLabel: m.progressLabel,
          resultAgents: m.resultAgents,
          resultSummary: m.resultSummary,
          resultError: m.resultError,
          imagePrompt: m.imagePrompt,
          imageUrl: m.imageUrl,
          approvalId: m.approvalId,
          agentName: m.agentName,
          approvalStatus: m.approvalStatus || 'pending',
          imageError: m.imageError,
          agentProgressTaskId: m.taskId,
          agentProgressOverall: m.overallProgress,
          agentProgressList: m.agents,
        }));
        return { messages, canvasState: p.canvasState || null };
      }
    }
  } catch {
    return null;
  }
  return null;
};

function AppContent() {
  const { updateState } = usePlatform();
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [resolvedModel, setResolvedModel] = useState<string>('');
  const [thinkingText, setThinkingText] = useState<string>('');
  const [inputMode, setInputMode] = useState<'chat' | 'plan'>('plan');
  const [canvasStateFromBackend, setCanvasStateFromBackend] = useState<any>(null);
  const socketRef = useRef<Socket | null>(null);
  const prevNotificationsRef = useRef<string[]>([]);

  const addChatMessage = useCallback((msg: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    setChatMessages((prev) => {
      // Update existing progress message by progressId instead of appending
      if (msg.messageType === 'progress' && msg.progressId) {
        const existingIdx = prev.findIndex(
          (m) => m.messageType === 'progress' && m.progressId === msg.progressId
        );
        if (existingIdx >= 0) {
          const updated = [...prev];
          updated[existingIdx] = { ...updated[existingIdx], ...msg, id: updated[existingIdx].id, timestamp: updated[existingIdx].timestamp };
          return updated;
        }
      }
      // Update existing agent_progress message by taskId instead of appending
      if (msg.messageType === 'agent_progress' && msg.agentProgressTaskId) {
        const existingIdx = prev.findIndex(
          (m) => m.messageType === 'agent_progress' && m.agentProgressTaskId === msg.agentProgressTaskId
        );
        if (existingIdx >= 0) {
          const updated = [...prev];
          updated[existingIdx] = { ...updated[existingIdx], ...msg, id: updated[existingIdx].id, timestamp: updated[existingIdx].timestamp };
          return updated;
        }
      }
      return [...prev, { ...msg, id: generateUUIDv4(), timestamp: Date.now() }];
    });
  }, []);

  const addActivity = useCallback((text: string) => {
    setActivityLog((prev) => {
      const updated = prev.map((entry) => ({ ...entry, status: 'completed' as const }));
      return [
        ...updated,
        { id: generateUUIDv4(), text, timestamp: Date.now(), status: 'current' as const },
      ];
    });
  }, []);

  const clearActivity = useCallback(() => {
    setActivityLog([]);
  }, []);

  useEffect(() => {
    const sessionId = generateUUIDv4();
    const socket = io(BACKEND_URL, {
      path: SOCKET_PATH,
      transports: ['polling', 'websocket'],
      withCredentials: false,
      timeout: 60000,
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      auth: {
        clientType: 'webapp',
        sessionId,
        threadId: '',
        userEnv: JSON.stringify({}),
        chatProfile: '',
      },
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('Socket connected:', socket.id);
      setConnectionStatus('connected');
      socket.emit('connection_successful');
    });

    socket.on('disconnect', (reason) => {
      console.log('Socket disconnected:', reason);
      setConnectionStatus('disconnected');
    });

    socket.on('reconnect', (attempt) => {
      console.log('Socket reconnected after', attempt, 'attempts');
      setConnectionStatus('connected');
    });

    socket.on('connect_error', (error) => {
      console.error('Socket connect error:', error);
      setConnectionStatus('disconnected');
    });

    const handleStateMessage = (message: any) => {
      // Check for chat session list or history first
      const sessionData = parseChatSessionMessage(message);
      if (sessionData) {
        if ('messages' in sessionData) {
          // chat_history — replace all messages + load canvas state
          setChatMessages(sessionData.messages);
          setCanvasStateFromBackend(sessionData.canvasState);
          clearActivity();
        } else if ('sessions' in sessionData) {
          // chat_sessions — update session list
          setChatSessions(sessionData.sessions);
          setActiveSessionId(sessionData.currentSessionId);
        }
        return;
      }

      // Check for chat reply
      const reply = parseChatReply(message);
      if (reply) {
        // Handle thinking chunks as streaming (not regular chat messages)
        if (reply.messageType === 'thinking') {
          setThinkingText(prev => (prev || '') + (reply.content || ''));
          setIsProcessing(true);
          return;
        }
        if (reply.messageType === 'thinking_done') {
          setThinkingText('');
          return;
        }

        addChatMessage(reply);
        clearActivity();

        // Set isProcessing based on message type
        if (reply.messageType === 'agent_progress' || reply.messageType === 'progress') {
          setIsProcessing(true);
        } else {
          setIsProcessing(false);
        }

        // Handle plan validation error — reset plan card to pending so user can edit
        if (reply.messageType === 'plan_validation_error') {
          setChatMessages((prev) =>
            prev.map((m) =>
              m.messageType === 'plan' && m.planStatus === 'approved'
                ? { ...m, planStatus: 'pending' }
                : m
            )
          );
          return;
        }

        // Sync plan to PlatformContext so canvas can auto-arrange
        if (reply.messageType === 'plan' && reply.planAgents) {
          const plan: Plan = {
            agents: planAgentsToAgents(reply.planAgents),
            task_description: reply.planTaskDescription || '',
            plan_type: reply.planType || 'new',
          };
          updateState({ current_plan: plan });
        }

        // Update selected model from catalog response
        if (reply.messageType === 'model_catalog') {
          if (reply.modelCatalogSelected) {
            setSelectedModel(reply.modelCatalogSelected);
          }
          if (reply.modelCatalogResolved) {
            setResolvedModel(reply.modelCatalogResolved);
          }
        }

        return;
      }

      const payload = parseStateMessage(message);
      if (payload) {
        if (payload.tasks) {
          payload.tasks = payload.tasks.map((t: any) => ({
            ...t,
            imageUrl: t.imageUrl || t.image_url,
            imagePrompt: t.imagePrompt || t.image_prompt,
            images: (t.images || []).map((img: any) => ({
              url: img.url || '',
              prompt: img.prompt || '',
              mediaType: img.media_type || img.mediaType || 'image',
            })),
          }));
        }
        updateState(payload);

        // Detect new notifications and show as activity
        const newNotifications = payload.notifications || [];
        const prevNotifications = prevNotificationsRef.current;
        const added = newNotifications.filter((n: string) => !prevNotifications.includes(n));
        for (const note of added) {
          addActivity(note);
        }
        prevNotificationsRef.current = [...newNotifications];

        // Only clear activity + isProcessing when no running tasks AND no notifications
        const payloadTasks = payload.tasks || [];
        const hasRunning = payloadTasks.some((t: any) => t.status === 'running');
        if (!hasRunning && newNotifications.length === 0) {
          clearActivity();
          setIsProcessing(false);
        }
      }
    };

    socket.on('new_message', handleStateMessage);
    socket.on('update_message', handleStateMessage);

    return () => {
      socket.disconnect();
    };
  }, [updateState]);

  const sendMessage = useCallback((output: string) => {
    const socket = socketRef.current;
    if (!socket || !socket.connected) {
      console.error('Socket not connected');
      return;
    }
    const message = {
      id: generateUUIDv4(),
      name: 'User',
      type: 'user_message',
      output,
      createdAt: new Date().toISOString(),
    };
    socket.emit('client_message', { message, fileReferences: [] });
  }, []);

  const handleSendCommand = useCallback(
    async (message: string, attachment?: { url: string; name: string; mime: string }) => {
      let attachmentUrl = attachment?.url;

      if (attachment && attachmentUrl) {
        try {
          const res = await fetch(`${BACKEND_URL}/api/upload`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              file_data: attachment.url,
              file_name: attachment.name,
              file_mime: attachment.mime,
            }),
          });
          const data = await res.json();
          if (data.url) {
            attachmentUrl = `${BACKEND_URL}${data.url}`;
          } else {
            console.error('Upload failed:', data.error);
          }
        } catch (e) {
          console.error('Upload error:', e);
        }
      }

      const messageToSend = attachmentUrl
        ? `${message}\n\n[ATTACHMENT|${attachmentUrl}|${attachment.name}|${attachment.mime}]`
        : message;
      const prefixed = `__mode:${inputMode}__\n${messageToSend}`;
      addChatMessage({
        role: 'user',
        content: message,
        attachmentUrl: attachmentUrl || attachment?.url,
        attachmentName: attachment?.name,
        attachmentMime: attachment?.mime,
      });
      clearActivity();
      addActivity('Sending message...');
      setIsProcessing(true);
      sendMessage(prefixed);
    },
    [sendMessage, addChatMessage, addActivity, clearActivity, updateState, inputMode]
  );

  const handleAction = useCallback(
    (name: string, payload?: Record<string, any>) => {
      // Optimistic update for plan actions
      if (name === 'accept_plan') {
        setChatMessages((prev) =>
          prev.map((m) =>
            m.messageType === 'plan' && m.planStatus === 'pending'
              ? { ...m, planStatus: 'approved' }
              : m
          )
        );
        setIsProcessing(true);
        addActivity('Agents running...');
        // Keep current_plan — StoryboardArea reads depends_on from it
      } else if (name === 'reject_plan') {
        setChatMessages((prev) =>
          prev
            .filter(m => m.messageType !== 'progress' && m.messageType !== 'agent_progress' && m.messageType !== 'result')
            .map(m =>
              m.messageType === 'plan' && m.planStatus === 'pending'
                ? { ...m, planStatus: 'rejected' }
                : m
            )
        );
        setActivityLog([]);
        setThinkingText('');
        setIsProcessing(false);
        updateState({ current_plan: null });
      } else if (name === 'approve_image') {
        const approvalId = payload?.approval_id;
        setChatMessages((prev) =>
          prev.map((m) =>
            m.messageType === 'image_approval' && m.approvalId === approvalId
              ? { ...m, approvalStatus: 'approved' }
              : m
          )
        );
        setIsProcessing(true);
        addActivity('Generating image...');
      } else if (name === 'reject_image') {
        const approvalId = payload?.approval_id;
        setChatMessages((prev) =>
          prev.map((m) =>
            m.messageType === 'image_approval' && m.approvalId === approvalId
              ? { ...m, approvalStatus: 'rejected' }
              : m
          )
        );
      } else if (name === 'retry_image') {
        const approvalId = payload?.approval_id;
        setChatMessages((prev) =>
          prev.map((m) =>
            m.messageType === 'image_approval' && m.approvalId === approvalId
              ? { ...m, approvalStatus: 'pending', imageError: '' }
              : m
          )
        );
        setIsProcessing(true);
        addActivity('Retrying image generation...');
      } else if (name === 'new_chat') {
        setChatMessages([]);
        updateState({ tasks: [], current_plan: null });
      } else if (name === 'delete_chat') {
        updateState({ tasks: [], current_plan: null });
      } else if (name === 'set_selected_model') {
        setSelectedModel(payload?.model_id || '');
      } else if (name === 'change_media_model') {
        const mediaType = payload?.media_type as 'imageModel' | 'videoModel' | 'searchModel' | 'ttsModel' | 'sttModel' | 'visionModel';
        const modelId = payload?.model_id as string;
        if (mediaType && modelId !== undefined) {
          setChatMessages((prev) =>
            prev.map((m) =>
              m.messageType === 'plan' && m.planStatus === 'pending'
                ? { ...m, [mediaType]: modelId }
                : m
            )
          );
        }
      } else if (name === 'change_agent_model') {
        const agentName = payload?.agent_name as string;
        const modelId = payload?.model_id as string;
        if (agentName && modelId) {
          setChatMessages((prev) =>
            prev.map((m) =>
              m.messageType === 'plan' && m.planStatus === 'pending' && m.planAgents
                ? {
                    ...m,
                    planAgents: m.planAgents.map((pa) =>
                      pa.name === agentName ? { ...pa, model: modelId } : pa
                    ),
                  }
                : m
            )
          );
        }
      }
      sendMessage(JSON.stringify({ type: 'action', name, payload: payload || {} }));
    },
    [sendMessage, updateState]
  );

  const handleStop = useCallback(() => {
    sendMessage(JSON.stringify({ type: 'action', name: 'stop_generation', payload: {} }));
    setIsProcessing(false);
    addActivity('Stopped');
  }, [sendMessage, addActivity]);

  return (
    <MainLayout
      onSendCommand={handleSendCommand}
      onStop={handleStop}
      onAction={handleAction}
      connectionStatus={connectionStatus}
      chatMessages={chatMessages}
      activityLog={activityLog}
      isProcessing={isProcessing}
      chatSessions={chatSessions}
      activeSessionId={activeSessionId}
      canvasStateFromBackend={canvasStateFromBackend}
      selectedModel={selectedModel}
      resolvedModel={resolvedModel}
      thinkingText={thinkingText}
      inputMode={inputMode}
      onModeChange={setInputMode}
    />
  );
}

function App() {
  return (
    <PlatformProvider>
      <AppContent />
    </PlatformProvider>
  );
}

export default App;
