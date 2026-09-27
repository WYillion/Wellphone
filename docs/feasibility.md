# Feasibility：D1 实测清单与阶段记录

> D1 是唯一关键路径。本文件是**实测记录模板**：每项实测后填写结果、机型与日期。
> 预判列来自 `docs/research.md`（平台原语）与 `docs/research_else.md`（lichj06 在 vivo/Android 16 的实测），**结论以自己实测为准**。

---

## 1. D1 实测清单（逐项过，勿跳）

| # | 实测项 | 方法 | 预判 | 实测结果 | 机型/日期 |
|---|---|---|---|---|---|
| 1 | 虚拟屏能否跑目标 App | `scrcpy --new-display=1080x1920 --start-app=com.tencent.mm --display-ime-policy=local --keep-active` | lichj06：vivo/Android 16 可跑设置类与普通 App | 待填 | 待填 |
| 2 | 主屏是否真的不受影响 | agent 在虚拟屏操作的同时主屏打字/滑动/切 App | lichj06：主屏全程不被抢 | 待填 | 待填 |
| 3 | `input -d <id>` 是否生效 | `adb shell input -d <id> tap/swipe/keyevent` | lichj06：生效；社区 StackOverflow #63368101 支持 | 待填 | 待填 |
| 4 | 中文输入走哪条路 | ADBKeyboard 广播 vs `ACTION_SET_TEXT` vs ASCII keyevent | 广播落点待实测；三级降级兜底 | 待填 | 待填 |
| 5 | IME 是否被隔离 | 虚拟屏输入框获焦，看软键盘出现在哪 | `--display-ime-policy=local` 应隔离到虚拟屏 | 待填 | 待填 |
| 6 | `screencap -d <id>` 是否可用 | `adb exec-out screencap -d <id> -p` | **预判无效**（lichj06："Display Id is not valid"）→ 主感知用 scrcpy 流抽帧 | 待填 | 待填 |
| 7 | scrcpy 输入通道稳定性 | 走 scrcpy 控制通道点击 | 部分机型有 bug（issue #4598，Samsung/Android 14 鼠标失效，双窗口 workaround） | 待填 | 待填 |
| 8 | 焦点隔离是否彻底 | 虚拟屏弹对话框/键盘时主屏焦点变化 | `OWN_FOCUS` flag 应保证独立（scrcpy 默认行为待确认） | 待填 | 待填 |
| 9 | 敏感页黑屏范围 | 虚拟屏投屏支付密码页 | 预判黑屏（ShadowAuto/OpenCyvis 一致），演示需规避 | 待填 | 待填 |
| 10 | 多任务剪贴板冲突 | 两个虚拟屏任务并行输入 | 预判互相覆盖，需串行化/加锁 | 待填 | 待填 |
| 11 | 机型差异矩阵 | 小米 HyperOS / OPPO ColorOS / Pixel / vivo 逐项跑 1–8 | Umbra 与 lichj06 覆盖 vivo；结论以自测为准 | 待填 | 待填 |
| 12 | 长任务稳定性 | 连续 50+ 步后内存/句柄/投屏延迟 | 待填 | 待填 | 待填 |
| 13 | 硬件编码器占用 | 同时建 2 块虚拟屏 | 预判手机一般 2–4 个编码器，**演示只开 1 块** | 待填 | 待填 |
| 14 | scrcpy 参数交互 | `--new-display` 与 `--no-video` 组合 | 预判互斥（lichj06）；无头环境录至 `/dev/null`（CPU≈0%） | 待填 | 待填 |

## 2. 关键结论区（D1 完成后提炼，不超过 5 条）

1. （待填）
2. （待填）

## 3. 阶段记录

| 阶段 | 日期 | 产出 | 卡点与解决 |
|---|---|---|---|
| D1 | 待填 | 待填 | 待填 |
| D2 | 待填 | 待填 | 待填 |
| D3 | 待填 | 待填 | 待填 |
| D4 | 待填 | 待填 | 待填 |
| D5 | 待填 | 待填 | 待填 |
| D6 | 待填 | 待填 | 待填 |
| D7 | 待填 | 待填 | 待填 |

## 4. 失败与降级预案

| 失败情形 | 降级路径 |
|---|---|
| 路径 B（scrcpy）建屏失败 | 路径 A（`overlay_display_devices`）对照 → 路径 C（自研 shell APK）→ 路径 D（App + Shizuku） |
| `input -d` 不生效 | 升级路径 C：`InputEvent#setDisplayId` + `injectInputEvent` |
| scrcpy 流抽帧不可用 | ffmpeg 依赖排查；或路径 C 的 `ImageReader` |
| ADBKeyboard 广播不落虚拟屏 | 改 `ACTION_SET_TEXT`（路径 C）或仅 ASCII 任务 |
| 目标 App 拒绝在虚拟屏运行 | 换演示 App；或 Task Reparenting（OpenCyvis 路线，成本高） |
