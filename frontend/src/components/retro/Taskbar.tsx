import { useWindowManager } from './WindowManager';
import type { WindowId } from './types';
import type { CreditsInfo } from '../../types/platform';
import { formatResetDate } from '../../utils/credits';

interface TaskbarProps {
  startMenuOpen: boolean;
  onToggleStartMenu: () => void;
  onOpenWindow: (id: WindowId) => void;
  credits?: CreditsInfo | null;
  notificationCount?: number;
}

export const Taskbar: React.FC<TaskbarProps> = ({ startMenuOpen, onToggleStartMenu, onOpenWindow, credits, notificationCount = 0 }) => {
  const { windows, activeWindowId, focusWindow, minimizeWindow } = useWindowManager();

  const handleTaskClick = (id: string) => {
    const win = windows.find(w => w.id === id);
    if (!win) return;
    if (win.minimized) {
      focusWindow(id);
    } else if (activeWindowId === id) {
      minimizeWindow(id);
    } else {
      focusWindow(id);
    }
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 h-10 bg-cream-2 border-t border-line-2 flex items-center gap-1 px-2 z-[1000]">
      {/* Start button */}
      <button
        className={`flex items-center gap-1.5 px-3.5 py-1.5 border rounded-retro text-xs font-bold transition-colors ${
          startMenuOpen
            ? 'bg-orange text-white border-orange'
            : 'bg-paper text-ink border-line-2 hover:bg-cream hover:border-orange'
        }`}
        onClick={onToggleStartMenu}
      >
        <span className="text-sm">🪟</span>
        <span>Start</span>
      </button>

      <div className="w-px h-6 bg-line-2 mx-1" />

      {/* Window tabs */}
      <div className="flex items-center gap-1 flex-1 overflow-hidden">
        {windows.map(w => (
          <button
            key={w.id}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 border rounded-retro text-[11px] font-medium transition-colors max-w-[160px] truncate ${
              activeWindowId === w.id && !w.minimized
                ? 'bg-paper border-line-2 text-ink'
                : 'bg-cream border-line text-ink-2 hover:bg-cream-2'
            }`}
            onClick={() => handleTaskClick(w.id)}
          >
            <span className="text-xs">{w.icon}</span>
            <span className="truncate">{w.title}</span>
          </button>
        ))}
      </div>

      <div className="w-px h-6 bg-line-2 mx-1" />

      {/* System tray */}
      <div className="flex items-center gap-2 px-2">
        <div className="relative cursor-pointer" title={`${notificationCount} items need approval`} onClick={() => onOpenWindow('notifications')}>
          <span className="text-sm">🔔</span>
          {notificationCount > 0 && (
            <span className="absolute -top-1 -right-1 bg-red text-white text-[8px] font-bold rounded-full w-3.5 h-3.5 flex items-center justify-center">{notificationCount}</span>
          )}
        </div>
        {credits && credits.limit !== null && credits.limit > 0 ? (
          <span className="text-[10px] font-mono text-ink-2" title={`Daily: $${credits.usage_daily?.toFixed(4) ?? 0} | Weekly: $${credits.usage_weekly?.toFixed(4) ?? 0} | Monthly: $${credits.usage_monthly?.toFixed(4) ?? 0}`}>
            ${(credits.limit_remaining ?? 0).toFixed(2)} / ${credits.limit.toFixed(2)}
            {credits.limit_reset && <span className="text-ink-3 ml-1">(Reset: {formatResetDate(credits.limit_reset)})</span>}
          </span>
        ) : credits && credits.is_free_tier ? (
          <span className="text-[10px] font-mono text-orange">Free Tier</span>
        ) : credits ? (
          <span className="text-[10px] font-mono text-ink-2">${credits.usage?.toFixed(2) ?? '—'} used</span>
        ) : null}
      </div>
    </div>
  );
};
