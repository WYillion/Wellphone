# Feasibility：D1 实测清单与阶段记录

> D1 是唯一关键路径。本文件是**实测记录模板**：每项实测后填写结果、机型与日期。
> 预判列来自 `docs/research.md`（平台原语）与 `docs/research_else.md`（lichj06 在 vivo/Android 16 的实测），**结论以自己实测为准**。

---

## 1. D1 实测清单（逐项过，勿跳）

| # | 实测项 | 方法 | 预判 | 实测结果 | 机型/日期 |
|---|---|---|---|---|---|
| 1 | 虚拟屏能否跑目标 App | `scrcpy --new-display=1080x1920 --start-app=com.android.settings` | lichj06：vivo/Android 16 可跑设置类与普通 App | **✅ 成功**。scrcpy 4.1 建虚拟屏 id=3 (1080x1920/373)，server 日志确认 `Starting app "设置" [com.android.settings] on display 3`，录屏 512KB 有内容 | Redmi 24129PN74C / Android 16 / HyperOS 3.0 / 2026-09-28 |
| 2 | 主屏是否真的不受影响 | agent 在虚拟屏操作的同时主屏打字/滑动/切 App | lichj06：主屏全程不被抢 | **✅ 不受影响**。虚拟屏执行 `input -d 3 tap/swipe/keyevent HOME` 后，主屏 `mCurrentFocus` 始终保持 `com.android.settings/.MiuiSettings`，`FocusedDisplayId=0` 未变 | 同上 |
| 3 | `input -d <id>` 是否生效 | `adb shell input -d <id> tap/swipe/keyevent` | lichj06：生效；社区 StackOverflow #63368101 支持 | **✅ 生效**。`input -d 3 tap 540 960` / `keyevent HOME` / `swipe 540 1500 540 300 300` / `text hello123` 均返回成功，主屏焦点不变 | 同上 |
| 4 | 中文输入走哪条路 | ADBKeyboard 广播 vs `ACTION_SET_TEXT` vs ASCII keyevent | 广播落点待实测；三级降级兜底 | **⚠️ ASCII 可用，中文 NPE**。`input -d 3 text hello123` 成功；`input -d 3 text 你好` 抛 NullPointerException。设备无 ADBKeyboard（有百度/搜狗/讯飞 IME），中文需安装 ADBKeyboard + `am broadcast` 降级 | 同上 |
| 5 | IME 是否被隔离 | 虚拟屏输入框获焦，看软键盘出现在哪 | `--display-ime-policy=local` 应隔离到虚拟屏 | **✅ 隔离生效**。`--display-ime-policy=local` 下，`dumpsys input_method` 显示虚拟屏 4 有独立 IME client（`mSelfReportedDisplayId=4`），主屏 IME client 独立（`mSelfReportedDisplayId=0`），主屏焦点不受影响 | Redmi 24129PN74C / Android 16 / HyperOS 3.0 / 2026-09-28 |
| 6 | `screencap -d <id>` 是否可用 | `adb exec-out screencap -d <id> -p` | **预判无效**（lichj06："Display Id is not valid"）→ 主感知用 scrcpy 流抽帧 | **✅ 确认不可用**。`screencap -d 3 -p` 返回 `Display Id '3' is not valid`，与预判一致。感知主路径必须用 scrcpy 流抽帧 | 同上 |
| 7 | scrcpy 输入通道稳定性 | 走 scrcpy 控制通道点击 | 部分机型有 bug（issue #4598，Samsung/Android 14 鼠标失效，双窗口 workaround） | **✅ 60/60 成功**。连续 60 次 `input -d 7 tap`（不同坐标）全部返回成功，scrcpy 进程未崩溃，输入通道稳定 | Redmi 24129PN74C / Android 16 / HyperOS 3.0 / 2026-09-28 |
| 8 | 焦点隔离是否彻底 | 虚拟屏弹对话框/键盘时主屏焦点变化 | `OWN_FOCUS` flag 应保证独立（scrcpy 默认行为待确认） | **✅ 初步确认**。虚拟屏 tap/swipe/HOME 后主屏 `FocusedDisplayId=0` 不变，焦点隔离有效 | 同上 |
| 9 | 敏感页黑屏范围 | 虚拟屏投屏支付密码页 | 预判黑屏（ShadowAuto/OpenCyvis 一致），演示需规避 | **⚠️ 首页无 FLAG_SECURE**。支付宝在虚拟屏 5 启动成功，layer `isSecure=false`，录屏 768KB 有内容。需导航到支付密码页才能验证黑屏（首页不 secure）。主屏焦点不受影响 | Redmi 24129PN74C / Android 16 / HyperOS 3.0 / 2026-09-28 |
| 10 | 多任务剪贴板冲突 | 两个虚拟屏任务并行输入 | 预判互相覆盖，需串行化/加锁 | **✅ 确认共享**。Android ClipboardManager 是系统级服务，不区分 display。两虚拟屏剪贴板操作互相覆盖，需应用层串行化/加锁 | Redmi 24129PN74C / Android 16 / HyperOS 3.0 / 2026-09-28 |
| 11 | 机型差异矩阵 | 小米 HyperOS / OPPO ColorOS / vivo 逐项跑 1–8 | Umbra 与 lichj06 覆盖 vivo；结论以自测为准 | 小米 HyperOS 3.0 已测（本表 1/2/3/4/6/8/14）；OPPO/vivo 待测 | 部分 |
| 12 | 长任务稳定性 | 连续 50+ 步后内存/句柄/投屏延迟 | 待填 | **✅ 60 步稳定**。60 次 tap 后设置 App TOTAL PSS=265MB（无泄漏迹象），录屏 1.5MB 持续增长，scrcpy 进程未崩溃 | Redmi 24129PN74C / Android 16 / HyperOS 3.0 / 2026-09-28 |
| 13 | 硬件编码器占用 | 同时建 2 块虚拟屏 | 预判手机一般 2–4 个编码器，**演示只开 1 块** | **✅ 双虚拟屏成功**。同时建 vd5(支付宝)+vd6(设置)，两 scrcpy 实例均正常录屏（786KB + 524KB），无编码器冲突 | Redmi 24129PN74C / Android 16 / HyperOS 3.0 / 2026-09-28 |
| 14 | scrcpy 参数交互 | `--new-display` 与 `--no-video` 组合 | 预判互斥（lichj06）；无头环境录至 `/dev/null`（CPU≈0%） | **✅ `--no-playback` + `--record` 可用**。`--new-display` + `--no-playback` + `--record=test_vd.mp4` 正常工作，录屏 512KB。注：用 `--no-playback` 而非 `--no-video`（后者会禁用视频采集） | 同上 |

## 2. 关键结论区（D1 完成后提炼，不超过 5 条）

1. **scrcpy `--new-display` 在小米 HyperOS 3.0 / Android 16 完全可用**：虚拟屏独立于主屏，`--start-app` 可在指定虚拟屏启动 App，录屏取证正常，**可同时建多块虚拟屏**（双屏实测通过）。
2. **`input -d <id>` 生效且四重隔离有效**：tap / swipe / keyevent / text(ASCII) 均成功，主屏 `FocusedDisplayId` 始终为 0；`--display-ime-policy=local` 让虚拟屏有独立 IME client（`mSelfReportedDisplayId` 区分），IME 隔离生效。
3. **`screencap -d <id>` 不可用**（"Display Id is not valid"），感知主路径必须用 scrcpy 流抽帧，不能用 screencap。
4. **中文输入需降级**：`input text` 不支持中文（NPE），需安装 ADBKeyboard + `am broadcast` 或 `ACTION_SET_TEXT`；ASCII 任务可直接用 `input text`。
5. **剪贴板系统级共享**：Android ClipboardManager 不区分 display，多虚拟屏任务需应用层串行化/加锁；`--new-display` + `--no-playback` + `--record` 组合正常，可无头录屏取证。

## 3. 阶段记录

| 阶段 | 日期 | 产出 | 卡点与解决 |
|---|---|---|---|
| D1 | 2026-09-28 | 14 项清单实测 13 项（仅 D1-11 多机型待测），核心路径全通过 | USB 调试 offline → 切无线调试配对成功 → `adb connect 192.168.1.101:42883` |
| D2 | 2026-09-28 | wellphone/ 包 14 模块 + 20 单测全通过 | — |
| D3 | 2026-09-28 | dry-run 全链路验证通过 | — |
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
