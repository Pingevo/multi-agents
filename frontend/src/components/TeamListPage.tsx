import { useState } from 'react';
import { Users, Plus, Sparkles, Trash2, Wallet } from 'lucide-react';
import type { Team } from '../types/team';
import type { Agent } from '../types/platform';
import type { CreditsInfo } from '../types/platform';
import { useAuth } from '../context/AuthContext';
import { LogOut } from 'lucide-react';

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
            <div className="flex items-center gap-1.5 text-xs text-text-2" title={`Daily: $${credits.usage_daily?.toFixed(4) ?? 0} | Monthly: $${credits.usage_monthly?.toFixed(4) ?? 0}`}>
              <Wallet className="w-3.5 h-3.5" />
              {credits.limit !== null && credits.limit > 0 ? (
                <span className={credits.limit_remaining !== null && credits.limit_remaining < 1 ? 'text-warning' : ''}>
                  ${credits.usage?.toFixed(2) ?? '0'} / ${credits.limit?.toFixed(2) ?? '—'}
                </span>
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
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-5xl mx-auto">
          {/* Action buttons */}
          <div className="flex items-center gap-3 mb-6">
            <button
              onClick={onCreateTeam}
              className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Create Team
            </button>
            <button
              onClick={onAICreateTeam}
              className="flex items-center gap-2 px-4 py-2 bg-surface-2 text-text border border-border rounded-lg text-sm font-medium hover:border-accent/50 transition-colors"
            >
              <Sparkles className="w-4 h-4 text-accent" />
              Create with AI
            </button>
          </div>

          {/* Team cards */}
          {teams.length === 0 ? (
            <div className="text-center py-20">
              <Users className="w-12 h-12 text-text-3 mx-auto mb-3" />
              <p className="text-text-2 text-sm">ยังไม่มีทีม สร้างทีมใหม่เพื่อเริ่มใช้งาน</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {teams.map((team) => {
                const teamAgents = getTeamAgents(team);
                return (
                  <div
                    key={team.id}
                    className="bg-surface border border-border rounded-xl p-4 hover:border-accent/30 transition-all cursor-pointer group relative"
                    onClick={() => onSelectTeam(team.id)}
                  >
                    {/* Delete button */}
                    {confirmDelete === team.id ? (
                      <div className="absolute top-2 right-2 flex items-center gap-1 z-10" onClick={(e) => e.stopPropagation()}>
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
                        className="absolute top-2 right-2 p-1.5 text-text-3 hover:text-error opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete team"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}

                    <h3 className="text-sm font-semibold text-text mb-1 pr-8">{team.name}</h3>
                    {team.description && (
                      <p className="text-xs text-text-2 mb-3 line-clamp-2">{team.description}</p>
                    )}

                    {/* Agent count + list preview */}
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-[10px] text-text-3 uppercase tracking-wide">Agents</span>
                      <span className="text-xs text-text-2 font-medium">{teamAgents.length}</span>
                    </div>

                    {teamAgents.length > 0 ? (
                      <div className="space-y-1">
                        {teamAgents.slice(0, 4).map((agent) => (
                          <div key={agent.id} className="flex items-center gap-2 text-xs text-text-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-accent/50" />
                            <span className="font-medium text-text">{agent.name}</span>
                            <span className="text-text-3 truncate">{agent.role}</span>
                          </div>
                        ))}
                        {teamAgents.length > 4 && (
                          <p className="text-[10px] text-text-3 pl-3.5">+{teamAgents.length - 4} more</p>
                        )}
                      </div>
                    ) : (
                      <p className="text-xs text-text-3 italic">No agents yet</p>
                    )}

                    {/* Footer */}
                    <div className="mt-3 pt-3 border-t border-border flex items-center justify-between">
                      <span className="text-[10px] text-text-3">
                        {team.manager_model !== 'auto' ? team.manager_model : 'Auto model'}
                      </span>
                      <span className="text-[10px] text-text-3">
                        {new Date(team.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
