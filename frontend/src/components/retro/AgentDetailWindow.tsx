import { useState, useEffect } from 'react';
import type { Agent, ToolCatalogEntry } from '../../types/platform';
import type { ModelCatalogEntry } from '../ModelPicker';
import { AgentDetailView, AgentConfigForm, AddAgentForm, agentIcon, isManager, isAgentBusy } from './AgentsWindow';

interface AgentDetailWindowProps {
  agents: Agent[];
  initialAgentId: string;
  availableTools: ToolCatalogEntry[];
  onAddAgent: (data: any) => void;
  onConfigAgent: (data: any) => void;
  onDeleteAgent: (agentId: string) => void;
  modelCatalog?: Record<string, ModelCatalogEntry[]>;
  modelSearchResults?: ModelCatalogEntry[];
  onSearchModels?: (query: string) => void;
  onFetchModelCatalog?: () => void;
  selectedModel?: string;
}

export const AgentDetailWindow: React.FC<AgentDetailWindowProps> = ({
  agents, initialAgentId, availableTools, onAddAgent, onConfigAgent, onDeleteAgent,
  modelCatalog, modelSearchResults, onSearchModels, onFetchModelCatalog, selectedModel,
}) => {
  const [selectedAgentId, setSelectedAgentId] = useState(initialAgentId);
  const [editingAgent, setEditingAgent] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);

  // Update selected agent when initialAgentId changes (clicked different agent in roster bar)
  useEffect(() => {
    setSelectedAgentId(initialAgentId);
    setEditingAgent(false);
    // Auto-show AddAgentForm when opened via "+" on roster bar (no agent selected)
    setShowAddForm(!initialAgentId);
  }, [initialAgentId]);

  const agent = agents.find(a => a.id === selectedAgentId);

  const handleSaveConfig = (data: any) => {
    onConfigAgent(data);
    setEditingAgent(false);
  };

  const handleDeleteAgent = (agentId: string) => {
    onDeleteAgent(agentId);
  };

  const handleAddSubmit = (data: any) => {
    onAddAgent(data);
    setShowAddForm(false);
  };

  // Add Agent form view
  if (showAddForm) {
    return (
      <div className="agents-body">
        <div className="adw-header">
          <button className="btn btn-no" onClick={() => setShowAddForm(false)}>← กลับ</button>
          <span className="adw-title">Add New Agent</span>
        </div>
        <AddAgentForm
          availableTools={availableTools}
          onSubmit={handleAddSubmit}
          onCancel={() => setShowAddForm(false)}
          modelCatalog={modelCatalog}
          modelSearchResults={modelSearchResults}
          onSearchModels={onSearchModels}
          onFetchModelCatalog={onFetchModelCatalog}
        />
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="agents-body" style={{ padding: '20px', textAlign: 'center' }}>
        <div style={{ fontSize: '24px', marginBottom: '6px' }}>🤖</div>
        <div style={{ fontSize: '11px', color: 'var(--ink3)' }}>Agent not found.</div>
      </div>
    );
  }

  const mgr = isManager(agent);
  const busy = isAgentBusy(agent);

  return (
    <div className="agents-body">
      {/* Header — display only, Add Agent is via roster bar + card */}
      <div className="adw-header">
        <div className="adw-identity-mini">
          <span className="text-base">{agentIcon(agent.name, agent.role)}</span>
          <span className="adw-title">{agent.name}</span>
          {mgr && <span className="rc-mgr">MGR</span>}
        </div>
      </div>

      {/* Two-column layout: left identity card, right config details */}
      <div className="adw-grid">
        {/* Left column — identity card */}
        <div className="adw-identity">
          <div className="adw-id-avatar" style={{ background: 'var(--cream2)' }}>
            {agentIcon(agent.name, agent.role)}
          </div>
          <div className="adw-id-name">{agent.name}</div>
          {mgr && <span className="rc-mgr">MANAGER</span>}
          <div className="adw-id-role">{agent.role}</div>
          <div className="adw-id-status">
            <span
              className="adw-id-dot"
              style={{
                background: busy ? 'var(--amber)' : 'var(--ink3)',
                animation: busy ? 'pulse 1s infinite' : 'none',
              }}
            />
            {agent.status || 'Idle'}
          </div>
          <div className="adw-id-model">
            <span style={{ color: agent.model ? 'var(--amber)' : 'var(--green)', fontWeight: 600 }}>
              {agent.model || 'Auto Router'}
            </span>
          </div>
        </div>

        {/* Right column — detail/edit */}
        <div className="adw-config">
          {editingAgent ? (
            <AgentConfigForm
              agent={agent}
              availableTools={availableTools}
              onSave={handleSaveConfig}
              onCancel={() => setEditingAgent(false)}
              onDelete={handleDeleteAgent}
              modelCatalog={modelCatalog}
              modelSearchResults={modelSearchResults}
              onSearchModels={onSearchModels}
              onFetchModelCatalog={onFetchModelCatalog}
              selectedModel={selectedModel}
            />
          ) : (
            <AgentDetailView
              agent={agent}
              onEdit={() => setEditingAgent(true)}
              onDelete={handleDeleteAgent}
            />
          )}
        </div>
      </div>
    </div>
  );
};
