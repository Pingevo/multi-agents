import { useState, useCallback, useRef, useEffect, type ReactNode } from 'react';

interface RetroWindowProps {
  id: string;
  title: string;
  icon: string;
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex: number;
  active: boolean;
  minimized: boolean;
  maximized: boolean;
  onFocus: () => void;
  onClose: () => void;
  onMinimize: () => void;
  onMaximize: () => void;
  onMove: (x: number, y: number) => void;
  onResize: (width: number, height: number) => void;
  children: ReactNode;
}

export const RetroWindow: React.FC<RetroWindowProps> = ({
  title, icon, x, y, width, height, zIndex, active, minimized, maximized,
  onFocus, onClose, onMinimize, onMaximize, onMove, onResize, children,
}) => {
  const [dragging, setDragging] = useState(false);
  const [resizing, setResizing] = useState(false);
  const [viewport, setViewport] = useState({ w: window.innerWidth, h: window.innerHeight });
  const dragStart = useRef({ x: 0, y: 0, winX: 0, winY: 0 });
  const resizeStart = useRef({ x: 0, y: 0, w: 0, h: 0 });

  useEffect(() => {
    const onResize = () => setViewport({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    if (e.target !== e.currentTarget && (e.target as HTMLElement).closest('.win-btn')) return;
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY, winX: x, winY: y };
    onFocus();
  }, [x, y, onFocus]);

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setResizing(true);
    resizeStart.current = { x: e.clientX, y: e.clientY, w: width, h: height };
  }, [width, height]);

  useEffect(() => {
    if (!dragging && !resizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (dragging) {
        const dx = e.clientX - dragStart.current.x;
        const dy = e.clientY - dragStart.current.y;
        const newX = Math.max(0, Math.min(window.innerWidth - 100, dragStart.current.winX + dx));
        const newY = Math.max(0, Math.min(window.innerHeight - 80, dragStart.current.winY + dy));
        onMove(newX, newY);
      }
      if (resizing) {
        const dw = e.clientX - resizeStart.current.x;
        const dh = e.clientY - resizeStart.current.y;
        const newW = Math.max(280, resizeStart.current.w + dw);
        const newH = Math.max(180, resizeStart.current.h + dh);
        onResize(newW, newH);
      }
    };

    const handleMouseUp = () => {
      setDragging(false);
      setResizing(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragging, resizing, onMove, onResize]);

  if (minimized) return null;

  const SIDEBAR_W = 90;
  // Taskbar (40px) + Team Roster Bar (76px) = 116px reserved at bottom
  const TASKBAR_H = 116;
  const maxStyle = maximized
    ? { left: SIDEBAR_W, top: 0, width: viewport.w - SIDEBAR_W, height: viewport.h - TASKBAR_H }
    : { left: x, top: y, width, height };

  return (
    <div
      className={`absolute flex flex-col overflow-hidden bg-paper border border-line-2 rounded-retro ${
        active ? 'shadow-retro-active' : 'shadow-retro-lg'
      }`}
      style={{ ...maxStyle, zIndex }}
      onMouseDown={onFocus}
    >
      {/* Title bar */}
      <div
        className="flex items-center gap-2 px-2.5 py-1.5 bg-cream border-b border-line cursor-default select-none text-[11px] font-semibold text-ink-2"
        onMouseDown={handleDragStart}
      >
        <span className="text-sm">{icon}</span>
        <span className="flex-1">{title}</span>
        <div className="flex gap-1">
          <button
            className="w-5 h-5 border border-line-2 bg-paper rounded-retro-sm text-[10px] flex items-center justify-center text-ink-2 hover:bg-cream hover:border-ink-3 transition-colors"
            onClick={(e) => { e.stopPropagation(); onMinimize(); }}
          >
            _
          </button>
          <button
            className="win-btn w-5 h-5 border border-line-2 bg-paper rounded-retro-sm text-[10px] flex items-center justify-center text-ink-2 hover:bg-cream hover:border-ink-3 transition-colors"
            onClick={(e) => { e.stopPropagation(); onMaximize(); }}
          >
            {maximized ? '❐' : '□'}
          </button>
          <button
            className="win-btn close w-5 h-5 border border-line-2 bg-paper rounded-retro-sm text-[10px] flex items-center justify-center text-ink-2 hover:bg-red hover:text-white hover:border-red transition-colors"
            onClick={(e) => { e.stopPropagation(); onClose(); }}
          >
            x
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto min-h-0 flex flex-col">
        {children}
      </div>

      {/* Resize handle — hidden when maximized */}
      {!maximized && (
        <div
          className="absolute bottom-0 right-0 w-4 h-4 cursor-nwse-resize z-10"
          onMouseDown={handleResizeStart}
        >
          <div className="absolute bottom-[3px] right-[3px] w-2 h-2 border-r-2 border-b-2 border-ink-3 hover:border-orange" />
        </div>
      )}
    </div>
  );
};
