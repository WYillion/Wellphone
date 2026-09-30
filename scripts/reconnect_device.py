"""设备重启后自动重连。

用法:
    python scripts/reconnect_device.py            # 自动发现并重连
    python scripts/reconnect_device.py --check     # 仅检查 input 权限

流程:
    1. 轮询 adb mdns services 等待设备上线
    2. 自动 adb connect
    3. 更新 .env 的 WELLPHONE_ADB_SERIAL
    4. 测试 input tap 权限
"""
import argparse
import os
import re
import subprocess
import sys
import time

ADB = r'D:\Documents\AI learning\Wellphone\.tools\platform-tools\adb.exe'
ADB_PORT = '5038'
ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))


def run(args, timeout=20):
    result = subprocess.run(
        [ADB, '-P', ADB_PORT] + args, capture_output=True, text=True, timeout=timeout
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def discover(timeout_s=180):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        rc, out, err = run(['mdns', 'services'])
        match = re.search(r'_adb-tls-connect\._tcp\s+(\S+)', out)
        if match:
            return match.group(1)
        print('.', end='', flush=True)
        time.sleep(3)
    print()
    return None


def update_env(serial):
    if not os.path.exists(ENV_PATH):
        print(f"  (.env 不存在，跳过更新)")
        return
    with open(ENV_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    found = False
    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.startswith('WELLPHONE_ADB_SERIAL='):
                f.write(f'WELLPHONE_ADB_SERIAL={serial}\n')
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f'WELLPHONE_ADB_SERIAL={serial}\n')
    print(f"  .env 已更新: WELLPHONE_ADB_SERIAL={serial}")


def check_input(serial):
    print("  测试 input tap 权限...")
    rc, out, err = run(['-s', serial, 'shell', 'input', 'tap', '100', '100'])
    combined = (out + err).lower()
    if 'securityexception' in combined or 'inject_events' in combined:
        print("  ❌ 仍缺 INJECT_EVENTS 权限（安全设置未生效或需重启）")
        return False
    print("  ✅ input tap 权限正常")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='仅检查 input 权限')
    parser.add_argument('--serial', default=None, help='已知设备 serial')
    args = parser.parse_args()

    if args.check:
        serial = args.serial
        if not serial:
            rc, out, err = run(['devices'])
            m = re.search(r'(\d+\.\d+\.\d+\.\d+:\d+)\s+device', out)
            serial = m.group(1) if m else None
        if not serial:
            print("未找到设备")
            sys.exit(1)
        print(f"检查 {serial} ...")
        sys.exit(0 if check_input(serial) else 1)

    print("=== 等待设备上线（轮询 mDNS）===")
    serial = args.serial or discover()
    if not serial:
        print("❌ 超时未发现设备，请确认无线调试已开启")
        sys.exit(1)
    print(f"\n发现设备: {serial}")

    print("连接中...")
    rc, out, err = run(['connect', serial])
    print(f"  {out or err}")

    time.sleep(2)
    rc, out, err = run(['devices', '-l'])
    print(f"  设备列表: {out}")

    update_env(serial)
    check_input(serial)
    print("\n完成。可运行: python -m wellphone.main --dry-run")


if __name__ == '__main__':
    main()
