import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Bot, CheckCircle, XCircle,
  Image as ImageIcon, Video, Volume2, FileText, Copy,
  Cpu, ChevronDown, Square, Pencil, Trash2, Check, X,
  Loader2,
} from 'lucide-react';
import type {
  ChatMessage, ActivityEntry, ResultAgent, PlanAgent,
  ImageApprovalStatus, AgentReviewStatus,
} from '../chatTypes';
import type { ChatSession } from '../ChatSidebar';
import { ModelPicker, PROVIDER_FAVICONS, getProvider, findModelName } from '../ModelPicker';
import type { ModelCatalogEntry } from '../ModelPicker';
import { withMediaToken } from '../../utils/media';
import MarkdownRenderer from '../MarkdownRenderer';

// ============================================================
// Props
// ============================================================

interface ChatWindowProps {
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
  onRejectImage?: (approvalId: string, feedback?: string) => void;
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
  onViewTasks?: () => void;
  uploadLimitMb?: number;
}

// ============================================================
// Helpers
// ============================================================

const relativeTime = (timestamp: string): string => {
  if (!timestamp) return '';
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  if (isNaN(then)) return '';
  const diff = now - then;
  const sec = Math.floor(diff / 1000);
  const min = Math.floor(sec / 60);
  const hour = Math.floor(min / 60);
  const day = Math.floor(hour / 24);
  if (day > 7) return new Date(timestamp).toLocaleDateString();
  if (day > 0) return `${day} day${day > 1 ? 's' : ''} ago`;
  if (hour > 0) return `${hour} hour${hour > 1 ? 's' : ''} ago`;
  if (min > 0) return `${min} minute${min > 1 ? 's' : ''} ago`;
  return 'just now';
};

const agentIcon = (name: string): string => {
  const n = name.toLowerCase();
  if (n.includes('analyst') || n.includes('product')) return '📊';
  if (n.includes('copy') || n.includes('writer')) return '✍️';
  if (n.includes('image') || n.includes('design') || n.includes('visual')) return '🎨';
  if (n.includes('seo') || n.includes('search')) return '🔍';
  if (n.includes('manager')) return '🧠';
  if (n.includes('video')) return '🎬';
  return '🤖';
};

const roleIcon = (role: string): string => {
  const r = role.toLowerCase();
  if (r.includes('analyst') || r.includes('product')) return '📊';
  if (r.includes('copy') || r.includes('writer')) return '✍️';
  if (r.includes('image') || r.includes('design')) return '🎨';
  if (r.includes('seo') || r.includes('search')) return '🔍';
  if (r.includes('manager')) return '🧠';
  return '🤖';
};

// ============================================================
// Sub-components
// ============================================================

const FeedUserMessage: React.FC<{ msg: ChatMessage }> = ({ msg }) => (
  <div className="feed-user">
    <MarkdownRenderer content={msg.content} />
    {(() => {
      const atts = msg.attachments || (msg.attachmentUrl ? [{ url: msg.attachmentUrl, name: msg.attachmentName || '', mime: msg.attachmentMime || '' }] : []);
      if (atts.length === 0) return null;
      return (
        <div style={{ marginTop: '6px' }}>
          {atts.map((att, i) => (
            <div key={i}>
              {att.mime?.startsWith('image/') ? (
                <img src={withMediaToken(att.url)} alt={att.name} style={{ maxWidth: '100%', borderRadius: '3px', display: 'block' }} />
              ) : att.mime?.startsWith('audio/') ? (
                <audio src={withMediaToken(att.url)} controls style={{ maxWidth: '100%' }} />
              ) : att.mime?.startsWith('video/') ? (
                <video src={withMediaToken(att.url)} controls style={{ maxWidth: '100%', borderRadius: '3px' }} />
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 8px', background: 'rgba(255,255,255,0.15)', borderRadius: '3px' }}>
                  <FileText size={14} />
                  <span style={{ fontSize: '11px' }}>{att.name || 'Attachment'}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      );
    })()}
  </div>
);

const FeedAgentMessage: React.FC<{ avatar: string; name: string; children: React.ReactNode; meta?: string }> = ({ avatar, name, children, meta }) => (
  <div className="feed-agent">
    <div className="fa-av">{avatar}</div>
    <div className="fa-bubble">
      <span className="fa-name">{name}</span>
      {children}
      {meta && <span className="fa-meta">{meta}</span>}
    </div>
  </div>
);

const FeedThinking: React.FC<{ model?: string }> = ({ model }) => (
  <div className="feed-thinking">
    <div className="ft-av">🧠</div>
    <div className="ft-bubble">
      <span className="dots"><span></span><span></span><span></span></span>
    </div>
  </div>
);

const FeedProgress: React.FC<{ label: string; onViewProgress?: () => void }> = ({ label, onViewProgress }) => (
  <div className="feed-progress">
    <span className="dots"><span></span><span></span><span></span></span>
    <span>{label}</span>
    {onViewProgress && (
      <button className="fe-btn sm" onClick={onViewProgress}>ดู progress</button>
    )}
  </div>
);

// Plan card with waves
const ChatPlanCard: React.FC<{
  msg: ChatMessage;
  onAccept?: () => void;
  onReject?: () => void;
  isPending?: boolean;
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
}> = ({
  msg, onAccept, onReject, isPending,
  onChangeAgentModel, onChangeManagerModel, onChangeMediaModel,
  modelCatalog, modelSearchResults, mediaCatalog, mediaSearchResults,
  onSearchModels, onFetchModelCatalog, onFetchMediaCatalog,
}) => {
  const agents = msg.planAgents || [];
  const [editingAgent, setEditingAgent] = useState<string | null>(null);
  const [editingMedia, setEditingMedia] = useState<string | null>(null);
  const agentModelRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const mediaModelRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const wave1 = agents.filter(a => !a.depends_on || a.depends_on.length === 0);
  const wave1Names = wave1.map(a => a.name);
  const wave2 = agents.filter(a => a.depends_on?.some(d => wave1Names.includes(d)) && !wave1Names.includes(a.name));
  const wave2Names = wave2.map(a => a.name);
  const wave3 = agents.filter(a => a.depends_on?.some(d => wave2Names.includes(d)) && !wave1Names.includes(a.name) && !wave2Names.includes(a.name));
  const remaining = agents.filter(a => !wave1Names.includes(a.name) && !wave2Names.includes(a.name) && !wave3.map(w => w.name).includes(a.name));

  const waves = [
    { label: 'Wave 1', agents: wave1 },
    { label: 'Wave 2', agents: wave2 },
    { label: 'Wave 3', agents: wave3 },
  ].filter(w => w.agents.length > 0);

  const planStatus = msg.planStatus || 'pending';
  const pending = planStatus === 'pending' && isPending;

  const hasImageTool = msg.hasImageTool;
  const hasVideoTool = msg.hasVideoTool;
  const hasSearchTool = msg.hasSearchTool;
  const hasTtsTool = msg.hasTtsTool;
  const hasSttTool = msg.hasSttTool;
  const hasVisionTool = msg.hasVisionTool;
  const hasVisionInput = msg.hasVisionInput;
  const hasMediaTools = hasImageTool || hasVideoTool || hasSearchTool || hasTtsTool || hasSttTool || hasVisionTool;

  const renderAgentModel = (agent: PlanAgent) => {
    const modelId = agent.model || '';
    const modelName = modelId ? findModelName(modelId, msg.hasVisionInput ? (mediaCatalog || {}) : (modelCatalog || {}), modelSearchResults || []) : 'Auto';
    if (!pending || !onChangeAgentModel) {
      return <span className="plan-model">{modelName}</span>;
    }
    return (
      <>
        <button
          ref={(el) => { agentModelRefs.current[agent.name] = el; }}
          className="plan-model"
          style={{ cursor: 'pointer', fontWeight: 600 }}
          onClick={() => {
            if (hasVisionInput) {
              if (mediaCatalog && !mediaCatalog['vision'] && onFetchMediaCatalog) onFetchMediaCatalog('vision');
            } else if (editingAgent !== agent.name && modelCatalog && Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) {
              onFetchModelCatalog();
            }
            setEditingAgent(editingAgent === agent.name ? null : agent.name);
          }}
        >
          {modelName}
        </button>
        {editingAgent === agent.name && (
          <ModelPicker
            recommended={hasVisionInput ? { vision: mediaCatalog?.['vision'] || [] } : (modelCatalog || {})}
            searchResults={modelSearchResults || []}
            selectedModel={modelId}
            onSelect={(mid) => { onChangeAgentModel(agent.name, mid); setEditingAgent(null); }}
            onSearch={onSearchModels || (() => {})}
            onClose={() => setEditingAgent(null)}
            anchorRef={{ current: agentModelRefs.current[agent.name] }}
            showAutoRouter={true}
          />
        )}
      </>
    );
  };

  const renderMediaModel = (label: string, mediaKey: string, modelId?: string, icon?: string, fetchKey?: string) => {
    if (!modelId && (!pending || !onChangeMediaModel)) return null;
    const modelName = modelId ? (findModelName(modelId, mediaCatalog || {}, mediaSearchResults || []) || modelId) : '';
    if (!pending || !onChangeMediaModel) {
      return <span className="plan-model">{icon} {label}: {modelName}</span>;
    }
    return (
      <>
        <button
          ref={(el) => { mediaModelRefs.current[mediaKey] = el; }}
          className="plan-model"
          style={{ cursor: 'pointer', fontWeight: 600 }}
          onClick={() => {
            if (editingMedia !== mediaKey && onFetchMediaCatalog && fetchKey) onFetchMediaCatalog(fetchKey);
            setEditingMedia(editingMedia === mediaKey ? null : mediaKey);
          }}
        >
          {icon} {label}{modelName ? `: ${modelName}` : ': เลือกโมเดล'}
        </button>
        {editingMedia === mediaKey && (
          <ModelPicker
            recommended={{ [fetchKey || mediaKey]: mediaCatalog?.[fetchKey || mediaKey] || [] }}
            searchResults={mediaSearchResults || []}
            selectedModel={modelId}
            onSelect={(mid) => { onChangeMediaModel(mediaKey as any, mid); setEditingMedia(null); }}
            onSearch={onSearchModels || (() => {})}
            onClose={() => setEditingMedia(null)}
            anchorRef={{ current: mediaModelRefs.current[mediaKey] }}
            showAutoRouter={false}
            isMediaPicker
          />
        )}
      </>
    );
  };

  const renderAgentChanges = (agent: PlanAgent) => {
    if (!agent.is_existing) return null;
    const changes: React.ReactNode[] = [];

    // Goal change
    if (agent.original_goal && agent.goal && agent.goal !== agent.original_goal) {
      changes.push(
        <div key="goal" style={{ fontSize: '10px', color: 'var(--ink2)', marginTop: '2px', marginLeft: '18px' }}>
          <span style={{ color: 'var(--amber)' }}>Goal เปลี่ยน:</span> {agent.goal.slice(0, 80)}{agent.goal.length > 80 ? '...' : ''}
        </div>
      );
    }

    // Tool changes
    const tools = agent.tools || [];
    const origTools = agent.original_tools || [];
    const added = tools.filter(t => !origTools.includes(t));
    const removed = origTools.filter(t => !tools.includes(t));
    if (added.length > 0 || removed.length > 0) {
      changes.push(
        <div key="tools" style={{ display: 'flex', flexWrap: 'wrap', gap: '3px', marginTop: '2px', marginLeft: '18px' }}>
          {added.map((tool, i) => (
            <span key={`a-${i}`} style={{ fontSize: '9px', padding: '1px 5px', borderRadius: '2px', border: '1px dashed rgba(100,120,200,0.3)', color: 'var(--blue, #6678aa)', background: 'rgba(100,120,200,0.05)' }}>+{tool}</span>
          ))}
          {removed.map((tool, i) => (
            <span key={`r-${i}`} style={{ fontSize: '9px', padding: '1px 5px', borderRadius: '2px', background: 'rgba(200,80,80,0.05)', color: 'rgba(200,80,80,0.5)', textDecoration: 'line-through' }}>{tool}</span>
          ))}
        </div>
      );
    }

    // Persona change
    if (agent.original_persona && agent.persona && agent.persona !== agent.original_persona) {
      changes.push(
        <div key="persona" style={{ fontSize: '10px', color: 'var(--ink2)', marginTop: '2px', marginLeft: '18px' }}>
          <span style={{ color: 'var(--amber)' }}>Persona เปลี่ยน</span>
        </div>
      );
    }

    return changes.length > 0 ? <>{changes}</> : null;
  };

  const renderAgentStep = (agent: PlanAgent, j: number) => (
    <div key={j} className="chat-plan-step" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', width: '100%' }}>
        <span className="cps-ic">{roleIcon(agent.role)}</span>
        <span style={{ fontWeight: 600, flexShrink: 0 }}>{agent.name}</span>
        {agent.is_existing ? (
          <span style={{ fontSize: '9px', padding: '1px 5px', borderRadius: '2px', background: 'rgba(100,160,80,0.15)', color: 'var(--green)', flexShrink: 0 }}>Existing</span>
        ) : (
          <span style={{ fontSize: '9px', padding: '1px 5px', borderRadius: '2px', background: 'rgba(200,146,32,0.1)', color: 'var(--amber)', flexShrink: 0 }}>New</span>
        )}
        {renderAgentModel(agent)}
      </div>
      <div style={{ fontSize: '10px', color: 'var(--ink2)', marginTop: '2px', marginLeft: '18px' }}>
        {agent.goal || agent.role}
      </div>
      {agent.task_description && agent.task_description !== agent.goal && (
        <div style={{ fontSize: '10px', color: 'var(--ink3)', marginTop: '2px', marginLeft: '18px' }}>
          {agent.task_description}
        </div>
      )}
      {agent.depends_on && agent.depends_on.length > 0 && (
        <div style={{ fontSize: '10px', color: 'var(--ink3)', marginTop: '2px', marginLeft: '18px' }}>
          Depends on: {agent.depends_on.join(', ')}
        </div>
      )}
      {renderAgentChanges(agent)}
    </div>
  );

  return (
    <div className="chat-plan">
      <div className="chat-plan-waves">
        {waves.map((wave, i) => (
          <div key={i} className="chat-plan-wave">
            <div className="cpw-label">{wave.label}</div>
            {wave.agents.map((agent, j) => renderAgentStep(agent, j))}
          </div>
        ))}
        {remaining.length > 0 && (
          <div className="chat-plan-wave">
            <div className="cpw-label">More</div>
            {remaining.map((agent, j) => renderAgentStep(agent, j))}
          </div>
        )}
      </div>
      {hasMediaTools && (
        <div className="plan-models">
          {hasImageTool && renderMediaModel('Image', 'imageModel', msg.imageModel, '🖼️', 'image')}
          {hasVideoTool && renderMediaModel('Video', 'videoModel', msg.videoModel, '🎬', 'video')}
          {hasTtsTool && renderMediaModel('TTS', 'ttsModel', msg.ttsModel, '🔊', 'tts')}
          {hasSttTool && renderMediaModel('STT', 'sttModel', msg.sttModel, '🎙️', 'stt')}
          {hasVisionTool && renderMediaModel('Vision', 'visionModel', msg.visionModel, '👁️', 'vision')}
        </div>
      )}
      <div className="chat-plan-meta">
        {agents.length} agents · {waves.length} waves
        {msg.planTaskDescription ? ` · ${msg.planTaskDescription}` : ''}
      </div>
      {planStatus === 'pending' && (
        (() => {
          const missingModels: string[] = [];
          if (hasImageTool && !msg.imageModel) missingModels.push('Image');
          if (hasVideoTool && !msg.videoModel) missingModels.push('Video');
          if (hasTtsTool && !msg.ttsModel) missingModels.push('TTS');
          if (hasSttTool && !msg.sttModel) missingModels.push('STT');
          if (hasVisionTool && !msg.visionModel) missingModels.push('Vision');
          const canApprove = missingModels.length === 0;
          return (
            <div className="chat-plan-actions">
              {missingModels.length > 0 && (
                <div style={{ fontSize: '10px', color: 'var(--red)', fontWeight: 600, padding: '4px 8px', marginBottom: '4px' }}>
                  กรุณาเลือกโมเดล: {missingModels.join(', ')}
                </div>
              )}
              <button className="cp-btn reject" onClick={onReject}>ปฏิเสธ</button>
              <button className="cp-btn approve" disabled={!canApprove} style={!canApprove ? { opacity: 0.4, cursor: 'not-allowed' } : {}} onClick={canApprove ? onAccept : undefined}>อนุมัติแผน</button>
            </div>
          );
        })()
      )}
      {planStatus === 'approved' && (
        <div className="chat-plan-actions">
          <span style={{ fontSize: '11px', color: 'var(--green)', fontWeight: 700, padding: '8px 14px' }}>✅ อนุมัติแล้ว</span>
        </div>
      )}
      {planStatus === 'rejected' && (
        <div className="chat-plan-actions">
          <span style={{ fontSize: '11px', color: 'var(--red)', fontWeight: 700, padding: '8px 14px' }}>❌ ปฏิเสธแล้ว</span>
        </div>
      )}
    </div>
  );
};

// Result card
const ResultCard: React.FC<{ msg: ChatMessage }> = ({ msg }) => {
  const isError = msg.resultError;
  const agents = msg.resultAgents || [];
  return (
    <>
      <div className="card" style={{ borderLeft: `4px solid ${isError ? 'var(--red)' : 'var(--green)'}` }}>
        <div className="card-hdr">
          {isError ? <XCircle size={14} style={{ color: 'var(--red)' }} /> : <CheckCircle size={14} style={{ color: 'var(--green)' }} />}
          <span>{isError ? 'Error' : 'Completed'}</span>
        </div>
        <div className="card-body">
          <MarkdownRenderer content={msg.resultSummary || 'Done'} />
        </div>
      </div>
      {agents.map((agent, i) => (
        <FeedAgentMessage key={i} avatar={agentIcon(agent.name)} name={agent.name}>
          <MarkdownRenderer content={agent.output} />
        </FeedAgentMessage>
      ))}
    </>
  );
};

// Image approval card
const ImageApprovalCard: React.FC<{
  msg: ChatMessage;
  onApprove?: (model?: string) => void;
  onReject?: (feedback?: string) => void;
  onRetry?: () => void;
}> = ({ msg, onApprove, onReject, onRetry }) => {
  const status = msg.approvalStatus as ImageApprovalStatus;
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectFeedback, setRejectFeedback] = useState('');
  // Dynamic labels based on media type — without this, all cards say 'Image' regardless of actual media type
  const mediaLabels: Record<string, { label: string; promptLabel: string }> = {
    image: { label: 'Image', promptLabel: 'Prompt สำหรับสร้างภาพ:' },
    video: { label: 'Video', promptLabel: 'Prompt สำหรับสร้างวิดีโอ:' },
    tts:   { label: 'Audio', promptLabel: 'ข้อความสำหรับสร้างเสียง:' },
    stt:   { label: 'Transcription', promptLabel: 'ไฟล์เสียง:' },
    vision: { label: 'Vision', promptLabel: 'คำถามสำหรับวิเคราะห์ภาพ:' },
  };
  const meta = mediaLabels[msg.mediaType || 'image'] || mediaLabels.image;
  if (status === 'approved') {
    return (
      <div className="card" style={{ borderLeft: '4px solid var(--green)' }}>
        <div className="card-hdr"><CheckCircle size={14} style={{ color: 'var(--green)' }} /> <span>{meta.label} Approved — กำลังสร้าง...</span></div>
        <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px' }}>
          <Loader2 size={14} className="animate-spin" style={{ color: 'var(--ink3)' }} />
          <span style={{ fontSize: '11px', color: 'var(--ink3)' }}>กรุณารอสักครู่...</span>
        </div>
      </div>
    );
  }
  if (status === 'generated') {
    // Merge: show generated image inline in the approval card — replaces separate ImageResultCard
    return (
      <div className="card" style={{ borderLeft: '4px solid var(--green)' }}>
        <div className="card-hdr">
          <ImageIcon size={14} style={{ color: 'var(--purple)' }} />
          <span>{meta.label} Result — {msg.agentName || 'Agent'}</span>
        </div>
        <div className="card-body">
          <div className="img-result">
            {msg.mediaType === 'video' ? (
              <video src={withMediaToken(msg.imageUrl)} controls style={{ maxWidth: '400px', width: '100%', border: '1px solid var(--line)', borderRadius: '8px' }} />
            ) : (
              <img src={withMediaToken(msg.imageUrl)} alt={msg.imagePrompt} style={{ maxWidth: '400px', width: '100%', border: '1px solid var(--line)', borderRadius: '8px' }} />
            )}
            <div className="ir-info">{msg.imagePrompt}</div>
            {msg.model && <div className="ir-info">🤖 {msg.model}</div>}
          </div>
        </div>
      </div>
    );
  }
  if (status === 'rejected') {
    return (
      <div className="card" style={{ borderLeft: '4px solid var(--red)' }}>
        <div className="card-hdr"><XCircle size={14} style={{ color: 'var(--red)' }} /> <span>{meta.label} Rejected</span></div>
      </div>
    );
  }
  return (
    <div className="card" style={{ borderLeft: '4px solid var(--red)', background: 'rgba(160,48,32,0.03)' }}>
      <div className="card-hdr">
        <ImageIcon size={14} style={{ color: 'var(--purple)' }} />
        <span>{meta.label} Approval — {msg.agentName || 'Agent'}</span>
      </div>
      <div className="card-body">
        {msg.imageError ? (
          <div style={{ color: 'var(--red)', fontSize: '11px' }}>⚠ {msg.imageError}</div>
        ) : (
          <div>
            <div style={{ fontSize: '10px', color: 'var(--ink3)', marginBottom: '4px' }}>{meta.promptLabel}</div>
            <div className="img-prompt" style={{ whiteSpace: 'pre-wrap', maxHeight: '120px', overflowY: 'auto' }}>{msg.imagePrompt || ''}</div>
          </div>
        )}
        {msg.model && (
          <div className="img-model-sel" style={{ marginBottom: '4px' }}>
            🤖 {msg.model}
            {msg.mediaType && <span style={{ marginLeft: '6px', color: 'var(--ink3)' }}>({msg.mediaType})</span>}
            {msg.duration ? <span style={{ marginLeft: '6px', color: 'var(--ink3)' }}>{msg.duration}s</span> : null}
          </div>
        )}
      </div>
      <div className="card-footer">
        {msg.imageError ? (
          <>
            <button className="btn btn-warm" onClick={onRetry}>🔄 Retry</button>
            {/* Dismiss — calls onReject to collapse card to minimal "Rejected" state.
                Without this, error cards with persistent API failures (e.g. xAI 520) stay stuck. */}
            <button className="btn btn-no" onClick={() => onReject?.()}>✕ Dismiss</button>
          </>
        ) : showRejectInput ? (
          <>
            <input
              type="text"
              placeholder="Feedback for agent (optional)..."
              value={rejectFeedback}
              onChange={e => setRejectFeedback(e.target.value)}
              style={{ flex: 1, fontSize: '10px', padding: '4px 6px', border: '1px solid var(--line)', borderRadius: '3px', background: 'var(--paper)', color: 'var(--ink)' }}
              autoFocus
              onKeyDown={e => {
                if (e.key === 'Enter') { onReject?.(rejectFeedback); }
                if (e.key === 'Escape') { setShowRejectInput(false); setRejectFeedback(''); }
              }}
            />
            <button className="btn btn-no" style={{ padding: '3px 8px', fontSize: '10px' }} onClick={() => onReject?.(rejectFeedback)}>Confirm Reject</button>
            <button className="btn" style={{ padding: '3px 8px', fontSize: '10px' }} onClick={() => { setShowRejectInput(false); setRejectFeedback(''); }}>Cancel</button>
          </>
        ) : (
          <>
            <button className="btn btn-no" onClick={() => setShowRejectInput(true)}>❌ Reject</button>
            <button className="btn btn-yes" onClick={() => onApprove?.()}>✓ Generate</button>
          </>
        )}
      </div>
    </div>
  );
};

// Batch media approval panel — groups consecutive image_approval messages when there are 2+
// Shows Approve All / Reject All for pending items, with collapsible per-item details
const MediaApprovalPanel: React.FC<{
  messages: ChatMessage[];
  onApprove?: (approvalId: string, model?: string) => void;
  onReject?: (approvalId: string, feedback?: string) => void;
  onRetry?: (approvalId: string) => void;
}> = ({ messages, onApprove, onReject, onRetry }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [zoom, setZoom] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectFeedback, setRejectFeedback] = useState('');
  const mediaLabels: Record<string, string> = {
    image: 'Image', video: 'Video', tts: 'Audio', stt: 'Transcription', vision: 'Vision',
  };

  const pending = messages.filter(m => m.approvalStatus === 'pending' || m.approvalStatus === 'error');
  const generated = messages.filter(m => m.approvalStatus === 'generated');
  const approved = messages.filter(m => m.approvalStatus === 'approved');
  const rejected = messages.filter(m => m.approvalStatus === 'rejected');

  const summaryParts: string[] = [];
  if (pending.length) summaryParts.push(`${pending.length} pending`);
  if (approved.length) summaryParts.push(`${approved.length} generating`);
  if (generated.length) summaryParts.push(`${generated.length} done`);
  if (rejected.length) summaryParts.push(`${rejected.length} rejected`);

  const handleApproveAll = () => {
    pending.forEach(m => onApprove?.(m.approvalId || '', m.model));
  };
  const handleRejectAll = () => {
    const feedback = window.prompt('Feedback for all rejected items (optional):') || '';
    pending.forEach(m => onReject?.(m.approvalId || '', feedback));
  };

  return (
    <>
    {zoom && (
      <div className="tw-lightbox" onClick={() => setZoom(null)}>
        {zoom.includes('.mp4') || zoom.includes('.webm') ? (
          <video src={zoom} controls autoPlay style={{ maxWidth: '90vw', maxHeight: '90vh' }} />
        ) : (
          <img src={zoom} alt="Zoomed" />
        )}
      </div>
    )}
    <div className="tw-map">
      {/* Header */}
      <div className="tw-map-hdr" onClick={() => setCollapsed(!collapsed)}>
        <ImageIcon size={14} style={{ color: 'var(--purple)', flexShrink: 0 }} />
        <span style={{ fontWeight: 600, flexShrink: 0 }}>Media Approvals ({messages.length})</span>
        <span className="tw-map-summary">{summaryParts.join(' · ')}</span>
        <ChevronDown size={14} style={{ marginLeft: 'auto', transform: collapsed ? 'rotate(-90deg)' : '', transition: 'transform .15s', flexShrink: 0 }} />
      </div>

      {/* Batch actions — only when there are pending items */}
      {pending.length > 0 && (
        <div className="tw-map-actions">
          <button className="btn btn-yes" onClick={handleApproveAll}>✓ Approve All ({pending.length})</button>
          <button className="btn btn-no" onClick={handleRejectAll}>❌ Reject All</button>
        </div>
      )}

      {/* Item list — collapsible */}
      {!collapsed && (
        <div className="tw-map-list">
          {messages.map((msg, i) => {
            const status = msg.approvalStatus as ImageApprovalStatus;
            const label = mediaLabels[msg.mediaType || 'image'] || 'Image';

            if (status === 'approved') {
              return (
                <div key={msg.id} className="tw-map-item approved">
                  <Loader2 size={12} className="animate-spin" style={{ color: 'var(--ink3)', flexShrink: 0 }} />
                  <span style={{ fontSize: '11px', color: 'var(--ink3)' }}>#{i + 1} {label} — Generating...</span>
                </div>
              );
            }
            if (status === 'generated') {
              return (
                <div key={msg.id} className="tw-map-item generated">
                  <div className="tw-map-thumb" onClick={() => setZoom(withMediaToken(msg.imageUrl) || '')} style={{ cursor: 'pointer' }}>
                    {msg.mediaType === 'video' ? (
                      <video src={withMediaToken(msg.imageUrl)} muted style={{ width: '100%', height: '100%', objectFit: 'cover', pointerEvents: 'none' }} />
                    ) : (
                      <img src={withMediaToken(msg.imageUrl)} alt={msg.imagePrompt} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    )}
                  </div>
                  <div className="tw-map-info">
                    <div className="tw-map-item-title">#{i + 1} {label} — {msg.agentName || 'Agent'} ✓</div>
                    <div className="tw-map-prompt" title={msg.imagePrompt}>{msg.imagePrompt}</div>
                    {msg.model && <div className="tw-map-model">🤖 {msg.model}</div>}
                  </div>
                </div>
              );
            }
            if (status === 'rejected') {
              return (
                <div key={msg.id} className="tw-map-item rejected">
                  <XCircle size={14} style={{ color: 'var(--red)', flexShrink: 0 }} />
                  <span style={{ fontSize: '11px', color: 'var(--ink3)' }}>#{i + 1} {label} — Rejected</span>
                </div>
              );
            }
            // pending or error
            return (
              <div key={msg.id} className="tw-map-item pending">
                <div className="tw-map-info">
                  <div className="tw-map-item-title">#{i + 1} {label} — {msg.agentName || 'Agent'}</div>
                  {msg.imageError ? (
                    <div style={{ color: 'var(--red)', fontSize: '11px' }}>⚠ {msg.imageError}</div>
                  ) : (
                    <div className="tw-map-prompt" title={msg.imagePrompt}>{msg.imagePrompt}</div>
                  )}
                  {msg.model && <div className="tw-map-model">🤖 {msg.model}{msg.mediaType ? ` (${msg.mediaType})` : ''}{msg.duration ? ` · ${msg.duration}s` : ''}</div>}
                </div>
                <div className="tw-map-item-actions">
                  {msg.imageError ? (
                    <>
                      <button className="btn btn-warm" style={{ padding: '2px 8px', fontSize: '10px' }} onClick={() => onRetry?.(msg.approvalId || '')}>🔄 Retry</button>
                      {/* Dismiss — collapses stuck error items without retrying failed API */}
                      <button className="btn btn-no" style={{ padding: '2px 8px', fontSize: '10px' }} onClick={() => onReject?.(msg.approvalId || '')}>✕</button>
                    </>
                  ) : (
                    <>
                      <button className="btn btn-no" style={{ padding: '2px 8px', fontSize: '10px' }} onClick={() => { setRejectingId(msg.approvalId || ''); setRejectFeedback(''); }}>❌</button>
                      <button className="btn btn-yes" style={{ padding: '2px 8px', fontSize: '10px' }} onClick={() => onApprove?.(msg.approvalId || '', msg.model)}>✓</button>
                    </>
                  )}
                  {rejectingId === msg.approvalId && (
                    <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '4px', alignItems: 'center', marginTop: '4px' }}>
                      <input
                        type="text"
                        placeholder="Feedback (optional)..."
                        value={rejectFeedback}
                        onChange={e => setRejectFeedback(e.target.value)}
                        style={{ flex: 1, fontSize: '10px', padding: '3px 6px', border: '1px solid var(--line)', borderRadius: '3px', background: 'var(--paper)', color: 'var(--ink)' }}
                        autoFocus
                        onKeyDown={e => {
                          if (e.key === 'Enter') { onReject?.(msg.approvalId || '', rejectFeedback); setRejectingId(null); }
                          if (e.key === 'Escape') { setRejectingId(null); setRejectFeedback(''); }
                        }}
                      />
                      <button className="btn btn-no" style={{ padding: '2px 8px', fontSize: '10px' }} onClick={() => { onReject?.(msg.approvalId || '', rejectFeedback); setRejectingId(null); }}>Confirm</button>
                      <button className="btn" style={{ padding: '2px 8px', fontSize: '10px' }} onClick={() => { setRejectingId(null); setRejectFeedback(''); }}>Cancel</button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
    </>
  );
};

// Image result card
const ImageResultCard: React.FC<{
  msg: ChatMessage;
  onEditPrompt?: (approvalId: string, newPrompt: string) => void;
}> = ({ msg, onEditPrompt }) => {
  const [editing, setEditing] = useState(false);
  const [newPrompt, setNewPrompt] = useState(msg.imagePrompt || '');

  return (
    <div className="card">
      <div className="card-hdr">
        <ImageIcon size={14} style={{ color: 'var(--purple)' }} />
        <span>{(msg.mediaType === 'video' ? 'Video' : msg.mediaType === 'tts' ? 'Audio' : msg.mediaType === 'stt' ? 'Transcription' : msg.mediaType === 'vision' ? 'Vision' : 'Image')} Result — {msg.agentName || 'Agent'}</span>
      </div>
      <div className="card-body">
        <div className="img-result">
          {msg.mediaType === 'video' ? (
            <video src={withMediaToken(msg.imageUrl)} controls style={{ maxWidth: '400px', width: '100%', border: '1px solid var(--line)', borderRadius: '8px' }} />
          ) : (
            <img src={withMediaToken(msg.imageUrl)} alt={msg.imagePrompt} style={{ maxWidth: '400px', width: '100%', border: '1px solid var(--line)', borderRadius: '8px' }} />
          )}
          <div className="ir-info">{msg.imagePrompt}</div>
          {msg.model && <div className="ir-info">🤖 {msg.model}</div>}
          <div className="ir-actions">
            {editing ? (
              <>
                <input
                  type="text"
                  value={newPrompt}
                  onChange={e => setNewPrompt(e.target.value)}
                  style={{ flex: 1, fontSize: '10px', padding: '4px 6px', border: '1px solid var(--line)', borderRadius: '3px', background: 'var(--paper)', color: 'var(--ink)' }}
                />
                <button className="btn btn-yes" style={{ padding: '3px 8px', fontSize: '10px' }} onClick={() => { onEditPrompt?.(msg.approvalId || '', newPrompt); setEditing(false); }}>Save</button>
                <button className="btn btn-no" style={{ padding: '3px 8px', fontSize: '10px' }} onClick={() => setEditing(false)}>Cancel</button>
              </>
            ) : (
              <button className="btn btn-no" style={{ padding: '3px 10px', fontSize: '10px' }} onClick={() => setEditing(true)}>✏️ Edit Prompt</button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Agent review card
const AgentReviewCard: React.FC<{
  msg: ChatMessage;
  onApprove?: () => void;
  onReject?: (feedback: string) => void;
}> = ({ msg, onApprove, onReject }) => {
  const [feedback, setFeedback] = useState('');
  const [showReject, setShowReject] = useState(false);
  const status = (msg.reviewStatus || 'pending') as AgentReviewStatus;

  if (status === 'approved') {
    return (
      <div className="card" style={{ borderLeft: '4px solid var(--green)' }}>
        <div className="card-hdr"><CheckCircle size={14} style={{ color: 'var(--green)' }} /> <span>Approved — {msg.agentName}</span></div>
      </div>
    );
  }
  if (status === 'rejected') {
    return (
      <div className="card" style={{ borderLeft: '4px solid var(--red)' }}>
        <div className="card-hdr"><XCircle size={14} style={{ color: 'var(--red)' }} /> <span>Rejected — {msg.agentName}</span></div>
      </div>
    );
  }

  return (
    <div className="card" style={{ borderLeft: '4px solid var(--blue)' }}>
      <div className="card-hdr">
        <span>🧠 Agent Review — {msg.agentName}</span>
        <span className="ch-badge">{msg.agentRole}</span>
      </div>
      <div className="card-body">
        <div className="review-output">{msg.content}</div>
        {showReject && (
          <div className="review-feedback" style={{ marginTop: '6px' }}>
            <textarea
              placeholder="Feedback for re-run..."
              value={feedback}
              onChange={e => setFeedback(e.target.value)}
            />
          </div>
        )}
      </div>
      <div className="card-footer">
        {showReject ? (
          <>
            <button className="btn btn-no" onClick={() => setShowReject(false)}>Cancel</button>
            <button className="btn btn-warm" onClick={() => onReject?.(feedback)}>Send Back</button>
          </>
        ) : (
          <>
            <button className="btn btn-no" onClick={() => setShowReject(true)}>✕ Send Back</button>
            <button className="btn btn-yes" onClick={onApprove}>✓ Approve</button>
          </>
        )}
      </div>
    </div>
  );
};

// Tuning proposal card
const TuningCard: React.FC<{
  msg: ChatMessage;
  onConfirm?: (proposals?: any[]) => void;
  onReject?: () => void;
}> = ({ msg, onConfirm, onReject }) => {
  const proposals = msg.tuningProposals || [];
  const status = msg.tuningStatus;

  return (
    <div className="card" style={{ borderLeft: '4px solid var(--amber)' }}>
      <div className="card-hdr"><span>📝 ปรับแต่ง Agent</span></div>
      <div className="card-body">
        {proposals.map((proposal, pi) => (
          <div key={pi} style={{ marginBottom: '8px' }}>
            <div className="ti-agent">{proposal.agent_name}</div>
            {proposal.changes.map((change: any, ci: number) => (
              <div key={ci} className="tuning-item">
                <div className="ti-change">
                  <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--ink2)' }}>{change.field}:</span>
                  <span className="ti-old">{Array.isArray(change.old_value) ? change.old_value.join(', ') || '(empty)' : change.old_value || '(empty)'}</span>
                  <span className="ti-arrow">→</span>
                  <span className="ti-new">{Array.isArray(change.new_value) ? change.new_value.join(', ') : change.new_value}</span>
                </div>
                <div className="ti-reason">{change.reason}</div>
              </div>
            ))}
          </div>
        ))}
        {status === 'confirmed' && <div style={{ fontSize: '11px', color: 'var(--green)', fontWeight: 600 }}>✅ ยืนยันแล้ว</div>}
        {status === 'rejected' && <div style={{ fontSize: '11px', color: 'var(--red)', fontWeight: 600 }}>❌ ปฏิเสธแล้ว</div>}
        {!status && (
          <div className="card-footer" style={{ padding: '6px 0', borderTop: 'none' }}>
            <button className="btn btn-no" onClick={onReject}>ปฏิเสธ</button>
            <button className="btn btn-yes" onClick={() => onConfirm?.(proposals)}>ยืนยัน</button>
          </div>
        )}
      </div>
    </div>
  );
};

// Audio result
const AudioResultCard: React.FC<{ msg: ChatMessage }> = ({ msg }) => (
  <div className="media-result">
    <div className="mr-hdr">🔊 Audio — {msg.agentName || 'Agent'}</div>
    <div className="mr-body">
      {msg.audioPrompt && <div style={{ fontSize: '10px', color: 'var(--ink3)', fontStyle: 'italic', marginBottom: '4px' }}>"{msg.audioPrompt}"</div>}
      <audio controls src={withMediaToken(msg.audioUrl)} style={{ width: '100%', height: '32px' }} />
      <div className="mr-info">
        {msg.agentName && <span>Agent: {msg.agentName}</span>}
        {msg.model && <span>Model: {msg.model}</span>}
      </div>
    </div>
  </div>
);

// Transcription result
const TranscriptionCard: React.FC<{ msg: ChatMessage }> = ({ msg }) => (
  <div className="media-result">
    <div className="mr-hdr">🎤 Transcription — {msg.agentName || 'Agent'}</div>
    <div className="mr-body">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--ink2)' }}>Transcription</span>
        <button
          style={{ fontSize: '9px', color: 'var(--orange)', cursor: 'pointer', background: 'none', border: 'none', display: 'flex', alignItems: 'center', gap: '2px' }}
          onClick={() => navigator.clipboard.writeText(msg.transcriptionText || '')}
        >
          <Copy size={10} /> Copy
        </button>
      </div>
      <div style={{ fontSize: '11px', color: 'var(--ink)', whiteSpace: 'pre-wrap' }}>{msg.transcriptionText}</div>
      <div className="mr-info">
        {msg.agentName && <span>Agent: {msg.agentName}</span>}
        {msg.model && <span>Model: {msg.model}</span>}
      </div>
    </div>
  </div>
);

// Video result
const VideoResultCard: React.FC<{ msg: ChatMessage }> = ({ msg }) => (
  <div className="media-result">
    <div className="mr-hdr">🎬 Video — {msg.agentName || 'Agent'}</div>
    <div className="mr-body">
      {msg.videoPrompt && <div style={{ fontSize: '10px', color: 'var(--ink3)', fontStyle: 'italic', marginBottom: '4px' }}>"{msg.videoPrompt}"</div>}
      <video controls src={withMediaToken(msg.videoUrl)} style={{ width: '100%', borderRadius: '3px' }} />
      <div className="mr-info">
        {msg.agentName && <span>Agent: {msg.agentName}</span>}
        {msg.model && <span>Model: {msg.model}</span>}
      </div>
    </div>
  </div>
);

// File result
const FileResultCard: React.FC<{ msg: ChatMessage }> = ({ msg }) => (
  <div className="media-result">
    <div className="mr-hdr">📎 File — {msg.agentName || 'Agent'}</div>
    <div className="mr-file">
      <a href={withMediaToken(msg.fileUrl)} download={msg.fileName} style={{ display: 'flex', alignItems: 'center', gap: '6px', textDecoration: 'none', color: 'var(--blue)' }}>
        <FileText size={18} />
        <div>
          <div className="mr-file-n">{msg.fileName || 'Download file'}</div>
          {msg.fileMime && <div className="mr-file-t">{msg.fileMime}</div>}
        </div>
      </a>
    </div>
    {msg.agentName && <div className="mr-info"><span>Agent: {msg.agentName}</span></div>}
  </div>
);

// ============================================================
// Main ChatWindow Component
// ============================================================

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages, activityLog, isProcessing, chatSessions, activeSessionId,
  onSend, onStop, onNewChat, onSwitchChat, onRenameChat, onDeleteChat,
  onAcceptPlan, onRejectPlan, onConfirmTuning, onRejectTuning,
  onApproveImage, onRejectImage, onRetryImage, onEditImagePrompt,
  onApproveAgentResult, onRejectAgentResult,
  onFetchModelCatalog, onFetchMediaCatalog, onSearchModels, onSelectModel,
  onChangeAgentModel, onChangeManagerModel, onChangeMediaModel,
  selectedModel, resolvedModel, thinkingText, thinkingDuration, isThinking,
  inputMode, onModeChange, disabled,
  preloadedModelCatalog, preloadedModelSearchResults,
  preloadedMediaCatalog, preloadedMediaSearchResults,
  onViewTasks,
  uploadLimitMb = 500, // Default until backend sends actual value via model catalog
}) => {
  const [input, setInput] = useState('');
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
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
  const inputBarRef = useRef<HTMLDivElement>(null);

  const [sidebarWidth, setSidebarWidth] = useState(140);
  const sidebarResizeRef = useRef<HTMLDivElement>(null);

  const handleSidebarResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = sidebarWidth;
    const onMove = (ev: MouseEvent) => {
      const newWidth = Math.max(100, Math.min(300, startWidth + ev.clientX - startX));
      setSidebarWidth(newWidth);
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [sidebarWidth]);

  // Auto-scroll
  const handleScroll = useCallback(() => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      isNearBottomRef.current = scrollHeight - scrollTop - clientHeight < 100;
    }
  }, []);

  useEffect(() => {
    if (scrollRef.current && isNearBottomRef.current) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.messageType === 'model_catalog') return;
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, activityLog, isProcessing]);

  // Process model_catalog messages
  useEffect(() => {
    const textCatalogMsgs = messages.filter(
      m => m.messageType === 'model_catalog' && m.modelCatalogRecommended && (m.catalogType || 'text') === 'text'
    );
    if (textCatalogMsgs.length > 0) {
      const latest = textCatalogMsgs[textCatalogMsgs.length - 1];
      setModelCatalog(latest.modelCatalogRecommended!);
      setModelSearchResults(latest.modelCatalogSearchResults || []);
    }
    const mediaCatalogMsgs = messages.filter(
      m => m.messageType === 'model_catalog' && m.modelCatalogRecommended && m.catalogType === 'media'
    );
    if (mediaCatalogMsgs.length > 0) {
      const merged: Record<string, any[]> = {};
      const mergedSearch: any[] = [];
      for (const msg of mediaCatalogMsgs) {
        const rec = msg.modelCatalogRecommended!;
        for (const [provider, models] of Object.entries(rec)) {
          if (!merged[provider]) merged[provider] = [];
          for (const model of models) {
            if (!merged[provider].some(m => m.id === model.id)) merged[provider].push(model);
          }
        }
        mergedSearch.push(...(msg.modelCatalogSearchResults || []));
      }
      setMediaCatalog(merged);
      setMediaSearchResults(mergedSearch);
    }
  }, [messages]);

  // Use preloaded catalog data
  useEffect(() => {
    if (preloadedModelCatalog && Object.keys(preloadedModelCatalog).length > 0) {
      setModelCatalog(prev => Object.keys(prev).length > 0 ? prev : preloadedModelCatalog);
    }
    if (preloadedModelSearchResults && preloadedModelSearchResults.length > 0) {
      setModelSearchResults(prev => prev.length > 0 ? prev : preloadedModelSearchResults);
    }
    if (preloadedMediaCatalog) {
      setMediaCatalog(preloadedMediaCatalog);
    }
    if (preloadedMediaSearchResults) {
      setMediaSearchResults(preloadedMediaSearchResults);
    }
  }, [preloadedModelCatalog, preloadedModelSearchResults, preloadedMediaCatalog, preloadedMediaSearchResults]);

  const handleOpenModelPicker = () => {
    if (modelPickerOpen) { setModelPickerOpen(false); return; }
    if (Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) onFetchModelCatalog();
    setModelPickerOpen(true);
  };

  const handleSearchModels = (query: string) => { onSearchModels?.(query); };
  const handleSelectModel = (modelId: string) => { onSelectModel?.(modelId); setModelPickerOpen(false); };

  const handleSubmit = async () => {
    if ((!input.trim() && attachments.length === 0) || disabled) return;
    await onSend(input.trim(), attachments.length > 0 ? attachments : undefined);
    setInput('');
    setAttachments([]);
    setAttachmentPreviews([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 80) + 'px';
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const newAtt: Array<{ url: string; name: string; mime: string }> = [];
    const newPrev: Array<string> = [];
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
            // Warn but don't block — user may intend for an agent to process the file
            console.warn(`[Upload] Model '${selectedModel}' may not support ${modality} input (file: ${file.name})`);
            // Show non-blocking warning (not alert, to allow multiple files)
            const warningDiv = document.createElement('div');
            warningDiv.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#f59e0b;color:#fff;padding:10px 16px;border-radius:8px;font-size:13px;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.3);max-width:400px;';
            warningDiv.textContent = `⚠️ โมเดล '${selectedModel}' อาจไม่รองรับไฟล์ ${modality} (${file.name}) — แนะนำให้เปลี่ยนโมเดลหรือสร้าง Agent ถอดเสียง`;
            document.body.appendChild(warningDiv);
            setTimeout(() => warningDiv.remove(), 5000);
            break; // One warning is enough
          }
        }
      }
    }

    for (let i = 0; i < total; i++) {
      const file = files[i];
      if (file.size > uploadLimitMb * 1024 * 1024) { alert(`File "${file.name}" too large. Maximum ${uploadLimitMb}MB.`); processed++; continue; }
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        newAtt.push({ url: dataUrl, name: file.name, mime: file.type || 'application/octet-stream' });
        if (file.type.startsWith('image/')) newPrev.push(dataUrl);
        else if (file.type.startsWith('audio/')) newPrev.push('audio');
        else if (file.type.startsWith('video/')) newPrev.push('video');
        else newPrev.push('file');
        processed++;
        if (processed === total) {
          setAttachments(prev => [...prev, ...newAtt]);
          setAttachmentPreviews(prev => [...prev, ...newPrev]);
        }
      };
      reader.readAsDataURL(file);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
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

  const startEditSession = (id: string, title: string) => { setEditingSessionId(id); setEditTitle(title); };
  const confirmEditSession = () => {
    if (editingSessionId && editTitle.trim()) onRenameChat(editingSessionId, editTitle.trim());
    setEditingSessionId(null); setEditTitle('');
  };

  // Render messages — groups consecutive image_approval messages into a batch panel when there are 2+
  const renderMessages = () => {
    const result: React.ReactNode[] = [];
    let i = 0;
    while (i < messages.length) {
      const msg = messages[i];
      if (msg.messageType === 'image_approval') {
        // Collect consecutive image_approval messages into a group
        const group: ChatMessage[] = [];
        while (i < messages.length && messages[i].messageType === 'image_approval') {
          group.push(messages[i]);
          i++;
        }
        if (group.length === 1) {
          // Single approval — render as individual card (same as before)
          const m = group[0];
          result.push(
            <ImageApprovalCard
              key={m.id} msg={m}
              onApprove={(model) => onApproveImage?.(m.approvalId || '', model)}
              onReject={(feedback) => onRejectImage?.(m.approvalId || '', feedback)}
              onRetry={() => onRetryImage?.(m.approvalId || '')}
            />
          );
        } else {
          // 2+ approvals — render as batch panel
          result.push(
            <MediaApprovalPanel
              key={group[0].id} messages={group}
              onApprove={(id, model) => onApproveImage?.(id, model)}
              onReject={(id, feedback) => onRejectImage?.(id, feedback)}
              onRetry={(id) => onRetryImage?.(id)}
            />
          );
        }
      } else {
        result.push(renderMessage(msg));
        i++;
      }
    }
    return result;
  };

  // Render messages
  const renderMessage = (msg: ChatMessage) => {
    const msgType = msg.messageType || 'text';

    if (msgType === 'plan' && msg.planAgents) {
      return (
        <ChatPlanCard
          key={msg.id} msg={msg}
          onAccept={onAcceptPlan} onReject={onRejectPlan}
          isPending={!disabled}
          onChangeAgentModel={onChangeAgentModel}
          onChangeManagerModel={onChangeManagerModel}
          onChangeMediaModel={onChangeMediaModel}
          modelCatalog={modelCatalog}
          modelSearchResults={modelSearchResults}
          mediaCatalog={mediaCatalog}
          mediaSearchResults={mediaSearchResults}
          onSearchModels={onSearchModels}
          onFetchModelCatalog={onFetchModelCatalog}
          onFetchMediaCatalog={onFetchMediaCatalog}
        />
      );
    }
    // Progress card — shows live progress during execution.
    // Previously return null to fix "stuck at กำลังเริ่มทำงาน..." bug, but the real fix
    // is updating progress via reply_progress() in orchestrator as agents complete.
    if (msgType === 'progress') {
      return <FeedProgress key={msg.id} label={msg.progressLabel || 'กำลังทำงาน...'} onViewProgress={onViewTasks} />;
    }
    // agent_progress updates go to Storyboard only — not shown as chat bubbles
    if (msgType === 'agent_progress') {
      return null;
    }
    // return null — result card duplicates agent bubbles in chat;
    // result data goes to Storyboard/TasksWindow only (reply_result is persist-only)
    if (msgType === 'result') {
      return null;
    }
    if (msgType === 'image_approval') {
      return (
        <ImageApprovalCard
          key={msg.id} msg={msg}
          onApprove={(model) => onApproveImage?.(msg.approvalId || '', model)}
          onReject={() => onRejectImage?.(msg.approvalId || '')}
          onRetry={() => onRetryImage?.(msg.approvalId || '')}
        />
      );
    }
    if (msgType === 'image_result') {
      // image_result is merged into image_approval card by App.tsx (updates approvalStatus to 'generated')
      // — return null to avoid duplicate card. The MediaApprovalPanel shows generated results inline.
      return null;
    }
    if (msgType === 'model_catalog') { return null; }
    if (msgType === 'agent_review') {
      return (
        <AgentReviewCard
          key={msg.id} msg={msg}
          onApprove={() => onApproveAgentResult?.(msg.reviewId || '')}
          onReject={(feedback) => onRejectAgentResult?.(msg.reviewId || '', feedback)}
        />
      );
    }
    if (msgType === 'tuning_proposal' && msg.tuningProposals) {
      return <TuningCard key={msg.id} msg={msg} onConfirm={onConfirmTuning} onReject={onRejectTuning} />;
    }
    if (msgType === 'audio_result') { return <AudioResultCard key={msg.id} msg={msg} />; }
    if (msgType === 'transcription_result') { return <TranscriptionCard key={msg.id} msg={msg} />; }
    if (msgType === 'video_result') { return <VideoResultCard key={msg.id} msg={msg} />; }
    if (msgType === 'file_result') { return <FileResultCard key={msg.id} msg={msg} />; }
    if (msgType === 'thinking' || msgType === 'thinking_done') { return null; }

    // Default: text message
    if (msg.role === 'user') {
      return <FeedUserMessage key={msg.id} msg={msg} />;
    }
    return (
      <FeedAgentMessage key={msg.id} avatar={agentIcon(msg.agentName || 'Manager')} name={msg.agentName || 'Manager'}>
        <MarkdownRenderer content={msg.content || ''} />
      </FeedAgentMessage>
    );
  };

  return (
    <div className="chat-body">
      {/* Session sidebar */}
      <div className="chat-sessions" style={{ width: sidebarWidth }}>
        <div className="cs-header">Sessions</div>
        <div className="cs-new" onClick={onNewChat}>+ New Session</div>
        <div className="cs-list">
          {chatSessions.length === 0 ? (
            <div style={{ fontSize: '10px', color: 'var(--ink3)', padding: '8px 10px', textAlign: 'center' }}>No chats yet</div>
          ) : (
            chatSessions.map(s => (
              <div
                key={s.id}
                className={`cs-item ${activeSessionId === s.id ? 'active' : ''}`}
                onClick={() => editingSessionId !== s.id && onSwitchChat(s.id)}
              >
                {editingSessionId === s.id ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', overflow: 'hidden', width: '100%' }}>
                    <input
                      type="text" value={editTitle}
                      onChange={e => setEditTitle(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') { e.stopPropagation(); confirmEditSession(); }
                        if (e.key === 'Escape') { e.stopPropagation(); setEditingSessionId(null); setEditTitle(''); }
                      }}
                      autoFocus
                      style={{ flex: 1, minWidth: 0, fontSize: '11px', padding: '2px 4px', border: '1px solid var(--line)', borderRadius: '3px', background: 'var(--paper)', color: 'var(--ink)' }}
                    />
                    <button onClick={e => { e.stopPropagation(); confirmEditSession(); }} style={{ color: 'var(--green)', cursor: 'pointer', background: 'none', border: 'none' }}><Check size={12} /></button>
                    <button onClick={e => { e.stopPropagation(); setEditingSessionId(null); setEditTitle(''); }} style={{ color: 'var(--ink3)', cursor: 'pointer', background: 'none', border: 'none' }}><X size={12} /></button>
                  </div>
                ) : (
                  <>
                    <div className="cs-name">{s.title}</div>
                    <div className="cs-preview">{relativeTime(s.updated_at)}</div>
                    <div style={{ display: 'flex', gap: '4px', marginTop: '2px', opacity: 0.6 }}>
                      <button onClick={e => { e.stopPropagation(); startEditSession(s.id, s.title); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink3)' }}><Pencil size={10} /></button>
                      <button onClick={e => { e.stopPropagation(); if (confirm('Delete this chat?')) { onDeleteChat(s.id); } }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink3)' }}><Trash2 size={10} /></button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </div>
      {/* Sidebar resize handle */}
      <div
        ref={sidebarResizeRef}
        onMouseDown={handleSidebarResizeStart}
        style={{
          width: '4px',
          cursor: 'col-resize',
          background: 'transparent',
          flexShrink: 0,
          position: 'relative',
          zIndex: 5,
        }}
      >
        <div style={{ position: 'absolute', inset: '0 1px', background: 'var(--line)', opacity: 0.3 }} />
      </div>

      {/* Chat area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 200, minHeight: 0 }}>
        {/* Feed */}
        <div ref={scrollRef} onScroll={handleScroll} className="chat-feed">
          {messages.length === 0 && activityLog.length === 0 && !isProcessing ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--ink3)' }}>
              <Bot size={40} style={{ opacity: 0.3, marginBottom: '8px' }} />
              <span style={{ fontSize: '13px' }}>No conversation yet</span>
              <span style={{ fontSize: '11px', marginTop: '2px' }}>Type a message below to start</span>
            </div>
          ) : (
            <>
              {renderMessages()}

              {/* Activity log */}
              {(activityLog.length > 0 || isProcessing) && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingLeft: '40px' }}>
                  {activityLog.map(entry => (
                    <div key={entry.id} className="feed-event system">
                      <span className="fe-ic">{entry.status === 'current' ? '⏳' : '✓'}</span>
                      <div className="fe-body"><div className="fe-title">{entry.text}</div></div>
                    </div>
                  ))}
                </div>
              )}

              {/* Thinking indicator */}
              {isThinking && !messages.some(m => m.messageType === 'plan' && m.planStatus === 'pending') && (
                <FeedThinking model={resolvedModel} />
              )}
            </>
          )}
        </div>

        {/* Input bar */}
        <div ref={inputBarRef} className="chat-input">
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
          {/* Model status + mode toggle */}
          <div className="ci-top">
            <button className="ci-model" onClick={handleOpenModelPicker} disabled={disabled}>
              {(() => {
                const modelId = selectedModel || resolvedModel || '';
                const provider = getProvider(modelId);
                const favicon = PROVIDER_FAVICONS[provider];
                if (favicon) return <img src={favicon} alt="" style={{ width: '12px', height: '12px', borderRadius: '2px', objectFit: 'contain' }} onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                return <Cpu size={12} />;
              })()}
              {selectedModel ? (
                <>
                  <span>{findModelName(selectedModel, modelCatalog, modelSearchResults)}</span>
                  <span style={{ fontSize: '8px', padding: '1px 4px', borderRadius: '2px', background: 'rgba(192,80,30,0.15)', color: 'var(--orange)' }}>Manual</span>
                </>
              ) : (
                <>
                  <span>{resolvedModel ? findModelName(resolvedModel, modelCatalog, modelSearchResults) : 'auto-router'}</span>
                  <span style={{ fontSize: '8px', padding: '1px 4px', borderRadius: '2px', background: 'rgba(90,122,74,0.15)', color: 'var(--green)' }}>Auto</span>
                </>
              )}
              <ChevronDown size={12} style={{ transform: modelPickerOpen ? 'rotate(180deg)' : '' }} />
            </button>
            <div className="ci-mode">
              <button className={`ci-mode-btn ${inputMode === 'chat' ? 'active' : ''}`} onClick={() => onModeChange?.('chat')} disabled={true} title="Chat mode is temporarily disabled">💬 Chat</button>
              <button className={`ci-mode-btn ${inputMode === 'plan' ? 'active' : ''}`} onClick={() => onModeChange?.('plan')} disabled={disabled}>✨ Plan</button>
            </div>
          </div>
          {/* Attachments preview */}
          {attachments.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '6px' }}>
              {attachments.map((att, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 8px', background: 'var(--paper)', border: '1px solid var(--line)', borderRadius: '3px' }}>
                  <div style={{ width: '24px', height: '24px', borderRadius: '3px', background: 'rgba(192,80,30,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {attachmentPreviews[idx]?.startsWith('data:') ? (
                      <img src={attachmentPreviews[idx]} alt="" style={{ width: '24px', height: '24px', borderRadius: '3px', objectFit: 'cover' }} />
                    ) : attachmentPreviews[idx] === 'audio' ? (
                      <Volume2 size={14} style={{ color: 'var(--orange)' }} />
                    ) : attachmentPreviews[idx] === 'video' ? (
                      <Video size={14} style={{ color: 'var(--orange)' }} />
                    ) : (
                      <FileText size={14} style={{ color: 'var(--orange)' }} />
                    )}
                  </div>
                  <span style={{ fontSize: '10px', color: 'var(--ink)', maxWidth: '100px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{att.name}</span>
                  <button onClick={() => { setAttachments(prev => prev.filter((_, i) => i !== idx)); setAttachmentPreviews(prev => prev.filter((_, i) => i !== idx)); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink3)' }}><X size={12} /></button>
                </div>
              ))}
            </div>
          )}
          <input ref={fileInputRef} type="file" multiple onChange={handleFileSelect} style={{ display: 'none' }} accept="image/*,audio/*,video/*,.pdf,.txt,.json,.csv,.doc,.docx,.md,.py,.js,.ts,.html,.css,.yaml,.yml,.toml,.sh,.sql,.ini,.cfg,.pptx,.xlsx,.zip,.tar,.gz" />
          {/* Input row */}
          <div className="ci-row">
            <button className="ci-plus" onClick={() => fileInputRef.current?.click()} disabled={disabled} title="Attach file">+</button>
            <textarea
              ref={textareaRef}
              className="ci-input"
              placeholder={disabled ? 'Waiting...' : 'พิมพ์คำสั่งถึงทีม...'}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              disabled={disabled}
              rows={1}
            />
            {isProcessing ? (
              <button className="ci-send" onClick={() => onStop?.()} style={{ background: 'var(--red)' }} title="Stop">
                <Square size={13} className="fill-current" />
              </button>
            ) : (
              <button className="ci-send" onClick={handleSubmit} disabled={disabled || (!input.trim() && attachments.length === 0)}>➤</button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
