import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Bot, User, Loader2, CheckSquare, CheckCircle, XCircle, ChevronDown, ChevronRight,
  Wrench, Image, Pencil, Search, PenTool, Eye, Brain, Send, MessageSquare, Plus,
  Trash2, Check, X, Cpu, Video, Square, Sparkles, Volume2, Mic, Paperclip, FileText, Copy,
} from 'lucide-react';
import type {
  ChatMessage, ActivityEntry, AgentProgressEntry, PlanAgent, ResultAgent,
  PlanStatus, ImageApprovalStatus,
} from './chatTypes';
import type { ChatSession } from './ChatSidebar';
import { ModelPicker, PROVIDER_FAVICONS, getProvider, findModelName } from './ModelPicker';
import type { ModelCatalogEntry } from './ModelPicker';

interface ChatPanelRightProps {
  messages: ChatMessage[];
  activityLog: ActivityEntry[];
  isProcessing: boolean;
  chatSessions: ChatSession[];
  activeSessionId: string | null;
  onSend: (message: string, attachment?: { url: string; name: string; mime: string }) => void | Promise<void>;
  onStop?: () => void;
  onNewChat: () => void;
  onSwitchChat: (id: string) => void;
  onRenameChat: (id: string, title: string) => void;
  onDeleteChat: (id: string) => void;
  onAcceptPlan?: () => void;
  onRejectPlan?: () => void;
  onConfirmTuning?: () => void;
  onRejectTuning?: () => void;
  onApproveImage?: (approvalId: string) => void;
  onRejectImage?: (approvalId: string) => void;
  onRetryImage?: (approvalId: string) => void;
  onEditImagePrompt?: (approvalId: string, newPrompt: string) => void;
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
  managerModel?: string;
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
}> = ({ agents, taskDescription, planType, planStatus, imageModel, videoModel, searchModel, ttsModel, sttModel, visionModel, hasImageTool, hasVideoTool, hasSearchTool, hasTtsTool, hasSttTool, hasVisionTool, managerModel, onAccept, onReject, onChangeAgentModel, onChangeManagerModel, onChangeMediaModel, modelCatalog, modelSearchResults, mediaCatalog, mediaSearchResults, onSearchModels, onFetchModelCatalog, onFetchMediaCatalog }) => {
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
    agents.forEach(a => { map[a.name] = a.model || 'openrouter/auto'; });
    return map;
  });
  const [originalManagerModel] = useState(managerModel || '');
  const [editingManager, setEditingManager] = useState(false);
  const managerModelRef = useRef<HTMLButtonElement | null>(null);
  return (
    <div className={`rounded-xl border bg-surface/80 backdrop-blur-sm overflow-hidden ${isPending ? 'border-accent/30' : 'border-border'}`}>
      <div className="flex items-center justify-between px-3 py-2 bg-accent/5 border-b border-accent/20">
        <div className="flex items-center gap-2">
          <CheckSquare className="w-4 h-4 text-accent" />
          <span className="font-semibold text-xs text-text">
            {planStatus === 'approved' ? 'Plan Approved' : planStatus === 'rejected' ? 'Plan Rejected' : 'Plan Approval'}
          </span>
        </div>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/10 text-accent">
          {agents.length} agent(s) · {planType === 'existing' ? 'Existing' : 'New'}
        </span>
      </div>
      <div className="p-3 space-y-2">
        <div className="text-xs text-text-2">
          Task: <span className="text-text">{taskDescription}</span>
        </div>
        {/* Manager model row */}
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
                      pinnedModelId={originalManagerModel || 'openrouter/auto'}
                      showAutoRouter={true}
                    />
                  )}
                </>
              ) : (
                <span className="text-[9px] text-text font-mono">{managerModel ? findModelName(managerModel, modelCatalog || {}, modelSearchResults || []) : 'Auto (system default)'}</span>
              )}
          </div>
        </div>
        <div className="space-y-1.5">
          {agents.map((agent, idx) => (
            <div key={idx} className="p-2 rounded-lg bg-surface-2 border border-border/50">
              <div className="flex items-center gap-1.5 mb-0.5">
                <span className="text-[10px] font-mono text-accent">#{idx + 1}</span>
                <span className="text-xs font-medium text-text">{agent.name}</span>
                <span className="text-[10px] text-text-2">— {agent.role}</span>
                {agent.is_existing ? (
                  <span className="text-[9px] px-1 py-0.5 rounded-full bg-success/10 text-success">Existing</span>
                ) : (
                  <span className="text-[9px] px-1 py-0.5 rounded-full bg-accent/10 text-accent">New</span>
                )}
              </div>
              {agent.goal && <div className="text-[10px] text-text-2 ml-5">{agent.goal}</div>}
              <div className="flex items-center gap-1 mt-0.5 ml-5">
                <Cpu className="w-2.5 h-2.5 text-text-2 shrink-0" />
                <span className="text-[9px] text-text-2">Model:</span>
                {isPending && onChangeAgentModel ? (
                  <>
                    <button
                      ref={(el) => { agentModelRefs.current[agent.name] = el; }}
                      onClick={() => {
                        if (editingAgent !== agent.name && modelCatalog && Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) {
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
                      {agent.model ? findModelName(agent.model, modelCatalog || {}, modelSearchResults || []) : ''}
                    </button>
                      {editingAgent === agent.name && (
                        <ModelPicker
                          recommended={modelCatalog || {}}
                          searchResults={modelSearchResults || []}
                          selectedModel={agent.model}
                          onSelect={(modelId) => {
                            onChangeAgentModel(agent.name, modelId);
                            setEditingAgent(null);
                          }}
                          onSearch={onSearchModels || (() => {})}
                          onClose={() => setEditingAgent(null)}
                          anchorRef={{ current: agentModelRefs.current[agent.name] }}
                          pinnedModelId={originalAgentModels[agent.name] || 'openrouter/auto'}
                          showAutoRouter={true}
                        />
                      )}
                    </>
                  ) : (
                    <span className="text-[9px] text-text font-mono">{agent.model ? findModelName(agent.model, modelCatalog || {}, modelSearchResults || []) : 'Auto (system default)'}</span>
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
          <div className="flex gap-2">
            <button onClick={onAccept} className="px-3 py-1 rounded-md bg-accent text-white text-xs font-medium hover:bg-accent-hover transition-colors">
              ✅ Approve
            </button>
            <button onClick={onReject} className="px-3 py-1 rounded-md border border-border text-xs font-medium hover:bg-surface-2 transition-colors">
              ❌ Reject
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
  if (toolName === 'search_web') return <Search className="w-3 h-3 text-accent shrink-0" />;
  if (toolName === 'generate_image') return <Image className="w-3 h-3 text-purple-400 shrink-0" />;
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
            <div className="mt-1 text-[10px] text-text-2 bg-surface-3 rounded-md p-1.5 max-h-64 overflow-y-auto whitespace-pre-wrap">
              {agent.output}
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
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-lg bg-surface-2 border border-border/50 overflow-hidden">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-surface-3 transition-colors">
        {expanded ? <ChevronDown className="w-3 h-3 text-text-2 shrink-0" /> : <ChevronRight className="w-3 h-3 text-text-2 shrink-0" />}
        <span className="text-[10px] font-mono text-accent">#{index + 1}</span>
        <span className="text-xs font-medium text-text">{agent.name}</span>
        <span className="text-[10px] text-text-2 truncate">— {agent.role}</span>
      </button>
      {expanded && <div className="px-2.5 pb-2.5 text-xs text-text whitespace-pre-wrap max-h-48 overflow-y-auto">{agent.output}</div>}
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
  onApprove?: () => void; onReject?: () => void; onRetry?: () => void;
}> = ({ prompt, agentName, approvalStatus, mediaType = 'image', duration = 0, model = '', imageError = '', onApprove, onReject, onRetry }) => {
  const isPending = approvalStatus === 'pending';
  const isError = approvalStatus === 'error';
  const isVideo = mediaType === 'video';
  const label = isVideo ? 'Video' : 'Image';
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
          Prompt: <span className="text-text italic">"{prompt}"</span>
          {isVideo && duration > 0 && <span className="ml-1 text-[10px] text-text-3">({duration}s)</span>}
        </div>
        {model && (
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
          <div className="flex gap-2">
            <button onClick={onApprove} className="px-3 py-1 rounded-md bg-purple-500 text-white text-xs font-medium hover:bg-purple-600 transition-colors">
              {isVideo ? '🎬' : '🖼️'} Generate
            </button>
            <button onClick={onReject} className="px-3 py-1 rounded-md bg-surface-2 text-text-2 text-xs font-medium border border-border hover:bg-surface-3 transition-colors">
              ❌ Cancel
            </button>
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
          <video src={imageUrl} controls className="w-full rounded-lg border border-border" onError={() => setLoadError(true)} />
        ) : (
          <img src={imageUrl} alt={prompt} className="w-full rounded-lg border border-border" loading="lazy" onError={() => setLoadError(true)} />
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
// Chat Panel Right (main component)
// ============================================================

export const ChatPanelRight: React.FC<ChatPanelRightProps> = ({
  messages, activityLog, isProcessing, chatSessions, activeSessionId,
  onSend, onStop, onNewChat, onSwitchChat, onRenameChat, onDeleteChat,
  onAcceptPlan, onRejectPlan, onConfirmTuning, onRejectTuning, onApproveImage, onRejectImage, onRetryImage, onEditImagePrompt,
  onFetchModelCatalog, onFetchMediaCatalog, onSearchModels, onSelectModel, onChangeAgentModel, onChangeManagerModel, onChangeMediaModel,
  selectedModel, resolvedModel, thinkingText, thinkingDuration, isThinking, inputMode, onModeChange, disabled,
  preloadedModelCatalog, preloadedModelSearchResults, preloadedMediaCatalog, preloadedMediaSearchResults,
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
  const [attachment, setAttachment] = useState<{ url: string; name: string; mime: string } | null>(null);
  const [attachmentPreview, setAttachmentPreview] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
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

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
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
    if ((!input.trim() && !attachment) || disabled) return;
    await onSend(input.trim(), attachment || undefined);
    setInput('');
    setAttachment(null);
    setAttachmentPreview(null);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) {
      alert('File too large. Maximum 20MB.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      setAttachment({ url: dataUrl, name: file.name, mime: file.type || 'application/octet-stream' });
      if (file.type.startsWith('image/')) {
        setAttachmentPreview(dataUrl);
      } else if (file.type.startsWith('audio/')) {
        setAttachmentPreview('audio');
      } else if (file.type.startsWith('video/')) {
        setAttachmentPreview('video');
      } else {
        setAttachmentPreview('file');
      }
    };
    reader.readAsDataURL(file);
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
            setAttachment({ url: dataUrl, name: file.name || 'pasted-image.png', mime: file.type });
            setAttachmentPreview(dataUrl);
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
    <div className="flex shrink-0 relative" style={{ width }}>
      {/* Resize handle */}
      <div
        onMouseDown={startResize}
        className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-accent/30 transition-colors -translate-x-0.5 z-10"
      />

      <div className="flex-1 flex flex-col bg-bg border-l border-border min-w-0">
        {/* Header — session dropdown */}
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

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-2.5 space-y-2">
              {messages.length === 0 && activityLog.length === 0 && !isProcessing ? (
                <div className="flex flex-col items-center justify-center py-12 text-text-2">
                  <Bot className="w-10 h-10 mb-2 opacity-30" />
                  <p className="text-xs">No conversation yet</p>
                  <p className="text-[10px] mt-1">Type a message below to start</p>
                </div>
              ) : (
                <>
                  {messages.map((msg) => {
                    const msgType = msg.messageType || 'text';

                    if (msgType === 'plan' && msg.planAgents) {
                      return (
                        <div key={msg.id} className="flex gap-1.5 flex-row">
                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                            <Bot className="w-3 h-3" />
                          </div>
                          <div className="flex-1 min-w-0">
                            {/* Thinking block — inline like ChatGPT/Claude */}
                            {(isThinking || thinkingText) && (
                              <div className="mb-1.5 rounded-lg bg-surface-2/50 border border-border/50">
                                <button
                                  onClick={() => {
                                    thinkingManualExpandRef.current = true;
                                    setThinkingExpanded(!thinkingExpanded);
                                  }}
                                  className="w-full flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-surface-2/80 rounded-lg transition-colors"
                                >
                                  {isProcessing ? (
                                    <Loader2 className="w-3 h-3 text-accent animate-spin shrink-0" />
                                  ) : (
                                    <Brain className="w-3 h-3 text-text-2 shrink-0" />
                                  )}
                                  <span className="text-[11px] text-text-2 font-medium">
                                    {isProcessing ? 'กำลังคิด...' : thinkingDuration !== null ? `คิดเสร็จแล้ว (${thinkingDuration}s)` : 'ความคิดของ AI'}
                                  </span>
                                  <span className="ml-auto">
                                    {thinkingExpanded ? <ChevronDown className="w-3 h-3 text-text-2" /> : <ChevronRight className="w-3 h-3 text-text-2" />}
                                  </span>
                                </button>
                                {thinkingExpanded && (
                                  <div className="px-2.5 pb-2 pt-0.5">
                                    <div className="text-[11px] text-text-2 leading-relaxed">
                                      {isProcessing ? 'AI กำลังวิเคราะห์คำขอและวางแผนการทำงาน...' : 'AI วิเคราะห์คำขอเสร็จแล้ว แผนงานจะแสดงด้านล่าง'}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                            <PlanCard agents={msg.planAgents} taskDescription={msg.planTaskDescription || ''}
                              planType={msg.planType || 'new'} planStatus={msg.planStatus || 'pending'}
                              imageModel={msg.imageModel} videoModel={msg.videoModel} searchModel={msg.searchModel}
                              ttsModel={msg.ttsModel} sttModel={msg.sttModel} visionModel={msg.visionModel}
                              hasImageTool={msg.hasImageTool} hasVideoTool={msg.hasVideoTool} hasSearchTool={msg.hasSearchTool}
                              hasTtsTool={msg.hasTtsTool} hasSttTool={msg.hasSttTool} hasVisionTool={msg.hasVisionTool}
                              managerModel={msg.managerModel}
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
                        <div key={msg.id} className="flex gap-1.5 flex-row">
                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                            <Bot className="w-3 h-3" />
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
                      return (
                        <div key={msg.id} className="flex gap-1.5 flex-row">
                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                            <Bot className="w-3 h-3" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className={`rounded-xl border overflow-hidden backdrop-blur-sm ${isError ? 'border-danger/30 bg-surface/80' : 'border-success/30 bg-surface/80'}`}>
                              <div className={`flex items-center gap-2 px-3 py-2 border-b ${isError ? 'bg-danger/5 border-danger/20' : 'bg-success/5 border-success/20'}`}>
                                {isError ? <XCircle className="w-3.5 h-3.5 text-danger" /> : <CheckCircle className="w-3.5 h-3.5 text-success" />}
                                <span className="font-semibold text-xs text-text">{isError ? 'Error' : 'Completed'}</span>
                              </div>
                              <div className="p-3 text-xs text-text whitespace-pre-wrap leading-relaxed">
                                {msg.resultSummary || 'Done'}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    }

                    // image_approval, image_result, and model_catalog are not shown as chat messages
                    if (msgType === 'image_approval' || msgType === 'image_result' || msgType === 'model_catalog') {
                      return null;
                    }

                    if (msgType === 'tuning_proposal' && msg.tuningProposals) {
                      return (
                        <div key={msg.id} className="flex gap-1.5 flex-row">
                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                            <Bot className="w-3 h-3" />
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
                                            {change.old_value || '(empty)'}
                                          </span>
                                          <span className="text-text-2">→</span>
                                          <span className="px-2 py-0.5 rounded bg-accent/10 text-accent font-medium">
                                            {change.new_value}
                                          </span>
                                        </div>
                                        <div className="text-[10px] text-text-2 italic">{change.reason}</div>
                                      </div>
                                    ))}
                                  </div>
                                ))}
                                <div className="flex gap-2 pt-1">
                                  <button
                                    onClick={() => onConfirmTuning?.()}
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
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    }

                    if (msgType === 'audio_result') {
                      return (
                        <div key={msg.id} className="flex gap-1.5 flex-row">
                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                            <Volume2 className="w-3 h-3" />
                          </div>
                          <div className="max-w-[80%] rounded-lg px-2.5 py-2 bg-surface/80 backdrop-blur-sm border border-border text-text">
                            {msg.audioPrompt && <p className="text-[10px] text-text-2 mb-1 italic">"{msg.audioPrompt}"</p>}
                            <audio controls src={msg.audioUrl} className="w-full h-8" />
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
                        <div key={msg.id} className="flex gap-1.5 flex-row">
                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                            <Mic className="w-3 h-3" />
                          </div>
                          <div className="max-w-[80%] rounded-lg px-2.5 py-2 bg-surface/80 backdrop-blur-sm border border-border text-text">
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
                        <div key={msg.id} className="flex gap-1.5 flex-row">
                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                            <Video className="w-3 h-3" />
                          </div>
                          <div className="max-w-[80%] rounded-lg px-2.5 py-2 bg-surface/80 backdrop-blur-sm border border-border text-text">
                            {msg.videoPrompt && <p className="text-[10px] text-text-2 mb-1 italic">"{msg.videoPrompt}"</p>}
                            <video controls src={msg.videoUrl} className="w-full rounded" />
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
                        <div key={msg.id} className="flex gap-1.5 flex-row">
                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                            <FileText className="w-3 h-3" />
                          </div>
                          <div className="max-w-[80%] rounded-lg px-2.5 py-2 bg-surface/80 backdrop-blur-sm border border-border text-text">
                            <a href={msg.fileUrl} download={msg.fileName} className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors">
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
                      <div key={msg.id} className={`flex gap-1.5 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                          msg.role === 'user' ? 'bg-accent text-white' : 'bg-surface-2 text-text-2'}`}>
                          {msg.role === 'user' ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
                        </div>
                        <div className={`max-w-[80%] rounded-lg px-2.5 py-1.5 text-xs whitespace-pre-wrap ${
                          msg.role === 'user' ? 'bg-accent text-white' : 'bg-surface/80 backdrop-blur-sm border border-border text-text'}`}>
                          {msg.content}
                          {msg.attachmentUrl && (
                            <div className="mt-2 pt-2 border-t border-white/20">
                              {msg.attachmentMime?.startsWith('audio/') ? (
                                <audio src={msg.attachmentUrl} controls className="max-w-full mt-2" />
                              ) : msg.attachmentMime?.startsWith('video/') ? (
                                <video src={msg.attachmentUrl} controls className="max-w-full max-h-48 rounded mt-2" />
                              ) : msg.attachmentMime?.startsWith('image/') ? (
                                <img src={msg.attachmentUrl} alt={msg.attachmentName} className="max-w-full rounded max-h-48 object-cover" />
                              ) : (
                                <div className="flex items-center gap-1.5 text-xs">
                                  <FileText className="w-3.5 h-3.5" />
                                  <span className="truncate">{msg.attachmentName || 'Attachment'}</span>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}

                  {(activityLog.length > 0 || isProcessing) && (
                    <div className="flex flex-col gap-1 pl-7">
                      {activityLog.map((entry) => (
                        <div key={entry.id} className="flex items-center gap-1.5 text-[10px] text-text-2">
                          {entry.status === 'current' ? <Loader2 className="w-2.5 h-2.5 text-accent animate-spin shrink-0" /> :
                            <CheckCircle className="w-2.5 h-2.5 text-success shrink-0" />}
                          <span>{entry.text}</span>
                        </div>
                      ))}
                      {isProcessing && activityLog.length === 0 && !isThinking && (
                        <div className="flex items-center gap-1.5 text-[10px] text-text-2">
                          <Loader2 className="w-2.5 h-2.5 text-accent animate-spin shrink-0" />
                          <span>Processing...</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Standalone thinking block — when thinking is active but no plan message yet */}
                  {isThinking && !messages.some(m => m.messageType === 'plan') && (
                    <div className="flex gap-1.5 flex-row">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-surface-2 text-accent">
                        <Bot className="w-3 h-3" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="rounded-lg bg-surface-2/50 border border-border/50">
                          <button
                            onClick={() => {
                              thinkingManualExpandRef.current = true;
                              setThinkingExpanded(!thinkingExpanded);
                            }}
                            className="w-full flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-surface-2/80 rounded-lg transition-colors"
                          >
                            {isProcessing ? (
                              <Loader2 className="w-3 h-3 text-accent animate-spin shrink-0" />
                            ) : (
                              <Brain className="w-3 h-3 text-text-2 shrink-0" />
                            )}
                            <span className="text-[11px] text-text-2 font-medium">
                              {isProcessing ? 'กำลังคิด...' : thinkingDuration !== null ? `คิดเสร็จแล้ว (${thinkingDuration}s)` : 'ความคิดของ AI'}
                            </span>
                            <span className="ml-auto">
                              {thinkingExpanded ? <ChevronDown className="w-3 h-3 text-text-2" /> : <ChevronRight className="w-3 h-3 text-text-2" />}
                            </span>
                          </button>
                          {thinkingExpanded && (
                            <div className="px-2.5 pb-2 pt-0.5">
                              <div className="text-[11px] text-text-2 leading-relaxed">
                                {isProcessing ? 'AI กำลังวิเคราะห์คำขอและวางแผนการทำงาน...' : 'AI วิเคราะห์คำขอเสร็จแล้ว'}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Input bar */}
            <div ref={inputBarRef} className="border-t border-border p-2 shrink-0 relative">
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
                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg border mb-1.5 transition-colors text-left ${
                  modelPickerOpen
                    ? 'bg-accent/10 border-accent/40 text-text'
                    : 'bg-surface-2 border-border text-text-2 hover:text-text hover:border-border/80'
                } disabled:opacity-50`}
              >
                {(() => {
                  const modelId = selectedModel || resolvedModel || '';
                  const provider = getProvider(modelId);
                  const favicon = PROVIDER_FAVICONS[provider];
                  if (favicon) {
                    return <img src={favicon} alt="" className="w-4 h-4 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                  }
                  return <Cpu className={`w-3.5 h-3.5 shrink-0 ${modelPickerOpen ? 'text-accent' : ''}`} />;
                })()}
                {selectedModel ? (
                  <>
                    <span className="text-[10px] font-medium text-text flex-1 truncate">{findModelName(selectedModel, modelCatalog, modelSearchResults)}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent shrink-0">Manual</span>
                  </>
                ) : (
                  <>
                    <span className="text-[10px] font-medium text-text flex-1 truncate">
                      {resolvedModel ? findModelName(resolvedModel, modelCatalog, modelSearchResults) : 'Resolving...'}
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-500 shrink-0">Auto</span>
                  </>
                )}
                <ChevronDown className={`w-3 h-3 shrink-0 transition-transform ${modelPickerOpen ? 'rotate-180' : ''}`} />
              </button>
              {/* Mode toggle: Chat / Plan */}
              <div className="flex items-center gap-1 mb-1.5">
                <button
                  onClick={() => onModeChange?.('chat')}
                  disabled={disabled}
                  className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-colors ${
                    inputMode === 'chat'
                      ? 'bg-accent/15 text-accent border border-accent/30'
                      : 'bg-surface-2 text-text-2 border border-transparent hover:text-text'
                  } disabled:opacity-50`}
                >
                  <MessageSquare className="w-3 h-3" />
                  Chat
                </button>
                <button
                  onClick={() => onModeChange?.('plan')}
                  disabled={disabled}
                  className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-colors ${
                    inputMode === 'plan'
                      ? 'bg-accent/15 text-accent border border-accent/30'
                      : 'bg-surface-2 text-text-2 border border-transparent hover:text-text'
                  } disabled:opacity-50`}
                >
                  <Sparkles className="w-3 h-3" />
                  Plan
                </button>
              </div>
              {attachment && (
                <div className="flex items-center gap-1.5 mb-1 px-2 py-1 rounded-md bg-surface-2 border border-border/50">
                  {attachmentPreview && attachmentPreview.startsWith('data:') && (
                    <img src={attachmentPreview} alt="" className="w-6 h-6 rounded object-cover shrink-0" />
                  )}
                  {attachmentPreview === 'audio' && <Volume2 className="w-3.5 h-3.5 text-accent shrink-0" />}
                  {attachmentPreview === 'video' && <Video className="w-3.5 h-3.5 text-accent shrink-0" />}
                  {attachmentPreview === 'file' && <FileText className="w-3.5 h-3.5 text-accent shrink-0" />}
                  <span className="text-[10px] text-text-2 truncate flex-1">{attachment.name}</span>
                  <button onClick={() => { setAttachment(null); setAttachmentPreview(null); }} className="text-text-2 hover:text-danger transition-colors">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileSelect}
                className="hidden"
                accept="image/*,audio/*,video/*,.pdf,.txt,.json,.csv,.doc,.docx,.md"
              />
              <div className="flex items-end gap-1.5">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={disabled}
                  className="p-1.5 rounded-lg border border-border text-text-2 hover:text-accent hover:border-accent/50 disabled:opacity-50 transition-colors mb-0.5"
                  title="Attach file"
                >
                  <Paperclip className="w-3.5 h-3.5" />
                </button>
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={handleInput}
                  onKeyDown={handleKeyDown}
                  onPaste={handlePaste}
                  placeholder={disabled ? 'Waiting...' : 'Type a message...'}
                  disabled={disabled}
                  rows={1}
                  className="flex-1 bg-surface-2 border border-border rounded-lg px-2.5 py-1.5 text-xs text-text placeholder:text-text-2 focus:outline-none focus:border-accent disabled:opacity-50 resize-none overflow-hidden"
                  style={{ minHeight: '32px', maxHeight: '100px' }}
                />
                {isProcessing ? (
                  <button
                    onClick={() => onStop?.()}
                    className="p-1.5 rounded-lg bg-danger text-white hover:bg-danger/80 transition-colors mb-0.5"
                    title="Stop"
                  >
                    <Square className="w-3.5 h-3.5 fill-current" />
                  </button>
                ) : (
                  <button
                    onClick={handleSubmit}
                    disabled={disabled || (!input.trim() && !attachment)}
                    className="p-1.5 rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-50 transition-colors mb-0.5">
                    <Send className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
      </div>
    </div>
  );
};
