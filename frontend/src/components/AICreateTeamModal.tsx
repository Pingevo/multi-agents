import { useState, useRef, useEffect } from 'react';
import { X, Sparkles, Send, Check, Edit } from 'lucide-react';
import type { ChatMessage } from './chatTypes';

interface AICreateTeamModalProps {
  open: boolean;
  onClose: () => void;
  onSend: (message: string) => void;
  chatMessages: ChatMessage[];
  onCreateTeam: (data: { name: string; description: string; manager_model: string }) => void;
  onSelectModel: () => void;
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
  chatMessages,
  onCreateTeam,
  onSelectModel,
  selectedModel,
  resolvedModel,
  isThinking,
  thinkingText,
}) => {
  const [input, setInput] = useState('');
  const [parsedTeam, setParsedTeam] = useState<ParsedTeam | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [editedDesc, setEditedDesc] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const modalMessages = chatMessages.filter(
    (m) => m.messageType === 'text' || m.messageType === 'thinking' || m.messageType === 'thinking_done'
  );

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [modalMessages.length, isThinking]);

  // Try to parse team from latest AI text message
  useEffect(() => {
    const lastText = [...modalMessages].reverse().find((m) => m.messageType === 'text' && m.role === 'assistant');
    if (lastText?.content) {
      try {
        const jsonMatch = lastText.content.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[0]);
          if (parsed.name || parsed.team_name) {
            const team: ParsedTeam = {
              name: parsed.name || parsed.team_name || '',
              description: parsed.description || '',
              manager_model: parsed.manager_model || 'auto',
              agents: (parsed.agents || []).map((a: any) => ({
                name: a.name || '',
                role: a.role || '',
                goal: a.goal || '',
                model: a.model || 'auto',
              })),
            };
            setParsedTeam(team);
            setEditedName(team.name);
            setEditedDesc(team.description);
          }
        }
      } catch {
        // Not JSON — ignore
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
    onCreateTeam({
      name: editedName || parsedTeam.name,
      description: editedDesc || parsedTeam.description,
      manager_model: parsedTeam.manager_model,
    });
    setParsedTeam(null);
    setEditMode(false);
    setInput('');
    onClose();
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
            <Sparkles className="w-5 h-5 text-accent" />
            <h2 className="text-base font-semibold text-text">Create Team with AI</h2>
          </div>
          <button onClick={onClose} className="p-1 text-text-3 hover:text-text transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Model selector */}
        <div className="flex items-center gap-2 px-5 py-2 border-b border-border shrink-0">
          <span className="text-xs text-text-3">Model:</span>
          <button
            onClick={onSelectModel}
            className="text-xs px-2 py-1 bg-surface-2 border border-border rounded text-text-2 hover:border-accent/50 transition-colors"
          >
            {selectedModel || resolvedModel || 'Auto'}
          </button>
        </div>

        {/* Chat area */}
        <div ref={scrollRef} className="flex-1 overflow-auto px-5 py-4 space-y-3 min-h-0">
          {modalMessages.length === 0 && !isThinking && (
            <div className="text-center py-10">
              <Sparkles className="w-10 h-10 text-accent/50 mx-auto mb-3" />
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
            <div className="bg-accent/5 border border-accent/30 rounded-lg p-4 mt-3">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-accent uppercase tracking-wide">Team Preview</span>
                <button
                  onClick={() => setEditMode(!editMode)}
                  className="flex items-center gap-1 text-xs text-text-2 hover:text-accent transition-colors"
                >
                  <Edit className="w-3 h-3" />
                  {editMode ? 'Preview' : 'Edit'}
                </button>
              </div>

              {editMode ? (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                    className="w-full px-2 py-1.5 bg-bg border border-border rounded text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent/50"
                    placeholder="Team name"
                  />
                  <textarea
                    value={editedDesc}
                    onChange={(e) => setEditedDesc(e.target.value)}
                    rows={2}
                    className="w-full px-2 py-1.5 bg-bg border border-border rounded text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent/50 resize-none"
                    placeholder="Description"
                  />
                </div>
              ) : (
                <>
                  <h4 className="text-sm font-semibold text-text mb-1">{parsedTeam.name}</h4>
                  {parsedTeam.description && <p className="text-xs text-text-2 mb-2">{parsedTeam.description}</p>}
                </>
              )}

              {parsedTeam.agents.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  <span className="text-[10px] text-text-3 uppercase">Agents ({parsedTeam.agents.length})</span>
                  {parsedTeam.agents.map((agent, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <div className="w-1.5 h-1.5 rounded-full bg-accent/50" />
                      <span className="font-medium text-text">{agent.name}</span>
                      <span className="text-text-3">— {agent.role}</span>
                      <span className="text-text-3 ml-auto">{agent.model}</span>
                    </div>
                  ))}
                </div>
              )}

              <button
                onClick={handleConfirm}
                className="mt-3 w-full flex items-center justify-center gap-2 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
              >
                <Check className="w-4 h-4" />
                Create This Team
              </button>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="px-5 py-3 border-t border-border shrink-0">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="อธิบายทีมที่คุณต้องการ..."
              className="flex-1 px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text placeholder-text-3 focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="p-2 bg-accent text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-accent/90 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
