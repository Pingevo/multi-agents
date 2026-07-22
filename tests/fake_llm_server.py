"""Fake LLM server for deterministic E2E testing.

Implements a minimal OpenAI/OpenRouter-compatible HTTP server using stdlib only.
Returns canned responses based on simple pattern matching against the prompt.

Endpoints:
  GET  /models          — fixed model catalog with text/image/search models
  GET  /key             — fake credit info
  POST /chat/completions — canned response based on prompt content

Run: python tests/fake_llm_server.py [--port 11434]
"""

import json
import sys
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


# ─── Fixed model catalog ──────────────────────────────────────────────

FAKE_MODELS = [
    {
        "id": "openrouter/free",
        "name": "OpenRouter Free",
        "context_length": 131072,
        "pricing": {"prompt": "0", "completion": "0"},
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "supported_parameters": [],
    },
    {
        "id": "test/text-model:free",
        "name": "Test Text Model",
        "context_length": 131072,
        "pricing": {"prompt": "0", "completion": "0"},
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "supported_parameters": [],
    },
    {
        "id": "test/image-model:free",
        "name": "Test Image Model",
        "context_length": 65536,
        "pricing": {
            "prompt": "0.0005",
            "completion": "0.003",
            "image": "0.05",
            "image_output": "0.10",
        },
        "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]},
        "supported_parameters": [],
    },
    {
        "id": "test/search-model:free",
        "name": "Test Search Model",
        "context_length": 131072,
        "pricing": {
            "prompt": "0",
            "completion": "0",
            "web_search": "0.001",
        },
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "supported_parameters": ["web_search"],
    },
    {
        "id": "test/vision-model:free",
        "name": "Test Vision Model",
        "context_length": 131072,
        "pricing": {"prompt": "0", "completion": "0"},
        "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
        "supported_parameters": [],
    },
]

# ─── Canned LLM responses ─────────────────────────────────────────────

PLAN_RESPONSE = json.dumps({
    "action": "plan",
    "agents": [
        {
            "name": "Researcher",
            "role": "Research Specialist",
            "goal": "Research the topic thoroughly",
            "persona": "A diligent researcher",
            "tools": [],
            "task_description": "Research the given topic",
            "depends_on": [],
            "model": "openrouter/free",
        },
        {
            "name": "Writer",
            "role": "Content Writer",
            "goal": "Write a summary based on research",
            "persona": "A skilled writer",
            "tools": [],
            "task_description": "Write a summary",
            "depends_on": ["Researcher"],
            "model": "openrouter/free",
        },
    ],
})

CHAT_RESPONSE = "This is a test response from the fake LLM server. The task has been completed successfully."

IMAGE_PLAN_RESPONSE = json.dumps({
    "action": "plan",
    "agents": [
        {
            "name": "ImageGenerator",
            "role": "Image Generator",
            "goal": "Generate an image based on the request",
            "persona": "A creative image generator",
            "tools": ["generate_image"],
            "task_description": "Generate the requested image",
            "depends_on": [],
            "model": "openrouter/free",
        },
    ],
})

CREATE_AGENTS_RESPONSE = json.dumps({
    "action": "create_agents",
    "team_name": "Test Team",
    "team_description": "A test team for E2E testing",
    "manager_persona": "A test manager",
    "manager_goal": "Coordinate the team",
    "agents": [
        {
            "name": "Worker1",
            "role": "Worker",
            "goal": "Do the work",
            "persona": "A diligent worker",
            "tools": [],
            "task_description": "Do the work",
            "depends_on": [],
            "model": "openrouter/free",
        },
    ],
})


def _pick_response(prompt: str) -> str:
    """Pick a canned response based on prompt content."""
    prompt_lower = prompt.lower() if prompt else ""

    # Plan-related prompts (assess_and_plan)
    if any(kw in prompt_lower for kw in ['"action"', "plan", "agent", "team", "create_agents"]):
        if "create" in prompt_lower and "team" in prompt_lower:
            return CREATE_AGENTS_RESPONSE
        if "image" in prompt_lower or "poster" in prompt_lower or "picture" in prompt_lower:
            return IMAGE_PLAN_RESPONSE
        return PLAN_RESPONSE

    # Default chat response
    return CHAT_RESPONSE


# ─── HTTP handler ─────────────────────────────────────────────────────

class FakeLLMHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Suppress default logging to keep test output clean
        pass

    def _send_json(self, status: int, body: dict):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/models":
            self._send_json(200, {"data": FAKE_MODELS})
            return

        if parsed.path == "/key":
            self._send_json(200, {
                "data": {
                    "limit": 100.0,
                    "limit_remaining": 95.0,
                    "limit_reset": None,
                    "usage": 5.0,
                    "usage_daily": 1.0,
                    "usage_weekly": 3.0,
                    "usage_monthly": 5.0,
                    "is_free_tier": True,
                }
            })
            return

        # Health check
        if parsed.path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        self._send_json(404, {"error": {"message": f"Not found: {parsed.path}"}})

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/chat/completions":
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError:
                body = {}

            # Extract prompt from messages
            messages = body.get("messages", [])
            prompt = ""
            for msg in messages:
                if isinstance(msg.get("content"), str):
                    prompt = msg["content"]
                    break
                elif isinstance(msg.get("content"), list):
                    for block in msg["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            prompt = block.get("text", "")
                            break
                    if prompt:
                        break

            response_text = _pick_response(prompt)
            is_stream = body.get("stream", False)

            if is_stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
                # Send content chunk
                chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": body.get("model", "test-model"),
                    "choices": [{"index": 0, "delta": {"content": response_text}, "finish_reason": None}],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.flush()
                # Send finish chunk
                finish_chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": body.get("model", "test-model"),
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                self.wfile.write(f"data: {json.dumps(finish_chunk)}\n\n".encode())
                self.wfile.flush()
                # Send usage chunk
                usage_chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": body.get("model", "test-model"),
                    "choices": [],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                }
                self.wfile.write(f"data: {json.dumps(usage_chunk)}\n\n".encode())
                self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                return

            # Non-streaming response
            self._send_json(200, {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": body.get("model", "test-model"),
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            })
            return

        self._send_json(404, {"error": {"message": f"Not found: {parsed.path}"}})


def main():
    port = 11435
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    server = ThreadingHTTPServer(("127.0.0.1", port), FakeLLMHandler)
    print(f"[FakeLLM] Listening on http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
