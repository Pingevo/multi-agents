import React, { createContext, useContext, useState, useCallback } from 'react';
import type { PlatformState } from '../types/platform';

interface PlatformContextValue extends PlatformState {
  updateState: (partial: Partial<PlatformState>) => void;
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

  const updateState = useCallback((partial: Partial<PlatformState>) => {
    setState((prev) => ({ ...prev, ...partial }));
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
