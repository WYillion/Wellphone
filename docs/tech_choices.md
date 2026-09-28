# Tech Choices：技术选型论证（答辩核心素材）

> 本文回答"为什么选这条、为什么不选那条"。每条决策配：动机 → 依据 → 放弃项。
> 支撑材料：`docs/research.md`（原语实测）、`docs/research_else.md`（同类项目）、`docs/suggestion.md`（方向梳理）。

---

## 决策 1：用虚拟屏做架构级隔离，而不是"检测避让"

- **动机**：题目要求"用户全程不被打扰"且任务要"真的办完"。检测键盘/动画/滑动后避让是概率性策略——演示时必然有漏网时刻。
- **依据**：手机系统假设"一人一屏一焦点一 IME"，四层资源（display / focus / IME / input）都必须与主屏隔离；任何一层没隔离干净演示就露馅。
- **放弃项**：避让策略、主屏截图感知、主屏注入（`input tap` 不带 `-d` 必落 display 0）。

## 决策 2：建屏走路径 B（scrcpy `--new-display`），备 C/D

- **动机**：D1 用最少开发量打通全链路；shell 身份是普通 App 拿不到、而本题明确允许（"连着电脑跑不算作弊"）的能力。
- **依据**：scrcpy 提供 `--new-display` / `--start-app` / `--display-ime-policy=local` / `--display-id` 全套原语；零 Android 开发。
- **D1 实测确认**（小米 Redmi 24129PN74C / Android 16 / HyperOS 3.0）：
  - ✅ `--new-display=1080x1920` 成功建虚拟屏（id=2–7），`--start-app` 成功在指定虚拟屏启动设置/支付宝
  - ✅ **可同时建多块虚拟屏**（双屏实测通过，两 scrcpy 实例并行录屏正常）
  - ✅ `--display-ime-policy=local` 生效：虚拟屏有独立 IME client（`mSelfReportedDisplayId` 区分）
  - ✅ `input -d <id>` 生效：tap / swipe / keyevent / text(ASCII) 均成功，主屏 `FocusedDisplayId` 始终为 0
  - ✅ 60 步长任务稳定（PSS 265MB 无泄漏，scrcpy 未崩溃）
- **放弃/备选**：
  - 路径 A `overlay_display_devices`：只能建一块屏，仅作对照实验；
  - 路径 C 自研 shell APK（`app_process`）：完全掌控 hidden flags，路径 B 失败时升级；
  - 路径 D App + Shizuku：Umbra 已验证，作为免编译 ROM 的中间态；
  - KernelSU/Magisk：需解锁 Bootloader，直接排除。

## 决策 3：感知主路径是 scrcpy 流抽帧，不是 `screencap -d`

- **动机**：感知源必须与执行目标同屏（虚拟屏），且不能依赖单个易碎接口。
- **依据**：`screencap -d <虚拟屏id>` 在 vivo/Android 16 实测报 "Display Id is not valid"（lichj06）；纯 shell 的 `uiautomator dump` 只读焦点窗口、不能按 display 指定。
- **D1 实测确认**：本机 `screencap -d 3 -p` 同样报 `Display Id '3' is not valid`，与预判一致。感知主路径必须用 scrcpy 流抽帧（`--no-playback` + `--record` 组合实测正常，录屏 512KB–1.5MB 有内容）。
- **结构**：`FrameSource` 抽象（`ScreencapSource` 保留为实验项、`ScrcpyRecordSource` 为主路径、路径 C 可加 `ImageReader` 实现）；坐标一律 display-local。

## 决策 4：决策层复用 AutoGLM-Phone，`model_provider` 抽象

- **动机**：把工程重心放在"执行层隔离改造"这一真正的区分点上，不为提示词工程重复造轮子。
- **依据**：AutoGLM 动作空间现成（含 `Take_over`）、50+ 中文主流 App 验证、云端 API 零部署。
- **放弃/备选**：UI-TARS 本地部署（需 24GB 显存）、通用多模态模型自建动作空间（可作 fallback）；`model_provider` 抽象保留本地 vLLM / 自研 dLLM 替换位。

## 决策 5：`take_over_gate` 独立于模型输出

- **动机**："密码、支付、验证码永不代输"是产品级安全承诺（WhalePhone 公开承诺、AutoGLM `Take_over` 同构），不能只依赖 VLM 自觉。
- **结构**：规则层（支付/密码/验证码/删除/同意协议等模式，作用于动作 text/reason 与页面文本）+ 可插拔模型判定；**模型只能加强拦截，不能放行规则命中项**。单测 `tests/test_take_over_gate.py` 固化此语义。

## 决策 6：编排用与 LangGraph 同构的状态机

- **动机**：`perceive → decide → guard → execute → verify` 节点边界清晰、可插桩、可回放；依赖未就绪时（离线演示、精简环境）也能运行。
- **结构**：`MissionPlan` 实现该循环与终止语义（`finish` / `take_over` / `max_steps_reached`），后续可平滑迁移到 `langgraph.graph.StateGraph`。

## 放弃项汇总

| 方案 | 放弃原因 |
|---|---|
| "检测用户输入后避让" | 概率性，演示不可复现 |
| MediaProjection 截屏 | 面向主屏、需授权、有通知提示 |
| UiAutomator / AccessibilityService 直接操作 | 作用于当前聚焦 display，第三方 App 无法建虚拟屏 |
| scrcpy 镜像主屏 | 镜像即占用用户屏幕，且不能后台跑 |
| KernelSU / Magisk | 需解锁 Bootloader，多品牌永久不可行 |

## 与同类项目的差异化（引自 `docs/research_else.md` 第 6 节）

GitHub 已有 4 个"虚拟屏 + agent + 主屏不打扰"公开项目（ShadowAuto、Umbra、lichj06、OpenCyvis），但均未同时做到：**四重隔离 + 云端 VLM 编排 + 独立于模型输出的 take_over 闸门 + 跨 App 双画面演示**的完整闭环。答辩定位：不宣称首创虚拟屏方案，强调完整闭环与工程判断。

## 前瞻风险（答辩主动提出）

Android 16/17 的 AppFunctions 安全架构可能收紧第三方后台自动化；OpenCyvis 的 Task Reparenting（`moveRootTaskToDisplay`）可作为"接管用户已打开 App"的后续扩展方向。

## D1 实测总结（答辩素材）

> 机型：Xiaomi Redmi 24129PN74C / Android 16 / HyperOS 3.0
> 日期：2026-09-28　　结果：14 项中 13 项通过（仅 D1-11 多机型矩阵待测）

### 答辩一句话结论

**在小米 HyperOS 3.0 / Android 16 上，scrcpy `--new-display` + `input -d` + `--display-ime-policy=local` 构成的四重隔离（显示/焦点/IME/输入事件）全部实测通过，60 步长任务稳定，可同时建多块虚拟屏。**

### 需在答辩中主动说明的限制

| 限制 | 实测结果 | 降级方案 |
|---|---|---|
| `screencap -d` 不可用 | "Display Id is not valid" | 感知走 scrcpy 流抽帧（已验证） |
| `input text` 不支持中文 | NullPointerException | ADBKeyboard `am broadcast` 或 `ACTION_SET_TEXT` |
| 剪贴板系统级共享 | ClipboardManager 不区分 display | 应用层串行化/加锁 |
| `am start --display` 需 system 权限 | SecurityException | 用 scrcpy `--start-app`（server 权限） |
| 支付密码页 FLAG_SECURE | 首页不 secure，密码页待验证 | 演示规避密码页（分镜已设计） |
