import { useEffect, useCallback, useState, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { PlatformProvider, usePlatform } from './context/PlatformContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginScreen } from './components/LoginScreen';
import { TeamListPage } from './components/TeamListPage';
import { TeamCreateModal } from './components/TeamCreateModal';
import { AICreateTeamModal } from './components/AICreateTeamModal';
import { RetroDesktop } from './components/retro/RetroDesktop';
import type { ChatMessage, ActivityEntry, PlanAgent, HistoryTaskLog, NotificationItem } from './components/chatTypes';
import type { ChatSession } from './components/ChatSidebar';
import type { ChatReplyEnvelope, ChatReplyPayload, ChatReplyPlan, ChatReplyAgentReview } from './schemas/messages';
import type { Agent, Plan } from './types/platform';
import type { Team } from './types/team';

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

const BACKEND_URL = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000';
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
          teamName: (planP as any).teamName || '',
          teamDescription: (planP as any).teamDescription || '',
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
          hasVisionInput: planP.hasVisionInput || false,
          managerModel: planP.managerModel || '',
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

      // Tuning proposal
      if (msgType === 'tuning_proposal') {
        return {
          role: 'assistant',
          content: '',
          messageType: 'tuning_proposal',
          tuningProposals: (p as any).proposals || [],
          tuningStatus: (p as any).tuningStatus,
        };
      }

      // Agent review card
      if (msgType === 'agent_review') {
        const rp = p as ChatReplyAgentReview;
        // Update existing review message if same reviewId, else add new
        return {
          role: 'assistant',
          content: rp.output || '',
          messageType: 'agent_review',
          reviewId: rp.reviewId || '',
          reviewTaskId: rp.taskId || '',
          agentName: rp.agentName || '',
          agentRole: rp.agentRole || '',
          reviewStatus: rp.reviewStatus || 'pending',
        };
      }

      // Default: text reply
      return {
        role: 'assistant',
        content: (p as any).message || '',
        messageType: 'text',
        agentName: (p as any).agentName || '',
      };
    }
  } catch {
    return null;
  }
  return null;
};

const parseTeamList = (message: any): Team[] | null => {
  const text = message?.output || message?.content || '';
  if (!text) return null;
  try {
    const parsed = JSON.parse(text);
    if (parsed.type === 'chat_reply' && parsed.payload?.messageType === 'team_list') {
      return (parsed.payload.teams || []) as Team[];
    }
  } catch {
    return null;
  }
  return null;
};

const parseChatSessionMessage = (message: any): { sessions: ChatSession[]; currentSessionId: string } | { messages: ChatMessage[]; canvasState: any; selectedModel?: string } | { notifications: NotificationItem[] } | null => {
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
          teamName: m.teamName,
          teamDescription: m.teamDescription,
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
          mediaType: m.mediaType,
          duration: m.duration,
          model: m.model,
          videoUrl: m.videoUrl,
          videoPrompt: m.videoPrompt,
          audioUrl: m.audioUrl,
          voice: m.voice,
          transcriptionText: m.transcriptionText,
          fileUrl: m.fileUrl,
          fileName: m.fileName,
          fileMime: m.fileMime,
          agentProgressTaskId: m.taskId,
          agentProgressOverall: m.overallProgress,
          agentProgressList: m.agents,
          imageModel: m.imageModel,
          videoModel: m.videoModel,
          searchModel: m.searchModel,
          ttsModel: m.ttsModel,
          sttModel: m.sttModel,
          visionModel: m.visionModel,
          managerModel: m.managerModel,
          estimatedCost: m.estimatedCost,
          hasImageTool: m.hasImageTool,
          hasVideoTool: m.hasVideoTool,
          hasSearchTool: m.hasSearchTool,
          hasTtsTool: m.hasTtsTool,
          hasSttTool: m.hasSttTool,
          hasVisionTool: m.hasVisionTool,
          hasVisionInput: m.hasVisionInput,
          tuningProposals: m.proposals,
          tuningStatus: m.tuningStatus,
          attachmentUrl: m.attachmentUrl,
          attachmentName: m.attachmentName,
          attachmentMime: m.attachmentMime,
          attachments: m.attachments || (m.attachmentUrl ? [{ url: m.attachmentUrl, name: m.attachmentName || '', mime: m.attachmentMime || '' }] : undefined),
        }));

        // Filter out transient progress messages — they're UI state, not conversation content.
        // Without this, stale "ดำเนินการ 100%" cards reappear after refresh and block new progress cards
        // (new task has different progressId so update-in-place won't find the old one).
        const filtered = messages.filter((m: ChatMessage) =>
          m.messageType !== 'progress' && m.messageType !== 'agent_progress'
        );

        // Merge image_result into image_approval card — same logic as live merge (App.tsx:708-717).
        // Without this, refreshed image_approval cards show "กรุณารอสักครู่..." forever because
        // backend persists approvalStatus="approved" (not "generated") and the merge only happens
        // in-memory on live image_result arrivals, not on history restore.
        for (const m of filtered) {
          if (m.messageType === 'image_result' && m.approvalId) {
            const approvalIdx = filtered.findIndex(
              (am) => am.messageType === 'image_approval' && am.approvalId === m.approvalId
            );
            if (approvalIdx >= 0) {
              filtered[approvalIdx] = {
                ...filtered[approvalIdx],
                imageUrl: m.imageUrl,
                approvalStatus: 'generated',
                mediaType: m.mediaType,
                model: m.model,
              };
            }
          }
        }

        return { messages: filtered, canvasState: p.canvasState || null, selectedModel: p.selectedModel || '' };
      }

      if (msgType === 'history_data') {
        return { historyLogs: p.historyLogs || [] } as any;
      }

      if (msgType === 'notifications') {
        const notifs = (p.notifications || []).map((n: any) => ({
          id: n.id || generateUUIDv4(),
          sessionId: n.sessionId || '',
          sessionTitle: n.sessionTitle || '',
          timestamp: typeof n.timestamp === 'string' ? new Date(n.timestamp).getTime() : (n.timestamp || Date.now()),
          messageType: n.messageType || 'plan',
          planStatus: n.planStatus,
          approvalStatus: n.approvalStatus,
          reviewStatus: n.reviewStatus,
          tuningStatus: n.tuningStatus,
          planTaskDescription: n.planTaskDescription,
          planAgents: n.planAgents,
          planType: n.planType,
          imagePrompt: n.imagePrompt,
          agentName: n.agentName,
          agentRole: n.agentRole,
          reviewId: n.reviewId,
          approvalId: n.approvalId,
          tuningProposals: n.tuningProposals,
          imageError: n.imageError,
          content: n.content,
        })) as NotificationItem[];
        return { notifications: notifs };
      }
    }
  } catch {
    return null;
  }
  return null;
};

function AppContent() {
  const { updateState, agents, tasks, credits, system_status, available_tools, current_plan } = usePlatform();
  const { isAuthenticated, token, isLoading: authLoading } = useAuth();
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [historyLogs, setHistoryLogs] = useState<HistoryTaskLog[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [resolvedModel, setResolvedModel] = useState<string>('');
  const [uploadLimitMb, setUploadLimitMb] = useState<number>(500); // Default until backend sends actual value
  const [thinkingText, setThinkingText] = useState<string>('');
  const [thinkingDuration, setThinkingDuration] = useState<number | null>(null);
  const [isThinking, setIsThinking] = useState(false);
  const isThinkingRef = useRef(false);
  const thinkingStartRef = useRef<number | null>(null);
  const [inputMode, setInputMode] = useState<'chat' | 'plan'>('plan');
  // Temporarily disable chat mode: always fall back to plan
  const handleModeChange = useCallback((mode: 'chat' | 'plan') => {
    if (mode === 'chat') return;
    setInputMode('plan');
  }, []);
  useEffect(() => {
    if (inputMode === 'chat') setInputMode('plan');
  }, [inputMode]);
  const [canvasStateFromBackend, setCanvasStateFromBackend] = useState<any>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAICreateModal, setShowAICreateModal] = useState(false);
  const [aiChatMessages, setAiChatMessages] = useState<ChatMessage[]>([]);
  const [aiIsThinking, setAiIsThinking] = useState(false);
  const [aiThinkingText, setAiThinkingText] = useState<string>('');
  const aiModalOpenRef = useRef(false);
  const [modelCatalogData, setModelCatalogData] = useState<{ recommended: Record<string, any[]>; searchResults: any[]; mediaCatalog: Record<string, any[]>; mediaSearchResults: any[] }>({ recommended: {}, searchResults: [], mediaCatalog: {}, mediaSearchResults: [] });
  const socketRef = useRef<Socket | null>(null);
  const prevNotificationsRef = useRef<string[]>([]);
  const stoppedRef = useRef(false);

  const addChatMessage = useCallback((msg: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    setChatMessages((prev) => {
      // Ignore progress messages that arrive after result —
      // orchestrator schedules final 100% progress via call_soon_threadsafe
      // which can arrive AFTER reply_result, re-adding the stuck card
      if (msg.messageType === 'progress') {
        const hasResult = prev.some(m => m.messageType === 'result');
        if (hasResult) return prev;
      }
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
      // Update existing agent_review message by reviewId instead of appending
      if (msg.messageType === 'agent_review' && msg.reviewId) {
        const existingIdx = prev.findIndex(
          (m) => m.messageType === 'agent_review' && m.reviewId === msg.reviewId
        );
        if (existingIdx >= 0) {
          const updated = [...prev];
          // If incoming output is empty, preserve existing content
          const incomingOutput = msg.content || '';
          updated[existingIdx] = {
            ...updated[existingIdx],
            ...msg,
            content: incomingOutput || updated[existingIdx].content || '',
            id: updated[existingIdx].id,
            timestamp: updated[existingIdx].timestamp,
          };
          return updated;
        }
      }
      // Update existing image_approval message by approvalId instead of appending
      // — when status changes (pending→approved/rejected/error), update the same card in-place
      if (msg.messageType === 'image_approval' && msg.approvalId) {
        const existingIdx = prev.findIndex(
          (m) => m.messageType === 'image_approval' && m.approvalId === msg.approvalId
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

  useEffect(() => {
    aiModalOpenRef.current = showAICreateModal;
  }, [showAICreateModal]);

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
    if (!isAuthenticated || !token) return;
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
        userEnv: JSON.stringify({ authToken: token }),
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
      // Socket.IO will auto-reconnect (reconnection: true is set above)
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
      // TEMP: log ALL incoming messages to find where image_result disappears
      const _text = message?.output || message?.content || '';
      console.log('[TRACE-WS] msg type=' + message?.type + ' output=' + (typeof _text === 'string' ? _text.substring(0, 120) : typeof _text));
      // Check for team list first
      const teamList = parseTeamList(message);
      if (teamList) {
        setTeams(teamList);
        return;
      }

      // Check for chat session list or history first
      const sessionData = parseChatSessionMessage(message);
      if (sessionData) {
        if ('messages' in sessionData) {
          // chat_history — replace all messages + load canvas state
          setChatMessages(sessionData.messages);
          setCanvasStateFromBackend(sessionData.canvasState);
          if (sessionData.selectedModel) {
            setSelectedModel(sessionData.selectedModel);
          }
          // Restore current_plan from last pending plan message
          const lastPlan = [...sessionData.messages].reverse().find(m => m.messageType === 'plan' && m.planStatus === 'pending');
          if (lastPlan && lastPlan.planAgents) {
            updateState({
              current_plan: {
                agents: planAgentsToAgents(lastPlan.planAgents),
                task_description: lastPlan.planTaskDescription || '',
                plan_type: lastPlan.planType || 'new',
              },
            });
          }
          clearActivity();
        } else if ('sessions' in sessionData) {
          // chat_sessions — update session list
          setChatSessions(sessionData.sessions);
          setActiveSessionId(sessionData.currentSessionId);
        } else if ('historyLogs' in (sessionData as any)) {
          // history_data — update history logs
          setHistoryLogs((sessionData as any).historyLogs);
        } else if ('notifications' in sessionData) {
          // notifications — update cross-session notification list
          setNotifications(sessionData.notifications);
        }
        return;
      }

      // Check for chat reply
      const reply = parseChatReply(message);
      if (reply) {
        if (reply.messageType === 'image_result' || reply.messageType === 'image_approval') {
          console.log('[TRACE-PARSED] messageType=' + reply.messageType + ' approvalId=' + reply.approvalId + ' imageUrl=' + (reply as any).imageUrl);
        }
        // Ignore in-flight processing messages after user clicked stop
        // But allow text, result, and tuning_proposal through so UI updates
        if (stoppedRef.current && (reply.messageType === 'progress' || reply.messageType === 'agent_progress' || reply.messageType === 'thinking' || reply.messageType === 'thinking_done')) {
          return;
        }
        // Reset stoppedRef when receiving terminal messages (text with stop confirmation, or result)
        if (stoppedRef.current && (reply.messageType === 'text' || reply.messageType === 'result')) {
          if (reply.messageType === 'text' && reply.content?.includes('หยุดการทำงาน')) {
            // Stop confirmation — keep stoppedRef true so in-flight messages stay blocked
          } else {
            stoppedRef.current = false;
          }
        }
        // Intercept template/scheduled data messages
        if (reply.messageType === 'text' && reply.content) {
          try {
            const data = JSON.parse(reply.content);
            if (data.type === 'task_templates' || data.type === 'scheduled_tasks') {
              window.dispatchEvent(new CustomEvent('chat-data', { detail: data }));
              return;
            }
          } catch {
            // Not JSON, continue as normal text
          }
        }
        // Route to AI modal if open and message is text/thinking/plan
        if (aiModalOpenRef.current && (reply.messageType === 'text' || reply.messageType === 'thinking' || reply.messageType === 'thinking_done' || reply.messageType === 'plan')) {
          if (reply.messageType === 'thinking') {
            setAiThinkingText(prev => (prev || '') + (reply.content || ''));
            setAiIsThinking(true);
            return;
          }
          if (reply.messageType === 'thinking_done') {
            setAiIsThinking(false);
            return;
          }
          if (reply.messageType === 'plan') {
            // Send plan message directly to AI modal — no JSON string conversion
            const planAgents = reply.planAgents || [];
            setAiChatMessages(prev => [...prev, {
              id: generateUUIDv4(),
              timestamp: Date.now(),
              role: 'assistant',
              content: '',
              messageType: 'plan',
              planAgents: planAgents,
              teamName: (reply as any).teamName || '',
              teamDescription: (reply as any).teamDescription || '',
            }]);
            setAiIsThinking(false);
            setAiThinkingText('');
            return;
          }
          setAiChatMessages(prev => [...prev, { ...reply, id: generateUUIDv4(), timestamp: Date.now() }]);
          setAiThinkingText('');
          return;
        }

        // Handle thinking chunks as streaming (not regular chat messages)
        if (reply.messageType === 'thinking') {
          setThinkingDuration(null);
          setThinkingText(prev => (prev || '') + (reply.content || ''));
          setIsProcessing(true);
          setIsThinking(true);
          isThinkingRef.current = true;
          return;
        }
        if (reply.messageType === 'thinking_done') {
          if (thinkingStartRef.current !== null) {
            setThinkingDuration(Math.round((Date.now() - thinkingStartRef.current) / 1000));
            thinkingStartRef.current = null;
          }
          setIsThinking(false);
          isThinkingRef.current = false;
          return;
        }

        // image_result is merged into image_approval card below — don't add as separate message.
        // Without this skip, image_result stays as an orphan that ChatWindow renders as null (invisible).
        if (reply.messageType === 'image_result') {
          // Still persist so it survives refresh — but don't add to chatMessages
          // The merge below updates the image_approval card in-place
        } else if (reply.messageType === 'image_approval' && reply.approvalId) {
          // Update existing approval card in-place by approvalId (status change: pending→approved→generated)
          // instead of adding a duplicate card
          setChatMessages(prev => {
            let lastIdx = -1;
            for (let i = prev.length - 1; i >= 0; i--) {
              if (prev[i].messageType === 'image_approval' && prev[i].approvalId === reply.approvalId) {
                lastIdx = i;
                break;
              }
            }
            if (lastIdx >= 0) {
              const updated = [...prev];
              updated[lastIdx] = { ...updated[lastIdx], ...reply };
              return updated;
            }
            return [...prev, { ...reply, id: generateUUIDv4(), timestamp: Date.now() }];
          });
        } else {
          addChatMessage(reply);
        }
        clearActivity();

        // Merge: when image_result arrives, update the existing image_approval card
        // (by approvalId) with the imageUrl instead of creating a separate ImageResultCard.
        // This eliminates the redundant second card — the approval card shows the result inline.
        if (reply.messageType === 'image_result' && reply.approvalId) {
          setChatMessages(prev => {
            // Use findLastIndex — with duplicate approval cards (from retries),
            // the last one is the most visible (error/pending status the user clicked retry on)
            let lastIdx = -1;
            for (let i = prev.length - 1; i >= 0; i--) {
              if (prev[i].messageType === 'image_approval' && prev[i].approvalId === reply.approvalId) {
                lastIdx = i;
                break;
              }
            }
            if (lastIdx >= 0) {
              const updated = [...prev];
              updated[lastIdx] = { ...updated[lastIdx], imageUrl: reply.imageUrl, approvalStatus: 'generated' };
              return updated;
            }
            // Fallback: no matching approval card found — add as standalone message
            return [...prev, { ...reply, id: generateUUIDv4(), timestamp: Date.now() }];
          });
        }

        // Refresh credits only on terminal events — 'progress' and 'agent_progress' excluded
        // because they fire frequently during execution and cause unnecessary Taskbar re-renders/blinking
        if (reply.messageType === 'result' || reply.messageType === 'text' ||
            reply.messageType === 'plan') {
          sendAction('refresh_credits');
        }

        // Set isProcessing based on message type — only false for terminal types
        const TERMINAL_TYPES = ['result', 'text', 'plan', 'plan_validation_error', 'image_result', 'audio_result', 'video_result', 'file_result', 'transcription_result', 'tuning_proposal'];
        if (reply.messageType === 'agent_progress' || reply.messageType === 'progress' || reply.messageType === 'agent_review') {
          setIsProcessing(true);
        } else if (TERMINAL_TYPES.includes(reply.messageType)) {
          setIsProcessing(false);
          setIsThinking(false);
          if (reply.messageType === 'result') {
            updateState({ current_plan: null });
            // Remove progress card — task is complete, no need to show "ดำเนินการ X%" anymore
            setChatMessages(prev => prev.filter(m => m.messageType !== 'progress'));
          }
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
          if ((reply as any).uploadLimitMb) {
            setUploadLimitMb((reply as any).uploadLimitMb);
          }
          // Also store catalog data in separate state for persistence across chat resets
          if (reply.modelCatalogRecommended) {
            const catalogType = (reply as any).catalogType || 'text';
            if (catalogType === 'media') {
              setModelCatalogData(prev => {
                const merged = { ...prev.mediaCatalog };
                for (const [provider, models] of Object.entries(reply.modelCatalogRecommended!)) {
                  if (!merged[provider]) merged[provider] = [];
                  for (const m of models) {
                    if (!merged[provider].some((x: any) => x.id === m.id)) merged[provider].push(m);
                  }
                }
                return { ...prev, mediaCatalog: merged, mediaSearchResults: [...prev.mediaSearchResults, ...(reply.modelCatalogSearchResults || [])] };
              });
            } else {
              setModelCatalogData(prev => ({ ...prev, recommended: reply.modelCatalogRecommended!, searchResults: reply.modelCatalogSearchResults || [] }));
            }
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

        // Instead of using stale chatMessages from closure to decide whether to clear activity,
        // we'll safely use functional state update if we really need to check.
        // Or simply NOT clear activity here, because terminal messages (result/text)
        // already clear activity correctly. Only plan/image approvals need special care.
        // We remove the buggy clearActivity() call from the 15s poll here.
      }
    };

    socket.on('new_message', handleStateMessage);
    socket.on('update_message', handleStateMessage);

    // Poll credits every 15 seconds for more real-time updates
    const creditInterval = setInterval(() => {
      sendAction('refresh_credits');
    }, 15000);

    return () => {
      clearInterval(creditInterval);
      socket.disconnect();
    };
  }, [updateState, isAuthenticated, token]);

  const sendMessage = useCallback((output: string) => {
    const socket = socketRef.current;
    if (!socket || !socket.connected) {
      console.warn('Socket not connected (sendMessage)');
      return;
    }
    setThinkingText('');
    setThinkingDuration(null);
    thinkingStartRef.current = Date.now();
    setIsThinking(true);
    isThinkingRef.current = true;
    const message = {
      id: generateUUIDv4(),
      name: 'User',
      type: 'user_message',
      output,
      createdAt: new Date().toISOString(),
    };
    socket.emit('client_message', { message, fileReferences: [] });
  }, []);

  const sendAction = useCallback((name: string, payload?: Record<string, any>) => {
    const socket = socketRef.current;
    if (!socket || !socket.connected) {
      console.warn('Socket not connected (sendAction)');
      return;
    }
    const message = {
      id: generateUUIDv4(),
      name: 'User',
      type: 'user_message',
      output: JSON.stringify({ type: 'action', name, payload: payload || {} }),
      createdAt: new Date().toISOString(),
    };
    socket.emit('client_message', { message, fileReferences: [] });
  }, []);

  const sendAIModalMessage = useCallback((message: string) => {
    const socket = socketRef.current;
    if (!socket || !socket.connected) {
      console.warn('Socket not connected (sendAIModalMessage)');
      return;
    }
    const prefixed = `__mode:plan__\n${message}`;
    const msg = {
      id: generateUUIDv4(),
      name: 'User',
      type: 'user_message',
      output: prefixed,
      createdAt: new Date().toISOString(),
    };
    socket.emit('client_message', { message: msg, fileReferences: [] });
  }, []);

  const handleSendCommand = useCallback(
    async (message: string, attachments?: Array<{ url: string; name: string; mime: string }>) => {
      const uploadedAttachments: Array<{ url: string; name: string; mime: string }> = [];

      if (attachments && attachments.length > 0) {
        for (const att of attachments) {
          try {
            const res = await fetch(`${BACKEND_URL}/api/upload`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
              },
              body: JSON.stringify({
                file_data: att.url,
                file_name: att.name,
                file_mime: att.mime,
              }),
            });
            const data = await res.json();
            if (data.url) {
              uploadedAttachments.push({ url: data.url, name: att.name, mime: att.mime });
            } else {
              console.error('Upload failed:', data.error);
              uploadedAttachments.push(att);
            }
          } catch (e) {
            console.error('Upload error:', e);
            uploadedAttachments.push(att);
          }
        }
      }

      const attachmentParts = uploadedAttachments.map(
        (att) => `[ATTACHMENT|${att.url}|${att.name}|${att.mime}]`
      );
      const messageToSend = attachmentParts.length > 0
        ? `${message}\n\n${attachmentParts.join('\n')}`
        : message;
      const prefixed = `__mode:${inputMode}__\n${messageToSend}`;
      addChatMessage({
        role: 'user',
        content: message,
        attachmentUrl: uploadedAttachments[0]?.url,
        attachmentName: uploadedAttachments[0]?.name,
        attachmentMime: uploadedAttachments[0]?.mime,
        attachments: uploadedAttachments.map(a => ({ url: a.url, name: a.name, mime: a.mime })),
      });
      clearActivity();
      setIsProcessing(true);
      stoppedRef.current = false;
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
        setThinkingDuration(null);
        thinkingStartRef.current = null;
        setIsThinking(false);
        isThinkingRef.current = false;
        setIsProcessing(false);
        updateState({ current_plan: null });
      } else if (name === 'confirm_tuning') {
        setChatMessages((prev) =>
          prev.map((m) =>
            m.messageType === 'tuning_proposal'
              ? { ...m, tuningStatus: 'confirmed' as any }
              : m
          )
        );
      } else if (name === 'reject_tuning') {
        setChatMessages((prev) =>
          prev.map((m) =>
            m.messageType === 'tuning_proposal'
              ? { ...m, tuningStatus: 'rejected' as any }
              : m
          )
        );
        setIsProcessing(false);
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
        // Type-aware activity message — without this, all media types say 'Generating image...'
        const _mt = chatMessages.find(m => m.messageType === 'image_approval' && m.approvalId === approvalId)?.mediaType || 'image';
        const _activityLabels: Record<string, string> = {
          image: 'Generating image...', video: 'Generating video...',
          tts: 'Generating audio...', stt: 'Transcribing audio...',
          vision: 'Analyzing image...',
        };
        addActivity(_activityLabels[_mt] || 'Generating image...');
      } else if (name === 'reject_image') {
        const approvalId = payload?.approval_id;
        setChatMessages((prev) =>
          prev.map((m) =>
            m.messageType === 'image_approval' && m.approvalId === approvalId
              ? { ...m, approvalStatus: 'rejected' }
              : m
          )
        );
      } else if (name === 'approve_agent_result') {
        const reviewId = payload?.review_id;
        setChatMessages((prev) =>
          prev.map((m) =>
            m.messageType === 'agent_review' && m.reviewId === reviewId
              ? { ...m, reviewStatus: 'approved' }
              : m
          )
        );
        addActivity('Agent output approved — downstream agents can proceed');
      } else if (name === 'reject_agent_result') {
        const reviewId = payload?.review_id;
        setChatMessages((prev) =>
          prev.map((m) =>
            m.messageType === 'agent_review' && m.reviewId === reviewId
              ? { ...m, reviewStatus: 'rejected' }
              : m
          )
        );
        setIsProcessing(true);
        addActivity('Agent output rejected — re-running with feedback...');
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
        // Type-aware activity message for retry
        const _rmt = chatMessages.find(m => m.messageType === 'image_approval' && m.approvalId === approvalId)?.mediaType || 'image';
        const _retryLabels: Record<string, string> = {
          image: 'Retrying image generation...', video: 'Retrying video generation...',
          tts: 'Retrying audio generation...', stt: 'Retrying transcription...',
          vision: 'Retrying vision analysis...',
        };
        addActivity(_retryLabels[_rmt] || 'Retrying image generation...');
      } else if (name === 'new_chat') {
        setChatMessages([]);
        updateState({ tasks: [], current_plan: null });
      } else if (name === 'delete_chat') {
        setChatMessages([]);
        setNotifications([]);
        updateState({ current_plan: null, notifications: [] });
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
      } else if (name === 'change_manager_model') {
        const modelId = payload?.model_id as string;
        if (modelId) {
          setChatMessages((prev) =>
            prev.map((m) =>
              m.messageType === 'plan' && m.planStatus === 'pending'
                ? { ...m, managerModel: modelId }
                : m
            )
          );
        }
      } else if (name === 'config_agent') {
        const agentId = payload?.agent_id as string;
        if (agentId) {
          updateState((prev) => ({
            agents: (prev.agents || []).map(a =>
              a.id === agentId
                ? {
                    ...a,
                    name: payload.name || a.name,
                    role: payload.role || a.role,
                    goal: payload.goal ?? a.goal,
                    persona: payload.persona ?? a.persona,
                    model: payload.model ?? a.model,
                    tools: payload.tools || a.tools,
                    ...(payload.expertise ? { expertise: payload.expertise } : {}),
                    ...(payload.personality ? { personality: payload.personality } : {}),
                    ...(payload.brand_context ? { brand_context: payload.brand_context } : {}),
                  } as any
                : a
            ),
          }));
        }
      } else if (name === 'add_agent' || name === 'add_agent_form') {
        // No optimistic update — backend sends platform_state with the real agent
        // list after processing. Adding a temp agent with a fake ID here causes
        // duplicates and confusion when the real agent arrives with a different ID.
      } else if (name === 'delete_agent') {
        const agentId = payload?.agent_id as string;
        if (agentId) {
          updateState((prev) => ({ agents: (prev.agents || []).filter(a => a.id !== agentId) }));
        }
      }
      sendAction(name, payload);
    },
    [sendAction, updateState]
  );

  const handleStop = useCallback(() => {
    stoppedRef.current = true;
    sendMessage(JSON.stringify({ type: 'action', name: 'stop_generation', payload: {} }));
    setIsProcessing(false);
    setAiIsThinking(false);
    setAiThinkingText('');
    setThinkingText('');
    setIsThinking(false);
    isThinkingRef.current = false;
    addActivity('Stopped');
    // Fix: remove progress cards from chat when user stops — without this, the progress card
    // stays visible even though execution has stopped, making it look like the system is still working
    setChatMessages(prev => prev.filter(m => m.messageType !== 'progress' && m.messageType !== 'agent_progress'));
  }, [sendMessage, addActivity]);

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#e8dcc8' }}>
        <div className="text-ink-3 text-lg">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  const selectedTeam = teams.find((t) => t.id === selectedTeamId) || null;
  const statusText = connectionStatus === 'connected' ? system_status : 'Connecting...';

  // Team list page
  if (!selectedTeam) {
    return (
      <>
        <TeamListPage
          teams={teams}
          agents={agents}
          credits={credits}
          systemStatus={statusText}
          onCreateTeam={() => setShowCreateModal(true)}
          onAICreateTeam={() => setShowAICreateModal(true)}
          onSelectTeam={(teamId) => {
            setSelectedTeamId(teamId);
            setChatMessages([]);
            setNotifications([]);
            updateState({ tasks: [], current_plan: null });
            handleAction('select_team', { team_id: teamId });
          }}
          onDeleteTeam={(teamId) => handleAction('delete_team', { team_id: teamId })}
        />
        <TeamCreateModal
          open={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          onCreate={(data) => handleAction('create_team', data)}
          onFetchModelCatalog={() => handleAction('fetch_model_catalog')}
          onSearchModels={(query) => handleAction('search_models', { query })}
          modelCatalog={modelCatalogData.recommended}
          modelSearchResults={modelCatalogData.searchResults}
          selectedModel={selectedModel}
          resolvedModel={resolvedModel}
          availableTools={available_tools || []}
        />
        <AICreateTeamModal
          open={showAICreateModal}
          onClose={() => { setShowAICreateModal(false); setAiThinkingText(''); handleAction('refresh_credits'); }}
          onSend={(msg) => {
            setAiChatMessages(prev => [...prev, { id: generateUUIDv4(), timestamp: Date.now(), role: 'user', content: msg, messageType: 'text' }]);
            setAiIsThinking(true);
            setAiThinkingText('');
            sendAIModalMessage(msg);
          }}
          onStop={handleStop}
          chatMessages={aiChatMessages}
          onCreateTeam={(data) => {
            handleAction('create_team', data);
            setAiChatMessages([]);
            setAiThinkingText('');
          }}
          onFetchModelCatalog={() => handleAction('fetch_model_catalog')}
          onSearchModels={(query) => handleAction('search_models', { query })}
          onSelectModel={(modelId) => handleAction('set_selected_model', { model_id: modelId })}
          modelCatalog={modelCatalogData.recommended}
          modelSearchResults={modelCatalogData.searchResults}
          selectedModel={selectedModel}
          resolvedModel={resolvedModel}
          isThinking={aiIsThinking}
          thinkingText={aiThinkingText}
        />
      </>
    );
  }

  // Team detail page — Retro Desktop UI
  return (
    <>
      <RetroDesktop
        team={selectedTeam}
        onBack={() => {
          setSelectedTeamId(null);
        }}
        onDeleteTeam={(teamId) => handleAction('delete_team', { team_id: teamId })}
        chatMessages={chatMessages}
        notifications={notifications}
        chatSessions={chatSessions}
        activeSessionId={activeSessionId}
        activityLog={activityLog}
        isProcessing={isProcessing}
        isThinking={isThinking}
        thinkingText={thinkingText}
        thinkingDuration={thinkingDuration}
        inputMode={inputMode}
        selectedModel={selectedModel}
        resolvedModel={resolvedModel}
        connectionStatus={connectionStatus}
        systemStatus={system_status}
        onSendCommand={handleSendCommand}
        onStop={handleStop}
        onModeChange={handleModeChange}
        onAction={handleAction}
        agents={agents || []}
        currentPlan={current_plan}
        availableTools={available_tools || []}
        credits={credits || null}
        historyLogs={historyLogs}
        onFetchHistory={() => handleAction('fetch_history')}
        modelCatalog={modelCatalogData.recommended}
        modelSearchResults={modelCatalogData.searchResults}
        mediaCatalog={modelCatalogData.mediaCatalog}
        mediaSearchResults={modelCatalogData.mediaSearchResults}
        taskItems={(tasks || []) as any}
        uploadLimitMb={uploadLimitMb}
      />
      <TeamCreateModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={(data) => handleAction('create_team', data)}
        onFetchModelCatalog={() => handleAction('fetch_model_catalog')}
        onSearchModels={(query) => handleAction('search_models', { query })}
        modelCatalog={modelCatalogData.recommended}
        modelSearchResults={modelCatalogData.searchResults}
        selectedModel={selectedModel}
        resolvedModel={resolvedModel}
        availableTools={available_tools || []}
      />
    </>
  );
}

function App() {
  return (
    <AuthProvider>
      <PlatformProvider>
        <AppContent />
      </PlatformProvider>
    </AuthProvider>
  );
}

export default App;
