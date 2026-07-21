import { useEffect } from 'react';
import type { HistoryTaskLog } from '../chatTypes';

interface HistoryWindowProps {
  historyLogs: HistoryTaskLog[];
  onFetchHistory: () => void;
}

export const HistoryWindow: React.FC<HistoryWindowProps> = ({ historyLogs, onFetchHistory }) => {
  useEffect(() => {
    onFetchHistory();
  }, [onFetchHistory]);

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-line bg-cream">
        <span className="text-[11px] font-bold text-ink">Activity History</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {historyLogs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-ink-3 text-[12px]">
            No history yet.
          </div>
        ) : (
          <div className="hist-log">
            {historyLogs.slice().reverse().map(log => (
              <div key={log.task_id}>
                <div className="hist-log-task">📁 {log.task_title}</div>
                {log.entries.map((e, i) => (
                  <div key={i} className="hist-log-entry">
                    <span className="hist-log-time">{e.time}</span>{' '}
                    <span className="hist-log-actor">{e.actor}</span>{' '}
                    <span className="hist-log-action">{e.action}</span>
                    <span className="hist-log-target">{e.target}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
