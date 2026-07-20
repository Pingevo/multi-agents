import type { ChatMessage, PlanAgent, ResultAgent } from '../chatTypes';

// User message — right-aligned orange bubble
export const FeedUserMessage: React.FC<{ msg: ChatMessage }> = ({ msg }) => (
  <div className="self-end max-w-[80%] bg-orange text-white rounded-retro px-3 py-2 text-[12px] leading-relaxed">
    {msg.content}
    {msg.attachments && msg.attachments.length > 0 && (
      <div className="mt-2 flex flex-col gap-1">
        {msg.attachments.map((att, i) => (
          <div key={i} className="text-[10px] bg-white/10 rounded-retro-sm px-2 py-1">
            📎 {att.name}
          </div>
        ))}
      </div>
    )}
  </div>
);

// Thinking indicator — avatar + animated dots
export const FeedThinking: React.FC<{ model?: string }> = ({ model }) => (
  <div className="flex items-center gap-2 self-start">
    <div className="w-7 h-7 rounded-full bg-cream border border-line flex items-center justify-center text-sm">🧠</div>
    <div className="bg-cream border border-line rounded-retro px-3 py-2 flex items-center gap-1">
      <span className="w-1.5 h-1.5 bg-ink-3 rounded-full animate-thinking" style={{ animationDelay: '0s' }} />
      <span className="w-1.5 h-1.5 bg-ink-3 rounded-full animate-thinking" style={{ animationDelay: '0.2s' }} />
      <span className="w-1.5 h-1.5 bg-ink-3 rounded-full animate-thinking" style={{ animationDelay: '0.4s' }} />
      {model && <span className="text-[9px] text-ink-3 ml-1.5 font-mono">{model}</span>}
    </div>
  </div>
);

// Agent message — avatar + bubble with name
export const FeedAgentMessage: React.FC<{
  avatar: string;
  name: string;
  children: React.ReactNode;
  meta?: string;
}> = ({ avatar, name, children, meta }) => (
  <div className="flex items-start gap-2 self-start max-w-[80%]">
    <div className="w-7 h-7 rounded-full bg-cream border border-line flex items-center justify-center text-sm flex-shrink-0">{avatar}</div>
    <div className="bg-cream border border-line rounded-retro px-3 py-2 text-[12px] leading-relaxed text-ink">
      <span className="font-semibold text-ink-2 text-[11px] mr-1.5">{name}</span>
      {children}
      {meta && <span className="text-[10px] text-ink-3 font-mono ml-1.5">{meta}</span>}
    </div>
  </div>
);

// Progress line — compact
export const FeedProgress: React.FC<{ label: string; onViewProgress?: () => void }> = ({ label, onViewProgress }) => (
  <div className="flex items-center gap-2 self-start text-[11px] text-ink-3 py-1">
    <span className="flex items-center gap-1">
      <span className="w-1.5 h-1.5 bg-amber rounded-full animate-thinking" style={{ animationDelay: '0s' }} />
      <span className="w-1.5 h-1.5 bg-amber rounded-full animate-thinking" style={{ animationDelay: '0.2s' }} />
      <span className="w-1.5 h-1.5 bg-amber rounded-full animate-thinking" style={{ animationDelay: '0.4s' }} />
    </span>
    <span>{label}</span>
    {onViewProgress && (
      <button
        className="text-[10px] px-2.5 py-0.5 border border-line-2 bg-paper rounded-retro-sm text-orange hover:bg-orange hover:text-white hover:border-orange transition-colors font-semibold"
        onClick={onViewProgress}
      >
        ดู progress
      </button>
    )}
  </div>
);

// System event card
export const FeedEventCard: React.FC<{ icon: string; title: string; subtitle?: string; time?: string }> = ({ icon, title, subtitle, time }) => (
  <div className="flex items-center gap-2.5 self-start py-1">
    <span className="text-sm">{icon}</span>
    <div className="flex-1 min-w-0">
      <div className="text-[11px] font-semibold text-ink">{title}</div>
      {subtitle && <div className="text-[10px] text-ink-3">{subtitle}</div>}
    </div>
    {time && <span className="text-[9px] text-ink-3 font-mono">{time}</span>}
  </div>
);

// Plan card with wave grouping
export const ChatPlanCard: React.FC<{
  planAgents: PlanAgent[];
  taskDescription: string;
  planType?: string;
  onApprove?: () => void;
  onReject?: () => void;
}> = ({ planAgents, taskDescription, onApprove, onReject }) => {
  // Group agents by depends_on into waves
  const wave1 = planAgents.filter(a => !a.depends_on || a.depends_on.length === 0);
  const wave1Names = wave1.map(a => a.name);
  const wave2 = planAgents.filter(a => a.depends_on?.some(d => wave1Names.includes(d)));
  const wave2Names = wave2.map(a => a.name);
  const wave3 = planAgents.filter(a =>
    a.depends_on?.some(d => wave2Names.includes(d)) && !wave1Names.includes(a.name) && !wave2Names.includes(a.name)
  );
  const remaining = planAgents.filter(a =>
    !wave1Names.includes(a.name) && !wave2Names.includes(a.name) && !wave3.map(w => w.name).includes(a.name)
  );

  const waves = [
    { label: 'Wave 1', agents: wave1 },
    { label: 'Wave 2', agents: wave2 },
    { label: 'Wave 3', agents: wave3 },
  ].filter(w => w.agents.length > 0);

  const agentIcon = (role: string): string => {
    const r = role.toLowerCase();
    if (r.includes('analyst') || r.includes('product')) return '📊';
    if (r.includes('copy') || r.includes('writer')) return '✍️';
    if (r.includes('image') || r.includes('design')) return '🎨';
    if (r.includes('seo') || r.includes('search')) return '🔍';
    if (r.includes('manager')) return '🧠';
    return '🤖';
  };

  return (
    <div className="self-start max-w-[80%] bg-paper border border-line border-l-4 border-l-orange rounded-retro overflow-hidden">
      <div className="p-2.5 flex flex-col gap-2">
        {waves.map((wave, i) => (
          <div key={i} className="px-2.5 py-1.5 bg-cream rounded-retro-sm border-l-[3px] border-l-line-2">
            <div className="text-[9px] font-bold text-ink-3 uppercase tracking-wider mb-1">{wave.label}</div>
            {wave.agents.map((agent, j) => (
              <div key={j} className="flex items-center gap-2 text-[11px] text-ink-2 leading-relaxed">
                <span className="text-base w-5 text-center">{agentIcon(agent.role)}</span>
                <span>{agent.name} — {agent.goal || agent.role}</span>
              </div>
            ))}
          </div>
        ))}
        {remaining.length > 0 && (
          <div className="px-2.5 py-1.5 bg-cream rounded-retro-sm border-l-[3px] border-l-line-2">
            {remaining.map((agent, j) => (
              <div key={j} className="flex items-center gap-2 text-[11px] text-ink-2 leading-relaxed">
                <span className="text-base w-5 text-center">{agentIcon(agent.role)}</span>
                <span>{agent.name} — {agent.goal || agent.role}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="px-3.5 py-1.5 text-[10px] text-ink-3 font-mono border-t border-line">
        {planAgents.length} agents · {waves.length} waves · {taskDescription}
      </div>
      <div className="flex gap-2 p-2.5">
        <button
          className="flex-1 py-1.5 px-4 rounded-retro-sm text-[12px] font-bold border border-line-2 bg-paper text-ink-2 hover:bg-cream-2 transition-colors"
          onClick={onReject}
        >
          ปฏิเสธ
        </button>
        <button
          className="flex-1 py-1.5 px-4 rounded-retro-sm text-[12px] font-bold border border-green bg-green text-white hover:bg-green-light transition-colors shadow-retro"
          onClick={onApprove}
        >
          อนุมัติแผน
        </button>
      </div>
    </div>
  );
};

// Result as separate agent bubbles
export const FeedResultBubbles: React.FC<{
  agents: ResultAgent[];
  summary?: string;
  isError?: boolean;
}> = ({ agents, summary, isError }) => {
  const agentIcon = (name: string): string => {
    const n = name.toLowerCase();
    if (n.includes('analyst') || n.includes('product')) return '📊';
    if (n.includes('copy') || n.includes('writer')) return '✍️';
    if (n.includes('image') || n.includes('design')) return '🎨';
    if (n.includes('seo') || n.includes('search')) return '🔍';
    if (n.includes('manager')) return '🧠';
    return '🤖';
  };

  return (
    <>
      {agents.map((agent, i) => (
        <FeedAgentMessage key={i} avatar={agentIcon(agent.name)} name={agent.name}>
          {agent.output}
        </FeedAgentMessage>
      ))}
      <FeedAgentMessage avatar="🧠" name="Manager">
        {isError ? 'เกิดข้อผิดพลาด ❌' : 'เสร็จหมดแล้วครับ ✅'}
        {summary && <span className="text-[10px] text-ink-3 font-mono ml-1.5">{summary}</span>}
      </FeedAgentMessage>
    </>
  );
};
