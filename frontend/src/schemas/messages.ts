// TypeScript mirror of schemas/__init__.py (Pydantic)
// These interfaces define the contract between backend and frontend.

export interface PlanAgentItem {
  name: string;
  role: string;
  goal: string;
  persona?: string;
  tools: string[];
  is_existing: boolean;
  model?: string;
}

export interface ResultAgentItem {
  name: string;
  role: string;
  output: string;
}

export interface AgentProgressEntry {
  name: string;
  role: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  progress: number;
  output: string;
  current_task: string;
  current_tool: string;
  tool_description: string;
}

export interface TaskItem {
  id: string;
  title: string;
  agent: string;
  status: 'running' | 'complete' | 'error' | 'idle';
  progress: number;
  result: string;
  agent_outputs: ResultAgentItem[];
  agent_progress: AgentProgressEntry[];
  imageUrl: string;
  imagePrompt: string;
}

export interface AgentItem {
  id: string | null;
  name: string;
  role: string;
  goal: string;
  persona: string;
  tools: string[];
  model: string;
  status: string;
}

export interface ToolCatalogEntry {
  name: string;
  description: string;
}

// Chat reply payloads
export type ChatMessageType =
  | 'text'
  | 'plan'
  | 'progress'
  | 'agent_progress'
  | 'result'
  | 'image_approval'
  | 'image_result'
  | 'thinking'
  | 'thinking_done'
  | 'audio_result'
  | 'transcription_result'
  | 'video_result'
  | 'file_result'
  | 'agent_review'
  | 'tuning_proposal';

export interface ChatReplyText {
  messageType: 'text';
  message: string;
}

export interface ChatReplyPlan {
  messageType: 'plan';
  planAgents: PlanAgentItem[];
  planTaskDescription: string;
  planType: string;
  imageModel?: string;
  videoModel?: string;
  searchModel?: string;
  ttsModel?: string;
  sttModel?: string;
  visionModel?: string;
  hasImageTool?: boolean;
  hasVideoTool?: boolean;
  hasSearchTool?: boolean;
  hasTtsTool?: boolean;
  hasSttTool?: boolean;
  hasVisionTool?: boolean;
  hasVisionInput?: boolean;
  managerModel?: string;
}

export interface ChatReplyProgress {
  messageType: 'progress';
  progressId: string;
  progressPercent: number;
  progressLabel: string;
}

export interface ChatReplyAgentProgress {
  messageType: 'agent_progress';
  taskId: string;
  overallProgress: number;
  agents: AgentProgressEntry[];
}

export interface ChatReplyResult {
  messageType: 'result';
  resultSummary: string;
  resultError: boolean;
  resultAgents: ResultAgentItem[];
}

export interface ChatReplyImageApproval {
  messageType: 'image_approval';
  imagePrompt: string;
  approvalId: string;
  agentName: string;
  mediaType: string;
  duration: number;
  model: string;
}

export interface ChatReplyImageResult {
  messageType: 'image_result';
  imageUrl: string;
  imagePrompt: string;
  approvalId: string;
  taskId: string;
  mediaType: string;
}

export interface ChatReplyAudioResult {
  messageType: 'audio_result';
  audioUrl: string;
  audioPrompt: string;
  voice: string;
  agentName: string;
  model: string;
  taskId: string;
}

export interface ChatReplyTranscriptionResult {
  messageType: 'transcription_result';
  transcriptionText: string;
  audioUrl: string;
  agentName: string;
  model: string;
  taskId: string;
}

export interface ChatReplyVideoResult {
  messageType: 'video_result';
  videoUrl: string;
  videoPrompt: string;
  agentName: string;
  model: string;
  taskId: string;
}

export interface ChatReplyFileResult {
  messageType: 'file_result';
  fileUrl: string;
  fileName: string;
  fileMime: string;
  agentName: string;
  taskId: string;
}

export interface ModelCatalogItem {
  id: string;
  name: string;
  context_length: any;
  prompt_price: any;
  completion_price: any;
  categories: string[];
  is_free: boolean;
}

export interface ChatReplyModelCatalog {
  messageType: 'model_catalog';
  recommended: Record<string, ModelCatalogItem[]>;
  searchResults: ModelCatalogItem[];
  selectedModel: string;
}

export interface ChatReplyThinking {
  messageType: 'thinking';
  chunk: string;
  thinkingId: string;
}

export interface ChatReplyThinkingDone {
  messageType: 'thinking_done';
  thinkingId: string;
}

export interface ChatReplyPlanValidationError {
  messageType: 'plan_validation_error';
  message: string;
  errors: string[];
}

export interface TuningChangeItem {
  field: string;
  old_value: string;
  new_value: string;
  reason: string;
}

export interface TuningProposalItem {
  agent_name: string;
  agent_id: string;
  changes: TuningChangeItem[];
}

export interface ChatReplyTuningProposal {
  messageType: 'tuning_proposal';
  proposals: TuningProposalItem[];
}

export interface ChatReplyAgentReview {
  messageType: 'agent_review';
  reviewId: string;
  taskId: string;
  agentName: string;
  agentRole: string;
  output: string;
  reviewStatus: 'pending' | 'approved' | 'rejected';
}

export type ChatReplyPayload =
  | ChatReplyText
  | ChatReplyPlan
  | ChatReplyPlanValidationError
  | ChatReplyProgress
  | ChatReplyAgentProgress
  | ChatReplyResult
  | ChatReplyImageApproval
  | ChatReplyImageResult
  | ChatReplyAudioResult
  | ChatReplyTranscriptionResult
  | ChatReplyVideoResult
  | ChatReplyFileResult
  | ChatReplyModelCatalog
  | ChatReplyThinking
  | ChatReplyThinkingDone
  | ChatReplyTuningProposal
  | ChatReplyAgentReview;

export interface ChatReplyEnvelope {
  type: 'chat_reply';
  payload: ChatReplyPayload;
}

// State payload
export interface StatePayload {
  agents: AgentItem[];
  tasks: TaskItem[];
  current_plan: Record<string, unknown> | null;
  notifications: string[];
  system_status: string;
  available_tools: ToolCatalogEntry[];
}

export interface StateEnvelope {
  type: 'state';
  payload: StatePayload;
}

// Union of all incoming messages
export type IncomingMessage = ChatReplyEnvelope | StateEnvelope;
