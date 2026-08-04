"""Global state and constants shared across the backend."""

import os
import threading
import contextvars

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

# ============================================================
# File Paths — Legacy (fallback for dev mode without auth)
# ============================================================
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
AGENT_REGISTRY_FILE = os.path.join(_PROJECT_ROOT, "agent_registry.json")
TASK_REGISTRY_FILE = os.path.join(_PROJECT_ROOT, "task_registry.json")
CHAT_SESSIONS_FILE = os.path.join(_PROJECT_ROOT, "chat_sessions.json")
TEAM_REGISTRY_FILE = os.path.join(_PROJECT_ROOT, "team_registry.json")

# ============================================================
# Per-User Data Directory
# ============================================================
DATA_DIR = os.environ.get("AGENT_APP_DATA_DIR", os.path.join(_PROJECT_ROOT, "data"))


def user_data_dir(user_id: str) -> str:
    """Get per-user data directory, creating it if needed."""
    path = os.path.join(DATA_DIR, "users", user_id)
    os.makedirs(path, exist_ok=True)
    return path


def user_file_path(user_id: str, filename: str) -> str:
    """Get full path for a per-user data file."""
    return os.path.join(user_data_dir(user_id), filename)


def resolve_data_path(filename: str, user_id: str | None = None) -> str:
    """Resolve data file path: per-user if user_id provided, legacy fallback otherwise."""
    if user_id:
        return user_file_path(user_id, filename)
    # Fallback to legacy paths for backward compatibility
    legacy_map = {
        "agent_registry.json": AGENT_REGISTRY_FILE,
        "task_registry.json": TASK_REGISTRY_FILE,
        "chat_sessions.json": CHAT_SESSIONS_FILE,
        "team_registry.json": TEAM_REGISTRY_FILE,
    }
    return legacy_map.get(filename, os.path.join(_PROJECT_ROOT, filename))

# ============================================================
# Global callback for progress updates from tools
# ============================================================
_progress_callback = None
_media_gen_manager = None
_media_tool_results = []  # Captures tool results directly (not agent final answer)
_thread_local = threading.local()  # Per-thread storage for agent name (parallel-safe)
user_prompt_ctx: contextvars.ContextVar = contextvars.ContextVar("user_prompt", default="")  # Cross-thread user_prompt
_search_model = ""  # AI-selected OpenRouter search model (set per run)

# Default per-agent search call limit when agent has search_web tool but spec doesn't set max_search_calls.
# Like max_iter=25 / max_retry_limit=3: a sensible default that spec can override.
DEFAULT_MAX_SEARCH_CALLS = 5
