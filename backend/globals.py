"""Global state and constants shared across the backend."""

import os
import threading

# ============================================================
# State Management
# ============================================================
STATE_IDLE = "IDLE"
STATE_ASSESSING = "ASSESSING"
STATE_GATHERING_REQUIREMENTS = "GATHERING_REQUIREMENTS"
STATE_PLANNING = "PLANNING"
STATE_CREATING_AGENT = "CREATING_AGENT"
STATE_AWAITING_APPROVAL = "AWAITING_APPROVAL"
STATE_EXECUTING = "EXECUTING"

AGENT_REGISTRY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent_registry.json")
TASK_REGISTRY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "task_registry.json")
CHAT_SESSIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chat_sessions.json")
TEAM_REGISTRY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "team_registry.json")

# ============================================================
# Global callback for progress updates from tools
# ============================================================
_progress_callback = None
_media_gen_manager = None
_media_tool_results = []  # Captures tool results directly (not agent final answer)
_thread_local = threading.local()  # Per-thread storage for agent name (parallel-safe)
_search_model = ""  # AI-selected OpenRouter search model (set per run)
