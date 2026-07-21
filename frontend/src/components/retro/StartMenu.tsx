import type { WindowId } from './types';

interface StartMenuProps {
  open: boolean;
  onClose: () => void;
  onOpenWindow: (id: WindowId) => void;
  onBack?: () => void;
}

const menuItems: { id: WindowId; icon: string; label: string }[] = [
  { id: 'chat', icon: '💬', label: 'Chat' },
  { id: 'tasks', icon: '📋', label: 'Tasks' },
  { id: 'agents', icon: '🤖', label: 'Agents' },
  { id: 'history', icon: '📜', label: 'History' },
  { id: 'schedule', icon: '⏰', label: 'Schedule' },
  { id: 'settings', icon: '⚙️', label: 'Settings' },
];

export const StartMenu: React.FC<StartMenuProps> = ({ open, onClose, onOpenWindow, onBack }) => {
  if (!open) return null;

  const handleClick = (id: WindowId) => {
    onOpenWindow(id);
    onClose();
  };

  return (
    <>
      <div className="fixed inset-0 z-[999]" onClick={onClose} />
      <div className="fixed bottom-11 left-2 z-[1001] w-56 bg-paper border border-line-2 rounded-retro shadow-retro-lg overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-orange to-orange-light text-white text-sm font-bold">
          <span className="text-base">🪟</span>
          Agent OS
        </div>
        <div className="p-1.5">
          {menuItems.map(item => (
            <button
              key={item.id}
              className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-retro-sm text-[12px] text-ink hover:bg-cream transition-colors text-left"
              onClick={() => handleClick(item.id)}
            >
              <span className="text-base">{item.icon}</span>
              <span className="font-medium">{item.label}</span>
            </button>
          ))}
        </div>
        {onBack && (
          <div className="border-t border-line p-1.5">
            <button
              className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-retro-sm text-[12px] text-ink-2 hover:bg-cream transition-colors text-left"
              onClick={() => { onBack(); onClose(); }}
            >
              <span className="text-base">�</span>
              <span>Back to team</span>
            </button>
          </div>
        )}
      </div>
    </>
  );
};
