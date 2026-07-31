import requests
import json

resp = requests.get("https://openrouter.ai/api/v1/models")
data = resp.json().get("data", [])

video_keywords = ["luma", "haiper", "kling", "runway", "minimax"]

for m in data:
    mid = m["id"].lower()
    if any(kw in mid for kw in video_keywords) and m.get("pricing", {}).get("video", "0") != "0":
         print(f"ID: {m['id']}")
         print(f"Arch: {m.get('architecture')}")
         print(f"Pricing: {m.get('pricing')}")
         print("---")
