import { Info } from 'lucide-react';

interface ToastProps {
  notifications: string[];
}

export const Toast: React.FC<ToastProps> = ({ notifications }) => {
  if (notifications.length === 0) return null;

  return (
    <div className="fixed bottom-16 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {notifications.map((note, i) => (
        <div
          key={i}
          className="flex items-start gap-2 p-3 rounded-lg bg-surface border border-border shadow-lg text-sm text-text animate-in slide-in-from-right"
        >
          <Info className="w-4 h-4 text-accent shrink-0 mt-0.5" />
          <span>{note}</span>
        </div>
      ))}
    </div>
  );
};
