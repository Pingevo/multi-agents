import React, { createContext, useContext, useState, useCallback } from 'react';
import type { PlatformState } from '../types/platform';

interface PlatformContextValue extends PlatformState {
  updateState: (partialOrFn: Partial<PlatformState> | ((prev: PlatformState) => Partial<PlatformState>)) => void;
  addNotification: (message: string) => void;
  clearPlan: () => void;
}

const defaultState: PlatformState = {
  agents: [],
  tasks: [],
  current_plan: null,
  notifications: [],
  system_status: 'Ready',
  available_tools: [],
  credits: null,
};

const PlatformContext = createContext<PlatformContextValue>({
  ...defaultState,
  updateState: () => {},
  addNotification: () => {},
  clearPlan: () => {},
});

export const PlatformProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<PlatformState>(defaultState);

  const updateState = useCallback((partialOrFn: Partial<PlatformState> | ((prev: PlatformState) => Partial<PlatformState>)) => {
    setState((prev) => {
      const partial = typeof partialOrFn === 'function' ? partialOrFn(prev) : partialOrFn;
      // Merge agents instead of overwriting: preserve fields the backend doesn't send
      // (expertise, personality, brand_context, learnings, depends_on)
      if (partial.agents && prev.agents.length > 0) {
        const prevMap = new Map(prev.agents.map(a => [a.id, a]));
        partial.agents = partial.agents.map((a: any) => {
          const prevAgent = prevMap.get(a.id);
          if (prevAgent) {
            return {
              ...prevAgent,
              ...a,
              // Preserve fields that backend doesn't send but frontend has
              expertise: a.expertise ?? (prevAgent as any).expertise,
              personality: a.personality ?? (prevAgent as any).personality,
              brand_context: a.brand_context ?? (prevAgent as any).brand_context,
              learnings: a.learnings ?? (prevAgent as any).learnings,
              depends_on: a.depends_on ?? prevAgent.depends_on,
            };
          }
          return a;
        });
      }
      return { ...prev, ...partial };
    });
  }, []);

  const addNotification = useCallback((message: string) => {
    setState((prev) => ({
      ...prev,
      notifications: [...prev.notifications.slice(-4), message],
    }));
  }, []);

  const clearPlan = useCallback(() => {
    setState((prev) => ({ ...prev, current_plan: null }));
  }, []);

  return (
    <PlatformContext.Provider value={{ ...state, updateState, addNotification, clearPlan }}>
      {children}
    </PlatformContext.Provider>
  );
};

export const usePlatform = () => useContext(PlatformContext);
