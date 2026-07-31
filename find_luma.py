import json
import urllib.request
req = urllib.request.Request("https://openrouter.ai/api/v1/models")
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
for m in data.get("data", []):
    if "luma" in m["id"] or "haiper" in m["id"] or "kling" in m["id"] or "runway" in m["id"]:
        print(m["id"])
        print(m["architecture"])
