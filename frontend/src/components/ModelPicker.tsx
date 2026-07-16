import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Search, Check, Cpu, Star, Sparkles } from 'lucide-react';

export interface ModelCatalogEntry {
  id: string;
  name: string;
  context_length: any;
  prompt_price: any;
  completion_price: any;
  image_price?: any;
  video_price?: any;
  audio_price?: any;
  web_search_price?: any;
  categories: string[];
  is_free: boolean;
  input_modalities?: string[];
  output_modalities?: string[];
}

interface ModelPickerProps {
  recommended: Record<string, ModelCatalogEntry[]>;
  searchResults: ModelCatalogEntry[];
  selectedModel: string;
  onSelect: (modelId: string) => void;
  onSearch: (query: string) => void;
  onClose: () => void;
  anchorRef?: React.RefObject<HTMLElement | null>;
  showAutoRouter?: boolean;
  pinnedModelId?: string;
}

export const getProvider = (modelId: string): string => {
  const parts = modelId.split('/');
  return parts.length > 1 ? parts[0] : '';
};

export const displayModelId = (modelId: string): string => {
  if (!modelId) return '';
  const parts = modelId.split('/');
  const name = parts.length > 1 ? parts[parts.length - 1] : modelId;
  return name.split(':')[0];
};

const parsePrice = (price: any): number | null => {
  if (price === '?' || price === undefined || price === null) return null;
  const num = parseFloat(price);
  return isNaN(num) ? null : num;
};

const formatPrice = (price: any): string => {
  const num = parsePrice(price);
  if (num === null) return 'Unknown';
  if (num === 0) return 'Free';
  if (num < 0.001) return `$${num.toFixed(6)}`;
  if (num < 1) return `$${num.toFixed(3)}`;
  return `$${num.toFixed(2)}`;
};

const getMaxPrice = (model: ModelCatalogEntry): number => {
  const prices = [
    parsePrice(model.prompt_price),
    parsePrice(model.completion_price),
    parsePrice(model.image_price),
    parsePrice(model.video_price),
    parsePrice(model.audio_price),
    parsePrice(model.web_search_price),
  ].filter((p): p is number => p !== null && p > 0);
  return prices.length > 0 ? Math.max(...prices) : 0;
};

const ROUTING_MODELS = ['openrouter/free'];

const WHITELISTED_MODELS = new Set([
  'openrouter/free',
  'google/gemini-3.5-flash',
  'anthropic/claude-sonnet-5',
  'openai/gpt-5.6-luna',
]);

const isModelAllowed = (model: ModelCatalogEntry): boolean => {
  return WHITELISTED_MODELS.has(model.id);
};

const isRoutingModel = (model: ModelCatalogEntry): boolean =>
  ROUTING_MODELS.includes(model.id);

const isModelFree = (model: ModelCatalogEntry): boolean => {
  if (isRoutingModel(model)) return false;
  const prices = [
    parsePrice(model.prompt_price),
    parsePrice(model.completion_price),
    parsePrice(model.image_price),
    parsePrice(model.video_price),
    parsePrice(model.audio_price),
    parsePrice(model.web_search_price),
  ];
  // Free only if all known prices are 0 (ignore unknown/null)
  const knownPrices = prices.filter((p): p is number => p !== null);
  return knownPrices.length > 0 && knownPrices.every((p) => p === 0);
};

const formatContext = (ctx: any): string => {
  if (ctx === '?' || ctx === undefined || ctx === null) return '?';
  const num = typeof ctx === 'string' ? parseInt(ctx) : ctx;
  if (isNaN(num)) return '?';
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
  return String(num);
};

// Known provider favicons — unknown providers get a generic Cpu icon
export const PROVIDER_FAVICONS: Record<string, string> = {
  'anthropic': 'https://www.google.com/s2/favicons?domain=anthropic.com&sz=32',
  'openai': 'https://www.google.com/s2/favicons?domain=openai.com&sz=32',
  'google': 'https://www.google.com/s2/favicons?domain=ai.google&sz=32',
  'meta-llama': 'https://www.google.com/s2/favicons?domain=meta.ai&sz=32',
  'deepseek': 'https://www.google.com/s2/favicons?domain=deepseek.com&sz=32',
  'qwen': 'https://www.google.com/s2/favicons?domain=qwenlm.ai&sz=32',
  'mistralai': 'https://www.google.com/s2/favicons?domain=mistral.ai&sz=32',
  'x-ai': 'https://www.google.com/s2/favicons?domain=x.ai&sz=32',
  'nvidia': 'https://www.google.com/s2/favicons?domain=nvidia.com&sz=32',
  'perplexity': 'https://www.google.com/s2/favicons?domain=perplexity.ai&sz=32',
  'cohere': 'https://www.google.com/s2/favicons?domain=cohere.com&sz=32',
  'microsoft': 'https://www.google.com/s2/favicons?domain=microsoft.com&sz=32',
};

export const getProviderFavicon = (provider: string): string | null => {
  return PROVIDER_FAVICONS[provider] || null;
};

export const stripProviderPrefix = (name: string): string => {
  const colonIdx = name.indexOf(': ');
  if (colonIdx > 0 && colonIdx < 20) {
    return name.substring(colonIdx + 2);
  }
  return name;
};

export const findModelName = (
  modelId: string,
  catalog: Record<string, ModelCatalogEntry[]>,
  searchResults: ModelCatalogEntry[]
): string => {
  if (!modelId) {
    return 'Free Router';
  }
  const all = Object.values(catalog).flat().concat(searchResults);
  const found = all.find((m) => m.id === modelId);
  if (found) return stripProviderPrefix(found.name);
  // Fallback: strip provider prefix from ID
  const parts = modelId.split('/');
  return parts.length > 1 ? parts[parts.length - 1].split(':')[0] : modelId;
};

const getModelCostTier = (model: ModelCatalogEntry): 'free' | 'low' | 'mid' | 'high' | 'unknown' => {
  if (isRoutingModel(model)) return 'unknown';
  const maxPrice = getMaxPrice(model);
  if (maxPrice === 0) {
    // Check if all prices are explicitly 0 (truly free) or all unknown
    const prices = [
      parsePrice(model.prompt_price),
      parsePrice(model.completion_price),
      parsePrice(model.image_price),
      parsePrice(model.video_price),
    ];
    const hasKnown = prices.some((p) => p !== null);
    return hasKnown ? 'free' : 'unknown';
  }
  if (maxPrice < 1) return 'low';
  if (maxPrice < 10) return 'mid';
  return 'high';
};

const COST_TIER_COLORS: Record<string, string> = {
  free: '#22c55e',
  low: '#3b82f6',
  mid: '#eab308',
  high: '#ef4444',
  unknown: '#6b7280',
};

export const ModelPicker: React.FC<ModelPickerProps> = ({
  recommended,
  searchResults,
  selectedModel,
  onSelect,
  onSearch,
  onClose,
  anchorRef,
  showAutoRouter = true,
  pinnedModelId,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'recommended' | 'search'>('recommended');
  const [hoveredModel, setHoveredModel] = useState<ModelCatalogEntry | null>(null);
  const [position, setPosition] = useState<{ top?: number; bottom?: number; right: number; maxWidth: number } | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const isAdaptive = selectedModel === '' || selectedModel === 'adaptive';
  const selectedEntry = useMemo(() => {
    if (isAdaptive) return null;
    const all = Object.values(recommended).flat().concat(searchResults);
    return all.find((m) => m.id === selectedModel) || null;
  }, [recommended, searchResults, selectedModel, isAdaptive]);

  const previewModel = hoveredModel || selectedEntry;

  useEffect(() => {
    if (activeTab === 'search' && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [activeTab]);

  useEffect(() => {
    const updatePosition = () => {
      if (anchorRef?.current) {
        const rect = anchorRef.current.getBoundingClientRect();
        const padding = 8;
        const dropdownHeight = 360;
        const viewportHeight = window.innerHeight;
        const viewportWidth = window.innerWidth;

        // Calculate right position: align right edge with anchor, clamp to viewport
        const right = Math.max(padding, Math.min(viewportWidth - rect.right, viewportWidth - 520 - padding));
        const maxWidth = Math.min(520, viewportWidth - padding * 2);

        // Decide whether to open above or below the anchor
        const spaceAbove = rect.top;
        const spaceBelow = viewportHeight - rect.bottom;

        if (spaceAbove >= dropdownHeight + padding) {
          // Open above
          setPosition({ bottom: viewportHeight - rect.top + padding, right, maxWidth });
        } else if (spaceBelow >= dropdownHeight + padding) {
          // Open below
          setPosition({ top: rect.bottom + padding, right, maxWidth });
        } else {
          // Not enough space either way — pick the side with more room and clamp
          if (spaceAbove >= spaceBelow) {
            setPosition({ bottom: padding, right, maxWidth });
          } else {
            setPosition({ top: padding, right, maxWidth });
          }
        }
      } else {
        // No anchor — center in viewport
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const maxWidth = Math.min(520, viewportWidth - 16);
        setPosition({ top: Math.max(8, (viewportHeight - 360) / 2), right: Math.max(8, (viewportWidth - maxWidth) / 2), maxWidth });
      }
    };
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [anchorRef]);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onClose]);

  const handleSearch = useCallback((value: string) => {
    setSearchQuery(value);
    if (value.trim().length >= 2) {
      setActiveTab('search');
      onSearch(value.trim());
    } else if (value.trim().length === 0) {
      setActiveTab('recommended');
    }
  }, [onSearch]);

  const handleSelect = (modelId: string) => {
    onSelect(modelId);
    onClose();
  };

  const filteredSearchResults = activeTab === 'search' ? searchResults.filter(isModelAllowed) : [];

  if (!position) return null;

  const dropdown = (
    <div
      ref={containerRef}
      className="fixed bg-surface border border-border rounded-xl shadow-2xl z-[100] overflow-hidden flex flex-row"
      style={{ ...(position.top !== undefined ? { top: position.top } : { bottom: position.bottom }), right: position.right, width: position.maxWidth, height: '360px' }}
    >
      {/* Left panel — model list */}
      <div className="w-[58%] flex flex-col border-r border-border">
        {/* Search bar */}
        <div className="px-3 py-2 border-b border-border bg-surface shrink-0">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-2" />
            <input
              ref={searchInputRef}
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Search models..."
              className="w-full bg-surface-2 border border-border rounded-md pl-8 pr-2 py-1 text-xs text-text placeholder:text-text-2 focus:outline-none focus:border-accent"
            />
          </div>
        </div>

        {/* Model list */}
        <div className="overflow-y-auto flex-1 min-h-0 p-1">
          {activeTab === 'recommended' && !searchQuery && (
            <div className="p-1">
              {/* Pinned AI-selected model — always shown at top */}
              {pinnedModelId && (() => {
                const all = Object.values(recommended).flat().concat(searchResults);
                let pinned = all.find(m => m.id === pinnedModelId);
                if (!pinned) {
                  // Model not in catalog — create a minimal entry from the ID
                  pinned = { id: pinnedModelId, name: pinnedModelId.split('/').pop()?.split(':')[0] || pinnedModelId, context_length: '?', prompt_price: '?', completion_price: '?', categories: [], is_free: false };
                }
                const provider = getProvider(pinned.id);
                return (
                  <button
                    onClick={() => handleSelect(pinnedModelId)}
                    onMouseEnter={() => setHoveredModel(pinned)}
                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-left transition-colors mb-2 border border-border/50 ${
                      selectedModel === pinnedModelId ? 'bg-accent/10 text-text' : 'text-text-2 hover:bg-surface-2'
                    }`}
                  >
                    {PROVIDER_FAVICONS[provider] ? (
                      <img src={PROVIDER_FAVICONS[provider]!} alt="" className="w-4 h-4 rounded shrink-0 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                    ) : (
                      <Cpu className="w-4 h-4 shrink-0 text-text-2" />
                    )}
                    <span className="text-xs font-medium flex-1">{stripProviderPrefix(pinned.name)}</span>
                    <span className="text-[9px] text-text-2 shrink-0">AI selected</span>
                    {selectedModel === pinnedModelId && <Check className="w-3.5 h-3.5 text-accent shrink-0" />}
                  </button>
                );
              })()}
              {/* All whitelisted models — flat list, no categories */}
              {(() => {
                const allModels = Object.values(recommended).flat().filter(isModelAllowed);
                const uniqueModels = Array.from(new Map(allModels.map(m => [m.id, m])).values());
                return uniqueModels.map((model) => (
                  <ModelRow
                    key={model.id}
                    model={model}
                    isSelected={model.id === selectedModel}
                    onSelect={handleSelect}
                    onHover={setHoveredModel}
                  />
                ));
              })()}
            </div>
          )}

          {activeTab === 'search' && (
            <div className="p-1">
              {filteredSearchResults.map((model) => (
                <ModelRow
                  key={model.id}
                  model={model}
                  isSelected={model.id === selectedModel}
                  onSelect={handleSelect}
                  onHover={setHoveredModel}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right panel — details */}
      <div className="w-[42%] bg-surface-2 p-3 flex flex-col">
        {previewModel ? (
          <>
            <div className="flex items-start gap-2 mb-3">
              {PROVIDER_FAVICONS[getProvider(previewModel.id)] ? (
                <img
                  src={PROVIDER_FAVICONS[getProvider(previewModel.id)]!}
                  alt=""
                  className="w-7 h-7 rounded-lg shrink-0 object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
              ) : (
                <Cpu className="w-7 h-7 shrink-0 text-text-2" />
              )}
              <div className="min-w-0">
                <div className="text-sm font-semibold text-text leading-tight">{stripProviderPrefix(previewModel.name)}</div>
                <div className="text-[10px] text-text-2 mt-0.5">{previewModel.id}</div>
              </div>
            </div>

            <div className="space-y-3 flex-1">
              <div>
                <div className="text-[10px] text-text-2 uppercase tracking-wide mb-1">Context</div>
                <div className="text-xs text-text">{formatContext(previewModel.context_length)} tokens</div>
              </div>

              <div>
                <div className="text-[10px] text-text-2 uppercase tracking-wide mb-1">Cost / 1M tokens</div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-2">Input</span>
                    <span className="text-text">{formatPrice(previewModel.prompt_price)}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-2">Output</span>
                    <span className="text-text">{formatPrice(previewModel.completion_price)}</span>
                  </div>
                  {parsePrice(previewModel.image_price) !== null && parsePrice(previewModel.image_price)! > 0 && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-2">Image</span>
                      <span className="text-text">{formatPrice(previewModel.image_price)}</span>
                    </div>
                  )}
                  {parsePrice(previewModel.video_price) !== null && parsePrice(previewModel.video_price)! > 0 && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-2">Video</span>
                      <span className="text-text">{formatPrice(previewModel.video_price)}</span>
                    </div>
                  )}
                  {parsePrice(previewModel.audio_price) !== null && parsePrice(previewModel.audio_price)! > 0 && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-2">Audio</span>
                      <span className="text-text">{formatPrice(previewModel.audio_price)}</span>
                    </div>
                  )}
                  {parsePrice(previewModel.web_search_price) !== null && parsePrice(previewModel.web_search_price)! > 0 && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-2">Web Search</span>
                      <span className="text-text">{formatPrice(previewModel.web_search_price)}</span>
                    </div>
                  )}
                </div>
                {/* Cost tier bar */}
                <div className="text-[9px] text-text-2 mb-1">Cost tier</div>
                <div className="flex items-center gap-1.5">
                  <div className="flex-1 h-1.5 rounded-full bg-surface-3 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${getModelCostTier(previewModel) === 'free' ? 100 : getModelCostTier(previewModel) === 'low' ? 75 : getModelCostTier(previewModel) === 'mid' ? 45 : getModelCostTier(previewModel) === 'unknown' ? 30 : 20}%`,
                        backgroundColor: COST_TIER_COLORS[getModelCostTier(previewModel)],
                      }}
                    />
                  </div>
                  <span className="text-[9px] text-text-2 capitalize shrink-0">{getModelCostTier(previewModel)}</span>
                </div>
              </div>

              {isModelFree(previewModel) && (
                <div className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-500 text-[10px]">
                  <Star className="w-3 h-3" />
                  Free model
                </div>
              )}
            </div>

          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 px-4 text-center">
            <Sparkles className="w-8 h-8 text-accent" />
            <div className="text-sm font-semibold text-text">Free Router</div>
            <div className="text-[11px] text-text-2 leading-relaxed">
              OpenRouter automatically selects a free model for each request based on prompt complexity, task type, and model capabilities.
            </div>
            {isAdaptive && (
              <div className="text-[10px] text-accent font-medium">Currently active</div>
            )}
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(dropdown, document.body);
};

const ModelRow: React.FC<{
  model: ModelCatalogEntry;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onHover: (model: ModelCatalogEntry | null) => void;
}> = ({ model, isSelected, onSelect, onHover }) => {
  const provider = getProvider(model.id);

  return (
    <button
      onClick={() => onSelect(model.id)}
      onMouseEnter={() => onHover(model)}
      className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-left transition-colors ${
        isSelected ? 'bg-accent/10 text-text' : 'text-text-2 hover:bg-surface-2'
      }`}
    >
      {PROVIDER_FAVICONS[provider] ? (
        <img
          src={PROVIDER_FAVICONS[provider]!}
          alt=""
          className="w-4 h-4 rounded shrink-0 object-contain"
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
        />
      ) : (
        <Cpu className="w-4 h-4 shrink-0 text-text-2" />
      )}
      <span className="text-xs truncate flex-1">{stripProviderPrefix(model.name)}</span>
      <div
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{ backgroundColor: COST_TIER_COLORS[getModelCostTier(model)] }}
        title={`Cost: ${isModelFree(model) ? 'Free' : formatPrice(getMaxPrice(model))}/1M`}
      />
      {isSelected && <Check className="w-3.5 h-3.5 text-accent shrink-0" />}
    </button>
  );
};
