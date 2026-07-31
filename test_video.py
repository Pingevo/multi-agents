import requests
resp = requests.get("https://openrouter.ai/api/v1/models")
data = resp.json().get("data", [])
for m in data:
    mid = m["id"].lower()
    if "luma" in mid or "haiper" in mid or "runway" in mid or "kling" in mid:
        print(f"ID: {m['id']} Pricing: {m['pricing']} Modalities: {m.get('architecture', {})}")
