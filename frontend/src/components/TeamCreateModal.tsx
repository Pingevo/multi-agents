import { useState, useRef } from 'react';
import { X, Cpu, ChevronDown } from 'lucide-react';
import { ModelPicker, PROVIDER_FAVICONS, getProvider, findModelName } from './ModelPicker';
import type { ModelCatalogEntry } from './ModelPicker';

interface TeamCreateModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (data: { name: string; description: string; manager_model: string }) => void;
  onFetchModelCatalog?: () => void;
  onSearchModels?: (query: string) => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  selectedModel?: string;
  resolvedModel?: string;
}

export const TeamCreateModal: React.FC<TeamCreateModalProps> = ({
  open,
  onClose,
  onCreate,
  onFetchModelCatalog,
  onSearchModels,
  modelCatalog = {},
  modelSearchResults = [],
  selectedModel: externalSelectedModel,
  resolvedModel,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [managerModel, setManagerModel] = useState('');
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const inputBarRef = useRef<HTMLDivElement>(null);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onCreate({ name: name.trim(), description: description.trim(), manager_model: managerModel || 'auto' });
    setName('');
    setDescription('');
    setManagerModel('');
    onClose();
  };

  const handleOpenModelPicker = () => {
    if (modelPickerOpen) {
      setModelPickerOpen(false);
      return;
    }
    if (Object.keys(modelCatalog).length === 0 && onFetchModelCatalog) {
      onFetchModelCatalog();
    }
    setModelPickerOpen(true);
  };

  const handleSelectModel = (modelId: string) => {
    setManagerModel(modelId);
  };

  const handleSearchModels = (query: string) => {
    if (onSearchModels) {
      onSearchModels(query);
    }
  };

  const displayModel = managerModel || externalSelectedModel || resolvedModel || '';

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

          <div ref={inputBarRef}>
            {modelPickerOpen && (
              <ModelPicker
                recommended={modelCatalog}
                searchResults={modelSearchResults}
                selectedModel={managerModel}
                onSelect={handleSelectModel}
                onSearch={handleSearchModels}
                onClose={() => setModelPickerOpen(false)}
                anchorRef={inputBarRef}
              />
            )}
            <label className="block text-xs font-medium text-text-2 mb-1.5">Manager Model</label>
            <button
              type="button"
              onClick={handleOpenModelPicker}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors text-left ${
                modelPickerOpen
                  ? 'bg-accent/10 border-accent/40 text-text'
                  : 'bg-bg border-border text-text-2 hover:text-text hover:border-border/80'
              }`}
            >
              {(() => {
                const provider = getProvider(displayModel);
                const favicon = PROVIDER_FAVICONS[provider];
                if (favicon) {
                  return <img src={favicon} alt="" className="w-4 h-4 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />;
                }
                return <Cpu className={`w-3.5 h-3.5 shrink-0 ${modelPickerOpen ? 'text-accent' : ''}`} />;
              })()}
              <span className="text-sm font-medium text-text flex-1 truncate">
                {displayModel ? findModelName(displayModel, modelCatalog, modelSearchResults) : 'Auto Router'}
              </span>
              <span className={`text-[9px] px-1.5 py-0.5 rounded-full shrink-0 ${managerModel ? 'bg-accent/15 text-accent' : 'bg-emerald-500/15 text-emerald-500'}`}>
                {managerModel ? 'Manual' : 'Auto'}
              </span>
              <ChevronDown className={`w-3.5 h-3.5 shrink-0 transition-transform ${modelPickerOpen ? 'rotate-180' : ''}`} />
            </button>
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
