import os
import requests

api_key = os.getenv("LLM_API_KEY", "")
resp = requests.get(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {api_key}"}
)
data = resp.json().get("data", [])
for m in data:
    arch = m.get("architecture", {})
    if "video" in arch.get("output_modalities", []):
        print(f"FOUND: {m['id']}")
