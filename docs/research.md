# Wellphone Research：手机后台并行 Agent 的实现思路调研

> 本文档是联网调研（GitHub / arXiv / AOSP / 技术社区）的结果沉淀，用于记录**实现思路、平台原语、同类项目、论文与待验证问题**。
> 调研日期：2026-09-24。

---

## 1. 结论摘要（先看这里）

| 问题 | 结论 |
|---|---|
| 核心矛盾 | 不是"怎么写点击脚本"，而是**显示 / 焦点 / 输入法 / 输入事件四重资源隔离** |
| 唯一可行路径 | 以 **shell 权限**（`adb shell` + `app_process`，或 scrcpy 的 server）创建 **VirtualDisplay**，把目标 App 跑在虚拟屏上 |
| 为什么不能用普通 App | 第三方 App 无法创建带独立焦点/触摸能力的 VirtualDisplay，也无法注入到指定 display（需系统权限 / hidden API） |
| 已有完整同类实现 | **ShadowAuto**（Apache-2.0，Android 10+，无需 root）几乎就是本题答案的工程化版本 |
| 决策层可直接复用 | **Open-AutoGLM**（AutoGLM-Phone）+ 论文里的 ReAct / 多 agent 范式 |
| 最小可行原型 | **scrcpy `--new-display` + `adb shell input -d <id>` + VLM**（纯 Python，零 Android 开发） |
| 最稳的进阶方案 | 自研 shell APK（抄 ShadowAuto），完全掌控 flags / IME policy / 输入注入 |

**一句话实现思路**：把所有操作（显示、感知、推理、执行）全部绑定到同一个 `displayId` 上，主屏（display 0）从头到尾不参与。

---

## 2. 问题定义：为什么这是资源隔离问题

手机的系统假设是「一个人、一块屏、一个焦点、一个 IME」。要让 agent 与用户**同时**用同一台设备且互不打扰，必须逐层打破这个假设：

| 资源 | 冲突表现 | 隔离手段 |
|---|---|---|
| 显示 (display) | agent 启动 App 会覆盖用户画面 | VirtualDisplay：独立窗口栈，渲染到独立 Surface |
| 焦点 (focus) | agent 点击会让用户正在输入的框失焦 | `VIRTUAL_DISPLAY_FLAG_OWN_FOCUS`（hidden flag） |
| 输入法 (IME) | agent 输入文字会弹出软键盘遮住用户 | `setDisplayImePolicy(displayId, DISPLAY_IME_POLICY_LOCAL)` |
| 输入事件 (input) | 注入的 tap/key 默认落到 display 0 | `InputEvent#setDisplayId(displayId)` 后再注入 |
| 感知 (perception) | 截图 / UI dump 默认读主屏 | `UiAutomation.getWindowsOnAllDisplays()` 按 displayId 过滤；`screencap -d <id>` |

**关键判断（答辩核心论点）**：这四层里任何一层没隔离干净，演示时都会露馅。所以"不打扰"必须是**架构保证**，而不是靠"检测用户是否在输入然后避让"这种概率性策略。

---

## 3. 需要纠正的两类常见误区

方案设计中最容易出现两类关键技术判断错误，必须在实现前纠正，否则会在演示时失败。

### 3.1 误区一：认为"agent 通过 ADB 操作主屏，用户无感知"

常见表述：

> 用户看到的是手机的正常显示，agent 的操作通过底层 ADB 执行，用户在应用层无感知。

**这是错的。** `adb shell input tap x y` 不带 `-d` 时，事件注入到 **display 0（主屏）**。用户会直接看到：
- 画面跳转（agent 启动 App 会切前台）
- 焦点被抢（用户正在打的字会中断）
- 键盘弹出 / 收起

ADB 只是"执行通道"，它不提供任何隔离。**隔离必须来自 VirtualDisplay。**

### 3.2 误区二：认为"UiAutomator / AccessibilityService 可后台执行且不抢焦点"

常见表述：

> UiAutomator：Android 官方自动化框架，可后台执行

UiAutomator 操作的是**当前聚焦的 display**；AccessibilityService 只能看到/操作**它所在 display 的窗口**，且第三方 App 无法创建虚拟屏。二者都不能解决"不打扰"。

### 3.3 结论

上述判断中**通用的分层思路**（云端大脑 + 手机端执行的分层、模型选型对比、风险表）可以保留；但**执行层必须整体替换为虚拟屏方案**，以本文档后续章节为准。

---

## 4. 平台原语层：Android 虚拟屏机制

### 4.1 创建虚拟屏：`DisplayManager.createVirtualDisplay`

```java
int flags = DisplayManager.VIRTUAL_DISPLAY_FLAG_PUBLIC          // 系统可见，App 可启动到上面
        | DisplayManager.VIRTUAL_DISPLAY_FLAG_PRESENTATION      // 承载独立展示内容
        | DisplayManager.VIRTUAL_DISPLAY_FLAG_OWN_CONTENT_ONLY  // 只显示自己的内容
        | hiddenFlag("VIRTUAL_DISPLAY_FLAG_SUPPORTS_TOUCH")     // 允许触摸落到虚拟屏
        | hiddenFlag("VIRTUAL_DISPLAY_FLAG_OWN_FOCUS")          // 独立焦点（关键！）
        | hiddenFlag("VIRTUAL_DISPLAY_FLAG_TRUSTED");           // 按可信显示屏处理

VirtualDisplay display = manager.createVirtualDisplay(
        "wellphone", width, height, dpi, outputSurface, flags);
int displayId = display.getDisplay().getDisplayId();
```

要点：
- 后三个 flag 是 **hidden API**，不同 Android 版本/厂商可能存在差异，必须用反射读取（读不到就返回 0，降级）。
- `OWN_FOCUS` 是"不抢焦点"的关键；`SUPPORTS_TOUCH` 是"能点"的关键。
- `outputSurface` 决定画面去向：给 `MediaCodec.createInputSurface()` 就能硬编码成 H.264 投屏；给 `ImageReader` 的 Surface 就能截图。
- **普通第三方 App 调用这个 API 会被权限拒绝**（需要 `CAPTURE_VIDEO_OUTPUT` / 系统签名），所以必须走 shell 身份。

### 4.2 把 App 启动到虚拟屏

```bash
am start --display <displayId> -f 0x10008000 -n <package/activity>
```

- `--display` 指定目标虚拟屏。
- `-f 0x10008000` 是 `FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_MULTIPLE_TASK` 的组合（ShadowAuto 用法），保证在新 display 上开新任务而不是复用主屏任务。
- 先用 `pm.getInstalledApplications()` + `getLaunchIntentForPackage()` 列出可启动 App，让模型从列表里选包名。

### 4.3 输入注入：必须带 displayId

```java
// 反射拿到 hidden API
setDisplayId.invoke(event, displayId);                       // InputEvent#setDisplayId
inject.invoke(inputManager, event, INJECT_WAIT_FOR_FINISH);  // InputManager#injectInputEvent
```

触摸 = 一对带 displayId 的 DOWN/UP `MotionEvent`；按键 = 一对 DOWN/UP `KeyEvent`。

**纯 shell 等价命令（无需写 Java）**：

```bash
adb shell input -d <displayId> tap <x> <y>
adb shell input -d <displayId> swipe <x1> <y1> <x2> <y2> <duration_ms>
adb shell input -d <displayId> text "hello"     # 仅 ASCII
adb shell input -d <displayId> keyevent 4        # BACK
```

`input` 命令签名：`input [<source>] [-d DISPLAY_ID] <command> [<arg>...]`。
社区实测（StackOverflow #63368101）：`adb shell input -d <display-id> tap <x> <y>` **可用**；但无线手柄/键盘这类外设输入不生效。

### 4.4 文本输入（中文）的三级降级

`input text` 只支持 ASCII，中文必须换路。ShadowAuto 的优先级（可直接照抄）：

1. Accessibility `ACTION_SET_TEXT`（最稳，直接设文本，不依赖 IME）
2. 设置剪贴板 + 粘贴（`set_clipboard` → `paste_clipboard`）
3. 退化为 key event 逐个输入（仅 ASCII）

AutoGLM 走的是另一条路：装 **ADBKeyboard.apk**，通过广播 `ADB_INPUT_TEXT` 注入文本。这条路要注意——广播作用于**当前聚焦的输入框**，在虚拟屏上是否落到虚拟屏的输入框，**必须实测**。

### 4.5 IME 隔离

```java
int previous = windowManager.getDisplayImePolicy(displayId);
windowManager.setDisplayImePolicy(displayId, DISPLAY_IME_POLICY_LOCAL);
```

- `DISPLAY_IME_POLICY_LOCAL` = 软键盘显示在该 display 内部，而不是默认显示。
- 若不支持，就退化为「尽量不依赖软键盘」：用 `ACTION_SET_TEXT` / 剪贴板完成输入，用 `keyevent 66`（ENTER）/ `keyevent 84`（SEARCH）提交。
- scrcpy 侧的等价开关：`--display-ime-policy=local`。

### 4.6 感知：UI 树 + 截图 + OCR 三路

```java
Method m = UiAutomation.class.getMethod("getWindowsOnAllDisplays");
SparseArray<List<AccessibilityWindowInfo>> all =
        (SparseArray<List<AccessibilityWindowInfo>>) m.invoke(automation);
List<AccessibilityWindowInfo> windows = all.get(displayId);   // 只取虚拟屏的窗口
```

三路感知各有分工：

| 方式 | 实现 | 适用 |
|---|---|---|
| UI 节点树 | `UiAutomation`（按 displayId 过滤） | 标准控件页，可拿到 text / bounds / clickable |
| 截图 | `SurfaceControl.screenshot` 或 `screencap -d <id>` 或 VirtualDisplay 的 `ImageReader` | 给 VLM 做视觉理解 |
| OCR 兜底 | Paddle Lite OCR（离线） | 自绘页面、复杂列表、电商/地图页等无无障碍节点的情况 |

**坐标系纪律（最容易踩的坑）**：所有坐标必须是**虚拟屏 display-local 坐标**。
- 不能用投屏预览窗口的像素坐标当点击坐标。
- 不能用主屏状态栏高度去修正虚拟屏坐标。
- 注入前必须 `setDisplayId(displayId)`。

### 4.7 投屏（可选，但演示需要）

VirtualDisplay 直接渲染到 `MediaCodec` 的 input surface → 系统硬编码 H.264 → 推给控制端 → `MediaCodec` 解码到 `TextureView`。

编码参数参考：`MIMETYPE_VIDEO_AVC`、`COLOR_FormatSurface`、`FRAME_RATE=8`、`I_FRAME_INTERVAL=1`。

**演示价值**：把虚拟屏投到电脑/另一个窗口，就能在视频里**同时展示**「用户主屏正常使用」+「agent 在虚拟屏上把任务做完」，直接满足交付要求里的双画面。

---

## 5. 工具层：三条创建虚拟屏的路径

### 5.1 路径 A：`settings put global overlay_display_devices`（最轻）

```bash
# 创建（分辨率/密度）
adb shell settings put global overlay_display_devices "1920x1080/200"
# 查 display id
adb shell dumpsys display | grep -E 'Display [0-9]{1,2}'
# 投射
scrcpy --display-id 21
# 清理
adb shell settings put global overlay_display_devices none   # 或 ""
```

- 本质是开发者选项里的 "Simulate secondary displays"。
- 优点：一条命令，零开发，App 能正常启动（社区实测可跑游戏）。
- 缺点：**只能创建一个**（改值不会新增第二个，需先清空）；部分国产 ROM 可能屏蔽该选项；输入注入要靠 `input -d`；焦点/IME 策略不可控。

### 5.2 路径 B：scrcpy `--new-display`（推荐作为 D1 首选）

```bash
scrcpy --new-display=1080x1920 --start-app=com.tencent.mm \
       --display-ime-policy=local --keep-active
```

可用原语（均已在官方文档核实）：

| 参数 | 作用 |
|---|---|
| `--new-display=WxH[/dpi]` | 新建虚拟屏（退出即销毁） |
| `--start-app=<pkg>` | 把 App 启动到虚拟屏 |
| `--flex-display` / `-x` | 虚拟屏随窗口自适应 |
| `--display-id=<id>` | 指定 mirror 的 display（用于投射已存在的虚拟屏） |
| `--display-ime-policy=local` | 虚拟屏 IME 不抢主屏键盘 |
| `--no-vd-system-decorations` | 关闭虚拟屏系统装饰 |
| `--no-vd-destroy-content` | 退出时不销毁虚拟屏里的 App |
| `--keyboard=uhid --mouse=uhid` | 物理 HID 模拟，绕过 IME |
| `--keep-active` / `--stay-awake` | 防息屏打断 |
| `--video-codec=h265 -b16M` | 投屏画质/码率 |

- 优点：**零 Android 开发**，纯命令行 + Python 编排即可；文档完备。
- 缺点：输入注入依赖 scrcpy 控制通道或 `input -d`；存在机型/版本 bug（见下）。

**已知坑**：scrcpy issue #4598 报告 Samsung + Android 14 上鼠标动作失效，workaround 是开**两个 scrcpy 窗口**，一个 `--display-id=90` 只发键盘、另一个 `--display-id=91` 只发点击。→ 说明"scrcpy 对虚拟屏的输入注入"在部分机型不稳定，**D1 必须实测**。

### 5.3 路径 C：自研 shell APK + `app_process`（最稳，ShadowAuto 路线）

```bash
adb push silent-shell.apk /data/local/tmp/
adb shell "CLASSPATH=/data/local/tmp/silent-shell.apk nohup sh -c \
  'exec app_process /system/bin com.silentauto.shell.Main --port=43110' \
  >/data/local/tmp/silent-auto.log 2>&1 </dev/null &"
```

- 以 **shell 身份**运行（Android 10+），可访问系统服务与部分 hidden API，**无需 root**。
- 完全掌控：虚拟屏 flags（`OWN_FOCUS`/`SUPPORTS_TOUCH`）、IME policy、输入注入、UI dump、OCR。
- 代价：需要 Java/Android 开发 + Gradle 编译。
- 参考实现：ShadowAuto（Apache-2.0，可直接参考/复用代码）。

**三条路径的取舍建议**：
- D1–D3 用**路径 B** 快速验证可行性（改造成本最低）。
- 若输入注入或 IME 隔离在目标机型上失败，升级到**路径 C**。
- 路径 A 可作为快速对照实验，用于证明"虚拟屏能跑真实 App"。

---

## 6. 决策层：大脑怎么选、怎么循环

### 6.1 直接复用 AutoGLM-Phone（`zai-org/Open-AutoGLM`）

- 架构：截图 → VLM 理解界面 → 输出动作 → ADB 执行 → 循环。
- 动作空间：`Launch / Tap / Type / Swipe / Back / Home / Long Press / Double Tap / Wait / Take_over`。
- 内置**敏感操作确认**与**人工接管回调**（`confirmation_callback` / `takeover_callback`）——正好对应我们要的 `take_over_gate`。
- 接入方式（云端 API，零部署）：
  ```bash
  python main.py --base-url https://open.bigmodel.cn/api/paas/v4 \
                 --model "autoglm-phone" --apikey "YOUR_KEY" "打开美团搜索附近的火锅店"
  ```
  也支持 ModelScope，或本地 vLLM/SGLang 部署 `AutoGLM-Phone-9B`（需 24GB+ 显存）。
- 包结构（改造点）：`phone_agent/adb/{connection,screenshot,input,device}.py`、`actions/handler.py`、`model/client.py`。
  → **只需把 `device.py` 的注入目标从 display 0 改成虚拟屏 displayId**，决策层可原样复用。
- 环境变量：`PHONE_AGENT_BASE_URL / PHONE_AGENT_MODEL / PHONE_AGENT_API_KEY / PHONE_AGENT_MAX_STEPS`。

### 6.2 ReAct 循环 + tool call（ShadowAuto 范式）

每一步：`Observe（读 UI simple dump） → Think（模型选一个 tool） → Act（执行） → Observe`，直到 `finish` 或用户停止。

提示词约束要点（可直接借鉴）：

```text
You control an Android app on a 1080x2400 virtual display.
Rules:
1. Call exactly one tool, never answer with prose.
2. Coordinates are display-local in this virtual display.
3. Prefer tap_target using targetIndex from targets.
4. Use focus_input before input_text.
5. Use get_screen_ocr when UI layout is sparse, empty, or wrong.
```

工具集（约 20 个，覆盖全流程）：

```text
get_ui_layout  get_screen_ocr
tap_target  tap  long_press  drag  scroll_ui
focus_input  input_text  set_clipboard  paste_clipboard
copy_selection  select_all_text  delete_selection  clear_text
press_back  press_key  wait  finish
```

**执行器要有"不完全相信模型"的兜底**（通用约束，不是给某个 App 写死）：
- 模型点了输入框但忘记输入 → 执行器按 hint 自动补一次 `input_text`。
- 输入搜索词后模型选择 wait/back → 执行器优先提交搜索。
- 搜索结果页 UI 节点为空 → 不要立刻返回，先试 OCR / full dump / 等待 / 滚动。

### 6.3 论文支撑（用于答辩引用）

| 论文 | 要点 | 对本项目的用处 |
|---|---|---|
| **Mobile-Agent-v2**（arXiv 2406.01014, TMLR） | 三 agent 架构：planning / decision / reflection + memory unit；比单 agent 提升 30%+ | 长任务导航：用 planning agent 管任务进度，reflection agent 纠错 |
| **UI-TARS**（arXiv 2501.12326） | 端到端原生 GUI agent，纯截图输入；AndroidWorld 46.6 超 GPT-4o 34.5；System-2 推理（任务分解 / 反思 / 里程碑识别） | 说明"单模型端到端"路线可行；里程碑识别可用于 verify 阶段 |
| **AutoGLM**（arXiv 2411.00820） | Autonomous foundation agents for GUIs | AutoGLM-Phone 的论文出处 |
| **LLM-Powered GUI Agents in Phone Automation**（arXiv 2504.19838, TMLR 2025） | 综述：Prompt Engineering / Training / Datasets / Benchmarks；框架分 Single / Multi / Plan-then-Act | 答辩时的全景地图，用来论证选型 |
| **AndroidWorld**（arXiv 2405.14573） | 动态 Android 评测环境 | 可用于自测任务完成率 |

**选型建议**：单步 VLM 决策起步（简单、可调试）→ 长任务再引入 Mobile-Agent-v2 式的 planning + reflection。不要一上来就多 agent。

---

## 7. 同类开源项目（重点参考）

### 7.1 ShadowAuto（`github.com/android-notes/ShadowAuto`）— 最接近本题的完整实现

- 中文名「隐控」，Apache-2.0，**Android 10+，无需 root**。
- 定位：让真实 App 跑在后台虚拟屏，由 AI 读取屏幕、注入点击/输入/滚动到虚拟屏，**主屏保持可用**。
- 三模块：
  - `android-shell`：`app_process` 启动的 shell 进程，负责虚拟屏创建、启动 App、UI/OCR 感知、调用大模型、执行 tool call、H.264 投屏。监听 `127.0.0.1:43110`（JSON-RPC）。
  - `controller-app`：手机端控制 App（配置模型、输入目标、看投屏、看日志、停止任务）。
  - `web-launcher`：Svelte + TangoADB WebUSB 启动器（浏览器里推文件 + 启动 shell 进程）。
- 已实现我们需要的全部能力：`OWN_FOCUS` 独立焦点、`setDisplayImePolicy` 本地 IME、`setDisplayId` 输入注入、`getWindowsOnAllDisplays` 按屏过滤、OCR 兜底、多任务并行、ReAct tool-call 循环。
- 文档：`docs/android-virtual-display-ai-automation.md`（中文技术深潜，本文档第 4 节大量结论来源于此）。
- **实战教训（直接写进我们的风险清单）**：
  - 敏感页（支付密码）投屏可能黑屏（Android 安全限制）。
  - 多任务并行会互相覆盖剪贴板，导致输入失败/串字。
  - **不要在主屏点开正在被自动化的那个 App**（会把它从虚拟屏拉走，自动化中断）。
  - hidden API 与 shell 权限在不同 Android 版本/厂商间存在差异。
  - 浏览器启动器需要 WebUSB 独占，Android Studio / adb server 会抢占。

### 7.2 OpenCyvis（`github.com/opencyvis/opencyvis-phone`）— 系统集成路线

- 有完整的分层文档（DeepWiki）：`VirtualDisplayManager` / `ScreenCapture` / `VdAccessibilityService` / `InputInjector` / `CoordinateMapper` / `Safety Guards` / `Takeover` / `Voice Input`。
- 关键差异：
  - 使用 `VIRTUAL_DISPLAY_FLAG_TRUSTED` + `OWN_FOCUS`。
  - **Task Reparenting**：反射 `IActivityTaskManager.moveRootTaskToDisplay`，把已有窗口从主屏"迁移"到虚拟屏（用于接管用户已经打开的 App）。
  - v1.0 走 **AOSP 集成 + privileged permissions**（需要系统签名/编译 ROM），门槛更高。
- 值得借鉴：`Safety Guards and Repeat Detection`（重复动作检测）、`CoordinateMapper`（坐标系换算）、`Takeover` 机制。
- 行业观察：有文章指出 Android 16/17 的 AppFunctions 安全架构可能收紧第三方后台自动化——**这是答辩时可以主动提出的前瞻性风险**。

### 7.3 其他相关参考

| 项目 / 资料 | 用途 |
|---|---|
| `Genymobile/scrcpy` | 虚拟屏创建 + 投屏 + 输入通道（路径 B 的基础） |
| gist `1999AZZAR/2d075b3acf97886f78f0f83759ac46db` | 现成 bash 脚本：`overlay_display_devices` 创建虚拟屏 + 自动探测 display id + scrcpy 投射 + trap 清理 |
| `zai-org/Open-AutoGLM` | 决策层 + 动作空间 + take-over 回调 |
| `X-PLUG/MobileAgent` | Mobile-Agent-v2 官方实现 |
| AOSP `samples/VirtualDeviceManager` | 官方示例：点击图标 → 创建虚拟屏 → 在虚拟屏启动 App → 流式传输画面 |
| AOSP Multi-Display / Input routing 文档 | 多显示器输入路由的官方说明 |
| `senzhk/ADBKeyBoard` | 广播式文本注入（中文输入方案之一） |
| `PhoneLLM/Awesome-LLM-Powered-Phone-GUI-Agents` | 论文/数据集/benchmark 全景清单 |

---

## 8. 推荐实现思路（分层）

```
┌───────────────────────────────────────────────────────────────┐
│ L5 编排层  mission_plan（LangGraph 状态机）                    │
│    perceive → decide → guard → execute → verify → loop/notify  │
│    跨 App 任务拆成独立可降级的 sub_mission                      │
├───────────────────────────────────────────────────────────────┤
│ L4 决策层  vlm_agent（AutoGLM-Phone / OpenAI 兼容 tool call）   │
│    单步 ReAct：读 display-local UI → 选 1 个 tool → 执行        │
│    model_provider 抽象，可切云端 API / 本地 vLLM               │
├───────────────────────────────────────────────────────────────┤
│ L3 安全层  take_over_gate                                      │
│    付款/密码/验证码/删除/发敏感内容 → 暂停 + 通知用户           │
├───────────────────────────────────────────────────────────────┤
│ L2 执行层  action_executor + input_channel                     │
│    所有事件 setDisplayId(displayId) 后注入                     │
│    文本：ACTION_SET_TEXT → 剪贴板 → keyevent 三级降级           │
├───────────────────────────────────────────────────────────────┤
│ L1 感知层  frame_source + ui_reader + ocr_fallback             │
│    只读虚拟屏：screencap -d / scrcpy 流 / getWindowsOnAllDisplays│
├───────────────────────────────────────────────────────────────┤
│ L0 平台层  virtual_display_runner                              │
│    创建 VirtualDisplay（OWN_FOCUS + SUPPORTS_TOUCH）            │
│    setDisplayImePolicy(local)；am start --display 启动 App      │
└───────────────────────────────────────────────────────────────┘
                              │
                     全部绑定同一个 displayId
```

### 8.1 分层与模块文件的对应

| 层 | 对应文件（snake_case） |
|---|---|
| L0 | `wellphone/device/virtual_display_runner.py`、`adb_client.py` |
| L1 | `wellphone/device/frame_source.py`、`ui_reader.py`、`ocr_fallback.py` |
| L2 | `wellphone/executor/action_executor.py`、`input_channel.py` |
| L3 | `wellphone/guard/take_over_gate.py` |
| L4 | `wellphone/agent/vlm_agent.py`、`action_space.py`、`model_provider.py` |
| L5 | `wellphone/agent/mission_plan.py`、`wellphone/main.py` |

### 8.2 阶段化落地（D1–D7）

| 阶段 | 做什么 | 走哪条路径 |
|---|---|---|
| D1 | 虚拟屏 + 主屏不被打扰的可行性验证 | 路径 B（scrcpy `--new-display`）+ 路径 A 对照 |
| D2 | `action_executor`：`input -d` 事件绑定 + 中文输入三级降级 | 路径 B，若失败切 C |
| D3 | `frame_source` + `vlm_agent`：单步 ReAct 接 AutoGLM API | 任意 |
| D4 | `take_over_gate` + 冲突实测（同 App 主屏/虚拟屏并存） | 任意 |
| D5 | `mission_plan` 跨 App 编排（微信回复 → 美团下单） | 任意 |
| D6 | 双画面录制 + README | 任意 |
| D7 | 答辩 + 失败清单 | — |

---

## 9. 待验证问题清单（D1 必须实测）

按优先级排序，建议逐条记录到 `docs/feasibility.md`：

1. **虚拟屏能否跑目标 App**：微信 / 美团在 `--new-display` 上能否正常启动、渲染、登录态正常？
2. **主屏是否真的不受影响**：agent 在虚拟屏点击时，主屏能否同时正常滑动、打字？
3. **`input -d <id>` 是否生效**：tap / swipe / keyevent 是否真的落到虚拟屏？（部分机型可能失效）
4. **中文输入走哪条路**：ADB Keyboard 广播在虚拟屏上是否落到虚拟屏的输入框？还是必须用 `ACTION_SET_TEXT`？
5. **IME 是否被隔离**：虚拟屏输入框获焦时，软键盘是否出现在虚拟屏而非主屏？
6. **`screencap -d <id>` 是否可用**：能否直接抓虚拟屏画面？（用于给 VLM 喂图）
7. **scrcpy 输入通道稳定性**：是否存在 issue #4598 那类"鼠标动作失效"问题？
8. **焦点隔离是否彻底**：虚拟屏内弹出对话框 / 键盘时，主屏焦点是否保持不变？
9. **敏感页黑屏范围**：支付类页面在虚拟屏投屏时是否黑屏？影响哪些步骤？
10. **多任务并行的剪贴板冲突**：同时跑两个任务时输入是否串字？
11. **机型差异**：小米 HyperOS / OPPO ColorOS / Pixel 上上述结论是否一致？
12. **长任务稳定性**：连续 50+ 步后是否出现内存/句柄泄漏、投屏卡顿？

---

## 10. 风险与坑（来自实战项目）

| 风险 | 来源 | 应对 |
|---|---|---|
| 输入注入落到主屏 | 通用 | 所有注入前强制 `setDisplayId(displayId)`；加断言校验 |
| 坐标系混用导致点偏 | ShadowAuto 常见问题 | 统一 display-local 坐标；禁止用预览窗口像素/主屏状态栏修正 |
| UI dump 为空但屏幕有内容 | ShadowAuto | OCR 兜底（Paddle Lite）；自绘页面/电商页高发 |
| 软键盘出现在主屏 | ShadowAuto | `setDisplayImePolicy(LOCAL)`；退化为 SET_TEXT / 剪贴板 |
| 敏感页投屏黑屏 | ShadowAuto / OpenCyvis | 接受黑屏；改用 UI dump + `take_over_gate` 交还用户 |
| 主屏点开被自动化的 App → 任务被拉走 | ShadowAuto 明确警告 | 演示脚本规避；必要时用 `moveRootTaskToDisplay` 迁移回来 |
| 多任务剪贴板互相覆盖 | ShadowAuto | 限制并行数；串行化剪贴板操作 |
| hidden API / shell 权限随版本厂商变化 | ShadowAuto | 反射读取 + 降级；实测记录机型矩阵 |
| scrcpy 对虚拟屏输入注入的机型 bug | scrcpy #4598 | 双窗口方案（键盘/点击分离）；或切路径 C |
| Android 16/17 AppFunctions 收紧后台自动化 | 行业分析 | 答辩时主动提出，体现前瞻性 |
| 虚拟屏兼容性（App 拒绝在副屏运行） | 通用 | D1 实测；降级为「支持 API 的走 API，其余走虚拟屏 UI」 |

---

## 11. 参考资料清单

**官方文档**
- scrcpy 虚拟屏：`https://github.com/Genymobile/scrcpy/blob/master/doc/virtual-display.md`
- scrcpy 设备控制：`https://github.com/Genymobile/scrcpy/blob/master/doc/device.md`
- scrcpy 控制通道：`https://github.com/Genymobile/scrcpy/blob/master/doc/control.md`
- scrcpy FAQ：`https://github.com/Genymobile/scrcpy/blob/master/FAQ.md`
- AOSP 多显示器概览：`https://source.android.com/docs/core/display/multi_display`
- AOSP 输入路由：`https://source.android.com/docs/core/display/multi_display/input-routing`
- AOSP VirtualDeviceManager 示例：`https://android.googlesource.com/platform/development/+/main/samples/VirtualDeviceManager/`
- Android VirtualDisplay API：`https://developer.android.com/reference/android/hardware/display/VirtualDisplay`

**开源项目**
- ShadowAuto（最相关）：`https://github.com/android-notes/ShadowAuto`
  - 技术深潜：`https://github.com/android-notes/ShadowAuto/blob/main/docs/android-virtual-display-ai-automation.md`
- OpenCyvis：`https://github.com/opencyvis/opencyvis-phone`
  - 虚拟屏章节：`https://deepwiki.com/opencyvis/opencyvis-phone/4-virtual-display-and-screen-capture`
- Open-AutoGLM：`https://github.com/zai-org/Open-AutoGLM`
- MobileAgent：`https://github.com/X-PLUG/MobileAgent`
- ADBKeyboard：`https://github.com/senzhk/ADBKeyBoard`
- 虚拟屏 bash 脚本 gist：`https://gist.github.com/1999AZZAR/2d075b3acf97886f78f0f83759ac46db`
- 论文全景清单：`https://github.com/PhoneLLM/Awesome-LLM-Powered-Phone-GUI-Agents`

**论文**
- Mobile-Agent-v2：`https://arxiv.org/abs/2406.01014`
- UI-TARS：`https://arxiv.org/abs/2501.12326`
- AutoGLM：`https://arxiv.org/abs/2411.00820`
- Phone GUI Agents 综述（TMLR 2025）：`https://arxiv.org/abs/2504.19838`
- AndroidWorld：`https://arxiv.org/abs/2405.14573`

**问题讨论**
- StackOverflow #63368101（Android 10 向虚拟屏注入输入）：`https://stackoverflow.com/questions/63368101/`
- scrcpy issue #3344（投射 App 内创建的虚拟屏）：`https://github.com/Genymobile/scrcpy/issues/3344`
- scrcpy issue #4598（虚拟屏鼠标动作失效，双窗口 workaround）：`https://github.com/Genymobile/scrcpy/issues/4598`

**公司资料**
- 公司主页：`https://whaletech.ai`
- WhalePhone 产品页：`https://phone.whaletech.site`（架构线索来源）
- 作业提交入口：`https://assignment.whaletech.site`
