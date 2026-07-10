"""Audio tools: TTS, STT, and image analysis."""

from crewai.tools import tool
from backend.globals import _progress_callback, _media_tool_results, _thread_local, _media_gen_manager


@tool
def text_to_speech(text: str, voice: str = "alloy") -> str:
    """Convert text to speech audio using AI TTS models.

    Call this tool when you need to generate narration, voiceover, or any spoken audio from text.
    The text should be in the language you want spoken.
    Voice options: alloy, echo, fable, onyx, nova, shimmer (availability depends on model).
    Returns a URL to the generated audio file that can be used by other agents.
    """
    global _progress_callback, _media_tool_results
    agent_name = getattr(_thread_local, 'agent_name', '')
    if not text or not text.strip():
        return "Error: Empty text for speech generation"
    text_clean = text.strip()
    if _progress_callback:
        _progress_callback(100, "✅ เขียน prompt เสียงพากย์เสร็จแล้ว — รอผู้ใช้อนุมัติ")
    tts_model = _media_gen_manager.tts_model if _media_gen_manager else ""
    _media_tool_results.append({"type": "tts", "text": text_clean, "voice": voice, "agent_name": agent_name, "model": tts_model})
    return f"[TTS_PROMPT_READY]\nText: {text_clean}\nVoice: {voice}"


@tool
def transcribe_audio(audio_url: str) -> str:
    """Transcribe an audio file to text using AI STT models.

    Call this tool when you need to convert audio (speech) to text — for subtitles,
    transcription, or audio content analysis.
    audio_url should be a URL to an audio file (mp3, wav, etc.).
    Returns the transcribed text.
    """
    global _progress_callback, _media_tool_results
    agent_name = getattr(_thread_local, 'agent_name', '')
    if not audio_url or not audio_url.strip():
        return "Error: Empty audio URL for transcription"
    audio_url_clean = audio_url.strip()
    if _progress_callback:
        _progress_callback(100, "✅ ส่งคำขอถอดเสียงเป็นข้อความ — รอผู้ใช้อนุมัติ")
    stt_model = _media_gen_manager.stt_model if _media_gen_manager else ""
    _media_tool_results.append({"type": "stt", "audio_url": audio_url_clean, "agent_name": agent_name, "model": stt_model})
    return f"[STT_PROMPT_READY]\nAudio URL: {audio_url_clean}"


@tool
def analyze_image(image_url: str, question: str = "Describe this image in detail.") -> str:
    """Analyze and describe an image using AI vision models.

    Call this tool when you need to understand, describe, or extract information from an image.
    image_url should be a URL to an image file.
    question specifies what you want to know about the image.
    Returns a text description/analysis of the image.
    """
    global _progress_callback, _media_tool_results
    agent_name = getattr(_thread_local, 'agent_name', '')
    if not image_url or not image_url.strip():
        return "Error: Empty image URL for analysis"
    image_url_clean = image_url.strip()
    question_clean = question.strip() if question else "Describe this image in detail."
    if _progress_callback:
        _progress_callback(100, "✅ ส่งคำขอวิเคราะห์รูปภาพ — รอผู้ใช้อนุมัติ")
    vision_model = _media_gen_manager.vision_model if _media_gen_manager else ""
    _media_tool_results.append({"type": "vision", "image_url": image_url_clean, "question": question_clean, "agent_name": agent_name, "model": vision_model})
    return f"[VISION_PROMPT_READY]\nImage URL: {image_url_clean}\nQuestion: {question_clean}"
