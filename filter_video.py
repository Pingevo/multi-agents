import json
import urllib.request
req = urllib.request.Request("https://openrouter.ai/api/v1/models")
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
for m in data.get("data", []):
    if "video" in m.get("architecture", {}).get("output_modalities", []):
        print(m["id"], m.get("pricing"))
