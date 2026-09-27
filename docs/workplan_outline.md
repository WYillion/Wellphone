# Workplan Outline: 手机并行 Agent 系统

## 一、任务理解与核心挑战

### 1.1 任务目标
做一个 **后台并行手机 Agent**，能够在用户正常使用手机的同时，在后台完成指定的独立任务，全程不打扰用户（不抢焦点、键盘、屏幕）。

### 1.2 核心挑战分析

| 挑战类型 | 具体问题 | 技术关键点 |
|---------|---------|-----------|
| **屏幕焦点冲突** | 手机只有一个显示屏幕，用户和 agent 不能同时"看" | 虚拟显示器（VirtualDisplay）：独立窗口栈 + 独立 Surface |
| **输入冲突** | 只有一个触摸屏和一个软键盘 | 输入事件绑定 displayId + IME 本地化 |
| **感知与执行分离** | agent 需要感知屏幕状态但不能影响主屏 | 感知源与执行目标同为虚拟屏，主屏零参与 |
| **任务规划** | agent 需要理解 UI 并做出决策 | 多模态大模型 + GUI Agent |
| **实时性** | 边用边执行，不能有明显延迟感知 | 高效的状态同步机制 |

### 1.3 关键技术判断（先明确，避免走弯路）

- 手机的系统假设是「一个人、一块屏、一个焦点、一个 IME」。要让 agent 与用户**同时**使用且互不打扰，必须在**显示 / 焦点 / 输入法 / 输入事件**四层分别建立隔离。
- ADB 只是**执行通道**，本身不提供隔离：`adb shell input tap x y` 不带 `-d` 时会注入 display 0（主屏），导致抢焦点、跳屏、键盘弹出。
- 第三方 App（即使有 AccessibilityService）无法创建带独立焦点与触摸能力的 VirtualDisplay；可行的建屏路径是以 **shell 身份**运行（scrcpy 的 `app_process` 方案或自研 shell APK）。
- 因此，**"不打扰"必须由架构保证**，而不是靠"检测用户是否在输入然后避让"这类概率性策略。

---

## 二、技术架构设计

### 2.1 整体架构：云端大脑 + 手机端虚拟屏执行

```
┌─────────────────────────────────────────────────────────────┐
│                    云端 (LLM Brain)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 任务规划器   │  │ 屏幕理解     │  │ 决策引擎    │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└──────────────────────────┬──────────────────────────────────┘
                           │ API（截图 + 动作）
┌──────────────────────────▼──────────────────────────────────┐
│                手机端（虚拟屏平行空间）                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ L0 平台层：VirtualDisplay（OWN_FOCUS + SUPPORTS_TOUCH）│  │
│  │            IME policy = local；am start --display      │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 屏幕感知    │  │ 指令执行    │  │ 安全闸门    │          │
│  │ (只读虚拟屏)│  │ (setDisplayId│  │(take_over)  │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
        ▲ 主屏（display 0）全程不参与 agent 的任何操作
```

### 2.2 核心模块分解

#### 2.2.0 模块 0：虚拟显示器平台层（Virtual Display）
**功能**：创建并管理 agent 专用的虚拟屏，把目标 App 跑在虚拟屏上

技术方案：
- **路径 A（最轻）**：`adb shell settings put global overlay_display_devices "1920x1080/200"`，零开发，但只能创建一个屏
- **路径 B（首选）**：scrcpy `--new-display=1080x1920 --start-app=<pkg> --display-ime-policy=local --keep-active`，零 Android 开发
- **路径 C（最稳）**：自研 shell APK + `app_process`，以 shell 身份运行，完全掌控 flags / IME policy / 输入注入

关键点：
- flags 需包含 `OWN_FOCUS`（独立焦点）与 `SUPPORTS_TOUCH`（可点击），均为 hidden API，建议反射读取并做降级
- 启动 App 到虚拟屏：`am start --display <displayId> -f 0x10008000 -n <pkg/activity>`
- 退出清理：`settings put global overlay_display_devices none`

#### 2.2.1 模块 A：屏幕感知层（Screen Perception）
**功能**：捕获**虚拟屏**内容，供云端分析；不读主屏

技术方案：
- **虚拟屏抓帧**：`screencap -d <displayId>`，或 VirtualDisplay 输出到 `ImageReader` 的 Surface
- **视频流**：scrcpy 投出虚拟屏（同时用于演示双画面）
- **UI 节点树**：`UiAutomation.getWindowsOnAllDisplays()` 按 `displayId` 过滤窗口
- **OCR 兜底**：自绘页面（电商、地图类）无无障碍节点时使用

关键问题：
- 如何只读虚拟屏？→ 所有感知接口显式传 `displayId`，禁用主屏截图
- 捕获频率多少合适？→ 需平衡延迟与性能，通常按步抓取即可
- **坐标纪律**：所有坐标必须是虚拟屏 **display-local** 坐标，禁止用投屏预览像素或主屏状态栏高度修正

#### 2.2.2 模块 B：输入模拟层（Input Simulation）
**功能**：在**虚拟屏**上执行点击、滑动、输入等操作

技术方案：
- **带 displayId 的事件注入**：`adb shell input -d <displayId> tap/swipe/keyevent`
- **底层注入**（路径 C）：反射 `InputEvent#setDisplayId(displayId)` 后调用 `InputManager#injectInputEvent`
- **文本输入三级降级**：`ACTION_SET_TEXT` → 剪贴板粘贴 → keyevent（仅 ASCII）
- **IME 隔离**：`setDisplayImePolicy(displayId, DISPLAY_IME_POLICY_LOCAL)`，或 scrcpy `--display-ime-policy=local`

关键问题：
- 如何不抢用户焦点？→ 事件显式绑定虚拟屏 displayId，注入前加断言校验
- 中文输入怎么走？→ 优先 `ACTION_SET_TEXT`；ADB Keyboard 广播是否落到虚拟屏输入框需实测
- 输入冲突怎么办？→ 由 displayId 隔离从架构上消除，无需"避让"

#### 2.2.3 模块 C：冲突协调层（Conflict Coordination）
**功能**：在架构隔离的基础上，处理任务级资源竞争与演示期规避

技术方案：
- **架构隔离（主）**：显示、焦点、IME、输入事件四层隔离，主屏与虚拟屏互不干扰
- **剪贴板串行化**：多任务并行时剪贴板会互相覆盖，必要时加锁或限制并行数
- **演示脚本规避**：不在主屏打开正在被自动化的 App（否则会被拉出虚拟屏）
- **任务级协调**：跨 App 任务拆成独立可降级的 sub_mission

#### 2.2.4 模块 D：云端大脑（Cloud Brain）
**功能**：理解屏幕内容、规划任务、输出动作

技术方案：
- **多模态大模型 API**：接入 AutoGLM-Phone（`open.bigmodel.cn`）或 OpenAI 兼容接口
- **动作空间**：`Launch / Tap / Type / Swipe / Back / Home / Long Press / Double Tap / Wait / Take_over`
- **GUI Agent 框架**：参考 AutoGLM-Phone、Mobile-Agent-v2 等开源方案
- **`model_provider` 抽象**：可切云端 API / 本地 vLLM / 自研 dLLM
- **思维链与反思**：规划步骤、反思执行结果（长任务可加轻量 planning / reflection）

#### 2.2.5 模块 E：安全层（Safety Guard）
**功能**：敏感动作拦截与人工接管

技术方案：
- **`take_over_gate`**：付款 / 密码 / 验证码 / 删除 / 同意协议 → 暂停任务并通知用户
- **双重判定**：规则判定 + 模型判定，且闸门独立于模型输出
- **接管后续跑**：用户完成后 agent 可继续执行

### 2.3 分层与模块文件的对应

| 层 | 对应文件（snake_case） |
|---|---|
| L0 平台层 | `wellphone/device/virtual_display_runner.py`、`adb_client.py` |
| L1 感知层 | `wellphone/device/frame_source.py`、`ui_reader.py`、`ocr_fallback.py` |
| L2 执行层 | `wellphone/executor/action_executor.py`、`input_channel.py` |
| L3 安全层 | `wellphone/guard/take_over_gate.py` |
| L4 决策层 | `wellphone/agent/vlm_agent.py`、`action_space.py`、`model_provider.py` |
| L5 编排层 | `wellphone/agent/mission_plan.py`、`wellphone/main.py` |

---

## 三、技术选型对比

### 3.1 虚拟屏创建方案

| 方案 | 优点 | 缺点 | 推荐度 |
|-----|-----|-----|-------|
| scrcpy `--new-display`（路径 B） | 零 Android 开发、原语完整、免 root | 输入注入在部分机型不稳定（scrcpy #4598） | ⭐⭐⭐⭐⭐ |
| 自研 shell APK + `app_process`（路径 C） | 完全掌控 flags / IME / 注入，最稳 | 需 Java / Gradle 开发 | ⭐⭐⭐⭐ |
| `overlay_display_devices`（路径 A） | 一条命令、零开发 | 只能建一个屏，焦点 / IME 不可控 | ⭐⭐⭐ |

### 3.2 屏幕捕获方案

| 方案 | 优点 | 缺点 | 推荐度 |
|-----|-----|-----|-------|
| `screencap -d <displayId>` | 直接抓虚拟屏、无需授权 | 有一定延迟 | ⭐⭐⭐⭐⭐ |
| VirtualDisplay → ImageReader | 帧获取可控、可做流式 | 需在 shell 进程中实现 | ⭐⭐⭐⭐ |
| UiAutomation（按 displayId 过滤） | 可获取 UI 层次结构 | 自绘页面节点为空 | ⭐⭐⭐⭐ |
| OCR 兜底（Paddle Lite） | 覆盖无节点页面 | 精度与耗时需权衡 | ⭐⭐⭐ |
| MediaProjection | 帧率高 | 面向主屏、需授权、有通知提示 | ⭐ |

### 3.3 输入执行方案

| 方案 | 优点 | 缺点 | 推荐度 |
|-----|-----|-----|-------|
| `input -d <displayId>` | 简单、显式绑定虚拟屏 | 需 ADB / shell 通道 | ⭐⭐⭐⭐⭐ |
| 反射 `setDisplayId` + `injectInputEvent` | 最底层、完全可控 | 需 shell 身份与版本兼容处理 | ⭐⭐⭐⭐ |
| `ACTION_SET_TEXT`（Accessibility） | 文本输入最稳、不依赖 IME | 需无障碍权限 | ⭐⭐⭐⭐ |
| UiAutomator / AccessibilityService 直接操作 | 功能完整 | 作用于当前聚焦 display，无法解决主屏干扰 | ⭐ |

### 3.4 决策模型方案

| 方案 | 优点 | 缺点 | 推荐度 |
|-----|-----|-----|-------|
| AutoGLM-Phone 云端 API | 零部署、动作空间现成、含 take_over | 依赖网络与额度 | ⭐⭐⭐⭐⭐ |
| 本地 vLLM / SGLang 部署 9B | 数据不出本地、可控 | 需 24GB+ 显存 | ⭐⭐⭐⭐ |
| 通用多模态模型（GPT-4o / Qwen-VL 等） | 灵活 | 需自行设计动作空间与提示词 | ⭐⭐⭐ |

---

## 四、关键技术细节

### 4.1 如何做到"不打扰用户"

**核心思路**：agent 的全部操作运行在**独立虚拟屏**上，主屏（display 0）自始至终不参与，隔离由架构保证。

四重隔离：

| 资源 | 隔离手段 |
|---|---|
| 显示 | VirtualDisplay 独立窗口栈与 Surface，App 启动到虚拟屏 |
| 焦点 | `VIRTUAL_DISPLAY_FLAG_OWN_FOCUS`（hidden flag） |
| 输入法 | `setDisplayImePolicy(displayId, DISPLAY_IME_POLICY_LOCAL)` |
| 输入事件 | 注入前 `InputEvent#setDisplayId(displayId)`（或 `input -d <id>`） |

```
用户视角：主屏正常操作 App，画面/焦点/键盘不受影响
    ↓（架构隔离，非"检测避让"）
虚拟屏：agent 在 display_id ≠ 0 的独立空间内操作真实 App
    ↓
云端：按步接收虚拟屏画面，输出下一步动作
```

### 4.2 冲突处理策略

以**架构隔离**为主，任务级协调为辅：

```python
# 伪代码：注入前的校验与任务级协调
def execute_action(action):
    assert action.display_id != 0            # 绝不注入主屏
    assert action.display_id == virtual_display_id

    if action.type == "input_text":
        with clipboard_lock:                 # 多任务并行时剪贴板串行化
            return inject_text(action, action.display_id)

    return inject_event(action, action.display_id)
```

要点：
- 主屏与虚拟屏之间无需"避让"，冲突已在架构层消除
- 仍需处理的是 agent 侧的资源竞争（剪贴板、并行任务数）
- 演示脚本规避：不在主屏打开正在被自动化的 App

### 4.3 屏幕状态同步

```
┌─────────────────┐   虚拟屏帧 + UI 树   ┌─────────────┐
│  手机端虚拟屏    │ ──────────────────► │   云端      │
│  (display_id≠0) │                     │  (分析决策) │
└─────────────────┘                     └─────────────┘
        ▲                                      │
        │        下一步动作（带 displayId）     │
        └──────────────────────────────────────┘
```

### 4.4 坐标与文本输入

- 坐标系统一为虚拟屏 display-local；注入前必须绑定 displayId
- 文本输入三级降级：`ACTION_SET_TEXT` → 剪贴板 → keyevent（仅 ASCII）
- ADB Keyboard 广播能否落到虚拟屏输入框，需在 D1 实测确认

---

## 五、参考技术栈

### 5.1 必用技术
- **ADB (Android Debug Bridge)**：连接与控制 Android 设备
- **scrcpy**：虚拟屏创建、投屏与输入通道
- **Python**：主要开发语言
- **FastAPI**：云端 API 服务
- **多模态大模型 API**：屏幕理解与决策

### 5.2 Python 依赖（API Key 接入）

```python
# 云端服务
fastapi>=0.100.0
uvicorn>=0.23.0
python-multipart>=0.0.6  # 文件上传

# 图片处理
Pillow>=9.0.0
base64>=1.0.0          # 内置库，编码图片

# 其他
requests>=2.31.0
python-dotenv>=1.0.0   # 环境变量管理
```

### 5.3 可参考开源项目
- **Scrcpy**：虚拟屏创建（`--new-display`）、投屏与输入通道
- **ShadowAuto**：虚拟屏 + 输入注入 + ReAct 循环的完整工程实现（Apache-2.0，免 root）
- **AutoGLM-phone**：智谱 AI 的手机 Agent 方案（决策层与动作空间）
- **PhoneLLM/Awesome-LLM-Powered-Phone-GUI-Agents**：LLM 手机控制综述
- **AOSP VirtualDeviceManager 示例**：官方虚拟屏创建与启动 App 示例

### 5.4 可选技术
- **UiAutomatorViewer**：UI 层次结构分析
- **Appium**：移动端自动化测试框架
- **Celery/Redis**：任务队列（如果需要复杂调度）

---

## 六、可能的创新方向

1. **平行执行空间**：用户与 agent 各占一个显示空间，通过虚拟屏从系统层隔离，而非应用层避让
2. **预测式执行**：基于用户行为预测，提前准备 agent 操作
3. **安全边界设计**：`take_over_gate` 独立于模型输出，敏感动作强制交还用户
4. **多模态 + 强化学习**：让 agent 从历史操作中学习更优策略
5. **分布式 Agent**：手机只负责感知与执行，大脑在云端协同多个终端

---

## 七、阶段化落地（D1–D7）

| 阶段 | 做什么 | 走哪条路径 |
|---|---|---|
| D1 | 虚拟屏 + 主屏不被打扰的可行性验证 | 路径 B（scrcpy `--new-display`）+ 路径 A 对照 |
| D2 | `action_executor`：`input -d` 事件绑定 + 中文输入三级降级 | 路径 B，若失败切 C |
| D3 | `frame_source` + `vlm_agent`：单步 ReAct 接 AutoGLM API | 任意 |
| D4 | `take_over_gate` + 冲突实测（同 App 主屏 / 虚拟屏并存） | 任意 |
| D5 | `mission_plan` 跨 App 编排（微信回复 → 美团下单） | 任意 |
| D6 | 双画面录制 + README | 任意 |
| D7 | 答辩 + 失败清单 | — |
