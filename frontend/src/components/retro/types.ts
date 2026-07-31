export interface WindowState {
  id: string;
  title: string;
  icon: string;
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex: number;
  minimized: boolean;
  maximized: boolean;
}

export type WindowId = 'chat' | 'tasks' | 'agents' | 'agent-detail' | 'history' | 'schedule' | 'settings' | 'notifications';

export interface PlanAgentData {
  ic: string;
  name: string;
  stat: 'done' | 'running' | 'waiting' | 'idle';
  statText: string;
  output?: string;
  model?: string;
  duration?: string;
  approval?: { type: string; prompt: string; model: string };
}

export interface PlanWave {
  ic: string;
  name: string;
  task: string;
  depends?: string;
}

export interface PlanData {
  id: string;
  ic: string;
  title: string;
  status: 'pending' | 'running' | 'done';
  statusText: string;
  progress: number;
  planSummary?: string;
  waves?: PlanWave[];
  agents: PlanAgentData[];
}
