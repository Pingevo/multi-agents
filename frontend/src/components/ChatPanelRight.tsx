import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Bot, User, Loader2, CheckCircle, XCircle, ChevronDown, ChevronRight,
  Wrench, Image, Pencil, Search, PenTool, Eye, Brain, MessageSquare, Plus,
  Trash2, Check, X, Cpu, Video, Square, Volume2, Mic, FileText, Copy,
} from 'lucide-react';
import type {
  ChatMessage, ActivityEntry, AgentProgressEntry, PlanAgent, ResultAgent,
  PlanStatus, ImageApprovalStatus, AgentReviewStatus,
} from './chatTypes';
import type { ChatSession } from './ChatSidebar';
import { ModelPicker, PROVIDER_FAVICONS, getProvider, findModelName } from './ModelPicker';
import type { ModelCatalogEntry } from './ModelPicker';
import MarkdownRenderer from './MarkdownRenderer';
import { withMediaToken } from '../utils/media';

interface ChatPanelRightProps {
  messages: ChatMessage[];
  activityLog: ActivityEntry[];
  isProcessing: boolean;
  chatSessions: ChatSession[];
  activeSessionId: string | null;
  onSend: (message: string, attachments?: Array<{ url: string; name: string; mime: string }>) => void | Promise<void>;
  onStop?: () => void;
  onNewChat: () => void;
  onSwitchChat: (id: string) => void;
  onRenameChat: (id: string, title: string) => void;
  onDeleteChat: (id: string) => void;
  onAcceptPlan?: () => void;
  onRejectPlan?: () => void;
  onConfirmTuning?: (proposals?: any[]) => void;
  onRejectTuning?: () => void;
  onApproveImage?: (approvalId: string, model?: string) => void;
  onRejectImage?: (approvalId: string) => void;
  onRetryImage?: (approvalId: string) => void;
  onEditImagePrompt?: (approvalId: string, newPrompt: string) => void;
  onApproveAgentResult?: (reviewId: string) => void;
  onRejectAgentResult?: (reviewId: string, feedback: string) => void;
  onFetchModelCatalog?: () => void;
  onFetchMediaCatalog?: (mediaType: string) => void;
  onSearchModels?: (query: string) => void;
  onSelectModel?: (modelId: string) => void;
  onChangeAgentModel?: (agentName: string, modelId: string) => void;
  onChangeManagerModel?: (modelId: string) => void;
  onChangeMediaModel?: (mediaType: 'imageModel' | 'videoModel' | 'searchModel' | 'ttsModel' | 'sttModel' | 'visionModel', modelId: string) => void;
  selectedModel?: string;
  resolvedModel?: string;
  thinkingText?: string;
  thinkingDuration?: number | null;
  isThinking?: boolean;
  inputMode?: 'chat' | 'plan';
  onModeChange?: (mode: 'chat' | 'plan') => void;
  disabled?: boolean;
  preloadedModelCatalog?: Record<string, ModelCatalogEntry[]>;
  preloadedModelSearchResults?: ModelCatalogEntry[];
  preloadedMediaCatalog?: Record<string, ModelCatalogEntry[]>;
  preloadedMediaSearchResults?: ModelCatalogEntry[];
  fillContainer?: boolean;
  mentionText?: string;
  onMentionConsumed?: () => void;
  uploadLimitMb?: number;
}

// ============================================================
// Card Components (reused from ChatPanel)
// ============================================================

const PlanCard: React.FC<{
  agents: PlanAgent[];
  taskDescription: string;
  planType: string;
  planStatus: PlanStatus;
  imageModel?: string;
  videoModel?: string;
  searchModel?: string;
  ttsModel?: string;
  sttModel?: string;
  visionModel?: string;
  hasImageTool?: boolean;
  hasVideoTool?: boolean;
  hasSearchTool?: boolean;
  hasTtsTool?: boolean;
  hasSttTool?: boolean;
  hasVisionTool?: boolean;
  hasVisionInput?: boolean;
  managerModel?: string;
  estimatedCost?: string;
  onAccept?: () => void;
  onReject?: () => void;
  onChangeAgentModel?: (agentName: string, modelId: string) => void;
  onChangeManagerModel?: (modelId: string) => void;
  onChangeMediaModel?: (mediaType: 'imageModel' | 'videoModel' | 'searchModel' | 'ttsModel' | 'sttModel' | 'visionModel', modelId: string) => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  mediaCatalog?: Record<string, ModelCatalogEntry[]>;
  mediaSearchResults?: ModelCatalogEntry[];
  onSearchModels?: (query: string) => void;
  onFetchModelCatalog?: () => void;
  onFetchMediaCatalog?: (mediaType: string) => void;
}> = ({ agents, taskDescription, planType, planStatus, imageModel, videoModel, searchModel, ttsModel, sttModel, visionModel, hasImageTool, hasVideoTool, hasSearchTool, hasTtsTool, hasSttTool, hasVisionTool, hasVisionInput, managerModel, estimatedCost, onAccept, onReject, onChangeAgentModel, onChangeManagerModel, onChangeMediaModel, modelCatalog, modelSearchResults, mediaCatalog, mediaSearchResults, onSearchModels, onFetchModelCatalog, onFetchMediaCatalog }) => {
  const isPending = planStatus === 'pending';
  const [editingAgent, setEditingAgent] = useState<string | null>(null);
  const [editingMedia, setEditingMedia] = useState<string | null>(null);
  const agentModelRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const mediaModelRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [originalImageModel] = useState(imageModel || '');
  const [originalVideoModel] = useState(videoModel || '');
  const [originalSearchModel] = useState(searchModel || '');
  const [originalTtsModel] = useState(ttsModel || '');
  const [originalSttModel] = useState(sttModel || '');
  const [originalVisionModel] = useState(visionModel || '');
  const [originalAgentModels] = useState(() => {
    const map: Record<string, string> = {};
    agents.forEach(a => { map[a.name] = a.model || 'openrouter/free'; });
    return map;
  });
  const [originalManagerModel] = useState(managerModel || '');
  const [editingManager, setEditingManager] = useState(false);
  const managerModelRef = useRef<HTMLButtonElement | null>(null);
  return (
    <div className={`rounded-xl border bg-bg overflow-hidden ${isPending ? 'border-accent/30' : 'border-border'}`}>
      <div className="flex items-center justify-between px-3.5 py-2.5 bg-accent/5 border-b border-accent/20">
        <div className="flex items-center gap-2">
          <span className="text-sm">📋</span>
          <span className="font-semibold text-[13px] text-accent-light">
            {planType === 'create_agents'
              ? (planStatus === 'approved' ? 'สร้าง Agent (อนุมัติแล้ว)' : planStatus === 'rejected' ? 'สร้าง Agent (ปฏิเสธ)' : 'สร้าง Agent')
              : (planStatus === 'approved' ? 'แผนงาน (อนุมัติแล้ว)' : planStatus === 'rejected' ? 'แผนงาน (ปฏิเสธ)' : 'แผนงาน')}
          </span>
        </div>
        {planType !== 'create_agents' && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/10 text-accent">
            {agents.length} agent(s) · {planType === 'existing' ? 'Existing' : 'New'}
          </span>
        )}
      </div>
      <div className="p-3.5 space-y-2">
        <div className="text-xs text-text-2">
          {planType === 'create_agents' ? 'คำขอ: ' : 'Task: '}<span className="text-text">{taskDescription}</span>
        </div>
        {estimatedCost && (
          <div className="text-[11px] text-text-3 px-2 py-1 rounded-md bg-surface-2 border border-border">
            {estimatedCost}
          </div>
        )}
        {/* Manager model row — hidden, manager model is controlled by top bar selector */}
        {false && planType !== 'create_agents' && (
        <div className="p-2 rounded-lg bg-surface-2 border border-accent/20">
          <div className="flex items-center gap-1.5 mb-0.5">
            <Brain className="w-3 h-3 text-accent shrink-0" />
            <span className="text-xs font-medium text-text">Manager</span>
            <span className="text-[10px] text-text-2">— Coordinates & summarizes</span>
          </div>
          <div className="flex items-center gap-1 mt-0.5 ml-5">
            <Cpu className="w-2.5 h-2.5 text-text-2 shrink-0" />
            <span className="text-[9px] text-text-2">Model:</span>
            {isPending && onChangeManagerModel ? (
              <>
                <button
                  ref={(el) => { managerModelRef.current = el; }}
                  onClick={() => {
                    if (!editingManager && modelCatalog && Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) {
                      onFetchModelCatalog();
                    }
                    setEditingManager(!editingManager);
                  }}
                  className="text-[9px] text-text bg-surface-3 border border-border/50 rounded px-1.5 py-0.5 hover:border-accent/50 transition-colors max-w-[180px] truncate flex items-center gap-1"
                >
                  {(() => {
                    const modelId = managerModel || '';
                    if (!modelId) return <span className="text-text-2">Auto (system default)</span>;
                    const provider = getProvider(modelId);
                    const favicon = PROVIDER_FAVICONS[provider];
                    if (favicon) return <img src={favicon} alt="" className="w-3 h-3 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                    return null;
                  })()}
                  {managerModel ? findModelName(managerModel, modelCatalog || {}, modelSearchResults || []) : ''}
                </button>
                  {editingManager && (
                    <ModelPicker
                      recommended={modelCatalog || {}}
                      searchResults={modelSearchResults || []}
                      selectedModel={managerModel}
                      onSelect={(modelId) => {
                        onChangeManagerModel(modelId);
                        setEditingManager(false);
                      }}
                      onSearch={onSearchModels || (() => {})}
                      onClose={() => setEditingManager(false)}
                      anchorRef={{ current: managerModelRef.current }}
                      pinnedModelId={originalManagerModel || 'openrouter/free'}
                      showAutoRouter={true}
                    />
                  )}
                </>
              ) : (
                <span className="text-[9px] text-text font-mono">{managerModel ? findModelName(managerModel, modelCatalog || {}, modelSearchResults || []) : 'Auto (system default)'}</span>
              )}
          </div>
        </div>
        )}
        <div className="space-y-1.5">
          {agents.map((agent, idx) => (
            <div key={idx} className="px-2.5 py-2 rounded-lg bg-bg">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-accent/50 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-text">{agent.name}</div>
                  <div className="text-[11px] text-text-3">{agent.role}</div>
                </div>
                {agent.is_existing ? (
                  <span className="text-[9px] px-1 py-0.5 rounded-full bg-success/10 text-success shrink-0">Existing</span>
                ) : (
                  <span className="text-[9px] px-1 py-0.5 rounded-full bg-accent/10 text-accent shrink-0">New</span>
                )}
              </div>
              {agent.goal && (
                <div className="text-[11px] text-text-2 mt-1 ml-4">
                  <span className="text-text-3">Goal:</span> {agent.goal}
                  {agent.is_existing && agent.original_goal && agent.goal !== agent.original_goal && (
                    <span className="text-[9px] text-warning ml-1">(เดิม: {agent.original_goal.slice(0, 60)}{agent.original_goal.length > 60 ? '...' : ''})</span>
                  )}
                </div>
              )}
              {agent.persona && (
                <div className="text-[11px] text-text-2 mt-1 ml-4">
                  <span className="text-text-3">Persona:</span> {agent.persona}
                  {agent.is_existing && agent.original_persona && agent.persona !== agent.original_persona && (
                    <span className="text-[9px] text-warning ml-1">(เดิม: {agent.original_persona.slice(0, 60)}{agent.original_persona.length > 60 ? '...' : ''})</span>
                  )}
                </div>
              )}
              {agent.personality && (agent.personality.tone || agent.personality.communication_style || agent.personality.language) && (
                <div className="flex flex-wrap gap-1 mt-1 ml-4">
                  {agent.personality.tone && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-warning/10 text-warning">Tone: {agent.personality.tone}</span>
                  )}
                  {agent.personality.communication_style && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-warning/10 text-warning">Style: {agent.personality.communication_style}</span>
                  )}
                  {agent.personality.language && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-warning/10 text-warning">Lang: {agent.personality.language}</span>
                  )}
                </div>
              )}
              {agent.expertise && agent.expertise.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1 ml-4">
                  {agent.expertise.map((exp, i) => (
                    <span key={i} className="text-[9px] px-1.5 py-0.5 rounded-full bg-success/10 text-success">{exp}</span>
                  ))}
                </div>
              )}
              {agent.brand_context && (agent.brand_context.brand_name || agent.brand_context.target_audience) && (
                <div className="text-[11px] text-text-2 mt-1 ml-4">
                  {agent.brand_context.brand_name && <span className="text-text-3">Brand:</span>} {agent.brand_context.brand_name}
                  {agent.brand_context.brand_name && agent.brand_context.target_audience && ' · '}
                  {agent.brand_context.target_audience && <span className="text-text-3">Audience:</span>} {agent.brand_context.target_audience}
                </div>
              )}
              {(() => {
                const tools = agent.tools || [];
                const origTools = agent.original_tools || [];
                const hasDiff = agent.is_existing && origTools.length > 0;
                const added = tools.filter(t => !origTools.includes(t));
                const removed = origTools.filter(t => !tools.includes(t));
                const kept = tools.filter(t => origTools.includes(t));
                if (tools.length === 0 && removed.length === 0) return null;
                return (
                  <div className="flex flex-wrap gap-1 mt-1 ml-4">
                    {kept.map((tool, i) => (
                      <span key={`k-${i}`} className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent/10 text-accent flex items-center gap-0.5">
                        <Wrench className="w-2 h-2" />{tool}
                      </span>
                    ))}
                    {added.map((tool, i) => (
                      <span key={`a-${i}`} className="text-[9px] px-1.5 py-0.5 rounded-full border border-dashed border-accent/40 text-accent flex items-center gap-0.5 bg-accent/5">
                        <Wrench className="w-2 h-2" />+{tool}
                      </span>
                    ))}
                    {hasDiff && removed.map((tool, i) => (
                      <span key={`r-${i}`} className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/5 text-red-400/60 flex items-center gap-0.5 line-through">
                        <Wrench className="w-2 h-2" />{tool}
                      </span>
                    ))}
                  </div>
                );
              })()}
              {agent.depends_on && agent.depends_on.length > 0 && (
                <div className="text-[10px] text-text-3 mt-1 ml-4">
                  Depends on: {agent.depends_on.join(', ')}
                </div>
              )}
              <div className="flex items-center gap-1 mt-1 ml-4">
                <Cpu className="w-2.5 h-2.5 text-text-2 shrink-0" />
                <span className="text-[9px] text-text-2">Model:</span>
                {isPending && onChangeAgentModel ? (
                  <>
                    <button
                      ref={(el) => { agentModelRefs.current[agent.name] = el; }}
                      onClick={() => {
                        if (hasVisionInput) {
                          if (mediaCatalog && !mediaCatalog['vision'] && onFetchMediaCatalog) {
                            onFetchMediaCatalog('vision');
                          }
                        } else if (editingAgent !== agent.name && modelCatalog && Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) {
                          onFetchModelCatalog();
                        }
                        setEditingAgent(editingAgent === agent.name ? null : agent.name);
                      }}
                      className="text-[9px] text-text bg-surface-3 border border-border/50 rounded px-1.5 py-0.5 hover:border-accent/50 transition-colors max-w-[180px] truncate flex items-center gap-1"
                    >
                      {(() => {
                        const modelId = agent.model || '';
                        if (!modelId) return <span className="text-text-2">Auto (system default)</span>;
                        const provider = getProvider(modelId);
                        const favicon = PROVIDER_FAVICONS[provider];
                        if (favicon) return <img src={favicon} alt="" className="w-3 h-3 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                        return null;
                      })()}
                      {agent.model ? findModelName(agent.model, hasVisionInput ? (mediaCatalog || {}) : (modelCatalog || {}), modelSearchResults || []) : ''}
                    </button>
                    {editingAgent === agent.name && (
                      <ModelPicker
                        recommended={hasVisionInput ? { vision: mediaCatalog?.['vision'] || [] } : (modelCatalog || {})}
                        searchResults={modelSearchResults || []}
                        selectedModel={agent.model}
                        onSelect={(modelId) => {
                          onChangeAgentModel(agent.name, modelId);
                          setEditingAgent(null);
                        }}
                        onSearch={onSearchModels || (() => {})}
                        onClose={() => setEditingAgent(null)}
                        anchorRef={{ current: agentModelRefs.current[agent.name] }}
                        pinnedModelId={originalAgentModels[agent.name] || 'openrouter/free'}
                        showAutoRouter={true}
                      />
                    )}
                  </>
                ) : (
                  <span className="text-[9px] text-text font-mono">{agent.model ? findModelName(agent.model, hasVisionInput ? (mediaCatalog || {}) : (modelCatalog || {}), modelSearchResults || []) : 'Auto (system default)'}</span>
                )}
              </div>
            </div>
          ))}
        </div>
        {(hasImageTool || hasVideoTool || hasSearchTool || hasTtsTool || hasSttTool || hasVisionTool) && (
          <div className="flex flex-wrap gap-1.5 pt-1.5 border-t border-border/50">
            {hasImageTool && (
              <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-surface-2 border border-border/50">
                <Image className="w-2.5 h-2.5 text-accent shrink-0" />
                <span className="text-[9px] text-text-2">Image:</span>
                {isPending && onChangeMediaModel ? (
                  <>
                    <button
                      ref={(el) => { mediaModelRefs.current['imageModel'] = el; }}
                      onClick={() => {
                        if (editingMedia !== 'imageModel' && onFetchMediaCatalog) {
                          onFetchMediaCatalog('image');
                        }
                        setEditingMedia(editingMedia === 'imageModel' ? null : 'imageModel');
                      }}
                      className="text-[9px] text-text bg-surface-3 border border-border/50 rounded px-1.5 py-0.5 hover:border-accent/50 transition-colors max-w-[180px] truncate flex items-center gap-1"
                    >
                      {(() => {
                        const provider = getProvider(imageModel);
                        const favicon = PROVIDER_FAVICONS[provider];
                        if (favicon) return <img src={favicon} alt="" className="w-3 h-3 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                        return null;
                      })()}
                      {findModelName(imageModel, mediaCatalog || {}, mediaSearchResults || [])}
                    </button>
                    {editingMedia === 'imageModel' && (
                      <ModelPicker
                        recommended={{ image: mediaCatalog?.['image'] || [] }}
                        searchResults={mediaSearchResults || []}
                        selectedModel={imageModel}
                        onSelect={(modelId) => {
                          onChangeMediaModel('imageModel', modelId);
                          setEditingMedia(null);
                        }}
                        onSearch={onSearchModels || (() => {})}
                        onClose={() => setEditingMedia(null)}
                        anchorRef={{ current: mediaModelRefs.current['imageModel'] }}
                        showAutoRouter={false}
                        pinnedModelId={originalImageModel}
                      />
                    )}
                  </>
                ) : (
                  <span className="text-[9px] text-text font-mono truncate max-w-[120px]">{findModelName(imageModel, mediaCatalog || {}, mediaSearchResults || [])}</span>
                )}
              </div>
            )}
            {hasVideoTool && (
              <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-surface-2 border border-border/50">
                <Video className="w-2.5 h-2.5 text-accent shrink-0" />
                <span className="text-[9px] text-text-2">Video:</span>
                {isPending && onChangeMediaModel ? (
                  <>
                    <button
                      ref={(el) => { mediaModelRefs.current['videoModel'] = el; }}
                      onClick={() => {
                        if (editingMedia !== 'videoModel' && onFetchMediaCatalog) {
                          onFetchMediaCatalog('video');
                        }
                        setEditingMedia(editingMedia === 'videoModel' ? null : 'videoModel');
                      }}
                      className="text-[9px] text-text bg-surface-3 border border-border/50 rounded px-1.5 py-0.5 hover:border-accent/50 transition-colors max-w-[180px] truncate flex items-center gap-1"
                    >
                      {(() => {
                        const provider = getProvider(videoModel);
                        const favicon = PROVIDER_FAVICONS[provider];
                        if (favicon) return <img src={favicon} alt="" className="w-3 h-3 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                        return null;
                      })()}
                      {findModelName(videoModel, mediaCatalog || {}, mediaSearchResults || [])}
                    </button>
                    {editingMedia === 'videoModel' && (
                      <ModelPicker
                        recommended={{ video: mediaCatalog?.['video'] || [] }}
                        searchResults={mediaSearchResults || []}
                        selectedModel={videoModel}
                        onSelect={(modelId) => {
                          onChangeMediaModel('videoModel', modelId);
                          setEditingMedia(null);
                        }}
                        onSearch={onSearchModels || (() => {})}
                        onClose={() => setEditingMedia(null)}
                        anchorRef={{ current: mediaModelRefs.current['videoModel'] }}
                        showAutoRouter={false}
                        pinnedModelId={originalVideoModel}
                      />
                    )}
                  </>
                ) : (
                  <span className="text-[9px] text-text font-mono truncate max-w-[120px]">{findModelName(videoModel, mediaCatalog || {}, mediaSearchResults || [])}</span>
                )}
              </div>
            )}
            {hasSearchTool && (
              <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-surface-2 border border-border/50">
                <Search className="w-2.5 h-2.5 text-accent shrink-0" />
                <span className="text-[9px] text-text-2">Search:</span>
                {isPending && onChangeMediaModel ? (
                  <>
                    <button
                      ref={(el) => { mediaModelRefs.current['searchModel'] = el; }}
                      onClick={() => {
                        if (editingMedia !== 'searchModel' && onFetchMediaCatalog) {
                          onFetchMediaCatalog('search');
                        }
                        setEditingMedia(editingMedia === 'searchModel' ? null : 'searchModel');
                      }}
                      className="text-[9px] text-text bg-surface-3 border border-border/50 rounded px-1.5 py-0.5 hover:border-accent/50 transition-colors max-w-[180px] truncate flex items-center gap-1"
                    >
                      {(() => {
                        const provider = getProvider(searchModel);
                        const favicon = PROVIDER_FAVICONS[provider];
                        if (favicon) return <img src={favicon} alt="" className="w-3 h-3 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                        return null;
                      })()}
                      {findModelName(searchModel, mediaCatalog || {}, mediaSearchResults || [])}
                    </button>
                    {editingMedia === 'searchModel' && (
                      <ModelPicker
                        recommended={{ search: mediaCatalog?.['search'] || [] }}
                        searchResults={mediaSearchResults || []}
                        selectedModel={searchModel}
                        onSelect={(modelId) => {
                          onChangeMediaModel('searchModel', modelId);
                          setEditingMedia(null);
                        }}
                        onSearch={onSearchModels || (() => {})}
                        onClose={() => setEditingMedia(null)}
                        anchorRef={{ current: mediaModelRefs.current['searchModel'] }}
                        showAutoRouter={false}
                        pinnedModelId={originalSearchModel}
                      />
                    )}
                  </>
                ) : (
                  <span className="text-[9px] text-text font-mono truncate max-w-[120px]">{findModelName(searchModel, mediaCatalog || {}, mediaSearchResults || [])}</span>
                )}
              </div>
            )}
            {hasTtsTool && (
              <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-surface-2 border border-border/50">
                <Volume2 className="w-2.5 h-2.5 text-accent shrink-0" />
                <span className="text-[9px] text-text-2">TTS:</span>
                {isPending && onChangeMediaModel ? (
                  <>
                    <button
                      ref={(el) => { mediaModelRefs.current['ttsModel'] = el; }}
                      onClick={() => {
                        if (editingMedia !== 'ttsModel' && onFetchMediaCatalog) {
                          onFetchMediaCatalog('tts');
                        }
                        setEditingMedia(editingMedia === 'ttsModel' ? null : 'ttsModel');
                      }}
                      className="text-[9px] text-text bg-surface-3 border border-border/50 rounded px-1.5 py-0.5 hover:border-accent/50 transition-colors max-w-[180px] truncate flex items-center gap-1"
                    >
                      {(() => {
                        const provider = getProvider(ttsModel);
                        const favicon = PROVIDER_FAVICONS[provider];
                        if (favicon) return <img src={favicon} alt="" className="w-3 h-3 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                        return null;
                      })()}
                      {findModelName(ttsModel, mediaCatalog || {}, mediaSearchResults || [])}
                    </button>
                    {editingMedia === 'ttsModel' && (
                      <ModelPicker
                        recommended={{ tts: mediaCatalog?.['tts'] || [] }}
                        searchResults={mediaSearchResults || []}
                        selectedModel={ttsModel}
                        onSelect={(modelId) => {
                          onChangeMediaModel('ttsModel', modelId);
                          setEditingMedia(null);
                        }}
                        onSearch={onSearchModels || (() => {})}
                        onClose={() => setEditingMedia(null)}
                        anchorRef={{ current: mediaModelRefs.current['ttsModel'] }}
                        showAutoRouter={false}
                        pinnedModelId={originalTtsModel}
                      />
                    )}
                  </>
                ) : (
                  <span className="text-[9px] text-text font-mono truncate max-w-[120px]">{findModelName(ttsModel, mediaCatalog || {}, mediaSearchResults || [])}</span>
                )}
              </div>
            )}
            {hasSttTool && (
              <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-surface-2 border border-border/50">
                <Mic className="w-2.5 h-2.5 text-accent shrink-0" />
                <span className="text-[9px] text-text-2">STT:</span>
                {isPending && onChangeMediaModel ? (
                  <>
                    <button
                      ref={(el) => { mediaModelRefs.current['sttModel'] = el; }}
                      onClick={() => {
                        if (editingMedia !== 'sttModel' && onFetchMediaCatalog) {
                          onFetchMediaCatalog('stt');
                        }
                        setEditingMedia(editingMedia === 'sttModel' ? null : 'sttModel');
                      }}
                      className="text-[9px] text-text bg-surface-3 border border-border/50 rounded px-1.5 py-0.5 hover:border-accent/50 transition-colors max-w-[180px] truncate flex items-center gap-1"
                    >
                      {(() => {
                        const provider = getProvider(sttModel);
                        const favicon = PROVIDER_FAVICONS[provider];
                        if (favicon) return <img src={favicon} alt="" className="w-3 h-3 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                        return null;
                      })()}
                      {findModelName(sttModel, mediaCatalog || {}, mediaSearchResults || [])}
                    </button>
                    {editingMedia === 'sttModel' && (
                      <ModelPicker
                        recommended={{ stt: mediaCatalog?.['stt'] || [] }}
                        searchResults={mediaSearchResults || []}
                        selectedModel={sttModel}
                        onSelect={(modelId) => {
                          onChangeMediaModel('sttModel', modelId);
                          setEditingMedia(null);
                        }}
                        onSearch={onSearchModels || (() => {})}
                        onClose={() => setEditingMedia(null)}
                        anchorRef={{ current: mediaModelRefs.current['sttModel'] }}
                        showAutoRouter={false}
                        pinnedModelId={originalSttModel}
                      />
                    )}
                  </>
                ) : (
                  <span className="text-[9px] text-text font-mono truncate max-w-[120px]">{findModelName(sttModel, mediaCatalog || {}, mediaSearchResults || [])}</span>
                )}
              </div>
            )}
            {hasVisionTool && (
              <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-surface-2 border border-border/50">
                <Eye className="w-2.5 h-2.5 text-accent shrink-0" />
                <span className="text-[9px] text-text-2">Vision:</span>
                {isPending && onChangeMediaModel ? (
                  <>
                    <button
                      ref={(el) => { mediaModelRefs.current['visionModel'] = el; }}
                      onClick={() => {
                        if (editingMedia !== 'visionModel' && onFetchMediaCatalog) {
                          onFetchMediaCatalog('vision');
                        }
                        setEditingMedia(editingMedia === 'visionModel' ? null : 'visionModel');
                      }}
                      className="text-[9px] text-text bg-surface-3 border border-border/50 rounded px-1.5 py-0.5 hover:border-accent/50 transition-colors max-w-[180px] truncate flex items-center gap-1"
                    >
                      {(() => {
                        const provider = getProvider(visionModel);
                        const favicon = PROVIDER_FAVICONS[provider];
                        if (favicon) return <img src={favicon} alt="" className="w-3 h-3 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                        return null;
                      })()}
                      {findModelName(visionModel, mediaCatalog || {}, mediaSearchResults || [])}
                    </button>
                    {editingMedia === 'visionModel' && (
                      <ModelPicker
                        recommended={{ vision_analysis: mediaCatalog?.['vision'] || [] }}
                        searchResults={mediaSearchResults || []}
                        selectedModel={visionModel}
                        onSelect={(modelId) => {
                          onChangeMediaModel('visionModel', modelId);
                          setEditingMedia(null);
                        }}
                        onSearch={onSearchModels || (() => {})}
                        onClose={() => setEditingMedia(null)}
                        anchorRef={{ current: mediaModelRefs.current['visionModel'] }}
                        showAutoRouter={false}
                        pinnedModelId={originalVisionModel}
                      />
                    )}
                  </>
                ) : (
                  <span className="text-[9px] text-text font-mono truncate max-w-[120px]">{findModelName(visionModel, mediaCatalog || {}, mediaSearchResults || []) || visionModel || 'Auto'}</span>
                )}
              </div>
            )}
          </div>
        )}
        {isPending && (
          <div className="flex gap-2 mt-3">
            <button onClick={onAccept} className="px-3 py-1.5 rounded-md bg-success/15 text-success text-xs font-medium hover:bg-success/25 transition-colors">
              ✓ ยืนยันแผน
            </button>
            <button onClick={onReject} className="px-3 py-1.5 rounded-md bg-danger/15 text-danger text-xs font-medium hover:bg-danger/25 transition-colors">
              ✕ ปฏิเสธ
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const ProgressCard: React.FC<{ percent: number; label: string }> = ({ percent, label }) => {
  const isDone = percent >= 100;
  return (
    <div className="rounded-xl border border-border bg-surface/80 backdrop-blur-sm p-3">
      <div className="flex items-center gap-2 mb-1.5">
        {isDone ? <CheckCircle className="w-3.5 h-3.5 text-success" /> : <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />}
        <span className="text-xs text-text">{label}</span>
        <span className="text-[10px] text-text-2 ml-auto">{percent}%</span>
      </div>
      <div className="w-full bg-surface-2 rounded-full h-1.5 overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-300 ${isDone ? 'bg-success' : 'bg-accent'}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
};

const toolIcon = (toolName: string) => {
  if (toolName === 'generate_image') return <Image className="w-3 h-3 text-purple-400 shrink-0" />;
  if (toolName === 'generate_document') return <PenTool className="w-3 h-3 text-orange-400 shrink-0" />;
  if (toolName === 'write_code') return <PenTool className="w-3 h-3 text-blue-400 shrink-0" />;
  return <Wrench className="w-3 h-3 text-text-2 shrink-0" />;
};

const AgentStatusRow: React.FC<{
  agent: AgentProgressEntry;
  index: number;
  showOutput: boolean;
  onToggleOutput: () => void;
}> = ({ agent, index, showOutput, onToggleOutput }) => {
  const isRunning = agent.status === 'running';
  const isComplete = agent.status === 'complete';
  const isError = agent.status === 'error';
  const hasTool = isRunning && !!agent.current_tool;
  const hasOutput = !!agent.output && agent.output.length > 0;
  const hasThinking = isRunning && !!agent.thinking && agent.thinking.length > 0;

  return (
    <div className={`rounded-lg border overflow-hidden transition-colors ${
      isRunning ? 'border-accent/30 bg-accent/5' : isComplete ? 'border-success/20 bg-success/5' :
      isError ? 'border-danger/30 bg-danger/5' : 'border-border bg-surface-2'
    }`}>
      <div className="flex items-center gap-1.5 px-2.5 py-1.5">
        <span className="text-[10px] font-mono text-text-2 shrink-0">#{index + 1}</span>
        {isRunning ? <Loader2 className="w-3 h-3 text-accent animate-spin shrink-0" /> :
          isComplete ? <CheckCircle className="w-3 h-3 text-success shrink-0" /> :
          isError ? <XCircle className="w-3 h-3 text-danger shrink-0" /> :
          <div className="w-3 h-3 rounded-full border border-text-2/40 shrink-0" />}
        <span className="text-xs font-medium text-text truncate">{agent.name}</span>
        {isComplete && <span className="text-[9px] px-1 py-0.5 rounded-full bg-success/10 text-success shrink-0 ml-auto">Done</span>}
        {isRunning && hasTool && <span className="text-[9px] px-1 py-0.5 rounded-full bg-accent/10 text-accent shrink-0 ml-auto animate-pulse">Working</span>}
        {isRunning && !hasTool && <span className="text-[9px] px-1 py-0.5 rounded-full bg-accent/10 text-accent shrink-0 ml-auto">Thinking...</span>}
      </div>
      {isRunning && agent.current_task && (
        <div className="px-2.5 pb-1.5 flex items-start gap-1">
          <Brain className="w-2.5 h-2.5 text-text-2 shrink-0 mt-0.5" />
          <span className="text-[10px] text-text-2 line-clamp-2">{agent.current_task}</span>
        </div>
      )}
      {hasThinking && (
        <div className="px-2.5 pb-1.5">
          <div className="text-[10px] text-text-2 bg-surface-3 rounded-md p-1.5 max-h-32 overflow-y-auto whitespace-pre-wrap line-clamp-4">
            {agent.thinking}
          </div>
        </div>
      )}
      {hasTool && (
        <div className="px-2.5 pb-1.5 flex items-center gap-1">
          {toolIcon(agent.current_tool!)}
          <span className="text-[10px] text-text line-clamp-1">{agent.tool_description || agent.current_tool}</span>
        </div>
      )}
      {hasOutput && (
        <div className="px-2.5 pb-1.5">
          <button onClick={onToggleOutput} className="flex items-center gap-1 text-[10px] text-text-2 hover:text-text transition-colors">
            <Eye className="w-2.5 h-2.5" />
            {showOutput ? 'Hide' : 'Preview'} output
          </button>
          {showOutput && (
            <div className="mt-1 text-[10px] text-text-2 bg-surface-3 rounded-md p-1.5 max-h-64 overflow-y-auto">
              <MarkdownRenderer content={agent.output || ''} />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const AgentProgressCard: React.FC<{ agents: AgentProgressEntry[] }> = ({ agents }) => {
  const allDone = agents.every((a) => a.status === 'complete');
  const runningCount = agents.filter((a) => a.status === 'running').length;
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());

  const toggleOutput = (agentName: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(agentName)) next.delete(agentName);
      else next.add(agentName);
      return next;
    });
  };

  useEffect(() => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      for (const a of agents) {
        if ((a.status === 'complete' || a.status === 'waiting_approval') && a.output && a.output.length > 0 && !next.has(a.name)) {
          next.add(a.name);
        }
      }
      return next;
    });
  }, [agents]);

  return (
    <div className="rounded-xl border border-border bg-surface/80 backdrop-blur-sm p-3 space-y-2">
      <div className="flex items-center gap-2">
        {allDone ? <CheckCircle className="w-3.5 h-3.5 text-success" /> : <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />}
        <span className="text-xs font-medium text-text">
          {allDone ? 'All agents complete' : `${runningCount} agent(s) working...`}
        </span>
      </div>
      <div className="space-y-1.5">
        {agents.map((agent, idx) => (
          <AgentStatusRow key={agent.name} agent={agent} index={idx}
            showOutput={expandedAgents.has(agent.name)} onToggleOutput={() => toggleOutput(agent.name)} />
        ))}
      </div>
    </div>
  );
};

const ResultAgentCard: React.FC<{ agent: ResultAgent; index: number }> = ({ agent, index }) => {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className="rounded-lg bg-surface-2 border border-border/50 overflow-hidden">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-surface-3 transition-colors">
        {expanded ? <ChevronDown className="w-3 h-3 text-text-2 shrink-0" /> : <ChevronRight className="w-3 h-3 text-text-2 shrink-0" />}
        <span className="text-[10px] font-mono text-accent">#{index + 1}</span>
        <span className="text-xs font-medium text-text">{agent.name}</span>
        <span className="text-[10px] text-text-2 truncate">— {agent.role}</span>
      </button>
      {expanded && <div className="px-2.5 pb-2.5 max-h-[400px] overflow-y-auto"><MarkdownRenderer content={agent.output || ''} /></div>}
    </div>
  );
};

const ResultCard: React.FC<{ summary: string; agents?: ResultAgent[]; isError?: boolean }> = ({ summary, agents, isError }) => {
  return (
    <div className={`rounded-xl border overflow-hidden backdrop-blur-sm ${isError ? 'border-danger/30 bg-surface/80' : 'border-success/30 bg-surface/80'}`}>
      <div className={`flex items-center gap-2 px-3 py-2 border-b ${isError ? 'bg-danger/5 border-danger/20' : 'bg-success/5 border-success/20'}`}>
        {isError ? <XCircle className="w-3.5 h-3.5 text-danger" /> : <CheckCircle className="w-3.5 h-3.5 text-success" />}
        <span className="font-semibold text-xs text-text">{isError ? 'Error' : 'Completed'}</span>
      </div>
      <div className="p-3">
        <div className="text-xs text-text whitespace-pre-wrap leading-relaxed">
          {summary}
        </div>
      </div>
    </div>
  );
};

const ImageApprovalCard: React.FC<{
  prompt: string; agentName: string; approvalStatus: ImageApprovalStatus;
  mediaType?: string; duration?: number; model?: string; imageError?: string;
  mediaCatalog?: Record<string, ModelCatalogEntry[]>;
  mediaSearchResults?: ModelCatalogEntry[];
  onFetchMediaCatalog?: (mediaType: string) => void;
  onSearchModels?: (query: string) => void;
  onApprove?: (model?: string) => void; onReject?: () => void; onRetry?: () => void;
}> = ({ prompt, agentName, approvalStatus, mediaType = 'image', duration = 0, model = '', imageError = '', mediaCatalog, mediaSearchResults, onFetchMediaCatalog, onSearchModels, onApprove, onReject, onRetry }) => {
  const isPending = approvalStatus === 'pending';
  const isError = approvalStatus === 'error';
  // Media type metadata — labels, icons, and catalog keys for all supported media types
  // Without this mapping, TTS/STT/Vision would show 'Image' labels and fetch wrong model catalogs
  const mediaTypeMeta: Record<string, { label: string; icon: string; promptLabel: string; catalogKey: string }> = {
    image:   { label: 'Image',   icon: '🖼️', promptLabel: 'Prompt',      catalogKey: 'image' },
    video:   { label: 'Video',   icon: '🎬', promptLabel: 'Prompt',      catalogKey: 'video' },
    tts:     { label: 'Audio',   icon: '🔊', promptLabel: 'Text',        catalogKey: 'tts' },
    stt:     { label: 'Transcription', icon: '📝', promptLabel: 'Audio URL', catalogKey: 'stt' },
    vision:  { label: 'Vision',  icon: '👁️', promptLabel: 'Question',   catalogKey: 'vision' },
  };
  const meta = mediaTypeMeta[mediaType] || mediaTypeMeta.image;
  const label = meta.label;
  const [selectedModel, setSelectedModel] = useState(model);
  const [pickerOpen, setPickerOpen] = useState(false);
  const modelBtnRef = useRef<HTMLButtonElement>(null);
  const catalogKey = meta.catalogKey;
  return (
    <div className={`rounded-xl border bg-surface/80 backdrop-blur-sm overflow-hidden ${isPending ? 'border-purple-400/30' : isError ? 'border-danger/40' : 'border-border'}`}>
      <div className="flex items-center justify-between px-3 py-2 bg-purple-500/5 border-b border-purple-400/20">
        <div className="flex items-center gap-2">
          <Image className="w-3.5 h-3.5 text-purple-400" />
          <span className="font-semibold text-xs text-text">
            {approvalStatus === 'approved' ? `${label} Generated` : approvalStatus === 'rejected' ? `${label} Rejected` : isError ? `${label} Generation Failed` : `${label} Approval`}
          </span>
        </div>
        {agentName && <span className="text-[10px] text-text-2">by {agentName}</span>}
      </div>
      <div className="p-3 space-y-2">
        <div className="text-xs text-text-2">
          {meta.promptLabel}: <span className="text-text italic">"{prompt}"</span>
          {mediaType === 'video' && duration > 0 && <span className="ml-1 text-[10px] text-text-3">({duration}s)</span>}
        </div>
        {model && !isPending && (
          <div className="flex items-center gap-1 text-[10px] text-text-2">
            <Cpu className="w-2.5 h-2.5 shrink-0" />
            <span>Model: <span className="text-text font-mono">{model}</span></span>
          </div>
        )}
        {isError && imageError && (
          <div className="text-xs text-danger bg-danger/5 rounded-md px-2 py-1.5 border border-danger/20">
            ⚠️ {imageError}
          </div>
        )}
        {isPending && (
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <Cpu className="w-3 h-3 text-text-2 shrink-0" />
              <button
                ref={modelBtnRef}
                onClick={() => {
                  if (!pickerOpen && onFetchMediaCatalog) onFetchMediaCatalog(catalogKey);
                  setPickerOpen(!pickerOpen);
                }}
                className="flex-1 text-[10px] text-text bg-surface-2 border border-border rounded px-2 py-1 hover:border-purple-400/50 transition-colors truncate flex items-center gap-1"
              >
                {(() => {
                  const provider = getProvider(selectedModel);
                  const favicon = PROVIDER_FAVICONS[provider];
                  if (favicon) return <img src={favicon} alt="" className="w-3 h-3 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                  return null;
                })()}
                {findModelName(selectedModel, mediaCatalog || {}, mediaSearchResults || [])}
              </button>
              {pickerOpen && mediaCatalog && (
                <ModelPicker
                  recommended={{ [catalogKey]: mediaCatalog[catalogKey] || [] }}
                  searchResults={mediaSearchResults || []}
                  selectedModel={selectedModel}
                  onSelect={(modelId) => { setSelectedModel(modelId); setPickerOpen(false); }}
                  onSearch={onSearchModels || (() => {})}
                  onClose={() => setPickerOpen(false)}
                  anchorRef={modelBtnRef}
                  showAutoRouter={false}
                  pinnedModelId={model}
                />
              )}
            </div>
            <div className="flex gap-2">
              <button onClick={() => onApprove?.(selectedModel || undefined)} className="px-3 py-1 rounded-md bg-purple-500 text-white text-xs font-medium hover:bg-purple-600 transition-colors">
                {meta.icon} Generate
              </button>
              <button onClick={onReject} className="px-3 py-1 rounded-md bg-surface-2 text-text-2 text-xs font-medium border border-border hover:bg-surface-3 transition-colors">
                ❌ Cancel
              </button>
            </div>
          </div>
        )}
        {isError && (
          <div className="flex gap-2">
            <button onClick={onRetry} className="px-3 py-1 rounded-md bg-purple-500 text-white text-xs font-medium hover:bg-purple-600 transition-colors">
              🔄 Retry
            </button>
            <button onClick={onReject} className="px-3 py-1 rounded-md bg-surface-2 text-text-2 text-xs font-medium border border-border hover:bg-surface-3 transition-colors">
              ❌ Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const ImageResultCard: React.FC<{
  imageUrl: string; prompt: string; approvalId?: string; mediaType?: string;
  onEditPrompt?: (approvalId: string, newPrompt: string) => void;
}> = ({ imageUrl, prompt, approvalId, mediaType = 'image', onEditPrompt }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedPrompt, setEditedPrompt] = useState(prompt);
  const [loadError, setLoadError] = useState(false);
  const isVideo = mediaType === 'video';
  const isPlaceholder = imageUrl.includes('placeholder_');
  return (
    <div className="rounded-xl border border-purple-400/30 bg-surface/80 backdrop-blur-sm overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 bg-purple-500/5 border-b border-purple-400/20">
        <Image className="w-3.5 h-3.5 text-purple-400" />
        <span className="font-semibold text-xs text-text">{isVideo ? 'Generated Video' : 'Generated Image'}</span>
        {approvalId && onEditPrompt && (
          <div className="ml-auto flex items-center gap-2">
            <button onClick={() => onEditPrompt?.(approvalId, prompt)} className="text-text-2 hover:text-purple-400 transition-colors text-[10px]" title="Regenerate">🔄</button>
            <button onClick={() => setIsEditing(!isEditing)} className="text-text-2 hover:text-purple-400 transition-colors" title="Edit prompt"><Pencil className="w-3 h-3" /></button>
          </div>
        )}
      </div>
      <div className="p-2">
        {loadError || isPlaceholder ? (
          <div className="w-full rounded-lg border border-border bg-surface-2 p-4 text-center">
            <p className="text-xs text-text-2">{isVideo ? '🎬' : '🖼️'} {isVideo ? 'Video' : 'Image'} pending paid tier</p>
          </div>
        ) : isVideo ? (
          <video src={withMediaToken(imageUrl)} controls className="max-w-[400px] w-full rounded-lg border border-border" onError={() => setLoadError(true)} />
        ) : (
          <img src={withMediaToken(imageUrl)} alt={prompt} className="max-w-[400px] w-full rounded-lg border border-border" loading="lazy" onError={() => setLoadError(true)} />
        )}
        <p className="text-[10px] text-text-2 mt-1.5 italic">"{prompt}"</p>
        {isEditing && (
          <div className="mt-2 space-y-1.5">
            <textarea value={editedPrompt} onChange={(e) => setEditedPrompt(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-2 p-1.5 text-xs text-text focus:outline-none focus:border-purple-400" rows={2} />
            <div className="flex gap-1.5">
              <button onClick={() => { onEditPrompt?.(approvalId || '', editedPrompt); setIsEditing(false); }}
                className="px-2.5 py-1 rounded-md bg-purple-500 text-white text-xs font-medium hover:bg-purple-600 transition-colors">🔄 Regenerate</button>
              <button onClick={() => setIsEditing(false)} className="px-2.5 py-1 rounded-md border border-border text-xs font-medium hover:bg-surface-2 transition-colors">Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================
// Agent Review Card — per-agent output review
// ============================================================

const AgentReviewCard: React.FC<{
  agentName: string;
  agentRole: string;
  output: string;
  reviewStatus: AgentReviewStatus;
  onApprove?: () => void;
  onReject?: (feedback: string) => void;
}> = ({ agentName, agentRole, output, reviewStatus, onApprove, onReject }) => {
  const [feedback, setFeedback] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);

  const isPending = reviewStatus === 'pending';
  const isApproved = reviewStatus === 'approved';
  const isRejected = reviewStatus === 'rejected';

  return (
    <div className={`rounded-xl border overflow-hidden ${
      isApproved ? 'border-green-500/30 bg-green-500/5' :
      isRejected ? 'border-red-500/30 bg-red-500/5' :
      'border-blue-500/30 bg-surface/80 backdrop-blur-sm'
    }`}>
      <div className={`flex items-center gap-2 px-3 py-2 border-b ${
        isApproved ? 'border-green-500/20 bg-green-500/5' :
        isRejected ? 'border-red-500/20 bg-red-500/5' :
        'border-blue-500/20 bg-blue-500/5'
      }`}>
        {isApproved ? <CheckCircle className="w-4 h-4 text-green-400" /> :
         isRejected ? <XCircle className="w-4 h-4 text-red-400" /> :
         <Brain className="w-4 h-4 text-blue-400" />}
        <span className="font-semibold text-sm text-text">
          {isApproved ? 'Approved' : isRejected ? 'Rejected — Re-running' : 'Awaiting Review'}
        </span>
        <span className="text-sm text-text-muted ml-auto">{agentName}</span>
      </div>

      <div className="p-3 space-y-2">
        <div className="text-sm text-text-muted">{agentRole}</div>
        <div className="overflow-y-auto">
          <MarkdownRenderer content={output} />
        </div>

        {isPending && (
          <>
            {showFeedback && (
              <div className="space-y-2">
                <textarea
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="Feedback for re-running this agent..."
                  className="w-full text-sm p-2 rounded-lg bg-surface-2 border border-border text-text resize-none"
                  rows={3}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => { onReject?.(feedback); setShowFeedback(false); setFeedback(''); }}
                    className="flex-1 px-3 py-1.5 text-sm font-medium rounded-lg bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 transition-colors"
                  >
                    Send Back with Feedback
                  </button>
                  <button
                    onClick={() => setShowFeedback(false)}
                    className="px-3 py-1.5 text-sm rounded-lg bg-surface-2 text-text-muted border border-border hover:bg-surface-3 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
            {!showFeedback && (
              <div className="flex gap-2">
                <button
                  onClick={() => onApprove?.()}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-green-500/10 text-green-400 border border-green-500/30 hover:bg-green-500/20 transition-colors"
                >
                  <Check className="w-4 h-4" />
                  Approve
                </button>
                <button
                  onClick={() => setShowFeedback(true)}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/30 hover:bg-orange-500/20 transition-colors"
                >
                  <X className="w-4 h-4" />
                  Reject & Re-run
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// ============================================================
// Chat Panel Right (main component)
// ============================================================

export const ChatPanelRight: React.FC<ChatPanelRightProps> = ({
  messages, activityLog, isProcessing, chatSessions, activeSessionId,
  onSend, onStop, onNewChat, onSwitchChat, onRenameChat, onDeleteChat,
  onAcceptPlan, onRejectPlan, onConfirmTuning, onRejectTuning, onApproveImage, onRejectImage, onRetryImage, onEditImagePrompt, onApproveAgentResult, onRejectAgentResult,
  onFetchModelCatalog, onFetchMediaCatalog, onSearchModels, onSelectModel, onChangeAgentModel, onChangeManagerModel, onChangeMediaModel,
  selectedModel, resolvedModel, thinkingText, thinkingDuration, isThinking, inputMode, onModeChange, disabled,
  preloadedModelCatalog, preloadedModelSearchResults, preloadedMediaCatalog, preloadedMediaSearchResults,
  fillContainer = false,
  mentionText,
  onMentionConsumed,
  uploadLimitMb = 500, // Default until backend sends actual value via model catalog
}) => {
  const [width, setWidth] = useState(360);
  const [input, setInput] = useState('');
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [thinkingExpanded, setThinkingExpanded] = useState(false);
  const thinkingManualExpandRef = useRef(false);
  const [modelCatalog, setModelCatalog] = useState<Record<string, ModelCatalogEntry[]>>({});
  const [modelSearchResults, setModelSearchResults] = useState<ModelCatalogEntry[]>([]);
  const [mediaCatalog, setMediaCatalog] = useState<Record<string, ModelCatalogEntry[]>>({});
  const [mediaSearchResults, setMediaSearchResults] = useState<ModelCatalogEntry[]>([]);
  const [attachments, setAttachments] = useState<Array<{ url: string; name: string; mime: string }>>([]);
  const [attachmentPreviews, setAttachmentPreviews] = useState<Array<string>>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const resizingRef = useRef(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputBarRef = useRef<HTMLDivElement>(null);

  // Resizable logic
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizingRef.current) return;
      const newWidth = window.innerWidth - e.clientX;
      setWidth(Math.max(280, Math.min(600, newWidth)));
    };
    const handleMouseUp = () => { resizingRef.current = false; document.body.style.cursor = ''; };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    resizingRef.current = true;
    document.body.style.cursor = 'col-resize';
  }, []);

  // Track scroll position — only auto-scroll if user is near bottom
  const handleScroll = useCallback(() => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      isNearBottomRef.current = scrollHeight - scrollTop - clientHeight < 100;
    }
  }, []);

  // Auto-scroll only if user is near bottom (skip for model_catalog messages)
  useEffect(() => {
    if (scrollRef.current && isNearBottomRef.current) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.messageType === 'model_catalog') return;
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, activityLog, isProcessing]);

  // Auto-collapse thinking when done (unless user manually expanded)
  useEffect(() => {
    if (thinkingDuration !== null && !thinkingManualExpandRef.current) {
      setThinkingExpanded(false);
    }
  }, [thinkingDuration]);

  // Process model_catalog messages from backend — separate text vs media catalogs
  useEffect(() => {
    const textCatalogMsgs = messages.filter(
      (m) => m.messageType === 'model_catalog' && m.modelCatalogRecommended && (m.catalogType || 'text') === 'text'
    );
    if (textCatalogMsgs.length > 0) {
      const latest = textCatalogMsgs[textCatalogMsgs.length - 1];
      setModelCatalog(latest.modelCatalogRecommended!);
      setModelSearchResults(latest.modelCatalogSearchResults || []);
    }
    // Merge all media catalog messages (image, video, search come as separate messages)
    const mediaCatalogMsgs = messages.filter(
      (m) => m.messageType === 'model_catalog' && m.modelCatalogRecommended && m.catalogType === 'media'
    );
    if (mediaCatalogMsgs.length > 0) {
      const merged: Record<string, any[]> = {};
      const mergedSearch: any[] = [];
      for (const msg of mediaCatalogMsgs) {
        const rec = msg.modelCatalogRecommended!;
        for (const [provider, models] of Object.entries(rec)) {
          if (!merged[provider]) merged[provider] = [];
          // Avoid duplicates by model id
          for (const model of models) {
            if (!merged[provider].some((m) => m.id === model.id)) {
              merged[provider].push(model);
            }
          }
        }
        mergedSearch.push(...(msg.modelCatalogSearchResults || []));
      }
      setMediaCatalog(merged);
      setMediaSearchResults(mergedSearch);
    }
  }, [messages]);

  // Use preloaded catalog data if available (from App-level state)
  useEffect(() => {
    if (preloadedModelCatalog && Object.keys(preloadedModelCatalog).length > 0) {
      setModelCatalog(prev => Object.keys(prev).length > 0 ? prev : preloadedModelCatalog);
    }
    if (preloadedModelSearchResults && preloadedModelSearchResults.length > 0) {
      setModelSearchResults(prev => prev.length > 0 ? prev : preloadedModelSearchResults);
    }
    if (preloadedMediaCatalog && Object.keys(preloadedMediaCatalog).length > 0) {
      setMediaCatalog(prev => Object.keys(prev).length > 0 ? prev : preloadedMediaCatalog);
    }
    if (preloadedMediaSearchResults && preloadedMediaSearchResults.length > 0) {
      setMediaSearchResults(prev => prev.length > 0 ? prev : preloadedMediaSearchResults);
    }
  }, [preloadedModelCatalog, preloadedModelSearchResults, preloadedMediaCatalog, preloadedMediaSearchResults]);

  const handleOpenModelPicker = () => {
    if (modelPickerOpen) {
      setModelPickerOpen(false);
      return;
    }
    if (Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) {
      onFetchModelCatalog();
    }
    setModelPickerOpen(true);
  };

  const handleSearchModels = (query: string) => {
    if (onSearchModels) {
      onSearchModels(query);
    }
  };

  const handleSelectModel = (modelId: string) => {
    if (onSelectModel) {
      onSelectModel(modelId);
    }
    setModelPickerOpen(false);
  };

  const handleSubmit = async () => {
    if ((!input.trim() && attachments.length === 0) || disabled) return;
    await onSend(input.trim(), attachments.length > 0 ? attachments : undefined);
    setInput('');
    setAttachments([]);
    setAttachmentPreviews([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  useEffect(() => {
    if (mentionText) {
      setInput(prev => prev ? `${prev} ${mentionText}` : mentionText);
      onMentionConsumed?.();
      if (textareaRef.current) {
        textareaRef.current.focus();
        setTimeout(() => {
          if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
          }
        }, 0);
      }
    }
  }, [mentionText, onMentionConsumed]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const newAttachments: Array<{ url: string; name: string; mime: string }> = [];
    const newPreviews: Array<string> = [];
    let processed = 0;
    const total = files.length;

    // Early warning: check if selected model supports the file's modality
    // Uses input_modalities from OpenRouter API (no hardcoded model names)
    const mimeToModality = (mime: string): string | null => {
      if (mime.startsWith('image/') && mime !== 'image/svg+xml') return 'image';
      if (mime.startsWith('audio/')) return 'audio';
      if (mime.startsWith('video/')) return 'video';
      if (mime === 'application/pdf') return 'pdf';
      return null;
    };
    const findModelEntry = (modelId: string): ModelCatalogEntry | null => {
      for (const provider of Object.keys(modelCatalog)) {
        const found = modelCatalog[provider].find(m => m.id === modelId);
        if (found) return found;
      }
      for (const m of modelSearchResults) {
        if (m.id === modelId) return m;
      }
      return null;
    };
    if (selectedModel) {
      const modelEntry = findModelEntry(selectedModel);
      if (modelEntry) {
        const supportedModalities = modelEntry.input_modalities || [];
        for (let i = 0; i < total; i++) {
          const file = files[i];
          const modality = mimeToModality(file.type || '');
          if (modality && !supportedModalities.includes(modality)) {
            console.warn(`[Upload] Model '${selectedModel}' may not support ${modality} input (file: ${file.name})`);
            const warningDiv = document.createElement('div');
            warningDiv.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#f59e0b;color:#fff;padding:10px 16px;border-radius:8px;font-size:13px;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.3);max-width:400px;';
            warningDiv.textContent = `⚠️ โมเดล '${selectedModel}' อาจไม่รองรับไฟล์ ${modality} (${file.name}) — แนะนำให้เปลี่ยนโมเดลหรือสร้าง Agent ถอดเสียง`;
            document.body.appendChild(warningDiv);
            setTimeout(() => warningDiv.remove(), 5000);
            break;
          }
        }
      }
    }

    for (let i = 0; i < total; i++) {
      const file = files[i];
      if (file.size > uploadLimitMb * 1024 * 1024) {
        alert(`File "${file.name}" too large. Maximum ${uploadLimitMb}MB.`);
        processed++;
        if (processed === total) {
          if (newAttachments.length > 0) {
            setAttachments(prev => [...prev, ...newAttachments]);
            setAttachmentPreviews(prev => [...prev, ...newPreviews]);
          }
        }
        continue;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        newAttachments.push({ url: dataUrl, name: file.name, mime: file.type || 'application/octet-stream' });
        if (file.type.startsWith('image/')) {
          newPreviews.push(dataUrl);
        } else if (file.type.startsWith('audio/')) {
          newPreviews.push('audio');
        } else if (file.type.startsWith('video/')) {
          newPreviews.push('video');
        } else {
          newPreviews.push('file');
        }
        processed++;
        if (processed === total) {
          setAttachments(prev => [...prev, ...newAttachments]);
          setAttachmentPreviews(prev => [...prev, ...newPreviews]);
        }
      };
      reader.readAsDataURL(file);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 100) + 'px';
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const file = item.getAsFile();
        if (file) {
          const reader = new FileReader();
          reader.onload = () => {
            const dataUrl = reader.result as string;
            setAttachments(prev => [...prev, { url: dataUrl, name: file.name || 'pasted-image.png', mime: file.type }]);
            setAttachmentPreviews(prev => [...prev, dataUrl]);
          };
          reader.readAsDataURL(file);
        }
        break;
      }
    }
  };

  const activeSession = chatSessions.find((s) => s.id === activeSessionId);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setSessionDropdownOpen(false);
        setEditingSessionId(null);
      }
    };
    if (sessionDropdownOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [sessionDropdownOpen]);

  const startEditSession = (id: string, title: string) => {
    setEditingSessionId(id);
    setEditTitle(title);
  };
  const confirmEditSession = () => {
    if (editingSessionId && editTitle.trim()) onRenameChat(editingSessionId, editTitle.trim());
    setEditingSessionId(null);
    setEditTitle('');
  };

  return (
    <div className={fillContainer ? "flex-1 flex flex-col min-w-0 min-h-0" : "flex shrink-0 relative"} style={fillContainer ? undefined : { width }}>
      {/* Resize handle — only when not filling container */}
      {!fillContainer && (
        <div
          onMouseDown={startResize}
          className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-accent/30 transition-colors -translate-x-0.5 z-10"
        />
      )}

      <div className="flex-1 flex flex-col bg-bg border-l border-border min-w-0 min-h-0">
        {/* Header — chat title (when fillContainer) */}
        {fillContainer && (
          <div className="px-4 py-2.5 border-b border-border shrink-0">
            <span className="text-xs font-semibold text-text">💬 Chat</span>
          </div>
        )}
        {/* Header — session dropdown (hidden when fillContainer, sessions shown in left sidebar) */}
        {!fillContainer && (
        <div className="px-2 py-1.5 border-b border-border shrink-0 relative" ref={dropdownRef}>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setSessionDropdownOpen(!sessionDropdownOpen)}
              className="flex-1 flex items-center gap-1.5 px-2 py-1 rounded-md bg-surface-2 hover:bg-surface-3 transition-colors text-left min-w-0"
            >
              <MessageSquare className="w-3 h-3 text-accent shrink-0" />
              <span className="text-xs text-text truncate flex-1">{activeSession?.title || 'New Chat'}</span>
              <ChevronDown className={`w-3 h-3 text-text-2 shrink-0 transition-transform ${sessionDropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            <button
              onClick={onNewChat}
              disabled={messages.length === 0}
              className="p-1 rounded-md text-text-2 hover:text-accent hover:bg-surface-2 transition-colors shrink-0 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-text-2"
              title="New Chat"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Dropdown */}
          {sessionDropdownOpen && (
            <div className="absolute left-0 right-0 top-full mt-0.5 bg-surface border border-border rounded-lg shadow-xl z-50 max-h-72 overflow-y-auto">
              <div className="p-1.5 space-y-0.5">
                {chatSessions.length === 0 ? (
                  <div className="text-xs text-text-2 text-center py-3">No chats yet</div>
                ) : (
                  chatSessions.map((session) => (
                    <div
                      key={session.id}
                      className={`group flex items-center gap-1.5 px-2 py-1.5 rounded-md cursor-pointer transition-colors ${
                        session.id === activeSessionId ? 'bg-accent/10 text-text' : 'text-text-2 hover:bg-surface-2'
                      }`}
                      onClick={() => {
                        if (editingSessionId !== session.id) {
                          onSwitchChat(session.id);
                          setSessionDropdownOpen(false);
                        }
                      }}
                    >
                      <MessageSquare className="w-3 h-3 shrink-0" />
                      {editingSessionId === session.id ? (
                        <div className="flex-1 flex items-center gap-1">
                          <input
                            type="text"
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') { e.stopPropagation(); confirmEditSession(); }
                              if (e.key === 'Escape') { e.stopPropagation(); setEditingSessionId(null); setEditTitle(''); }
                            }}
                            autoFocus
                            className="flex-1 min-w-0 bg-bg border border-border rounded px-1 py-0.5 text-[10px] text-text"
                          />
                          <button onClick={(e) => { e.stopPropagation(); confirmEditSession(); }} className="text-success"><Check className="w-2.5 h-2.5" /></button>
                          <button onClick={(e) => { e.stopPropagation(); setEditingSessionId(null); setEditTitle(''); }} className="text-text-2"><X className="w-2.5 h-2.5" /></button>
                        </div>
                      ) : (
                        <>
                          <span className="flex-1 truncate text-[11px]">{session.title}</span>
                          <div className="hidden group-hover:flex items-center gap-1">
                            <button onClick={(e) => { e.stopPropagation(); startEditSession(session.id, session.title); }} className="text-text-2 hover:text-text"><Pencil className="w-2.5 h-2.5" /></button>
                            <button onClick={(e) => { e.stopPropagation(); if (confirm('Delete this chat?')) { onDeleteChat(session.id); setSessionDropdownOpen(false); } }} className="text-text-2 hover:text-danger"><Trash2 className="w-2.5 h-2.5" /></button>
                          </div>
                        </>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
        )}

        {/* Messages */}
        <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-5 space-y-3 flex flex-col min-h-0">
              {messages.length === 0 && activityLog.length === 0 && !isProcessing ? (
                <div className="flex flex-col items-center justify-center py-20 text-text-2">
                  <Bot className="w-12 h-12 mb-3 opacity-30" />
                  <p className="text-sm">No conversation yet</p>
                  <p className="text-xs mt-1">Type a message below to start</p>
                </div>
              ) : (
                <>
                  {messages.map((msg) => {
                    const msgType = msg.messageType || 'text';

                    if (msgType === 'plan' && msg.planAgents) {
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[75%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-accent">
                            <Bot className="w-3.5 h-3.5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <PlanCard agents={msg.planAgents} taskDescription={msg.planTaskDescription || ''}
                              planType={msg.planType || 'new'} planStatus={msg.planStatus || 'pending'}
                              imageModel={msg.imageModel} videoModel={msg.videoModel} searchModel={msg.searchModel}
                              ttsModel={msg.ttsModel} sttModel={msg.sttModel} visionModel={msg.visionModel}
                              hasImageTool={msg.hasImageTool} hasVideoTool={msg.hasVideoTool} hasSearchTool={msg.hasSearchTool}
                              hasTtsTool={msg.hasTtsTool} hasSttTool={msg.hasSttTool} hasVisionTool={msg.hasVisionTool}
                              hasVisionInput={msg.hasVisionInput}
                              managerModel={msg.managerModel}
                              estimatedCost={msg.estimatedCost}
                              onAccept={onAcceptPlan} onReject={onRejectPlan}
                              onChangeAgentModel={onChangeAgentModel}
                              onChangeManagerModel={onChangeManagerModel}
                              onChangeMediaModel={onChangeMediaModel}
                              modelCatalog={modelCatalog}
                              modelSearchResults={modelSearchResults}
                              mediaCatalog={mediaCatalog}
                              mediaSearchResults={mediaSearchResults}
                              onSearchModels={handleSearchModels}
                              onFetchModelCatalog={onFetchModelCatalog}
                              onFetchMediaCatalog={onFetchMediaCatalog} />
                          </div>
                        </div>
                      );
                    }

                    if (msgType === 'progress') {
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[75%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-accent">
                            <Bot className="w-3.5 h-3.5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <ProgressCard percent={msg.progressPercent || 0} label={msg.progressLabel || 'Processing...'} />
                          </div>
                        </div>
                      );
                    }

                    if (msgType === 'agent_progress') {
                      return null;
                    }

                    if (msgType === 'result') {
                      const isError = msg.resultError;
                      const agents = msg.resultAgents || [];
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[90%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-accent">
                            <Bot className="w-3.5 h-3.5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className={`rounded-xl border overflow-hidden backdrop-blur-sm ${isError ? 'border-danger/30 bg-surface/80' : 'border-success/30 bg-surface/80'}`}>
                              <div className={`flex items-center gap-2 px-3 py-2 border-b ${isError ? 'bg-danger/5 border-danger/20' : 'bg-success/5 border-success/20'}`}>
                                {isError ? <XCircle className="w-3.5 h-3.5 text-danger" /> : <CheckCircle className="w-3.5 h-3.5 text-success" />}
                                <span className="font-semibold text-xs text-text">{isError ? 'Error' : 'Completed'}</span>
                              </div>
                              <div className="p-3">
                                <MarkdownRenderer content={msg.resultSummary || 'Done'} />
                              </div>
                              {agents.length > 0 && (
                                <div className="px-3 pb-3 space-y-1.5">
                                  {agents.map((agent, ai) => (
                                    <ResultAgentCard key={ai} agent={agent} index={ai} />
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    }

                    // image_approval — show in chat
                    if (msgType === 'image_approval') {
                      // Type-aware avatar icon — without this, all media types show <Image> icon
                      const _approvalIcon: Record<string, React.ReactNode> = {
                        image: <Image className="w-3.5 h-3.5" />, video: <Video className="w-3.5 h-3.5" />,
                        tts: <Volume2 className="w-3.5 h-3.5" />, stt: <FileText className="w-3.5 h-3.5" />,
                        vision: <Eye className="w-3.5 h-3.5" />,
                      };
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[75%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-purple-400">
                            {_approvalIcon[msg.mediaType || 'image'] || <Image className="w-3.5 h-3.5" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <ImageApprovalCard
                              prompt={msg.imagePrompt || ''}
                              agentName={msg.agentName || ''}
                              approvalStatus={msg.approvalStatus as ImageApprovalStatus}
                              mediaType={msg.mediaType}
                              duration={msg.duration}
                              model={msg.model}
                              imageError={msg.imageError}
                              mediaCatalog={mediaCatalog}
                              mediaSearchResults={mediaSearchResults}
                              onFetchMediaCatalog={onFetchMediaCatalog}
                              onSearchModels={handleSearchModels}
                              onApprove={(model) => onApproveImage?.(msg.approvalId || '', model)}
                              onReject={() => onRejectImage?.(msg.approvalId || '')}
                              onRetry={() => onRetryImage?.(msg.approvalId || '')}
                            />
                          </div>
                        </div>
                      );
                    }

                    // image_result — show in chat
                    if (msgType === 'image_result') {
                      // Type-aware avatar icon — same as image_approval
                      const _resultIcon: Record<string, React.ReactNode> = {
                        image: <Image className="w-3.5 h-3.5" />, video: <Video className="w-3.5 h-3.5" />,
                        tts: <Volume2 className="w-3.5 h-3.5" />, stt: <FileText className="w-3.5 h-3.5" />,
                        vision: <Eye className="w-3.5 h-3.5" />,
                      };
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[75%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-purple-400">
                            {_resultIcon[msg.mediaType || 'image'] || <Image className="w-3.5 h-3.5" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <ImageResultCard
                              imageUrl={withMediaToken(msg.imageUrl || '')}
                              prompt={msg.imagePrompt || ''}
                              approvalId={msg.approvalId}
                              mediaType={msg.mediaType}
                              onEditPrompt={onEditImagePrompt}
                            />
                          </div>
                        </div>
                      );
                    }

                    if (msgType === 'model_catalog') {
                      return null;
                    }

                    // agent_review — show review card in chat
                    if (msgType === 'agent_review') {
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[75%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-blue-400">
                            <Brain className="w-3.5 h-3.5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <AgentReviewCard
                              agentName={msg.agentName || ''}
                              agentRole={msg.agentRole || ''}
                              output={msg.content || ''}
                              reviewStatus={(msg.reviewStatus || 'pending') as AgentReviewStatus}
                              onApprove={() => onApproveAgentResult?.(msg.reviewId || '')}
                              onReject={(feedback) => onRejectAgentResult?.(msg.reviewId || '', feedback)}
                            />
                          </div>
                        </div>
                      );
                    }

                    if (msgType === 'tuning_proposal' && msg.tuningProposals) {
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[75%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-accent">
                            <Bot className="w-3.5 h-3.5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="rounded-xl border border-accent/30 bg-surface/80 backdrop-blur-sm overflow-hidden">
                              <div className="flex items-center gap-2 px-3 py-2 border-b border-accent/20 bg-accent/5">
                                <span className="font-semibold text-xs text-text">📝 ปรับแต่ง Agent</span>
                              </div>
                              <div className="p-3 space-y-3">
                                {msg.tuningProposals.map((proposal, pi) => (
                                  <div key={pi} className="space-y-2">
                                    <div className="text-xs font-medium text-text">{proposal.agent_name}</div>
                                    {proposal.changes.map((change, ci) => (
                                      <div key={ci} className="space-y-1">
                                        <div className="text-[10px] text-text-2 font-medium">{change.field}</div>
                                        <div className="flex items-center gap-2 text-[11px]">
                                          <span className="px-2 py-0.5 rounded bg-surface-2 text-text-2 line-through opacity-60">
                                            {Array.isArray(change.old_value) ? change.old_value.join(', ') || '(empty)' : change.old_value || '(empty)'}
                                          </span>
                                          <span className="text-text-2">→</span>
                                          <span className="px-2 py-0.5 rounded bg-accent/10 text-accent font-medium">
                                            {Array.isArray(change.new_value) ? change.new_value.join(', ') : change.new_value}
                                          </span>
                                        </div>
                                        <div className="text-[10px] text-text-2 italic">{change.reason}</div>
                                      </div>
                                    ))}
                                  </div>
                                ))}
                                {msg.tuningStatus ? (
                                  <div className={`px-3 py-1.5 rounded-lg text-xs font-medium ${msg.tuningStatus === 'confirmed' ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'}`}>
                                    {msg.tuningStatus === 'confirmed' ? '✅ ยืนยันแล้ว' : '❌ ปฏิเสธแล้ว'}
                                  </div>
                                ) : (
                                  <div className="flex gap-2 pt-1">
                                    <button
                                      onClick={() => onConfirmTuning?.(msg.tuningProposals)}
                                      className="px-3 py-1.5 rounded-lg bg-success/10 text-success text-xs font-medium hover:bg-success/20 transition-colors"
                                    >
                                      ยืนยัน
                                    </button>
                                    <button
                                      onClick={() => onRejectTuning?.()}
                                      className="px-3 py-1.5 rounded-lg bg-danger/10 text-danger text-xs font-medium hover:bg-danger/20 transition-colors"
                                    >
                                      ปฏิเสธ
                                    </button>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    }

                    if (msgType === 'audio_result') {
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[75%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-accent">
                            <Volume2 className="w-3.5 h-3.5" />
                          </div>
                          <div className="max-w-[80%] rounded-xl px-3 py-2.5 bg-surface border border-border text-text">
                            {msg.audioPrompt && <p className="text-[10px] text-text-2 mb-1 italic">"{msg.audioPrompt}"</p>}
                            <audio controls src={withMediaToken(msg.audioUrl)} className="w-full h-8" />
                            <div className="flex items-center gap-2 mt-1">
                              {msg.agentName && <span className="text-[9px] text-text-2">Agent: {msg.agentName}</span>}
                              {msg.model && <span className="text-[9px] text-text-2">Model: {msg.model}</span>}
                            </div>
                          </div>
                        </div>
                      );
                    }

                    if (msgType === 'transcription_result') {
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[75%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-accent">
                            <Mic className="w-3.5 h-3.5" />
                          </div>
                          <div className="max-w-[80%] rounded-xl px-3 py-2.5 bg-surface border border-border text-text">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-[10px] font-medium text-text-2">Transcription</span>
                              <button
                                onClick={() => navigator.clipboard.writeText(msg.transcriptionText || '')}
                                className="text-[9px] text-accent hover:text-accent-hover transition-colors flex items-center gap-0.5"
                              >
                                <Copy className="w-2.5 h-2.5" /> Copy
                              </button>
                            </div>
                            <p className="text-xs text-text whitespace-pre-wrap">{msg.transcriptionText}</p>
                            <div className="flex items-center gap-2 mt-1">
                              {msg.agentName && <span className="text-[9px] text-text-2">Agent: {msg.agentName}</span>}
                              {msg.model && <span className="text-[9px] text-text-2">Model: {msg.model}</span>}
                            </div>
                          </div>
                        </div>
                      );
                    }

                    if (msgType === 'video_result') {
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[75%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-accent">
                            <Video className="w-3.5 h-3.5" />
                          </div>
                          <div className="max-w-[80%] rounded-xl px-3 py-2.5 bg-surface border border-border text-text">
                            {msg.videoPrompt && <p className="text-[10px] text-text-2 mb-1 italic">"{msg.videoPrompt}"</p>}
                            <video controls src={withMediaToken(msg.videoUrl)} className="w-full rounded" />
                            <div className="flex items-center gap-2 mt-1">
                              {msg.agentName && <span className="text-[9px] text-text-2">Agent: {msg.agentName}</span>}
                              {msg.model && <span className="text-[9px] text-text-2">Model: {msg.model}</span>}
                            </div>
                          </div>
                        </div>
                      );
                    }

                    if (msgType === 'file_result') {
                      return (
                        <div key={msg.id} className="flex gap-2 flex-row max-w-[75%]">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-accent">
                            <FileText className="w-3.5 h-3.5" />
                          </div>
                          <div className="max-w-[80%] rounded-xl px-3 py-2.5 bg-surface border border-border text-text">
                            <a href={withMediaToken(msg.fileUrl)} download={msg.fileName} className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors">
                              <FileText className="w-3.5 h-3.5" />
                              <span className="truncate">{msg.fileName || 'Download file'}</span>
                            </a>
                            {msg.fileMime && <span className="text-[9px] text-text-2 block mt-0.5">{msg.fileMime}</span>}
                            {msg.agentName && <span className="text-[9px] text-text-2 block mt-0.5">Agent: {msg.agentName}</span>}
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div key={msg.id} className={`flex gap-2 max-w-[75%] ${msg.role === 'user' ? 'flex-row-reverse self-end' : 'flex-row self-start'}`}>
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                          msg.role === 'user' ? 'bg-accent text-white' : 'bg-surface-2 border border-border text-text-2'}`}>
                          {msg.role === 'user' ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                        </div>
                        <div className={`rounded-xl px-3.5 py-2.5 text-sm whitespace-pre-wrap leading-relaxed ${
                          msg.role === 'user' ? 'bg-accent text-white rounded-tr-sm' : 'bg-surface border border-border text-text rounded-tl-sm'}`}>
                          {msg.content}
                          {(() => {
                            const atts = msg.attachments || (msg.attachmentUrl ? [{ url: msg.attachmentUrl, name: msg.attachmentName || '', mime: msg.attachmentMime || '' }] : []);
                            if (atts.length === 0) return null;
                            return (
                              <div className={`mt-2 pt-2 border-t ${msg.role === 'user' ? 'border-white/20' : 'border-border'}`}>
                                <div className="flex flex-wrap gap-2">
                                  {atts.map((att, i) => (
                                    <div key={i} className={att.mime?.startsWith('image/') ? 'w-full' : 'w-full'}>
                                      {att.mime?.startsWith('audio/') ? (
                                        <audio src={withMediaToken(att.url)} controls className="max-w-full" />
                                      ) : att.mime?.startsWith('video/') ? (
                                        <video src={withMediaToken(att.url)} controls className="max-w-full max-h-48 rounded" />
                                      ) : att.mime?.startsWith('image/') ? (
                                        <img src={withMediaToken(att.url)} alt={att.name} className="max-w-full rounded max-h-48 object-cover" />
                                      ) : (
                                        <div className={`flex items-center gap-2.5 rounded-lg px-3 py-2.5 ${msg.role === 'user' ? 'bg-white/10' : 'bg-surface-2 border border-border'}`}>
                                          <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-white/15' : 'bg-accent/10'}`}>
                                            <FileText className={`w-4.5 h-4.5 ${msg.role === 'user' ? 'text-white' : 'text-accent'}`} />
                                          </div>
                                          <div className="flex-1 min-w-0">
                                            <div className={`text-xs font-medium truncate ${msg.role === 'user' ? 'text-white' : 'text-text'}`}>{att.name || 'Attachment'}</div>
                                            <div className={`text-[10px] mt-0.5 ${msg.role === 'user' ? 'text-white/60' : 'text-text-3'}`}>
                                              {(att.mime?.split('/')[1] || 'file').toUpperCase()}
                                            </div>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            );
                          })()}
                        </div>
                      </div>
                    );
                  })}

                  {(activityLog.length > 0 || isProcessing) && (
                    <div className="flex flex-col gap-1.5 pl-9">
                      {activityLog.map((entry) => (
                        <div key={entry.id} className="flex items-center gap-2 text-[11px] text-text-2">
                          {entry.status === 'current' ? <Loader2 className="w-3 h-3 text-accent animate-spin shrink-0" /> :
                            <CheckCircle className="w-3 h-3 text-success shrink-0" />}
                          <span>{entry.text}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Standalone thinking indicator — simple ... animation */}
                  {isThinking && !messages.some(m => m.messageType === 'plan' && m.planStatus === 'pending') && (
                    <div className="flex gap-2 flex-row max-w-[75%]">
                      <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-surface-2 border border-border text-accent">
                        <Bot className="w-3.5 h-3.5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="px-3 py-2">
                          <div className="flex gap-1">
                            <div className="w-2 h-2 rounded-full bg-text-3 animate-bounce" style={{ animationDelay: '0ms' }} />
                            <div className="w-2 h-2 rounded-full bg-text-3 animate-bounce" style={{ animationDelay: '150ms' }} />
                            <div className="w-2 h-2 rounded-full bg-text-3 animate-bounce" style={{ animationDelay: '300ms' }} />
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Input bar */}
            <div ref={inputBarRef} className="border-t border-border p-3 shrink-0 relative">
              {modelPickerOpen && (
                <ModelPicker
                  recommended={modelCatalog}
                  searchResults={modelSearchResults}
                  selectedModel={selectedModel || ''}
                  onSelect={handleSelectModel}
                  onSearch={handleSearchModels}
                  onClose={() => setModelPickerOpen(false)}
                  anchorRef={inputBarRef}
                />
              )}
              {/* Model status bar — always visible */}
              <button
                onClick={handleOpenModelPicker}
                disabled={disabled}
                className={`w-full flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border mb-1.5 transition-colors text-left ${
                  modelPickerOpen
                    ? 'bg-accent/10 border-accent/40 text-text'
                    : 'bg-surface border-border text-text-2 hover:text-text hover:border-accent/50'
                } disabled:opacity-50`}
              >
                {(() => {
                  const modelId = selectedModel || resolvedModel || '';
                  const provider = getProvider(modelId);
                  const favicon = PROVIDER_FAVICONS[provider];
                  if (favicon) {
                    return <img src={favicon} alt="" className="w-3 h-3 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                  }
                  return <Cpu className={`w-3 h-3 shrink-0 ${modelPickerOpen ? 'text-accent' : ''}`} />;
                })()}
                {selectedModel ? (
                  <>
                    <span className="text-[10px] font-medium text-text flex-1 truncate">{findModelName(selectedModel, modelCatalog, modelSearchResults)}</span>
                    <span className="text-[8px] px-1.5 py-0.5 rounded bg-accent/15 text-accent shrink-0">Manual</span>
                  </>
                ) : (
                  <>
                    <span className="text-[10px] font-medium text-text flex-1 truncate">
                      {resolvedModel ? findModelName(resolvedModel, modelCatalog, modelSearchResults) : 'Resolving...'}
                    </span>
                    <span className="text-[8px] px-1.5 py-0.5 rounded bg-success/15 text-success shrink-0">Auto</span>
                  </>
                )}
                <ChevronDown className={`w-3 h-3 shrink-0 transition-transform ${modelPickerOpen ? 'rotate-180' : ''}`} />
              </button>
              {/* Mode toggle: Chat / Plan */}
              <div className="flex items-center gap-1 mb-1.5">
                <button
                  onClick={() => onModeChange?.('chat')}
                  disabled={true}
                  title="Chat mode is temporarily disabled"
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${
                    inputMode === 'chat'
                      ? 'bg-accent/15 text-accent-light border border-accent/30'
                      : 'bg-surface text-text-3 border border-transparent hover:text-text'
                  } disabled:opacity-50`}
                >
                  💬 Chat
                </button>
                <button
                  onClick={() => onModeChange?.('plan')}
                  disabled={disabled}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${
                    inputMode === 'plan'
                      ? 'bg-accent/15 text-accent-light border border-accent/30'
                      : 'bg-surface text-text-3 border border-transparent hover:text-text'
                  } disabled:opacity-50`}
                >
                  ✨ Plan
                </button>
              </div>
              {attachments.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {attachments.map((att, idx) => (
                    <div key={idx} className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-surface border border-border">
                      <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                        {attachmentPreviews[idx] && attachmentPreviews[idx].startsWith('data:') ? (
                          <img src={attachmentPreviews[idx]} alt="" className="w-8 h-8 rounded-lg object-cover" />
                        ) : attachmentPreviews[idx] === 'audio' ? (
                          <Volume2 className="w-4 h-4 text-accent" />
                        ) : attachmentPreviews[idx] === 'video' ? (
                          <Video className="w-4 h-4 text-accent" />
                        ) : (
                          <FileText className="w-4 h-4 text-accent" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0 max-w-[120px]">
                        <div className="text-[11px] font-medium text-text truncate">{att.name}</div>
                        <div className="text-[9px] text-text-3 mt-0.5">
                          {(att.mime?.split('/')[1] || 'file').toUpperCase()}
                        </div>
                      </div>
                      <button onClick={() => {
                        setAttachments(prev => prev.filter((_, i) => i !== idx));
                        setAttachmentPreviews(prev => prev.filter((_, i) => i !== idx));
                      }} className="w-5 h-5 rounded-full flex items-center justify-center text-text-3 hover:text-danger hover:bg-danger/10 transition-colors shrink-0">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                accept="image/*,audio/*,video/*,.pdf,.txt,.json,.csv,.doc,.docx,.md,.py,.js,.ts,.html,.css,.yaml,.yml,.toml,.sh,.sql,.ini,.cfg,.pptx,.xlsx,.zip,.tar,.gz"
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={disabled}
                  className="w-[34px] h-[34px] rounded-[9px] bg-surface border border-border text-text-2 hover:text-text hover:bg-surface-2 disabled:opacity-50 transition-colors flex items-center justify-center shrink-0 text-lg"
                  title="Attach file"
                >
                  +
                </button>
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={handleInput}
                  onKeyDown={handleKeyDown}
                  onPaste={handlePaste}
                  placeholder={disabled ? 'Waiting...' : 'พิมพ์ข้อความถึงทีม...'}
                  disabled={disabled}
                  rows={1}
                  className="flex-1 bg-surface border border-border rounded-[9px] px-3 py-2 text-sm text-text placeholder:text-text-3 focus:outline-none focus:border-accent disabled:opacity-50 resize-none overflow-hidden"
                  style={{ minHeight: '34px', maxHeight: '120px' }}
                />
                {isProcessing ? (
                  <button
                    onClick={() => onStop?.()}
                    className="px-3 py-2 rounded-lg bg-danger text-white hover:bg-danger/80 transition-colors text-xs font-medium shrink-0"
                    title="Stop"
                  >
                    <Square className="w-3.5 h-3.5 fill-current" />
                  </button>
                ) : (
                  <button
                    onClick={handleSubmit}
                    disabled={disabled || (!input.trim() && attachments.length === 0)}
                    className="px-3 py-2 rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-50 transition-colors text-xs font-medium shrink-0">
                    ส่ง
                  </button>
                )}
              </div>
            </div>
      </div>
    </div>
  );
};
