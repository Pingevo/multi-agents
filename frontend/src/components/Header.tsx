import { LayoutDashboard, Wallet, LogOut } from 'lucide-react';
import type { CreditsInfo } from '../types/platform';
import { useAuth } from '../context/AuthContext';

interface HeaderProps {
  systemStatus: string;
  credits?: CreditsInfo | null;
}

export const Header: React.FC<HeaderProps> = ({ systemStatus, credits }) => {
  const isConnected = systemStatus !== 'Connecting...';
  const { user, logout } = useAuth();
  return (
    <header className="h-12 bg-surface border-b border-border flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-2">
        <LayoutDashboard className="w-5 h-5 text-accent" />
        <h1 className="text-sm font-semibold text-text">Agent Platform</h1>
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
            <button
              onClick={logout}
              className="p-1 text-text-2 hover:text-error transition-colors"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
