import type { Agent } from '../../types/platform';
import { agentIcon, isManager } from './AgentsWindow';

interface TeamRosterBarProps {
  agents: Agent[];
  onAgentClick: (agentId: string) => void;
  onAddAgent?: () => void;
  activeAgentId?: string | null;
}

const statusInfo = (status: string): { color: string; label: string; running: boolean } => {
  const s = (status || '').toLowerCase();
  if (s.includes('running') || s.includes('busy')) return { color: 'var(--amber)', label: 'Running', running: true };
  if (s.includes('error')) return { color: 'var(--red)', label: 'Error', running: false };
  if (s.includes('review')) return { color: 'var(--blue)', label: 'Review', running: false };
  if (s.includes('waiting')) return { color: 'var(--red)', label: 'Waiting', running: false };
  return { color: 'var(--ink3)', label: 'Idle', running: false };
};

const avatarBg = (name: string, role: string): string => {
  const n = name.toLowerCase();
  const r = role.toLowerCase();
  if (n.includes('manager') || r.includes('manager')) return 'rgba(192,80,30,0.12)';
  if (n.includes('analyst') || n.includes('product') || r.includes('analyst')) return 'rgba(58,107,138,0.12)';
  if (n.includes('copy') || n.includes('writer') || r.includes('writer') || r.includes('content')) return 'rgba(200,146,32,0.12)';
  if (n.includes('image') || n.includes('design') || n.includes('visual') || n.includes('artist')) return 'rgba(106,74,122,0.12)';
  if (n.includes('seo') || n.includes('search')) return 'rgba(90,122,74,0.12)';
  if (n.includes('video')) return 'rgba(160,48,32,0.12)';
  return 'rgba(154,144,136,0.12)';
};

export const TeamRosterBar: React.FC<TeamRosterBarProps> = ({ agents, onAgentClick, onAddAgent, activeAgentId }) => {
  return (
    <div className="roster-bar">
      <div className="roster-label">Agents</div>
      <div className="roster-cards">
        {agents.map(agent => {
          const mgr = isManager(agent);
          const stat = statusInfo(agent.status);
          const isActive = activeAgentId === agent.id;
          const cls = `roster-card${stat.running ? ' running' : ''}${isActive ? ' selected' : ''}`;
          return (
            <button
              key={agent.id}
              className={cls}
              onClick={() => onAgentClick(agent.id)}
              title={`${agent.name} — ${stat.label}`}
            >
              {stat.running && <span className="roster-pulse" />}
              <div className="rc-avatar" style={{ background: avatarBg(agent.name, agent.role) }}>
                {agentIcon(agent.name, agent.role)}
              </div>
              <div className="rc-name">
                {agent.name}
                {mgr && <span className="rc-mgr">MGR</span>}
              </div>
              <div className="rc-stat" style={{ color: stat.color }}>{stat.label}</div>
            </button>
          );
        })}
        {onAddAgent && (
          <button className="roster-card add" onClick={onAddAgent} title="Add new agent">
            <span className="rc-plus">+</span>
          </button>
        )}
      </div>
    </div>
  );
};
