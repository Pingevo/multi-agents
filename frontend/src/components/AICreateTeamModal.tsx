import { useState, useRef, useEffect } from 'react';
import { X, Send, Check, Cpu, ChevronDown, XCircle } from 'lucide-react';
import { ModelPicker, PROVIDER_FAVICONS, getProvider, findModelName } from './ModelPicker';
import type { ModelCatalogEntry } from './ModelPicker';
import type { ChatMessage } from './chatTypes';

interface AICreateTeamModalProps {
  open: boolean;
  onClose: () => void;
  onSend: (message: string) => void;
  onStop?: () => void;
  chatMessages: ChatMessage[];
  onCreateTeam: (data: { name: string; description: string; manager_model: string; agents: Array<{ name: string; role: string; goal: string; model: string }> }) => void;
  onFetchModelCatalog?: () => void;
  onSearchModels?: (query: string) => void;
  onSelectModel?: (modelId: string) => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  selectedModel?: string;
  resolvedModel?: string;
  isThinking?: boolean;
  thinkingText?: string;
}

interface ParsedTeam {
  name: string;
  description: string;
  manager_model: string;
  agents: Array<{ name: string; role: string; goal: string; model: string }>;
}

export const AICreateTeamModal: React.FC<AICreateTeamModalProps> = ({
  open,
  onClose,
  onSend,
  onStop,
  chatMessages,
  onCreateTeam,
  onFetchModelCatalog,
  onSearchModels,
  onSelectModel,
  modelCatalog = {},
  modelSearchResults = [],
  selectedModel,
  resolvedModel,
  isThinking,
  thinkingText,
}) => {
  const [input, setInput] = useState('');
  const [parsedTeam, setParsedTeam] = useState<ParsedTeam | null>(null);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [agentModelPickerOpen, setAgentModelPickerOpen] = useState<number | null>(null);
  const [agentModels, setAgentModels] = useState<Record<number, string>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const modelBarRef = useRef<HTMLDivElement>(null);

  const modalMessages = chatMessages.filter(
    (m) => m.messageType === 'text' || m.messageType === 'plan' || m.messageType === 'thinking' || m.messageType === 'thinking_done'
  );

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [modalMessages.length, isThinking]);

  // Try to parse team from latest AI plan message
  useEffect(() => {
    const lastPlan = [...modalMessages].reverse().find((m) => m.messageType === 'plan' && m.role === 'assistant');
    if (lastPlan && (lastPlan as any).planAgents) {
      const planAgents = (lastPlan as any).planAgents || [];
      const team: ParsedTeam = {
        name: (lastPlan as any).teamName || '',
        description: (lastPlan as any).teamDescription || '',
        manager_model: planAgents.length > 0 ? (planAgents[0] as any).model || 'auto' : 'auto',
        agents: planAgents.map((a: any) => ({
          name: a.name || '',
          role: a.role || '',
          goal: a.goal || '',
          model: a.model || 'auto',
        })),
      };
      if (team.name || team.agents.length > 0) {
        setParsedTeam(team);
        setAgentModels({});
      }
    }
  }, [modalMessages]);

  if (!open) return null;

  const handleSend = () => {
    if (!input.trim()) return;
    onSend(input.trim());
    setInput('');
  };

  const handleConfirm = () => {
    if (!parsedTeam) return;
    const agents = parsedTeam.agents.map((a, i) => ({
      ...a,
      model: agentModels[i] || a.model,
    }));
    onCreateTeam({
      name: parsedTeam.name,
      description: parsedTeam.description,
      manager_model: parsedTeam.manager_model,
      agents,
    });
    setParsedTeam(null);
    setAgentModels({});
    setInput('');
    onClose();
  };

  const handleCancelPreview = () => {
    setParsedTeam(null);
    setAgentModels({});
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-2xl h-[80vh] flex flex-col bg-surface border border-border rounded-2xl shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-lg">🤖</span>
            <div>
              <h2 className="text-base font-semibold text-text">สร้างทีมด้วย AI</h2>
              <p className="text-[11px] text-text-3">บอก AI ว่าต้องการทีมแบบไหน — แล้ว AI จะสร้างให้</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 text-text-3 hover:text-text transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Model selector */}
        <div ref={modelBarRef} className="px-5 py-2 border-b border-border shrink-0 relative">
          {modelPickerOpen && (
            <ModelPicker
              recommended={modelCatalog}
              searchResults={modelSearchResults}
              selectedModel={selectedModel || ''}
              onSelect={(modelId) => { onSelectModel?.(modelId); }}
              onSearch={(q) => onSearchModels?.(q)}
              onClose={() => setModelPickerOpen(false)}
              anchorRef={modelBarRef}
            />
          )}
          <button
            onClick={() => {
              if (modelPickerOpen) { setModelPickerOpen(false); return; }
              if (Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) onFetchModelCatalog();
              setModelPickerOpen(true);
            }}
            className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg border transition-colors text-left ${
              modelPickerOpen
                ? 'bg-accent/10 border-accent/40 text-text'
                : 'bg-surface-2 border-border text-text-2 hover:text-text hover:border-border/80'
            }`}
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
            <span className="text-[10px] font-medium text-text flex-1 truncate">
              {selectedModel || resolvedModel ? findModelName(selectedModel || resolvedModel || '', modelCatalog, modelSearchResults) : 'Auto Router'}
            </span>
            <span className={`text-[9px] px-1.5 py-0.5 rounded-full shrink-0 ${selectedModel ? 'bg-accent/15 text-accent' : 'bg-emerald-500/15 text-emerald-500'}`}>
              {selectedModel ? 'Manual' : 'Auto'}
            </span>
            <ChevronDown className={`w-3 h-3 shrink-0 transition-transform ${modelPickerOpen ? 'rotate-180' : ''}`} />
          </button>
        </div>

        {/* Chat area */}
        <div ref={scrollRef} className="flex-1 overflow-auto px-5 py-4 space-y-3 min-h-0">
          {modalMessages.length === 0 && !isThinking && (
            <div className="text-center py-10">
              <span className="text-4xl mb-3 block">🤖</span>
              <p className="text-sm text-text-2 mb-1">อธิบายทีมที่คุณต้องการสร้าง</p>
              <p className="text-xs text-text-3">เช่น "ฉันต้องการทีมการตลาด 3 คน สำหรับร้านกาแฟ"</p>
            </div>
          )}

          {modalMessages.map((msg, i) => {
            if (msg.messageType === 'thinking') {
              return (
                <div key={i} className="flex justify-start">
                  <div className="bg-surface-2 border border-border rounded-lg px-3 py-2 max-w-[80%]">
                    <p className="text-xs text-text-3 italic">{thinkingText || 'Thinking...'}</p>
                  </div>
                </div>
              );
            }
            const isUser = msg.role === 'user';
            return (
              <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`rounded-lg px-3 py-2 max-w-[80%] text-sm ${
                    isUser
                      ? 'bg-accent text-white'
                      : 'bg-surface-2 border border-border text-text'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            );
          })}

          {isThinking && !modalMessages.some((m) => m.messageType === 'thinking') && (
            <div className="flex justify-start">
              <div className="bg-surface-2 border border-border rounded-lg px-3 py-2">
                <div className="flex gap-1">
                  <div className="w-2 h-2 rounded-full bg-text-3 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 rounded-full bg-text-3 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 rounded-full bg-text-3 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          {/* Team preview */}
          {parsedTeam && (
            <div className="bg-accent/5 border border-accent/30 rounded-xl p-4 mt-3">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-accent uppercase tracking-wide">ตัวอย่างทีม</span>
              </div>

              <h4 className="text-sm font-semibold text-text mb-1">{parsedTeam.name}</h4>
              {parsedTeam.description && <p className="text-xs text-text-2 mb-2">{parsedTeam.description}</p>}

              {parsedTeam.agents.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  <span className="text-[10px] text-text-3 uppercase">Agents ({parsedTeam.agents.length})</span>
                  {parsedTeam.agents.map((agent, i) => (
                    <div key={i} className="relative">
                      {agentModelPickerOpen === i && (
                        <ModelPicker
                          recommended={modelCatalog}
                          searchResults={modelSearchResults}
                          selectedModel={agentModels[i] || agent.model}
                          onSelect={(modelId) => { setAgentModels(prev => ({ ...prev, [i]: modelId })); setAgentModelPickerOpen(null); }}
                          onSearch={(q) => onSearchModels?.(q)}
                          onClose={() => setAgentModelPickerOpen(null)}
                        />
                      )}
                      <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-bg">
                        <div className="w-2 h-2 rounded-full bg-accent/50 shrink-0" />
                        <span className="text-xs font-medium text-text">{agent.name}</span>
                        <span className="text-[11px] text-text-3 truncate flex-1">— {agent.role}</span>
                        <button
                          onClick={() => {
                            if (agentModelPickerOpen === i) { setAgentModelPickerOpen(null); return; }
                            if (Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) onFetchModelCatalog();
                            setAgentModelPickerOpen(i);
                          }}
                          className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-2 border border-border text-text-2 hover:text-text hover:border-accent/30 transition-colors shrink-0"
                        >
                          {agentModels[i] || agent.model || 'auto'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-3 flex gap-2">
                <button
                  onClick={handleConfirm}
                  className="flex-1 flex items-center justify-center gap-2 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
                >
                  <Check className="w-4 h-4" />
                  สร้างทีมนี้
                </button>
                <button
                  onClick={handleCancelPreview}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-surface-2 text-text-2 border border-border rounded-lg text-sm hover:text-text hover:border-border/80 transition-colors"
                >
                  <XCircle className="w-4 h-4" />
                  ยกเลิก
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Input — disabled when team preview is shown */}
        <div className="px-5 py-3 border-t border-border shrink-0">
          {parsedTeam ? (
            <p className="text-xs text-text-3 text-center py-2">กด "สร้างทีมนี้" เพื่อยืนยัน หรือ "ยกเลิก" เพื่อพิมพ์ prompt ใหม่</p>
          ) : (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                placeholder="อธิบายทีมที่คุณต้องการ..."
                className="flex-1 px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text placeholder-text-3 focus:outline-none focus:ring-2 focus:ring-accent/50"
              />
              {isThinking && onStop ? (
                <button
                  onClick={onStop}
                  className="px-3 py-2 bg-error text-white rounded-lg text-sm font-medium hover:bg-error/90 transition-colors"
                >
                  หยุด
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="p-2 bg-accent text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-accent/90 transition-colors"
                >
                  <Send className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
