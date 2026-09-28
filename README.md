# Wellphone

一个**后台并行手机 Agent**：用户照常使用主屏的同时，agent 在一块独立虚拟屏上把真实任务办完——不抢焦点、不抢键盘、不切画面；付款/密码/验证码环节强制交还用户。

## 架构

```
  云端大脑 (VLM)                          手机端
┌───────────────────┐  截图/UI树  ┌──────────────────────────────┐
│  单步决策循环      │ ◄───────── │ 虚拟屏 (display_id > 0)       │
│  AutoGLM-Phone /  │            │  - 真实 App 在此运行          │
│  可换 provider    │ ─────────► │  - agent 在此点击/输入        │
└───────────────────┘  下一步动作 │  - take_over_gate 执行前拦截  │
        ▲                        │  - scrcpy 流抽帧感知          │
   用户主屏 (display 0)          └──────────────────────────────┘
   全程不参与 agent 操作
```

隔离原则：**显示 / 焦点 / 输入法 / 输入事件**四重绑定到同一个 `displayId`，主屏零参与；这是架构保证，不是"检测避让"。

## 部署步骤

```bash
pip install -r requirements.txt
# 安装 adb（Android platform-tools）与 scrcpy；手机开启 USB 调试后：
adb devices
python scripts/check_env.py                    # 环境自检
python -m wellphone.main --phase 1 --dry-run   # 无真机演练
python -m wellphone.main --phase 1 --start-app com.tencent.mm --text "收到，好的"
python -m wellphone.main --phase 2 --start-app com.sankuai.meituan   # 美团：付款前停下
```

## 自测

```bash
bash scripts/selftest.sh                       # 连通性自测：工具 / adb server / 设备状态 / display 基线
bash scripts/selftest.sh --full                # 完整 D1：再建虚拟屏 + 注入点击 + 感知测试
bash scripts/selftest.sh --full --app com.android.settings   # 顺带在虚拟屏启动指定 App
bash scripts/selftest.sh --vd --keep           # 只建虚拟屏并保留（Ctrl+C 后手动关闭）
```

脚本会自动处理 adb 端口残留（5037 → 5038/5039 自动回退），并对每种设备状态（`device` / `unauthorized` / `offline` / 无设备）给出对应的修复建议；退出码 0 表示设备就绪。

验收标准：**手机主屏照常用，虚拟屏窗口里的 App 独立运行，主屏一次都没被切走。**

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `VLM_BASE_URL` | OpenAI 兼容 API 地址 | `https://open.bigmodel.cn/api/paas/v4` |
| `VLM_API_KEY` | 模型 API Key | （必填） |
| `VLM_MODEL` | 决策模型 | `autoglm-phone` |
| `WELLPHONE_ADB_SERIAL` | 多设备时指定 serial | 自动 |
| `WELLPHONE_DISPLAY_WIDTH/HEIGHT/DPI` | 虚拟屏尺寸 | `1080/1920/240` |
| `MAX_ACTION_STEPS` | 任务步数上限 | `40` |
| `WELLPHONE_DRY_RUN` | 只打印命令不执行 | 空 |

## 技术选型说明

- **平行空间**：scrcpy `--new-display`（shell 身份建虚拟屏，免 root）；备选自研 shell APK（`app_process`）与 App+Shizuku。
- **感知**：主路径 scrcpy 视频流抽帧（`screencap -d` 对虚拟屏在部分机型无效，保留为实验项）；UI 树按 displayId 过滤 + OCR 兜底。
- **决策**：AutoGLM-Phone 动作空间（`Launch/Tap/Type/Swipe/Back/Home/LongPress/DoubleTap/Wait/Take_over`），`model_provider` 抽象可替换本地 vLLM / 自研 dLLM。
- **安全**：`take_over_gate` 规则层（支付/密码/验证码/删除/同意协议）+ 可插拔模型判定，规则独立于模型输出——模型只能加强拦截，不能放行。
- 详细论证见 `docs/suggestion.md` 与 `docs/tech_choices.md`。

## D1 实测结论（2026-09-28）

机型：Xiaomi Redmi 24129PN74C / Android 16 / HyperOS 3.0

| 实测项 | 结果 |
|---|---|
| scrcpy `--new-display` 建虚拟屏 + `--start-app` 跑 App | ✅ 虚拟屏 id=3 (1080x1920/373)，设置 App 成功启动 |
| 主屏是否受影响 | ✅ 虚拟屏 tap/swipe/HOME 后主屏 `FocusedDisplayId=0` 不变 |
| `input -d <id>` 注入 | ✅ tap / keyevent / swipe / text(ASCII) 均生效 |
| `screencap -d <id>` | ❌ 不可用（"Display Id is not valid"），感知走 scrcpy 流抽帧 |
| 中文输入 | ⚠️ `input text` 不支持中文（NPE），需 ADBKeyboard 广播降级 |
| `--no-playback` + `--record` 无头录屏 | ✅ 正常工作，录屏 512KB |

详见 `docs/feasibility.md`。

## 安全承诺

密码、支付、验证码**永不代输**：命中敏感特征的动作在执行前被闸门拦截，暂停任务并交还用户，接管后可继续。
