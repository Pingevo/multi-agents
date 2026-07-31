import json
import urllib.request
req = urllib.request.Request("https://openrouter.ai/api/v1/models")
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
for m in data.get("data", []):
    id = m["id"].lower()
    if "luma" in id or "kling" in id or "haiper" in id or "runway" in id or "sora" in id or "video" in id or "minimax" in id:
        print(f"{m['id']} -> output_modalities: {m.get('architecture', {}).get('output_modalities')}")
