import os, requests
api_key = os.getenv("LLM_API_KEY", "")
# Try with various possible video model names
for model in ["luma/ray-2", "luma/ray", "haiper/haiper-video-2", "kling/kling-video", "minimax/video", "google/veo-3", "aliyun/wan-2.1"]:
    resp = requests.post(
        "https://openrouter.ai/api/v1/videos",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "prompt": "test"},
        timeout=15,
    )
    print(f"Model: {model} -> Status: {resp.status_code}, Body: {resp.text[:200]}")
