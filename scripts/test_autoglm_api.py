"""AutoGLM-Phone API 快速测试脚本。

用法:
    python scripts/test_autoglm_api.py

需要 .env 中配置 VLM_API_KEY。
"""
import os
import sys
import base64
import json
import time
import subprocess

def load_env():
    env = {}
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return env

def main():
    env = load_env()
    api_key = env.get('VLM_API_KEY', '')
    base_url = env.get('VLM_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4')
    model = env.get('VLM_MODEL', 'autoglm-phone')

    if not api_key:
        print("ERROR: VLM_API_KEY 未设置。请在 .env 中填入你的 API Key。")
        print("获取地址: https://bigmodel.cn/usercenter/proj-mgmt/apikeys")
        sys.exit(1)

    print(f"=== AutoGLM-Phone API 测试 ===")
    print(f"Base URL: {base_url}")
    print(f"Model:    {model}")
    print(f"API Key:  {api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else f"API Key: {api_key}")
    print()

    # 截取主屏截图
    adb = env.get('WELLPHONE_ADB', 'adb')
    serial = env.get('WELLPHONE_ADB_SERIAL', '')
    print("截取主屏截图...")
    cmd = [adb, '-P', '5038']
    if serial:
        cmd += ['-s', serial]
    cmd += ['exec-out', 'screencap', '-p']
    result = subprocess.run(cmd, capture_output=True, timeout=10)
    if result.returncode != 0 or len(result.stdout) < 100:
        print(f"截图失败: rc={result.returncode}, size={len(result.stdout)}")
        sys.exit(1)
    screenshot_b64 = base64.b64encode(result.stdout).decode('utf-8')
    print(f"截图成功: {len(result.stdout)} bytes ({len(screenshot_b64)} base64)")

    # 构造 OpenAI 兼容请求
    import requests
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "请描述当前屏幕上显示的内容，并用 do(action=...) 格式给出下一步操作建议。如果屏幕上没有需要操作的内容，用 finish(message=\"测试完成\") 结束。"
                    }
                ]
            }
        ],
        "max_tokens": 3000,
        "temperature": 0.0,
        "stream": False,
    }

    print(f"\n发送请求到 {url} ...")
    start = time.time()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        elapsed = time.time() - start
        print(f"响应状态: {resp.status_code} ({elapsed:.1f}s)")

        if resp.status_code != 200:
            print(f"错误响应: {resp.text[:2000]}")
            sys.exit(1)

        data = resp.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        usage = data.get('usage', {})

        print(f"\n=== 模型响应 ===")
        print(content)
        print(f"\n=== Usage ===")
        print(f"prompt_tokens: {usage.get('prompt_tokens', 'N/A')}")
        print(f"completion_tokens: {usage.get('completion_tokens', 'N/A')}")
        print(f"total_tokens: {usage.get('total_tokens', 'N/A')}")
        print(f"\n=== 测试通过 ===")

    except requests.exceptions.Timeout:
        print("请求超时 (60s)")
        sys.exit(1)
    except Exception as e:
        print(f"请求异常: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
