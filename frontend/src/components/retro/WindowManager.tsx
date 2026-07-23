import { useState, useCallback, createContext, useContext, type ReactNode } from 'react';
import type { WindowState, WindowId } from './types';

interface WindowManagerContextValue {
  windows: WindowState[];
  activeWindowId: string | null;
  openWindow: (id: WindowId, title: string, icon: string, width?: number, height?: number) => void;
  closeWindow: (id: string) => void;
  focusWindow: (id: string) => void;
  minimizeWindow: (id: string) => void;
  toggleMaximize: (id: string) => void;
  moveWindow: (id: string, x: number, y: number) => void;
  resizeWindow: (id: string, width: number, height: number) => void;
}

const WindowManagerContext = createContext<WindowManagerContextValue | null>(null);

let zCounter = 100;

export const WindowManagerProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [windows, setWindows] = useState<WindowState[]>([]);
  const [activeWindowId, setActiveWindowId] = useState<string | null>(null);

  const openWindow = useCallback((id: WindowId, title: string, icon: string, width = 600, height = 400) => {
    setWindows(prev => {
      const existing = prev.find(w => w.id === id);
      const z = ++zCounter;
      if (existing) {
        // Re-open: un-minimize and center on screen
        const cx = Math.max(0, (window.innerWidth - width) / 2);
        const cy = Math.max(0, (window.innerHeight - height) / 2);
        setActiveWindowId(id);
        return prev.map(w => w.id === id ? { ...w, minimized: false, maximized: false, zIndex: z, x: cx, y: cy, width, height } : w);
      }
      // New window: center on screen
      const cx = Math.max(0, (window.innerWidth - width) / 2);
      const cy = Math.max(0, (window.innerHeight - height) / 2);
      setActiveWindowId(id);
      return [...prev, {
        id, title, icon,
        x: cx,
        y: cy,
        width, height,
        zIndex: z,
        minimized: false,
        maximized: false,
      }];
    });
  }, []);

  const closeWindow = useCallback((id: string) => {
    setWindows(prev => prev.filter(w => w.id !== id));
    setActiveWindowId(prev => prev === id ? null : prev);
  }, []);

  const focusWindow = useCallback((id: string) => {
    const z = ++zCounter;
    setActiveWindowId(id);
    setWindows(prev => prev.map(w => w.id === id ? { ...w, zIndex: z, minimized: false } : w));
  }, []);

  const minimizeWindow = useCallback((id: string) => {
    setWindows(prev => prev.map(w => w.id === id ? { ...w, minimized: true } : w));
    setActiveWindowId(prev => prev === id ? null : prev);
  }, []);

  const moveWindow = useCallback((id: string, x: number, y: number) => {
    setWindows(prev => prev.map(w => w.id === id ? { ...w, x, y } : w));
  }, []);

  const resizeWindow = useCallback((id: string, width: number, height: number) => {
    setWindows(prev => prev.map(w => w.id === id ? { ...w, width, height } : w));
  }, []);

  const toggleMaximize = useCallback((id: string) => {
    setWindows(prev => prev.map(w => w.id === id ? { ...w, maximized: !w.maximized } : w));
  }, []);

  return (
    <WindowManagerContext.Provider value={{
      windows, activeWindowId, openWindow, closeWindow, focusWindow, minimizeWindow, toggleMaximize, moveWindow, resizeWindow,
    }}>
      {children}
    </WindowManagerContext.Provider>
  );
};

export const useWindowManager = () => {
  const ctx = useContext(WindowManagerContext);
  if (!ctx) throw new Error('useWindowManager must be used within WindowManagerProvider');
  return ctx;
};
