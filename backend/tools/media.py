"""Image and video generation tools (queue prompts for user approval)."""

from crewai.tools import tool
from backend.globals import _progress_callback, _media_tool_results, _thread_local, _media_gen_manager


@tool
def generate_image(prompt: str) -> str:
    """Generate an image from a text prompt using AI image generation.

    Call this tool when you need to create any visual, illustration, poster, or image.
    The prompt should be in English and visually descriptive.
    The prompt will be reviewed by the user before generation to control costs.
    Returns a confirmation that the prompt is ready for user approval.
    """
    global _progress_callback, _media_tool_results
    agent_name = getattr(_thread_local, 'agent_name', '')
    if not prompt or not prompt.strip():
        return "Error: Empty prompt for image generation"
    prompt_clean = prompt.strip()
    prompt_hash = hash(prompt_clean.lower()[:200])
    existing = {hash(r.get("prompt", "")[:200].lower()) for r in _media_tool_results if r.get("type") == "image"}
    if prompt_hash in existing:
        print(f"[DEDUP] Skipping duplicate image prompt: {prompt_clean[:80]}...", flush=True)
        return f"[IMAGE_PROMPT_READY]\nPrompt: {prompt_clean}"
    if _progress_callback:
        _progress_callback(100, "✅ เขียน prompt รูปภาพเสร็จแล้ว — รอผู้ใช้อนุมัติ")
    image_model = _media_gen_manager.image_model if _media_gen_manager else ""
    _media_tool_results.append({"type": "image", "prompt": prompt_clean, "agent_name": agent_name, "model": image_model})
    return f"[IMAGE_PROMPT_READY]\nPrompt: {prompt_clean}"


@tool
def generate_video(prompt: str, duration: int = 5) -> str:
    """Generate a short video from a text prompt using AI video generation.

    Call this tool when you need to create a short video clip, animation, or motion content.
    The prompt should be in English and visually descriptive (describe scene, camera movement, lighting).
    Duration is in seconds (2-15). The prompt will be reviewed by the user before generation to control costs.
    Returns a confirmation that the prompt is ready for user approval.
    """
    global _progress_callback, _media_tool_results
    agent_name = getattr(_thread_local, 'agent_name', '')
    if not prompt or not prompt.strip():
        return "Error: Empty prompt for video generation"
    prompt_clean = prompt.strip()
    duration = max(2, min(15, int(duration)))
    prompt_hash = hash(prompt_clean.lower()[:200])
    existing = {hash(r.get("prompt", "")[:200].lower()) for r in _media_tool_results if r.get("type") == "video"}
    if prompt_hash in existing:
        print(f"[DEDUP] Skipping duplicate video prompt: {prompt_clean[:80]}...", flush=True)
        return f"[VIDEO_PROMPT_READY]\nPrompt: {prompt_clean}\nDuration: {duration}"
    if _progress_callback:
        _progress_callback(100, "✅ เขียน prompt วิดีโอเสร็จแล้ว — รอผู้ใช้อนุมัติ")
    video_model = _media_gen_manager.video_model if _media_gen_manager else ""
    _media_tool_results.append({"type": "video", "prompt": prompt_clean, "duration": duration, "agent_name": agent_name, "model": video_model})
    return f"[VIDEO_PROMPT_READY]\nPrompt: {prompt_clean}\nDuration: {duration}"
