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
  agents: Array<{ name: string; role: string; goal: string; persona: string; tools: string[]; model: string }>;
  cancelled?: boolean;
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
  const [parsedTeams, setParsedTeams] = useState<ParsedTeam[]>([]);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [agentModelPickerOpen, setAgentModelPickerOpen] = useState<number | null>(null);
  const [agentModels, setAgentModels] = useState<Record<number, string>>({});
  const [expandedAgent, setExpandedAgent] = useState<number | null>(null);
  const [expandedManager, setExpandedManager] = useState(false);
  const processedPlanIds = useRef<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);
  const modelBarRef = useRef<HTMLDivElement>(null);
  const agentRefs = useRef<(HTMLDivElement | null)[]>([]);
  const managerRef = useRef<HTMLDivElement>(null);
  const [managerModelPickerOpen, setManagerModelPickerOpen] = useState(false);
  const [managerModel, setManagerModel] = useState('auto');

  const modalMessages = chatMessages.filter(
    (m) => m.messageType === 'text' || m.messageType === 'plan' || m.messageType === 'thinking' || m.messageType === 'thinking_done'
  );

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [modalMessages.length, isThinking]);

  // Parse team from NEW plan messages only (skip already processed)
  useEffect(() => {
    const planMsgs = modalMessages.filter((m) => m.messageType === 'plan' && m.role === 'assistant');
    for (const msg of planMsgs) {
      const msgId = (msg as any).id || '';
      if (!msgId || processedPlanIds.current.has(msgId)) continue;
      processedPlanIds.current.add(msgId);
      const planAgents = (msg as any).planAgents || [];
      const team: ParsedTeam = {
        name: (msg as any).teamName || '',
        description: (msg as any).teamDescription || '',
        manager_model: planAgents.length > 0 ? (planAgents[0] as any).model || 'auto' : 'auto',
        agents: planAgents.map((a: any) => ({
          name: a.name || '',
          role: a.role || '',
          goal: a.goal || '',
          persona: a.persona || a.backstory || '',
          tools: a.tools || [],
          model: a.model || 'auto',
        })),
      };
      if (team.name || team.agents.length > 0) {
        setParsedTeams(prev => [...prev, team]);
        setManagerModel(team.manager_model);
        setAgentModels({});
      }
    }
  }, [chatMessages]);

  if (!open) return null;

  const handleSend = () => {
    if (!input.trim()) return;
    onSend(input.trim());
    setInput('');
  };

  const handleConfirm = (idx: number) => {
    const team = parsedTeams[idx];
    if (!team) return;
    const agents = team.agents.map((a, i) => ({
      ...a,
      model: agentModels[i] || a.model,
    }));
    onCreateTeam({
      name: team.name,
      description: team.description,
      manager_model: managerModel,
      agents,
    });
    setParsedTeams([]);
    setAgentModels({});
    setExpandedAgent(null);
    setInput('');
    onClose();
  };

  const handleCancelPreview = (idx: number) => {
    setParsedTeams(prev => prev.map((t, i) => i === idx ? { ...t, cancelled: true } : t));
    setExpandedAgent(null);
  };

  const hasActivePreview = parsedTeams.some(t => !t.cancelled);

  const renderTeamCard = (team: ParsedTeam, idx: number) => (
    <div key={`preview-${idx}`} className={`rounded-retro-lg p-4 mt-1 ${team.cancelled ? 'bg-cream-2/50 border border-line/50' : 'bg-orange/5 border border-orange/30'}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium uppercase tracking-wide" style={{ color: team.cancelled ? 'var(--ink3)' : 'var(--orange)' }}>
          ตัวอย่างทีม {parsedTeams.length > 1 ? `#${idx + 1}` : ''}
        </span>
        {team.cancelled && (
          <span className="text-[10px] text-ink-3 flex items-center gap-1">
            <XCircle className="w-3 h-3" />
            ปรับแก้
          </span>
        )}
      </div>

      <h4 className="text-sm font-semibold text-ink mb-1">{team.name}</h4>
      {team.description && <p className="text-xs text-ink-2 mb-2">{team.description}</p>}

      {/* Manager Agent */}
      <div className="mt-3 space-y-1.5">
        <span className="text-[10px] text-ink-3 uppercase">Manager</span>
        <div ref={managerRef} className="relative">
          {managerModelPickerOpen && !team.cancelled && (
            <ModelPicker
              recommended={modelCatalog}
              searchResults={modelSearchResults}
              selectedModel={managerModel}
              onSelect={(modelId) => { setManagerModel(modelId); setManagerModelPickerOpen(false); }}
              onSearch={(q) => onSearchModels?.(q)}
              onClose={() => setManagerModelPickerOpen(false)}
              anchorRef={managerRef}
            />
          )}
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-retro bg-cream border border-orange/20">
            <div className="w-2 h-2 rounded-full bg-orange shrink-0" />
            <span className="text-xs font-medium text-ink">Manager</span>
            <span className="text-[11px] text-ink-3 truncate flex-1">— ประสานงานทีมและกระจายงาน</span>
            <button
              onClick={() => setExpandedManager(!expandedManager)}
              className="text-[10px] text-ink-3 hover:text-ink transition-colors shrink-0"
            >
              {expandedManager ? '▲' : '▼'}
            </button>
            <button
              onClick={() => {
                if (managerModelPickerOpen) { setManagerModelPickerOpen(false); return; }
                if (Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) onFetchModelCatalog();
                setManagerModelPickerOpen(true);
              }}
              disabled={team.cancelled}
              className="text-[10px] px-1.5 py-0.5 rounded-full bg-cream-2 border border-line text-ink-2 hover:text-ink hover:border-orange/30 transition-colors shrink-0 disabled:opacity-50"
            >
              {managerModel || 'auto'}
            </button>
          </div>
          {expandedManager && (
            <div className="mt-2 pl-4 pr-2 space-y-1.5 border-t border-line/50 pt-2">
              <div>
                <span className="text-[9px] text-ink-3 uppercase">Role</span>
                <p className="text-[11px] text-ink-2 leading-relaxed">Team Manager / Coordinator</p>
              </div>
              <div>
                <span className="text-[9px] text-ink-3 uppercase">Goal</span>
                <p className="text-[11px] text-ink-2 leading-relaxed">ประสานงานระหว่าง agent ในทีม กระจายงาน และสรุปผลลัพธ์</p>
              </div>
              <div>
                <span className="text-[9px] text-ink-3 uppercase">Persona</span>
                <p className="text-[11px] text-ink-3">—</p>
              </div>
              <div className="grid grid-cols-3 gap-2 pt-1 border-t border-line/30">
                <div>
                  <span className="text-[9px] text-ink-3 uppercase">Tone</span>
                  <p className="text-[11px] text-ink-3">—</p>
                </div>
                <div>
                  <span className="text-[9px] text-ink-3 uppercase">Style</span>
                  <p className="text-[11px] text-ink-3">—</p>
                </div>
                <div>
                  <span className="text-[9px] text-ink-3 uppercase">Language</span>
                  <p className="text-[11px] text-ink-3">—</p>
                </div>
              </div>
              <div>
                <span className="text-[9px] text-ink-3 uppercase">Expertise</span>
                <p className="text-[11px] text-ink-3">—</p>
              </div>
              <div>
                <span className="text-[9px] text-ink-3 uppercase">Brand Context</span>
                <p className="text-[11px] text-ink-3">—</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Worker Agents */}
      {team.agents.length > 0 && (
        <div className="mt-3 space-y-1.5">
          <span className="text-[10px] text-ink-3 uppercase">Agents ({team.agents.length})</span>
          {team.agents.map((agent, i) => (
            <div key={i} ref={(el) => { agentRefs.current[i] = el; }} className="relative">
              {agentModelPickerOpen === i && !team.cancelled && (
                <ModelPicker
                  recommended={modelCatalog}
                  searchResults={modelSearchResults}
                  selectedModel={agentModels[i] || agent.model}
                  onSelect={(modelId) => { setAgentModels(prev => ({ ...prev, [i]: modelId })); setAgentModelPickerOpen(null); }}
                  onSearch={(q) => onSearchModels?.(q)}
                  onClose={() => setAgentModelPickerOpen(null)}
                  anchorRef={{ current: agentRefs.current[i] }}
                />
              )}
              <div className="px-2.5 py-1.5 rounded-retro bg-cream">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-orange/50 shrink-0" />
                  <span className="text-xs font-medium text-ink">{agent.name}</span>
                  <span className="text-[11px] text-ink-3 truncate flex-1">— {agent.role}</span>
                  {agent.tools.length > 0 && (
                    <span className="text-[9px] px-1.5 py-0.5 bg-orange/10 text-orange rounded-full shrink-0">
                      {agent.tools.length} tools
                    </span>
                  )}
                  <button
                    onClick={() => setExpandedAgent(expandedAgent === i ? null : i)}
                    className="text-[10px] text-ink-3 hover:text-ink transition-colors shrink-0"
                  >
                    {expandedAgent === i ? '▲' : '▼'}
                  </button>
                  <button
                    onClick={() => {
                      if (agentModelPickerOpen === i) { setAgentModelPickerOpen(null); return; }
                      if (Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) onFetchModelCatalog();
                      setAgentModelPickerOpen(i);
                    }}
                    disabled={team.cancelled}
                    className="text-[10px] px-1.5 py-0.5 rounded-full bg-cream-2 border border-line text-ink-2 hover:text-ink hover:border-orange/30 transition-colors shrink-0 disabled:opacity-50"
                  >
                    {agentModels[i] || agent.model || 'auto'}
                  </button>
                </div>
                {expandedAgent === i && (
                  <div className="mt-2 pl-4 pr-2 space-y-1.5 border-t border-line/50 pt-2">
                    <div>
                      <span className="text-[9px] text-ink-3 uppercase">Goal</span>
                      <p className="text-[11px] text-ink-2 leading-relaxed">{agent.goal || '—'}</p>
                    </div>
                    <div>
                      <span className="text-[9px] text-ink-3 uppercase">Persona</span>
                      <p className="text-[11px] text-ink-2 leading-relaxed">{agent.persona || '—'}</p>
                    </div>
                    <div>
                      <span className="text-[9px] text-ink-3 uppercase">Tools</span>
                      {agent.tools.length > 0 ? (
                        <div className="flex flex-wrap gap-1 mt-0.5">
                          {agent.tools.map((tool, ti) => (
                            <span key={ti} className="text-[9px] px-1.5 py-0.5 bg-cream-2 border border-line text-ink-2 rounded-retro-sm">
                              {tool}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-[11px] text-ink-3">—</p>
                      )}
                    </div>
                    <div className="grid grid-cols-3 gap-2 pt-1 border-t border-line/30">
                      <div>
                        <span className="text-[9px] text-ink-3 uppercase">Tone</span>
                        <p className="text-[11px] text-ink-3">—</p>
                      </div>
                      <div>
                        <span className="text-[9px] text-ink-3 uppercase">Style</span>
                        <p className="text-[11px] text-ink-3">—</p>
                      </div>
                      <div>
                        <span className="text-[9px] text-ink-3 uppercase">Language</span>
                        <p className="text-[11px] text-ink-3">—</p>
                      </div>
                    </div>
                    <div>
                      <span className="text-[9px] text-ink-3 uppercase">Expertise</span>
                      <p className="text-[11px] text-ink-3">—</p>
                    </div>
                    <div>
                      <span className="text-[9px] text-ink-3 uppercase">Brand Context</span>
                      <p className="text-[11px] text-ink-3">—</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 flex gap-2">
        {team.cancelled ? (
          <div className="flex-1 flex items-center justify-center gap-2 py-2 bg-cream-2 text-ink-3 border border-line rounded-retro text-sm">
            <XCircle className="w-4 h-4" />
            ปรับแก้ — พิมพ์สิ่งที่ต้องการเปลี่ยนด้านล่าง
          </div>
        ) : (
          <>
            <button
              onClick={() => handleConfirm(idx)}
              className="flex-1 flex items-center justify-center gap-2 py-2 bg-orange text-white rounded-retro text-sm font-medium hover:bg-orange-light transition-colors"
            >
              <Check className="w-4 h-4" />
              สร้างทีมนี้
            </button>
            <button
              onClick={() => handleCancelPreview(idx)}
              className="flex items-center justify-center gap-1.5 px-3 py-2 bg-cream-2 text-ink-2 border border-line rounded-retro text-sm hover:text-ink hover:border-line-2 transition-colors"
            >
              <XCircle className="w-4 h-4" />
              ปรับแก้
            </button>
          </>
        )}
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-2xl h-[80vh] flex flex-col bg-paper border border-line-2 rounded-retro-lg shadow-retro-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-line shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-lg">🤖</span>
            <div>
              <h2 className="text-base font-semibold text-ink">สร้างทีมด้วย AI</h2>
              <p className="text-[11px] text-ink-3">บอก AI ว่าต้องการทีมแบบไหน — แล้ว AI จะสร้างให้</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 text-ink-3 hover:text-ink transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Model selector */}
        <div ref={modelBarRef} className="px-5 py-2 border-b border-line shrink-0 relative">
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
            className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-retro border transition-colors text-left ${
              modelPickerOpen
                ? 'bg-orange/10 border-orange/40 text-ink'
                : 'bg-cream-2 border-line text-ink-2 hover:text-ink hover:border-line-2'
            }`}
          >
            {(() => {
              const modelId = selectedModel || resolvedModel || '';
              const provider = getProvider(modelId);
              const favicon = PROVIDER_FAVICONS[provider];
              if (favicon) {
                return <img src={favicon} alt="" className="w-4 h-4 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
              }
              return <Cpu className={`w-3.5 h-3.5 shrink-0 ${modelPickerOpen ? 'text-orange' : ''}`} />;
            })()}
            <span className="text-[10px] font-medium text-ink flex-1 truncate">
              {selectedModel || resolvedModel ? findModelName(selectedModel || resolvedModel || '', modelCatalog, modelSearchResults) : 'Free Router'}
            </span>
            <span className={`text-[9px] px-1.5 py-0.5 rounded-full shrink-0 ${selectedModel ? 'bg-orange/15 text-orange' : 'bg-green/15 text-green'}`}>
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
              <p className="text-sm text-ink-2 mb-1">อธิบายทีมที่คุณต้องการสร้าง</p>
              <p className="text-xs text-ink-3">เช่น "ฉันต้องการทีมการตลาด 3 คน สำหรับร้านกาแฟ"</p>
            </div>
          )}

          {modalMessages.map((msg, i) => {
            if (msg.messageType === 'thinking') {
              return (
                <div key={i} className="flex justify-start">
                  <div className="bg-cream-2 border border-line rounded-retro px-3 py-2 max-w-[80%]">
                    <p className="text-xs text-ink-3 italic">{thinkingText || 'Thinking...'}</p>
                  </div>
                </div>
              );
            }
            if (msg.messageType === 'plan' && msg.role === 'assistant') {
              const planMsg = msg as any;
              const teamLabel = planMsg.teamName || 'ทีมใหม่';
              const agentCount = (planMsg.planAgents || []).length;
              const planMsgs = modalMessages.filter((m: any) => m.messageType === 'plan' && m.role === 'assistant');
              const teamIdx = planMsgs.indexOf(msg);
              const isCancelled = teamIdx >= 0 && parsedTeams[teamIdx]?.cancelled;
              const team = teamIdx >= 0 ? parsedTeams[teamIdx] : null;
              return (
                <div key={i}>
                  <div className="flex justify-start">
                    <div className="bg-cream-2 border border-line rounded-retro px-3 py-2 max-w-[80%]">
                      <p className="text-sm text-ink">
                        {isCancelled
                          ? `ปรับแก้ทีม "${teamLabel}" — พิมพ์สิ่งที่ต้องการเปลี่ยนด้านล่าง`
                          : `AI เสนอทีม "${teamLabel}" (${agentCount} agent${agentCount > 1 ? 's' : ''}) — ดูรายละเอียดด้านล่าง`}
                      </p>
                    </div>
                  </div>
                  {team && renderTeamCard(team, teamIdx)}
                </div>
              );
            }
            const isUser = msg.role === 'user';
            return (
              <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`rounded-retro px-3 py-2 max-w-[80%] text-sm ${
                    isUser
                      ? 'bg-orange text-white'
                      : 'bg-cream-2 border border-line text-ink'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            );
          })}

          {isThinking && !modalMessages.some((m) => m.messageType === 'thinking') && (
            <div className="flex justify-start">
              <div className="bg-cream-2 border border-line rounded-retro px-3 py-2">
                <div className="flex gap-1">
                  <div className="w-2 h-2 rounded-full bg-ink-3 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 rounded-full bg-ink-3 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 rounded-full bg-ink-3 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          {/* Team previews for plan messages without a matching plan in modalMessages (shouldn't happen, but fallback) */}
          {parsedTeams.filter((t, idx) => {
            const planMsgs = modalMessages.filter((m: any) => m.messageType === 'plan' && m.role === 'assistant');
            return idx >= planMsgs.length;
          }).map((team, fi) => {
            const actualIdx = parsedTeams.indexOf(team);
            return renderTeamCard(team, actualIdx);
          })}
        </div>

        {/* Input — always visible, disabled only when there's an active (non-cancelled) preview */}
        <div className="px-5 py-3 border-t border-line shrink-0">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="อธิบายทีมที่คุณต้องการ..."
              disabled={hasActivePreview}
              className="flex-1 px-3 py-2 bg-cream border border-line rounded-retro text-sm text-ink placeholder-ink-3 focus:outline-none focus:ring-2 focus:ring-orange/50 disabled:opacity-50"
            />
            {isThinking && onStop ? (
              <button
                onClick={onStop}
                className="px-3 py-2 bg-red text-white rounded-retro text-sm font-medium hover:bg-red/90 transition-colors"
              >
                หยุด
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim() || hasActivePreview}
                className="p-2 bg-orange text-white rounded-retro disabled:opacity-50 disabled:cursor-not-allowed hover:bg-orange-light transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </div>
          {hasActivePreview && (
            <p className="text-[10px] text-ink-3 text-center mt-1.5">กด "สร้างทีมนี้" เพื่อยืนยัน หรือ "ยกเลิก" เพื่อพิมพ์ prompt ใหม่</p>
          )}
        </div>
      </div>
    </div>
  );
};
