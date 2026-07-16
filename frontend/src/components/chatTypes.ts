export interface PlanAgent {
  name: string;
  role: string;
  goal?: string;
  persona?: string;
  personality?: { tone?: string; communication_style?: string; language?: string };
  expertise?: string[];
  brand_context?: { brand_name?: string; guidelines?: string; target_audience?: string };
  tools?: string[];
  depends_on?: string[];
  is_existing?: boolean;
  model?: string;
}

export interface ResultAgent {
  name: string;
  role: string;
  output: string;
}

export type ChatMessageType = 'text' | 'plan' | 'plan_validation_error' | 'progress' | 'result' | 'image_approval' | 'image_result' | 'agent_progress' | 'model_catalog' | 'thinking' | 'thinking_done' | 'audio_result' | 'transcription_result' | 'video_result' | 'file_result' | 'tuning_proposal' | 'agent_review';

export type PlanStatus = 'pending' | 'approved' | 'rejected';

export type ImageApprovalStatus = 'pending' | 'approved' | 'rejected' | 'error';

export type AgentReviewStatus = 'pending' | 'approved' | 'rejected';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  messageType?: ChatMessageType;
  planAgents?: PlanAgent[];
  planTaskDescription?: string;
  planType?: string;
  planStatus?: PlanStatus;
  teamName?: string;
  teamDescription?: string;
  progressId?: string;
  progressPercent?: number;
  progressLabel?: string;
  agentProgressTaskId?: string;
  agentProgressOverall?: number;
  agentProgressList?: AgentProgressEntry[];
  resultAgents?: ResultAgent[];
  resultSummary?: string;
  resultError?: boolean;
  imagePrompt?: string;
  approvalId?: string;
  agentName?: string;
  approvalStatus?: ImageApprovalStatus;
  imageUrl?: string;
  mediaType?: string;
  duration?: number;
  model?: string;
  imageError?: string;
  modelCatalogRecommended?: Record<string, any[]>;
  modelCatalogSearchResults?: any[];
  modelCatalogSelected?: string;
  modelCatalogResolved?: string;
  catalogType?: string;
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
  estimatedCost?: string;
  audioUrl?: string;
  audioPrompt?: string;
  voice?: string;
  transcriptionText?: string;
  videoUrl?: string;
  videoPrompt?: string;
  fileUrl?: string;
  fileName?: string;
  fileMime?: string;
  attachmentUrl?: string;
  attachmentName?: string;
  attachmentMime?: string;
  tuningProposals?: TuningProposal[];
  // Agent review fields
  reviewId?: string;
  reviewTaskId?: string;
  reviewStatus?: AgentReviewStatus;
  agentRole?: string;
}

export interface AgentProgressEntry {
  name: string;
  role: string;
  status: 'pending' | 'running' | 'complete' | 'error' | 'waiting_approval' | 'awaiting_review';
  progress: number;
  output?: string;
  current_task?: string;
  current_tool?: string;
  tool_description?: string;
  model?: string;
  thinking?: string;
  delegated_by?: string[];
  review_round?: number;
  review_summary?: string;
  review_feedback?: string;
  review_history?: Array<{
    round: number;
    status: 'approved' | 'rejected';
    summary: string;
    feedback: string;
    output_preview: string;
  }>;
}

export interface TuningChange {
  field: string;
  old_value: string;
  new_value: string;
  reason: string;
}

export interface TuningProposal {
  agent_name: string;
  agent_id: string;
  changes: TuningChange[];
}

export interface ActivityEntry {
  id: string;
  text: string;
  timestamp: number;
  status: 'current' | 'completed';
}
