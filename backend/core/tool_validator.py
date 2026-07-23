"""Post-execution validation layer — ensures agents used their assigned tools.

If an agent had a tool assigned but didn't call it, and instead produced output
that should have gone through the tool (e.g., SVG instead of generate_image,
long text instead of generate_document), this module:
1. Extracts the relevant content from the agent's text output
2. Creates the appropriate tool result entry (media_tool_results)
3. Strips the raw content from the output so users don't see it in chat

Extraction strategy:
- Fast path: regex patterns catch common formats (code blocks, labeled prompts)
- Fallback: LLM extraction catches any format the agent writes the prompt in
  (multi-line, Thai labels, no label, etc.) — this is the reliable path since
  agents write prompts in unpredictable ways and regex can't cover all cases.
"""

import re


async def _llm_extract_prompt(output: str, llm_manager, prompt_type: str = "image") -> str | None:
    """Use LLM to extract an image/video prompt from agent text output.
    
    This is the fallback when regex patterns don't match — handles any format
    the agent writes the prompt in (multi-line, Thai labels, no label, etc.).
    Uses call_with_fallback so it follows the user's selected model.
    """
    if not llm_manager or not output or len(output) < 50:
        return None
    
    type_desc = "image generation" if prompt_type == "image" else "video generation"
    extraction_prompt = (
        f"You are a prompt extractor. The following text is output from an AI agent that was supposed to "
        f"create an {type_desc} prompt but wrote it in text instead of calling the tool.\n\n"
        f"Extract the {type_desc} prompt from the text below. "
        f"The prompt is typically a detailed English description of the visual to create.\n\n"
        f"Rules:\n"
        f"- Return ONLY the extracted prompt text, nothing else\n"
        f"- Do not add any explanation, labels, or formatting\n"
        f"- If the prompt contains Thai text mixed in, keep it as-is (it may be intentional text on the poster)\n"
        f"- If no {type_desc} prompt is found in the text, return exactly: NO_PROMPT_FOUND\n\n"
        f"--- AGENT OUTPUT START ---\n{output[:8000]}\n--- AGENT OUTPUT END ---"
    )
    
    try:
        result = await llm_manager.call_async(extraction_prompt, caller="extract_prompt")
        result = result.strip()
        if result and result != "NO_PROMPT_FOUND" and len(result) > 20:
            print(f"[TOOL-VALIDATOR] LLM extracted {prompt_type} prompt ({len(result)} chars)", flush=True)
            return result
        print(f"[TOOL-VALIDATOR] LLM returned NO_PROMPT_FOUND for {prompt_type}", flush=True)
        return None
    except Exception as e:
        print(f"[TOOL-VALIDATOR] LLM extraction failed: {e}", flush=True)
        return None


def _strip_svg(output: str) -> str:
    """Remove SVG/HTML markup from agent output text."""
    cleaned = re.sub(r'<svg[\s\S]*?</svg>', '', output, flags=re.IGNORECASE)
    cleaned = re.sub(r'<html[\s\S]*?</html>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned.strip())
    return cleaned


def _extract_image_prompt_from_svg(output: str) -> str | None:
    """Try to extract a usable image prompt from SVG content."""
    svg_match = re.search(r'<svg[\s\S]*?</svg>', output, flags=re.IGNORECASE)
    if not svg_match:
        return None
    svg_content = svg_match.group(0)
    texts = re.findall(r'<text[^>]*>([^<]+)</text>', svg_content, flags=re.IGNORECASE)
    if texts:
        combined = " ".join(t.strip() for t in texts if t.strip())
        if len(combined) > 10:
            return combined
    desc_match = re.search(r'<desc[^>]*>([^<]+)</desc>', svg_content, flags=re.IGNORECASE)
    if desc_match and desc_match.group(1).strip():
        return desc_match.group(1).strip()
    return None


def _extract_image_prompt_from_text(output: str) -> str | None:
    """Try to extract an image prompt from agent text output using multiple patterns.
    
    Handles both English and Thai-language output — agents often write analysis in Thai
    but the image prompt itself is in English (inside code blocks, quotes, or after labels).
    """
    patterns = [
        # English code block with prompt
        r'```\s*\n([A-Za-z][^`]{20,})\n```',
        # "Prompt:" or "Image Prompt:" label (English)
        r'Prompt[:\s]+([A-Za-z][^\n]{20,})',
        r'[Ii]mage [Pp]rompt[:\s]+([A-Za-z][^\n]{20,})',
        # Thai labels followed by English prompt: "พรอมต์ภาพ:" "คำสั่งภาพ:" "prompt ภาพ:"
        r'พรอมต์ภาพ[:\s]+([A-Za-z][^\n]{20,})',
        r'คำสั่งภาพ[:\s]+([A-Za-z][^\n]{20,})',
        r'prompt ภาพ[:\s]+([A-Za-z][^\n]{20,})',
        r'Prompt ภาพ[:\s]+([A-Za-z][^\n]{20,})',
        # Thai label with colon then English text on same line
        r'โปสเตอร์[:\s]*([A-Za-z][^\n]{20,})',
        # Quoted English text (long enough to be a prompt)
        r'"([A-Z][^"]{30,})"',
        # Bold English text
        r'\*\*([A-Z][^*]{30,})\*\*',
        # generate_image tool call with prompt argument
        r'generate_image\([^)]*"([^"]{20,})"',
        # "English prompt for image:" style
        r'[Pp]rompt\s+(?:for\s+)?(?:image|poster|picture)[:\s]+([A-Za-z][^\n]{20,})',
    ]
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            prompt = match.group(1).strip()
            if len(prompt) > 10:
                return prompt
    return None


def _extract_video_prompt_from_text(output: str) -> str | None:
    """Try to extract a video prompt from agent text output.
    
    Handles Thai-language output where the video prompt itself is in English.
    """
    patterns = [
        r'"name"\s*:\s*"generate_video"\s*,\s*"arguments"\s*:\s*\{[^}]*"prompt"\s*:\s*"([^"]+)"',
        r'[Vv]ideo [Pp]rompt[:\s]+([A-Za-z][^\n]{20,})',
        # Thai labels for video prompt
        r'พรอมต์วิดีโอ[:\s]+([A-Za-z][^\n]{20,})',
        r'คำสั่งวิดีโอ[:\s]+([A-Za-z][^\n]{20,})',
        r'prompt วิดีโอ[:\s]+([A-Za-z][^\n]{20,})',
        r'generate_video\([^)]*"([^"]{20,})"',
    ]
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            prompt = match.group(1).strip()
            if len(prompt) > 10:
                return prompt
    return None


async def validate_tool_usage(
    agent_specs: list[dict],
    agent_outputs: list[dict],
    media_tool_results: list[dict],
    image_model: str = "",
    llm_manager=None,
) -> None:
    """Check that agents with tools actually called them.

    If an agent had a tool assigned but didn't call it, attempt to extract
    the relevant content from the agent's text output and create a tool result
    entry. Also strip raw content (SVG, HTML, long documents) from the output
    so users don't see it in chat.

    Extraction order: regex fast path → LLM fallback (handles any format).
    Modifies agent_outputs and media_tool_results in place.
    """
    for i, spec in enumerate(agent_specs):
        if i >= len(agent_outputs):
            continue
        tools = spec.get("tools", [])
        output = agent_outputs[i].get("output", "") or ""
        agent_name = agent_outputs[i].get("name", spec.get("name", f"Agent {i+1}"))

        # --- generate_image ---
        if "generate_image" in tools:
            has_image = any(r.get("type") == "image" for r in media_tool_results)
            if not has_image:
                # Fast path: try regex extraction first
                prompt = _extract_image_prompt_from_svg(output)
                if not prompt:
                    prompt = _extract_image_prompt_from_text(output)
                # Fallback: LLM extraction handles any format the agent writes
                if not prompt and llm_manager:
                    print(f"[TOOL-VALIDATOR] Regex failed for '{agent_name}' — trying LLM extraction", flush=True)
                    prompt = await _llm_extract_prompt(output, llm_manager, "image")
                if prompt:
                    print(f"[TOOL-VALIDATOR] Agent '{agent_name}' had generate_image but didn't call it — extracting prompt from output", flush=True)
                    media_tool_results.append({
                        "type": "image",
                        "prompt": prompt,
                        "agent_name": agent_name,
                        "model": image_model,
                    })
                    agent_outputs[i]["output"] = _strip_svg(output)

        # --- generate_video ---
        if "generate_video" in tools:
            has_video = any(r.get("type") == "video" for r in media_tool_results)
            if not has_video:
                # Fast path: try regex extraction first
                prompt = _extract_video_prompt_from_text(output)
                # Fallback: LLM extraction
                if not prompt and llm_manager:
                    print(f"[TOOL-VALIDATOR] Regex failed for '{agent_name}' — trying LLM extraction for video", flush=True)
                    prompt = await _llm_extract_prompt(output, llm_manager, "video")
                if prompt:
                    print(f"[TOOL-VALIDATOR] Agent '{agent_name}' had generate_video but didn't call it — extracting prompt from output", flush=True)
                    media_tool_results.append({
                        "type": "video",
                        "prompt": prompt,
                        "duration": 5,
                        "agent_name": agent_name,
                    })

        # --- generate_document ---
        if "generate_document" in tools:
            has_doc = any(r.get("type") == "document" for r in media_tool_results)
            if not has_doc and len(output) > 2000:
                print(f"[TOOL-VALIDATOR] Agent '{agent_name}' had generate_document but didn't call it — creating document from output", flush=True)
                doc_filename = f"{agent_name.lower().replace(' ', '-')}-output.md"
                media_tool_results.append({
                    "type": "document",
                    "filename": doc_filename,
                    "content": output,
                    "doc_type": "markdown",
                })
                agent_outputs[i]["output"] = (
                    output[:500] + "\n\n[เอกสารถูกสร้างเป็นไฟล์แล้ว — ดูในส่วนดาวน์โหลด]"
                )
