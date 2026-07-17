import { useState } from 'react';
import { Users, Plus, Trash2, Wallet, MessageSquare } from 'lucide-react';
import type { Team } from '../types/team';
import type { Agent } from '../types/platform';
import type { CreditsInfo } from '../types/platform';
import { useAuth } from '../context/AuthContext';
import { LogOut } from 'lucide-react';
import { formatResetDate } from '../utils/credits';

const GRADIENTS = [
  'from-accent to-purple-500',
  'from-amber-500 to-red-500',
  'from-emerald-500 to-cyan-500',
  'from-pink-500 to-rose-500',
  'from-blue-500 to-indigo-500',
];

function teamGradient(teamId: string) {
  let hash = 0;
  for (let i = 0; i < teamId.length; i++) hash = teamId.charCodeAt(i) + ((hash << 5) - hash);
  return GRADIENTS[Math.abs(hash) % GRADIENTS.length];
}

function timeAgo(dateStr: string) {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (diff < 60) return 'เมื่อกี้';
  if (diff < 3600) return `${Math.floor(diff / 60)} นาทีที่แล้ว`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ชั่วโมงที่แล้ว`;
  if (diff < 604800) return `${Math.floor(diff / 86400)} วันที่แล้ว`;
  return `${Math.floor(diff / 604800)} สัปดาห์ที่แล้ว`;
}

interface TeamListPageProps {
  teams: Team[];
  agents: Agent[];
  credits?: CreditsInfo | null;
  systemStatus: string;
  onCreateTeam: () => void;
  onAICreateTeam: () => void;
  onSelectTeam: (teamId: string) => void;
  onDeleteTeam: (teamId: string) => void;
}

export const TeamListPage: React.FC<TeamListPageProps> = ({
  teams,
  agents,
  credits,
  systemStatus,
  onCreateTeam,
  onAICreateTeam,
  onSelectTeam,
  onDeleteTeam,
}) => {
  const { user, logout } = useAuth();
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const isConnected = systemStatus !== 'Connecting...';

  const getTeamAgents = (team: Team) => {
    return agents.filter((a) => team.agent_ids.includes(a.id));
  };

  return (
    <div className="h-full w-full flex flex-col bg-bg">
      {/* Header */}
      <header className="h-12 bg-surface border-b border-border flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-accent" />
          <h1 className="text-sm font-semibold text-text">Agent Teams</h1>
        </div>
        <div className="flex items-center gap-3">
          {credits && (
            <div className="flex items-center gap-1.5 text-xs text-text-2" title={`Daily: $${credits.usage_daily?.toFixed(4) ?? 0} | Weekly: $${credits.usage_weekly?.toFixed(4) ?? 0} | Monthly: $${credits.usage_monthly?.toFixed(4) ?? 0} | All-time: $${credits.usage?.toFixed(4) ?? 0}`}>
              <Wallet className="w-3.5 h-3.5" />
              {credits.limit !== null && credits.limit > 0 ? (
                (() => {
                  const usedThisPeriod = (credits.limit ?? 0) - (credits.limit_remaining ?? 0);
                  const isLow = (credits.limit_remaining ?? 0) < 1;
                  return (
                    <span className={isLow ? 'text-warning' : ''}>
                      ${usedThisPeriod.toFixed(2)} / ${credits.limit?.toFixed(2) ?? '—'}
                      {credits.limit_reset && <span className="text-text-3 ml-1">(รีเซ็ต {formatResetDate(credits.limit_reset)})</span>}
                    </span>
                  );
                })()
              ) : credits.is_free_tier ? (
                <span className="text-warning">Free Tier</span>
              ) : (
                <span>${credits.usage?.toFixed(2) ?? '—'} used</span>
              )}
            </div>
          )}
          <div className="flex items-center gap-1.5 text-xs text-text-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-success' : 'bg-warning'} ${isConnected ? '' : 'animate-pulse'}`} />
            <span>{systemStatus}</span>
          </div>
          {user && (
            <div className="flex items-center gap-2 pl-3 ml-1 border-l border-border">
              <div className="flex items-center gap-1.5 text-xs text-text-2">
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt="" className="w-5 h-5 rounded-full" />
                ) : (
                  <div className="w-5 h-5 rounded-full bg-accent/20 flex items-center justify-center text-[10px] font-medium text-accent">
                    {user.username.charAt(0).toUpperCase()}
                  </div>
                )}
                <span>{user.username}</span>
              </div>
              <button onClick={logout} className="p-1 text-text-2 hover:text-error transition-colors" title="Logout">
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-auto px-10 py-8">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-2xl font-bold text-text">Teams</h1>
              <p className="text-sm text-text-2 mt-1">เลือกทีมเพื่อเริ่มทำงาน หรือสร้างทีมใหม่</p>
            </div>
            <button
              onClick={onAICreateTeam}
              className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/30 rounded-lg text-sm font-medium hover:bg-accent/20 transition-colors"
            >
              <MessageSquare className="w-4 h-4 text-accent" />
              คุยกับ AI สร้างทีม
            </button>
          </div>

          {/* Team cards */}
          {teams.length === 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <button
                onClick={onCreateTeam}
                className="border border-dashed border-border rounded-xl flex flex-col items-center justify-center min-h-[200px] text-text-3 hover:text-text hover:border-accent/50 transition-colors"
              >
                <Plus className="w-8 h-8 mb-1" />
                <span className="text-sm">สร้างทีมใหม่</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {teams.map((team) => {
                const teamAgents = getTeamAgents(team);
                const manager = teamAgents.find((a) => a.is_manager);
                const regularAgents = teamAgents.filter((a) => !a.is_manager);
                const displayAgents = manager ? [manager, ...regularAgents] : regularAgents;
                return (
                  <div
                    key={team.id}
                    className="bg-surface border border-border rounded-xl p-5 cursor-pointer hover:border-accent hover:bg-surface-2/30 transition-all group relative"
                    onClick={() => onSelectTeam(team.id)}
                  >
                    {/* Delete action */}
                    {confirmDelete === team.id ? (
                      <div className="absolute top-4 right-4 flex items-center gap-1 z-10" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => { onDeleteTeam(team.id); setConfirmDelete(null); }}
                          className="px-2 py-1 bg-error text-white text-[10px] rounded font-medium"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => setConfirmDelete(null)}
                          className="px-2 py-1 bg-surface-2 text-text-2 text-[10px] rounded font-medium border border-border"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={(e) => { e.stopPropagation(); setConfirmDelete(team.id); }}
                        className="absolute top-4 right-4 p-1.5 rounded-md bg-surface-2 border border-border text-text-3 hover:text-error opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete team"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}

                    <div className="flex items-center gap-3 mb-3">
                      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${teamGradient(team.id)} flex items-center justify-center text-lg font-bold text-white shrink-0`}>
                        {team.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0 pr-10">
                        <h3 className="text-[15px] font-semibold text-text truncate">{team.name}</h3>
                        {team.description && <p className="text-xs text-text-2 truncate">{team.description}</p>}
                      </div>
                    </div>

                    <div className="flex items-center gap-3 text-[11px] text-text-2 mb-3">
                      <span className="flex items-center gap-1">
                        <MessageSquare className="w-3 h-3" />
                        {(team as any).session_count ?? 0} sessions
                      </span>
                      <span>📅 {timeAgo(team.created_at)}</span>
                    </div>

                    <div className="flex flex-wrap gap-1.5 pt-3 border-t border-border">
                      {displayAgents.slice(0, 8).map((agent) => (
                        <div
                          key={agent.id}
                          className={`flex items-center gap-1 rounded-md px-2 py-1 text-[10px] ${agent.is_manager ? 'bg-accent/10 border border-accent/30' : 'bg-surface-2'}`}
                        >
                          <div className={`w-1.5 h-1.5 rounded-full ${agent.status === 'Busy' ? 'bg-warning' : 'bg-success'}`} />
                          <span className={`font-medium ${agent.is_manager ? 'text-purple-400' : 'text-text'}`}>{agent.name}</span>
                          {agent.role && <span className="text-text-3 text-[9px]">{agent.role}</span>}
                        </div>
                      ))}
                      {displayAgents.length > 8 && (
                        <span className="text-[10px] text-text-3 px-1 py-1">+{displayAgents.length - 8}</span>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-3 mt-3 border-t border-border">
                      <div className="flex items-center gap-1.5 text-[10px] text-text-2">
                        <span className={`px-1.5 py-0.5 rounded text-[9px] ${team.manager_model && team.manager_model !== 'auto' ? 'bg-accent/15 text-purple-400' : 'bg-success/15 text-success'}`}>
                          {team.manager_model && team.manager_model !== 'auto' ? team.manager_model : 'Auto'}
                        </span>
                        <span>Manager model</span>
                      </div>
                    </div>
                  </div>
                );
              })}
              {/* Create team card */}
              <button
                onClick={onCreateTeam}
                className="border border-dashed border-border rounded-xl flex flex-col items-center justify-center min-h-[200px] text-text-3 hover:text-text hover:border-accent/50 transition-colors"
              >
                <Plus className="w-8 h-8 mb-1" />
                <span className="text-sm">สร้างทีมใหม่</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
