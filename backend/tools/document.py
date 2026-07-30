"""Document generation tool — create downloadable text/markdown files."""

from crewai.tools import tool
from backend.globals import _progress_callback, _media_tool_results


@tool
def generate_document(filename: str, content: str, doc_type: str = "markdown") -> str:
    """Generate a downloadable document file from text content.

    Call this tool when you need to produce a structured document — reports,
    plans, scripts, articles, or any text deliverable that the user can download.

    Important format limitations:
    - This tool ONLY supports three formats: "markdown", "text", or "html".
    - It DOES NOT support binary formats like PDF, Word (.docx), or Excel.
    - If the user requests a PDF, you must use "markdown" or "html" instead
      as the best alternative, and explicitly inform the user in your chat
      response that you generated an alternative format because PDF
      generation is not currently supported by your tools.

    Args:
        filename: Name of the file (e.g. "marketing-plan.md", "report.txt")
        content: Full text content of the document
        doc_type: Format type — MUST be exactly "markdown", "text", or "html". Do NOT use "pdf".

    Returns a confirmation that the document is ready for download.
    """
    global _progress_callback
    if not filename or not filename.strip():
        return "Error: Empty filename for document generation"
    if not content or not content.strip():
        return "Error: Empty content for document generation"

    filename_clean = filename.strip()
    content_clean = content.strip()
    doc_type_clean = (doc_type or "markdown").strip().lower()

    # Ensure extension matches doc_type
    if doc_type_clean == "markdown" and not filename_clean.endswith((".md", ".markdown")):
        if "." not in filename_clean.rsplit("/", 1)[-1]:
            filename_clean += ".md"
    elif doc_type_clean == "text" and not filename_clean.endswith(".txt"):
        if "." not in filename_clean.rsplit("/", 1)[-1]:
            filename_clean += ".txt"
    elif doc_type_clean == "html" and not filename_clean.endswith((".html", ".htm")):
        if "." not in filename_clean.rsplit("/", 1)[-1]:
            filename_clean += ".html"

    # Dedup by filename — when Manager rejects output and agent is re-run,
    # it calls generate_document again with the same filename, creating
    # duplicate file download cards. Skip if this filename already exists.
    existing_filenames = {r.get("filename", "") for r in _media_tool_results if r.get("type") == "document"}
    if filename_clean in existing_filenames:
        print(f"[DEDUP] Skipping duplicate document: {filename_clean}", flush=True)
        return f"[DOCUMENT_READY]\nFilename: {filename_clean}\nType: {doc_type_clean}\nLength: {len(content_clean)} chars"

    if _progress_callback:
        _progress_callback(100, f"📄 สร้างเอกสาร {filename_clean} แล้ว")

    # Store for frontend to provide as download — use global to avoid Chainlit context issues
    file_data = {
        "type": "document",
        "filename": filename_clean,
        "content": content_clean,
        "doc_type": doc_type_clean,
    }

    _media_tool_results.append(file_data)

    return f"[DOCUMENT_READY]\nFilename: {filename_clean}\nType: {doc_type_clean}\nLength: {len(content_clean)} chars"
