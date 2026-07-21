"""Pydantic schemas for all backend→frontend messages.

These models define the contract between the Python backend (StateMessenger)
and the TypeScript frontend (App.tsx). Every message sent to the frontend
should be validated against one of these models.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================
# Capability schemas
# ============================================================

class CapabilityItem(BaseModel):
    name: str
    description: str = ""
    type: Literal["tool", "model_trait"] = "model_trait"


class CapabilityResolution(BaseModel):
    type: Literal["tool", "model_trait"]
    tool_name: str = ""
    traits: dict[str, Any] = {}


class ResolvedAgent(BaseModel):
    name: str
    role: str = ""
    goal: str = ""
    backstory: str = ""
    tools: list[str] = []
    traits: dict[str, Any] = {}


# ============================================================
# Shared sub-models
# ============================================================

class PlanAgentItem(BaseModel):
    name: str
    role: str = ""
    goal: str = ""
    persona: str = ""
    personality: dict = {}
    expertise: list[str] = []
    brand_context: dict = {}
    tools: list[str] = []
    depends_on: list[str] = []
    is_existing: bool = False
    model: str = ""
    original_tools: list[str] = []
    original_goal: str = ""
    original_persona: str = ""
    task_description: str = ""


class ResultAgentItem(BaseModel):
    name: str
    role: str = ""
    output: str = ""


class AgentProgressEntry(BaseModel):
    name: str
    role: str = ""
    status: Literal["pending", "running", "complete", "error", "waiting_approval", "awaiting_review"] = "pending"
    progress: int = 0
    output: str = ""
    current_task: str = ""
    current_tool: str = ""
    tool_description: str = ""
    model: str = ""
    thinking: str = ""
    delegated_by: list[str] = []
    review_round: int = 0
    review_summary: str = ""
    review_feedback: str = ""
    review_history: list = []


class TaskItem(BaseModel):
    id: str
    title: str
    agent: str
    status: Literal["running", "complete", "error", "idle"] = "idle"
    progress: int = 0
    result: str = ""
    agent_outputs: list[ResultAgentItem] = []
    agent_progress: list[AgentProgressEntry] = []
    imageUrl: str = ""
    imagePrompt: str = ""


class AgentItem(BaseModel):
    id: str | None = None
    name: str
    role: str = ""
    goal: str = ""
    persona: str = ""
    tools: list[str] = []
    model: str = ""
    status: str = "Idle"


class ToolCatalogEntry(BaseModel):
    name: str
    description: str = ""


# ============================================================
# Chat reply payloads (type: "chat_reply")
# ============================================================

class ChatReplyText(BaseModel):
    messageType: Literal["text"] = "text"
    message: str = ""


class ChatReplyPlanValidationError(BaseModel):
    messageType: Literal["plan_validation_error"] = "plan_validation_error"
    message: str = ""
    errors: list[str] = []


class ChatReplyPlan(BaseModel):
    messageType: Literal["plan"] = "plan"
    planAgents: list[PlanAgentItem] = []
    planTaskDescription: str = ""
    planType: str = "new"
    teamName: str = ""
    teamDescription: str = ""
    imageModel: str = ""
    videoModel: str = ""
    searchModel: str = ""
    ttsModel: str = ""
    sttModel: str = ""
    visionModel: str = ""
    hasImageTool: bool = False
    hasVideoTool: bool = False
    hasSearchTool: bool = False
    hasTtsTool: bool = False
    hasSttTool: bool = False
    hasVisionTool: bool = False
    hasVisionInput: bool = False
    managerModel: str = ""
    estimatedCost: str = ""


class ChatReplyProgress(BaseModel):
    messageType: Literal["progress"] = "progress"
    progressId: str = ""
    progressPercent: int = 0
    progressLabel: str = "Processing..."


class ChatReplyAgentProgress(BaseModel):
    messageType: Literal["agent_progress"] = "agent_progress"
    taskId: str = ""
    overallProgress: int = 0
    agents: list[AgentProgressEntry] = []


class ChatReplyResult(BaseModel):
    messageType: Literal["result"] = "result"
    resultSummary: str = "Done"
    resultError: bool = False
    resultAgents: list[ResultAgentItem] = []


class ChatReplyImageApproval(BaseModel):
    messageType: Literal["image_approval"] = "image_approval"
    imagePrompt: str = ""
    approvalId: str = ""
    agentName: str = ""
    mediaType: str = "image"  # "image" or "video"
    duration: int = 0  # for video only
    model: str = ""  # generation model that will be used
    approvalStatus: str = "pending"  # "pending", "approved", "rejected", "error"
    imageError: str = ""  # error message if approvalStatus is "error"


class ChatReplyImageResult(BaseModel):
    messageType: Literal["image_result"] = "image_result"
    imageUrl: str = ""
    imagePrompt: str = ""
    approvalId: str = ""
    taskId: str = ""
    mediaType: str = "image"  # "image" or "video"
    agentName: str = ""


class ModelCatalogItem(BaseModel):
    id: str = ""
    name: str = ""
    context_length: Any = "?"
    prompt_price: Any = "?"
    completion_price: Any = "?"
    categories: list[str] = []
    is_free: bool = False


class ChatReplyModelCatalog(BaseModel):
    messageType: Literal["model_catalog"] = "model_catalog"
    recommended: dict[str, list[ModelCatalogItem]] = {}
    searchResults: list[ModelCatalogItem] = []
    selectedModel: str = ""
    catalogType: str = "text"  # "text" or "media"


class ChatReplyAudioResult(BaseModel):
    messageType: Literal["audio_result"] = "audio_result"
    audioUrl: str = ""
    audioPrompt: str = ""  # text that was spoken
    voice: str = ""
    agentName: str = ""
    model: str = ""
    taskId: str = ""


class ChatReplyTranscriptionResult(BaseModel):
    messageType: Literal["transcription_result"] = "transcription_result"
    transcriptionText: str = ""
    audioUrl: str = ""  # source audio
    agentName: str = ""
    model: str = ""
    taskId: str = ""


class ChatReplyVideoResult(BaseModel):
    messageType: Literal["video_result"] = "video_result"
    videoUrl: str = ""
    videoPrompt: str = ""
    agentName: str = ""
    model: str = ""
    taskId: str = ""


class ChatReplyFileResult(BaseModel):
    messageType: Literal["file_result"] = "file_result"
    fileUrl: str = ""
    fileName: str = ""
    fileMime: str = ""
    agentName: str = ""
    taskId: str = ""


class ChatReplyAgentReview(BaseModel):
    messageType: Literal["agent_review"] = "agent_review"
    reviewId: str = ""
    taskId: str = ""
    agentName: str = ""
    agentRole: str = ""
    output: str = ""
    reviewStatus: str = "pending"  # "pending", "approved", "rejected"


# ============================================================
# State payload (type: "state")
# ============================================================

class StatePayload(BaseModel):
    agents: list[AgentItem] = []
    tasks: list[TaskItem] = []
    current_plan: Optional[dict[str, Any]] = None
    notifications: list[str] = []
    system_status: str = "Ready"
    available_tools: list[ToolCatalogEntry] = []
    credits: Optional[dict[str, Any]] = None


# ============================================================
# Wrapper envelopes
# ============================================================

class ChatReplyEnvelope(BaseModel):
    type: Literal["chat_reply"] = "chat_reply"
    payload: ChatReplyText | ChatReplyPlanValidationError | ChatReplyPlan | ChatReplyProgress | ChatReplyAgentProgress | ChatReplyResult | ChatReplyImageApproval | ChatReplyImageResult | ChatReplyModelCatalog | ChatReplyAudioResult | ChatReplyTranscriptionResult | ChatReplyVideoResult | ChatReplyFileResult | ChatReplyAgentReview = Field(discriminator="messageType")


class StateEnvelope(BaseModel):
    type: Literal["state"] = "state"
    payload: StatePayload


# ============================================================
# Helper: build a chat_reply envelope as dict (for cl.Message)
# ============================================================

def chat_reply(payload: BaseModel) -> dict:
    """Wrap a ChatReply payload in an envelope and return as dict for JSON serialization."""
    return {"type": "chat_reply", "payload": payload.model_dump()}


def state_envelope(payload: StatePayload) -> dict:
    """Wrap a StatePayload in an envelope and return as dict."""
    return {"type": "state", "payload": payload.model_dump()}
