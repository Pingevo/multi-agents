import { useState } from 'react';
import { MessageSquare, Plus, Trash2, Pencil, Check, X } from 'lucide-react';

export interface ChatSession {
  id: string;
  title: string;
  updated_at: string;
}

interface ChatSidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onNewChat: () => void;
  onSwitchChat: (id: string) => void;
  onRenameChat: (id: string, title: string) => void;
  onDeleteChat: (id: string) => void;
  isNewChatDisabled?: boolean;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  sessions,
  activeSessionId,
  onNewChat,
  onSwitchChat,
  onRenameChat,
  onDeleteChat,
  isNewChatDisabled = false,
}) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const startEdit = (id: string, currentTitle: string) => {
    setEditingId(id);
    setEditTitle(currentTitle);
  };

  const confirmEdit = () => {
    if (editingId && editTitle.trim()) {
      onRenameChat(editingId, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle('');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditTitle('');
  };

  return (
    <div className="w-56 shrink-0 border-r border-border bg-surface flex flex-col">
      <div className="p-3 border-b border-border">
        <button
          onClick={onNewChat}
          disabled={isNewChatDisabled}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-accent/10 text-accent text-sm font-medium hover:bg-accent/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-accent/10"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {sessions.length === 0 ? (
          <div className="text-xs text-text-2 text-center py-4">No chats yet</div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.id}
              className={`group flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-colors ${
                session.id === activeSessionId
                  ? 'bg-accent/10 text-text'
                  : 'text-text-2 hover:bg-surface-2'
              }`}
              onClick={() => editingId !== session.id && onSwitchChat(session.id)}
            >
              <MessageSquare className="w-3.5 h-3.5 shrink-0" />
              {editingId === session.id ? (
                <div className="flex-1 flex items-center gap-1">
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') confirmEdit();
                      if (e.key === 'Escape') cancelEdit();
                    }}
                    autoFocus
                    className="flex-1 min-w-0 bg-bg border border-border rounded px-1 py-0.5 text-xs text-text"
                  />
                  <button onClick={(e) => { e.stopPropagation(); confirmEdit(); }} className="text-success hover:opacity-70">
                    <Check className="w-3 h-3" />
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); cancelEdit(); }} className="text-text-2 hover:opacity-70">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ) : (
                <>
                  <span className="flex-1 truncate text-xs">{session.title}</span>
                  <div className="hidden group-hover:flex items-center gap-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); startEdit(session.id, session.title); }}
                      className="text-text-2 hover:text-text"
                    >
                      <Pencil className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm('Delete this chat?')) onDeleteChat(session.id);
                      }}
                      className="text-text-2 hover:text-danger"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
