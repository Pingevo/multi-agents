import { useState } from 'react';
import { X } from 'lucide-react';

interface TeamCreateModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (data: { name: string; description: string; manager_model: string }) => void;
}

export const TeamCreateModal: React.FC<TeamCreateModalProps> = ({ open, onClose, onCreate }) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [managerModel, setManagerModel] = useState('auto');

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onCreate({ name: name.trim(), description: description.trim(), manager_model: managerModel });
    setName('');
    setDescription('');
    setManagerModel('auto');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-md bg-surface border border-border rounded-2xl shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text">Create New Team</h2>
          <button onClick={onClose} className="p-1 text-text-3 hover:text-text transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-text-2 mb-1.5">Team Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Marketing Team"
              autoFocus
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text placeholder-text-3 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-2 mb-1.5">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this team do?"
              rows={3}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text placeholder-text-3 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-transparent resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-2 mb-1.5">Manager Model</label>
            <select
              value={managerModel}
              onChange={(e) => setManagerModel(e.target.value)}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
            >
              <option value="auto">Auto (OpenRouter selects)</option>
              <option value="openrouter/auto">openrouter/auto</option>
              <option value="openrouter/free">openrouter/free</option>
            </select>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <button
              type="submit"
              disabled={!name.trim()}
              className="flex-1 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Create Team
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-surface-2 text-text-2 border border-border rounded-lg text-sm font-medium hover:text-text transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
