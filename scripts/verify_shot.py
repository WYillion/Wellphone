from PIL import Image
import io, base64, requests, os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

img = Image.open("workspace/window_shot_0.png")
extrema = img.getextrema()
print(f"size={img.size}, mode={img.mode}, extrema={extrema}")

buf = io.BytesIO()
img.convert("RGB").save(buf, format="PNG")
b64 = base64.b64encode(buf.getvalue()).decode()

env = {}
with open(os.path.join(os.path.dirname(__file__), "..", ".env")) as f:
    for line in f:
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

resp = requests.post(
    f"{env['VLM_BASE_URL']}/chat/completions",
    headers={"Authorization": f"Bearer {env['VLM_API_KEY']}"},
    json={"model": env["VLM_MODEL"], "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": "请描述当前屏幕上显示的内容。如果看到设置界面，请说明。用 finish(message=\"描述\") 结束。"}
    ]}], "max_tokens": 1000, "temperature": 0.0, "stream": False},
    timeout=60,
)
data = resp.json()
print(f"API status: {resp.status_code} ({data.get('usage', {}).get('total_tokens', '?')} tokens)")
print(data["choices"][0]["message"]["content"][:600])
