import os, requests
api_key = os.getenv("LLM_API_KEY", "")
# Try the videos endpoint with POST to see what models are available
resp = requests.post(
    "https://openrouter.ai/api/v1/videos",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json={"prompt": "test"},
    timeout=15,
)
print(f"Status: {resp.status_code}")
print(f"Body: {resp.text[:500]}")
