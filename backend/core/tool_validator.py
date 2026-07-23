"""Post-execution validation layer — ensures agents used their assigned tools.

If an agent had a tool assigned but didn't call it, and instead produced output
that should have gone through the tool (e.g., SVG instead of generate_image,
long text instead of generate_document), this module:
1. Extracts the relevant content from the agent's text output
2. Creates the appropriate tool result entry (media_tool_results)
3. Strips the raw content from the output so users don't see it in chat
"""

import re


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


def validate_tool_usage(
    agent_specs: list[dict],
    agent_outputs: list[dict],
    media_tool_results: list[dict],
    image_model: str = "",
) -> None:
    """Check that agents with tools actually called them.

    If an agent had a tool assigned but didn't call it, attempt to extract
    the relevant content from the agent's text output and create a tool result
    entry. Also strip raw content (SVG, HTML, long documents) from the output
    so users don't see it in chat.

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
                prompt = _extract_image_prompt_from_svg(output)
                if not prompt:
                    prompt = _extract_image_prompt_from_text(output)
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
                prompt = _extract_video_prompt_from_text(output)
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
