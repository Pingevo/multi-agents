export interface Team {
  id: string;
  name: string;
  description: string;
  manager_model: string;
  agent_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface TeamWithAgents extends Team {
  agents: Array<{
    id: string;
    name: string;
    role: string;
    model: string;
    status: string;
  }>;
}
