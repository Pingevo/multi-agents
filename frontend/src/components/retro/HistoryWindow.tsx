import type { ActivityEntry } from '../chatTypes';

interface HistoryWindowProps {
  activityLog: ActivityEntry[];
}

export const HistoryWindow: React.FC<HistoryWindowProps> = ({ activityLog }) => {
  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-line bg-cream">
        <span className="text-[11px] font-bold text-ink">Activity History</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2.5 flex flex-col gap-1">
        {activityLog.length === 0 ? (
          <div className="flex items-center justify-center h-full text-ink-3 text-[12px]">
            No activity yet.
          </div>
        ) : (
          activityLog.map(entry => (
            <div
              key={entry.id}
              className="flex items-center gap-2 px-2.5 py-2 bg-paper border border-line rounded-retro-sm"
            >
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${entry.status === 'current' ? 'bg-amber' : 'bg-green'}`} />
              <span className="text-[11px] text-ink-2 flex-1">{entry.text}</span>
              <span className="text-[9px] text-ink-3 font-mono flex-shrink-0">
                {new Date(entry.timestamp).toLocaleTimeString()}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
