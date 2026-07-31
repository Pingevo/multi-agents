import json
import urllib.request

req = urllib.request.Request("https://openrouter.ai/api/v1/models")
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())

models = data.get("data", [])
video_models = []
for m in models:
    arch = m.get("architecture", {})
    if "video" in arch.get("output_modalities", []):
        video_models.append(m)

for m in video_models:
    print(f"ID: {m['id']}")
