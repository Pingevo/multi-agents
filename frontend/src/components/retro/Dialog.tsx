import { type ReactNode } from 'react';

interface DialogProps {
  open: boolean;
  icon: string;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}

export const Dialog: React.FC<DialogProps> = ({ open, icon, title, onClose, children, footer }) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/20" onClick={onClose}>
      <div
        className="bg-paper border border-line-2 rounded-retro shadow-retro-lg flex flex-col max-w-[90vw] max-h-[80vh] min-w-[320px]"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 py-2 bg-cream border-b border-line select-none">
          <span className="text-sm">{icon}</span>
          <span className="flex-1 text-[12px] font-semibold text-ink-2">{title}</span>
          <button
            className="w-5 h-5 border border-line-2 bg-paper rounded-retro-sm text-[10px] flex items-center justify-center text-ink-2 hover:bg-red hover:text-white hover:border-red transition-colors"
            onClick={onClose}
          >
            x
          </button>
        </div>
        <div className="flex-1 overflow-auto p-4 min-h-0">
          {children}
        </div>
        {footer && (
          <div className="flex items-center justify-end gap-2 px-3 py-2 border-t border-line bg-cream">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
