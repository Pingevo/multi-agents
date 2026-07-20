import { useState, useEffect } from 'react';
import { useWindowManager } from './WindowManager';
import type { WindowId } from './types';

interface TaskbarProps {
  startMenuOpen: boolean;
  onToggleStartMenu: () => void;
  onOpenWindow: (id: WindowId) => void;
}

export const Taskbar: React.FC<TaskbarProps> = ({ startMenuOpen, onToggleStartMenu, onOpenWindow }) => {
  const { windows, activeWindowId, focusWindow, minimizeWindow } = useWindowManager();
  const [time, setTime] = useState('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      const h = now.getHours();
      const m = now.getMinutes().toString().padStart(2, '0');
      const ampm = h >= 12 ? 'PM' : 'AM';
      const h12 = h % 12 || 12;
      setTime(`${h12}:${m} ${ampm}`);
    };
    update();
    const interval = setInterval(update, 30000);
    return () => clearInterval(interval);
  }, []);

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
        <div className="relative cursor-pointer" title="2 items need approval" onClick={() => onOpenWindow('tasks')}>
          <span className="text-sm">🔔</span>
          <span className="absolute -top-1 -right-1 bg-red text-white text-[8px] font-bold rounded-full w-3.5 h-3.5 flex items-center justify-center">2</span>
        </div>
        <span className="text-xs font-mono text-ink-2">{time}</span>
      </div>
    </div>
  );
};
