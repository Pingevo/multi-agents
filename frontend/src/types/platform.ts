export interface Agent {
  id: string;
  name: string;
  role: string;
  goal?: string;
  persona?: string;
  tools: string[];
  model?: string;
  depends_on?: string[];
  status: 'Idle' | 'Busy' | string;
}

export interface AgentOutput {
  name: string;
  role: string;
  output: string;
}

export interface AgentProgress {
  name: string;
  role: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  progress: number;
  output?: string;
  current_task?: string;
  current_tool?: string;
  tool_description?: string;
}

export interface TaskImage {
  url: string;
  prompt: string;
  mediaType?: string;
}

export interface Task {
  id: string;
  title: string;
  agent: string;
  status: 'running' | 'complete' | 'error' | 'idle' | string;
  progress: number;
  result: string;
  agent_outputs?: AgentOutput[];
  agent_progress?: AgentProgress[];
  imageUrl?: string;
  imagePrompt?: string;
  images?: TaskImage[];
}

export interface Plan {
  agents: Agent[];
  task_description: string;
  plan_type: 'existing' | 'new' | string;
}

export interface ToolCatalogEntry {
  name: string;
  description: string;
}

export interface CreditsInfo {
  limit: number | null;
  limit_remaining: number | null;
  usage: number;
  usage_daily: number;
  usage_monthly: number;
  is_free_tier: boolean;
}

export interface PlatformState {
  agents: Agent[];
  tasks: Task[];
  current_plan: Plan | null;
  notifications: string[];
  system_status: string;
  available_tools?: ToolCatalogEntry[];
  credits?: CreditsInfo | null;
}

export interface AgentFormData {
  agent_id?: string;
  name: string;
  role: string;
  goal: string;
  persona: string;
  tools: string;
  model?: string;
}

export interface AssignFormData {
  agent_id: string;
  task: string;
}
