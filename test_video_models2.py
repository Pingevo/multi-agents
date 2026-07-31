import requests
resp = requests.get("https://openrouter.ai/api/v1/models")
data = resp.json().get("data", [])
for m in data:
    mid = m["id"].lower()
    if any(kw in mid for kw in ["luma", "haiper", "kling", "runway", "minimax"]):
         print(f"ID: {m['id']} - Arch: {m.get('architecture')}")
