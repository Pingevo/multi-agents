import os, requests
api_key = os.getenv("LLM_API_KEY", "")
# Try the videos endpoint to see what models are available
resp = requests.get(
    "https://openrouter.ai/api/v1/videos",
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=15,
)
print(f"Status: {resp.status_code}")
print(f"Body: {resp.text[:500]}")
