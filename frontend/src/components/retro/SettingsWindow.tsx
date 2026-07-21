import type { CreditsInfo } from '../../types/platform';
import type { Team } from '../../types/team';
import { useAuth } from '../../context/AuthContext';

interface SettingsWindowProps {
  credits: CreditsInfo | null;
  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  systemStatus?: string;
  team: Team;
  onBack: () => void;
  onDeleteTeam: (teamId: string) => void;
}

export const SettingsWindow: React.FC<SettingsWindowProps> = ({
  credits, connectionStatus, systemStatus, team, onBack, onDeleteTeam,
}) => {
  const { user, logout } = useAuth();
  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-line bg-cream">
        <span className="text-[11px] font-bold text-ink">Settings</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3.5 flex flex-col gap-2.5">
        {/* Connection status */}
        <div className="bg-paper border border-line rounded-retro p-3">
          <div className="text-[11px] font-bold text-ink mb-2">Connection</div>
          <div className="flex items-center gap-2 mb-1">
            <div className={`w-2.5 h-2.5 rounded-full ${
              connectionStatus === 'connected' ? 'bg-green' :
              connectionStatus === 'connecting' ? 'bg-amber' : 'bg-red'
            }`} />
            <span className="text-[11px] text-ink-2">
              {connectionStatus === 'connected' ? 'Connected' :
               connectionStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
            </span>
          </div>
          {systemStatus && <div className="text-[10px] text-ink-3 font-mono">{systemStatus}</div>}
        </div>

        {/* Credits */}
        <div className="bg-paper border border-line rounded-retro p-3">
          <div className="text-[11px] font-bold text-ink mb-2">Credits</div>
          {credits ? (
            <div className="flex flex-col gap-1">
              <div className="flex justify-between text-[10px]">
                <span className="text-ink-3">Daily usage:</span>
                <span className="text-ink font-mono">{credits.usage_daily.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-[10px]">
                <span className="text-ink-3">Weekly usage:</span>
                <span className="text-ink font-mono">{(credits.usage_weekly || 0).toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-[10px]">
                <span className="text-ink-3">Monthly usage:</span>
                <span className="text-ink font-mono">{credits.usage_monthly.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-[10px]">
                <span className="text-ink-3">Total usage:</span>
                <span className="text-ink font-mono">{credits.usage.toFixed(2)}</span>
              </div>
              {credits.limit !== null && (
                <>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-ink-3">Limit:</span>
                    <span className="text-ink font-mono">{credits.limit.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-ink-3">Remaining:</span>
                    <span className="text-ink font-mono">{(credits.limit_remaining || 0).toFixed(2)}</span>
                  </div>
                  {credits.limit_reset && (
                    <div className="flex justify-between text-[10px]">
                      <span className="text-ink-3">Reset:</span>
                      <span className="text-ink font-mono">{credits.limit_reset}</span>
                    </div>
                  )}
                </>
              )}
              <div className="flex justify-between text-[10px] mt-1 pt-1 border-t border-line">
                <span className="text-ink-3">Tier:</span>
                <span className={`font-bold ${credits.is_free_tier ? 'text-amber' : 'text-green'}`}>
                  {credits.is_free_tier ? 'Free' : 'Paid'}
                </span>
              </div>
            </div>
          ) : (
            <div className="text-[10px] text-ink-3">No credit info available.</div>
          )}
        </div>

        {/* Account */}
        <div className="bg-paper border border-line rounded-retro p-3">
          <div className="text-[11px] font-bold text-ink mb-2">Account</div>
          {user && (
            <>
              <div className="text-[10px] text-ink-2 mb-0.5"><span className="text-ink-3">User:</span> {user.username}</div>
              <div className="text-[10px] text-ink-2 mb-0.5"><span className="text-ink-3">Email:</span> {user.email}</div>
              <div className="text-[10px] text-ink-2 mb-2"><span className="text-ink-3">Provider:</span> {user.provider}</div>
            </>
          )}
          <div className="text-[10px] text-ink-2 mb-0.5"><span className="text-ink-3">Team:</span> {team.name}</div>
          {team.description && (
            <div className="text-[10px] text-ink-2 mb-0.5"><span className="text-ink-3">Desc:</span> {team.description}</div>
          )}
          <div className="text-[10px] text-ink-2 mb-2"><span className="text-ink-3">ID:</span> <span className="font-mono">{team.id}</span></div>
          <div className="mt-2 pt-2 border-t border-line">
            <button
              className="text-[10px] px-2.5 py-1.5 border border-line-2 bg-paper text-ink-2 rounded-retro-sm font-bold hover:bg-cream-2 transition-colors w-full"
              onClick={() => {
                if (confirm('Logout?')) {
                  logout();
                }
              }}
            >
              🚪 Logout
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
