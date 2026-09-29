"""无线调试配对助手。

用法:
    python scripts/pair_device.py

流程:
    1. 手机：设置 → 开发者选项 → 无线调试 → "使用配对码配对设备"
    2. 脚本提示输入配对码 + 端口
    3. 自动配对 + 连接
"""
import subprocess
import sys
import os

ADB = r'D:\Documents\AI learning\Wellphone\.tools\platform-tools\adb.exe'
PORT = '5038'
IP = '192.168.1.101'

def run_adb(args, timeout=15):
    cmd = [ADB, '-P', PORT] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def main():
    print("=== 无线调试配对助手 ===")
    print()
    print("请在手机上操作：")
    print("  设置 → 开发者选项 → 无线调试 → 点击「使用配对码配对设备」")
    print()
    print("手机会显示：")
    print("  - 配对码（6 位数字）")
    print("  - 配对端口（如 :38825）")
    print()

    pair_code = input("请输入配对码（6 位数字）: ").strip()
    if not pair_code or not pair_code.isdigit():
        print("ERROR: 配对码必须是数字")
        sys.exit(1)

    pair_port = input(f"请输入配对端口（如 38825）: ").strip()
    if not pair_port:
        print("ERROR: 端口不能为空")
        sys.exit(1)

    print(f"\n正在配对 {IP}:{pair_port} ...")
    rc, out, err = run_adb(['pair', f'{IP}:{pair_port}', pair_code])
    print(f"  结果: {out}")
    if rc != 0:
        print(f"  错误: {err}")
        sys.exit(1)

    print("\n配对成功！现在需要连接端口。")
    print("请看手机无线调试主页（不是配对页）上的「IP 地址和端口」")
    connect_port = input(f"请输入连接端口（如 42883）: ").strip()
    if not connect_port:
        print("ERROR: 端口不能为空")
        sys.exit(1)

    print(f"\n正在连接 {IP}:{connect_port} ...")
    rc, out, err = run_adb(['connect', f'{IP}:{connect_port}'])
    print(f"  结果: {out}")

    print("\n验证设备状态...")
    rc, out, err = run_adb(['devices', '-l'])
    print(f"  {out}")

    if 'device' in out and 'offline' not in out:
        print(f"\n✅ 设备已连接！")
        print(f"   Serial: {IP}:{connect_port}")

        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            with open(env_path, 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.startswith('WELLPHONE_ADB_SERIAL='):
                        f.write(f'WELLPHONE_ADB_SERIAL={IP}:{connect_port}\n')
                    else:
                        f.write(line)
            print(f"   .env 已更新: WELLPHONE_ADB_SERIAL={IP}:{connect_port}")
    else:
        print("\n❌ 设备未就绪，请检查手机无线调试是否开启")

if __name__ == '__main__':
    main()
