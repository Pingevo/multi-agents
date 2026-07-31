import json
import urllib.request

req = urllib.request.Request("https://openrouter.ai/api/v1/models")
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())

models = data.get("data", [])
for m in models:
    if "luma" in m["id"] or "kling" in m["id"] or "haiper" in m["id"] or "runway" in m["id"]:
        print(f"ID: {m['id']}")
