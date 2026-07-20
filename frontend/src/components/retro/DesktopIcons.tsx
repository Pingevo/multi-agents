import { useState } from 'react';
import type { WindowId } from './types';

interface DesktopIconsProps {
  onOpenWindow: (id: WindowId) => void;
}

const icons: { id: WindowId; icon: string; label: string }[] = [
  { id: 'chat', icon: '💬', label: 'Chat' },
  { id: 'tasks', icon: '📋', label: 'Tasks' },
  { id: 'agents', icon: '🤖', label: 'Agents' },
  { id: 'history', icon: '📜', label: 'History' },
  { id: 'schedule', icon: '⏰', label: 'Schedule' },
  { id: 'settings', icon: '⚙️', label: 'Settings' },
];

export const DesktopIcons: React.FC<DesktopIconsProps> = ({ onOpenWindow }) => {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="absolute top-3 left-3 flex flex-col gap-2">
      {icons.map(ic => (
        <div
          key={ic.id}
          className={`w-[72px] flex flex-col items-center gap-1 cursor-pointer px-1 py-2 rounded-retro transition-colors text-center ${
            selected === ic.id ? 'bg-orange/10 outline outline-1 outline-dashed outline-orange' : 'hover:bg-orange/5'
          }`}
          onClick={() => setSelected(ic.id)}
          onDoubleClick={() => onOpenWindow(ic.id)}
        >
          <span className="text-[28px] leading-none saturate-90">{ic.icon}</span>
          <span className="text-[10px] text-ink-2 font-medium leading-tight">{ic.label}</span>
        </div>
      ))}
    </div>
  );
};
