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

  const R = {
    dropdown: {
      position: 'fixed' as const,
      zIndex: 99999,
      background: 'var(--cream)',
      border: '2px solid var(--ink)',
      borderRadius: '4px',
      boxShadow: '3px 3px 10px rgba(0,0,0,0.3)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'row' as const,
    },
    leftPanel: {
      width: '58%',
      display: 'flex',
      flexDirection: 'column' as const,
      borderRight: '1px solid var(--line)',
    },
    searchWrap: {
      padding: '4px 6px',
      borderBottom: '1px solid var(--line)',
      background: 'var(--paper)',
      position: 'relative' as const,
      flexShrink: 0,
    },
    searchInput: {
      width: '100%',
      background: 'var(--cream)',
      border: '1px solid var(--line)',
      borderRadius: '2px',
      paddingLeft: '20px',
      paddingRight: '4px',
      padding: '3px 4px 3px 20px',
      fontSize: '10px',
      color: 'var(--ink)',
      outline: 'none',
    },
    modelList: {
      overflowY: 'auto' as const,
      flex: 1,
      minHeight: 0,
      padding: '3px',
    },
    rightPanel: {
      width: '42%',
      background: 'var(--paper)',
      padding: '8px',
      display: 'flex',
      flexDirection: 'column' as const,
    },
  };

  const dropdown = (
    <div
      ref={containerRef}
      style={{ ...R.dropdown, ...(position.top !== undefined ? { top: position.top } : { bottom: position.bottom }), right: position.right, width: position.maxWidth, height: '360px' }}
    >
      {/* Left panel — model list */}
      <div style={R.leftPanel}>
        {/* Search bar */}
        <div style={R.searchWrap}>
          <Search size={11} style={{ position: 'absolute', left: '6px', top: '50%', transform: 'translateY(-50%)', color: 'var(--ink3)' }} />
          <input
            ref={searchInputRef}
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search models..."
            style={R.searchInput}
          />
        </div>

        {/* Model list */}
        <div style={R.modelList}>
          {activeTab === 'recommended' && !searchQuery && (
            <div style={{ padding: '2px' }}>
              {/* Pinned AI-selected model — always shown at top */}
              {pinnedModelId && (() => {
                const all = Object.values(recommended).flat().concat(searchResults);
                let pinned = all.find(m => m.id === pinnedModelId);
                if (!pinned) {
                  pinned = { id: pinnedModelId, name: pinnedModelId.split('/').pop()?.split(':')[0] || pinnedModelId, context_length: '?', prompt_price: '?', completion_price: '?', categories: [], is_free: false };
                }
                const provider = getProvider(pinned.id);
                return (
                  <button
                    onClick={() => handleSelect(pinnedModelId)}
                    onMouseEnter={() => setHoveredModel(pinned)}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 6px',
                      borderRadius: '2px',
                      textAlign: 'left',
                      marginBottom: '4px',
                      border: '1px solid var(--line)',
                      background: selectedModel === pinnedModelId ? 'rgba(192,80,30,0.08)' : 'transparent',
                      color: selectedModel === pinnedModelId ? 'var(--ink)' : 'var(--ink2)',
                      cursor: 'pointer',
                    }}
                  >
                    {PROVIDER_FAVICONS[provider] ? (
                      <img src={PROVIDER_FAVICONS[provider]!} alt="" style={{ width: '14px', height: '14px', borderRadius: '2px', objectFit: 'contain', flexShrink: 0 }} onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                    ) : (
                      <Cpu size={14} style={{ flexShrink: 0, color: 'var(--ink3)' }} />
                    )}
                    <span style={{ fontSize: '10px', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{stripProviderPrefix(pinned.name)}</span>
                    <span style={{ fontSize: '8px', color: 'var(--ink3)', flexShrink: 0 }}>AI selected</span>
                    {selectedModel === pinnedModelId && <Check size={11} style={{ color: 'var(--orange)', flexShrink: 0 }} />}
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
            <div style={{ padding: '2px' }}>
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
      <div style={R.rightPanel}>
        {previewModel ? (
          <>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', marginBottom: '8px' }}>
              {PROVIDER_FAVICONS[getProvider(previewModel.id)] ? (
                <img
                  src={PROVIDER_FAVICONS[getProvider(previewModel.id)]!}
                  alt=""
                  style={{ width: '22px', height: '22px', borderRadius: '3px', objectFit: 'contain', flexShrink: 0 }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
              ) : (
                <Cpu size={22} style={{ flexShrink: 0, color: 'var(--ink3)' }} />
              )}
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--ink)', lineHeight: 1.2 }}>{stripProviderPrefix(previewModel.name)}</div>
                <div style={{ fontSize: '9px', color: 'var(--ink3)', marginTop: '1px' }}>{previewModel.id}</div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
              <div>
                <div style={{ fontSize: '8px', color: 'var(--ink3)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '2px' }}>Context</div>
                <div style={{ fontSize: '10px', color: 'var(--ink)' }}>{formatContext(previewModel.context_length)} tokens</div>
              </div>

              <div>
                <div style={{ fontSize: '8px', color: 'var(--ink3)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '2px' }}>Cost / 1M tokens</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '10px' }}>
                    <span style={{ color: 'var(--ink3)' }}>Input</span>
                    <span style={{ color: 'var(--ink)' }}>{formatPrice(previewModel.prompt_price)}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '10px' }}>
                    <span style={{ color: 'var(--ink3)' }}>Output</span>
                    <span style={{ color: 'var(--ink)' }}>{formatPrice(previewModel.completion_price)}</span>
                  </div>
                  {parsePrice(previewModel.image_price) !== null && parsePrice(previewModel.image_price)! > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '10px' }}>
                      <span style={{ color: 'var(--ink3)' }}>Image</span>
                      <span style={{ color: 'var(--ink)' }}>{formatPrice(previewModel.image_price)}</span>
                    </div>
                  )}
                  {parsePrice(previewModel.video_price) !== null && parsePrice(previewModel.video_price)! > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '10px' }}>
                      <span style={{ color: 'var(--ink3)' }}>Video</span>
                      <span style={{ color: 'var(--ink)' }}>{formatPrice(previewModel.video_price)}</span>
                    </div>
                  )}
                  {parsePrice(previewModel.audio_price) !== null && parsePrice(previewModel.audio_price)! > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '10px' }}>
                      <span style={{ color: 'var(--ink3)' }}>Audio</span>
                      <span style={{ color: 'var(--ink)' }}>{formatPrice(previewModel.audio_price)}</span>
                    </div>
                  )}
                  {parsePrice(previewModel.web_search_price) !== null && parsePrice(previewModel.web_search_price)! > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '10px' }}>
                      <span style={{ color: 'var(--ink3)' }}>Web Search</span>
                      <span style={{ color: 'var(--ink)' }}>{formatPrice(previewModel.web_search_price)}</span>
                    </div>
                  )}
                </div>
                {/* Cost tier bar */}
                <div style={{ fontSize: '8px', color: 'var(--ink3)', marginBottom: '2px' }}>Cost tier</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <div style={{ flex: 1, height: '5px', borderRadius: '2px', background: 'var(--line)', overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        borderRadius: '2px',
                        width: `${getModelCostTier(previewModel) === 'free' ? 100 : getModelCostTier(previewModel) === 'low' ? 75 : getModelCostTier(previewModel) === 'mid' ? 45 : getModelCostTier(previewModel) === 'unknown' ? 30 : 20}%`,
                        backgroundColor: COST_TIER_COLORS[getModelCostTier(previewModel)],
                      }}
                    />
                  </div>
                  <span style={{ fontSize: '8px', color: 'var(--ink3)', textTransform: 'capitalize', flexShrink: 0 }}>{getModelCostTier(previewModel)}</span>
                </div>
              </div>

              {isModelFree(previewModel) && (
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', padding: '2px 6px', borderRadius: '2px', background: 'rgba(90,122,74,0.15)', color: 'var(--green)', fontSize: '9px' }}>
                  <Star size={10} />
                  Free model
                </div>
              )}
            </div>

          </>
        ) : (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '12px', textAlign: 'center' }}>
            <Sparkles size={26} style={{ color: 'var(--orange)' }} />
            <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--ink)' }}>Free Router</div>
            <div style={{ fontSize: '10px', color: 'var(--ink3)', lineHeight: 1.4 }}>
              OpenRouter automatically selects a free model for each request based on prompt complexity, task type, and model capabilities.
            </div>
            {isAdaptive && (
              <div style={{ fontSize: '9px', color: 'var(--orange)', fontWeight: 600 }}>Currently active</div>
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
      style={{
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 6px',
        borderRadius: '2px',
        textAlign: 'left',
        background: isSelected ? 'rgba(192,80,30,0.08)' : 'transparent',
        color: isSelected ? 'var(--ink)' : 'var(--ink2)',
        cursor: 'pointer',
        border: 'none',
      }}
    >
      {PROVIDER_FAVICONS[provider] ? (
        <img
          src={PROVIDER_FAVICONS[provider]!}
          alt=""
          style={{ width: '14px', height: '14px', borderRadius: '2px', objectFit: 'contain', flexShrink: 0 }}
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
        />
      ) : (
        <Cpu size={14} style={{ flexShrink: 0, color: 'var(--ink3)' }} />
      )}
      <span style={{ fontSize: '10px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{stripProviderPrefix(model.name)}</span>
      <div
        style={{ width: '5px', height: '5px', borderRadius: '50%', flexShrink: 0, backgroundColor: COST_TIER_COLORS[getModelCostTier(model)] }}
        title={`Cost: ${isModelFree(model) ? 'Free' : formatPrice(getMaxPrice(model))}/1M`}
      />
      {isSelected && <Check size={11} style={{ color: 'var(--orange)', flexShrink: 0 }} />}
    </button>
  );
};
