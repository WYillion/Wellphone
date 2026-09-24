# Workplan Outline: 手机并行 Agent 系统

## 一、任务理解与核心挑战

### 1.1 任务目标
做一个 **后台并行手机 Agent**，能够在用户正常使用手机的同时，在后台完成指定的独立任务，全程不打扰用户（不抢焦点、键盘、屏幕）。

### 1.2 核心挑战分析

| 挑战类型 | 具体问题 | 技术关键点 |
|---------|---------|-----------|
| **屏幕焦点冲突** | 手机只有一个显示屏幕，用户和 agent 不能同时"看" | 屏幕镜像/共享方案 |
| **输入冲突** | 只有一个触摸屏和一个软键盘 | 虚拟输入 + 焦点隔离 |
| **感知与执行分离** | agent 需要感知屏幕状态但不能控制显示 | 屏幕截图/帧捕获独立于显示 |
| **任务规划** | agent 需要理解UI并做出决策 | 多模态大模型 + GUI Agent |
| **实时性** | 边用边执行，不能有明显延迟感知 | 高效的状态同步机制 |

---

## 二、技术架构设计

### 2.1 整体架构：云端大脑 + 手机端执行

```
┌─────────────────────────────────────────────────────────┐
│                    云端 (LLM Brain)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │ 任务规划器   │  │ 屏幕理解    │  │ 决策引擎    │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└────────────────────────┬────────────────────────────────┘
                         │ API / WebSocket
┌────────────────────────▼────────────────────────────────┐
│                   手机端 (执行层)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │ 屏幕捕获    │  │ 指令执行    │  │ 状态监控    │      │
│  │ (独立于显示)│  │ (模拟输入)  │  │ (后台运行)  │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心模块分解

#### 模块 A：屏幕感知层（Screen Perception）
**功能**：捕获当前屏幕内容，供云端分析

技术方案：
- **Scrcpy 方案**：通过 ADB 获取屏幕帧（`adb screencap`），完全独立于显示输出
- **MediaProjection API**：应用内截屏/录屏，不影响其他应用
- **SurfaceCapture**：更底层的屏幕捕获

关键问题：
- 如何在用户使用时同时捕获？→ Scrcpy 的 screenrecord 可以在后台运行
- 捕获频率多少合适？→ 需平衡延迟和性能

#### 模块 B：输入模拟层（Input Simulation）
**功能**：在后台执行点击、滑动、输入等操作

技术方案：
- **ADB Input**：`adb shell input tap x y`、`adb shell input text "..."`
- **UiAutomator**：Android 官方自动化框架，可后台执行
- **AccessibilityService**：无障碍服务，可模拟点击但需用户授权

关键问题：
- 如何不抢用户焦点？→ 物理按键/手势通过 shell 执行，应用层无感知
- 输入冲突怎么办？→ 检测当前输入状态，智能避让

#### 模块 C：状态同步层（State Synchronization）
**功能**：协调 agent 和用户的操作，避免冲突

技术方案：
- **焦点检测**：检测当前是否有输入框激活、是否有动画在进行
- **锁机制**：agent 执行操作前检查是否可以安全执行
- **队列机制**：用户操作优先，agent 操作排队

#### 模块 D：云端大脑（Cloud Brain）
**功能**：理解屏幕内容、规划任务、执行决策

技术方案：
- **多模态大模型 API**：通过 API Key 接入（推荐 GPT-4o / Claude 3.5 / GLM-4V / Qwen-VL）
- **GUI Agent 框架**：参考 PhoneLLM、AutoGLM-phone 等开源方案
- **思维链（Chain-of-Thought）**：规划步骤、反思执行结果
- **Python SDK**：各厂商提供的官方 SDK（如 `openai`、`anthropic`、`zhipuai` 等）

---

## 三、技术选型对比

### 3.1 屏幕捕获方案

| 方案 | 优点 | 缺点 | 推荐度 |
|-----|-----|-----|-------|
| Scrcpy/ADB screencap | 稳定、独立于显示、无需 root | 有一定延迟（~200ms） | ⭐⭐⭐⭐ |
| MediaProjection | 帧率高、可定制 | 需要用户授权、通知栏有提示 | ⭐⭐⭐ |
| UiAutomator | 可获取UI层次结构 | 需 Android 4.3+、部分操作需权限 | ⭐⭐⭐ |
| AccessibilityService | 可感知UI、可执行操作 | 需用户开启无障碍、功耗较高 | ⭐⭐⭐⭐ |

### 3.2 输入执行方案

| 方案 | 优点 | 缺点 | 推荐度 |
|-----|-----|-----|-------|
| ADB shell input | 简单稳定、可后台执行 | 需 USB 或无线 ADB 连接 | ⭐⭐⭐⭐ |
| UiAutomator | 功能完整、可后台 | 需授权、可能被安全软件拦截 | ⭐⭐⭐ |
| AccessibilityService | 可感知状态 | 需用户开启、侵入性强 | ⭐⭐⭐ |

### 3.3 大模型方案（API Key 接入）

| 方案 | API 来源 | 优点 | 缺点 | 推荐度 |
|-----|---------|-----|-----|-------|
| **GPT-4o / GPT-4o-mini** | OpenAI API | 能力强、生态成熟、视觉理解领先 | 费用较高、需翻墙 | ⭐⭐⭐⭐⭐ |
| **Claude 3.5 Sonnet** | Anthropic API | 推理能力强、上下文长、稳定性好 | 费用较高、需翻墙 | ⭐⭐⭐⭐⭐ |
| **GLM-4V** | 智谱 AI API | 国内可用、成本低、中文优化 | 能力略逊于GPT-4V | ⭐⭐⭐⭐ |
| **Qwen-VL** | 阿里云 API | 国内可用、免费额度多 | 生态相对新 | ⭐⭐⭐⭐ |
| **Doubao-Vision** | 字节跳动 API | 国内可用、价格低 | 生态新、文档相对少 | ⭐⭐⭐ |

**推荐方案**：优先使用国产 API（GLM-4V / Qwen-VL / Doubao），避免翻墙问题，成本可控。如果对效果要求更高，可选 GPT-4o 或 Claude 3.5。

---

## 四、实现路径建议

### 阶段一：基础能力验证（Day 1-2）
1. 搭建 ADB 连接环境（USB/无线）
2. 实现基础的屏幕捕获（`adb screencap`）
3. 实现基础的输入模拟（`adb shell input tap`）
4. 验证在用户使用时后台执行命令的可行性

### 阶段二：核心系统开发（Day 3-4）
1. 开发屏幕捕获服务（持续获取屏幕帧）
2. 开发输入冲突检测机制
3. 搭建云端 API 服务（接收屏幕帧、返回指令）
4. 集成大模型 API

### 阶段三：Agent 逻辑开发（Day 5-6）
1. 实现任务解析和规划
2. 实现执行-反馈-调整的循环
3. 实现状态同步和冲突处理
4. 端到端联调

### 阶段四：优化与演示（Day 7）
1. 性能优化（降低延迟）
2. 用户体验优化
3. 编写 README 和演示视频

---

## 五、关键技术细节

### 5.1 如何做到"不打扰用户"

**核心思路**：用户看到的是手机的正常显示，agent 的操作通过底层 ADB 执行，用户在应用层无感知。

```
用户视角：正常操作手机 App
    ↓ （无感知）
系统层：ADB 服务在后台运行
    ↓
Agent 操作通过 adb shell 执行，不经过当前前台应用
```

### 5.2 冲突处理策略

```python
# 伪代码：冲突检测逻辑
def can_agent_act():
    # 检测是否有输入框激活
    if is_soft_keyboard_active():
        return False

    # 检测是否有动画/过渡在进行
    if is_animation_playing():
        return False

    # 检测用户是否在快速滑动
    if is_user_scrolling_fast():
        return False

    return True
```

### 5.3 屏幕状态同步

```
┌─────────────┐     定期截图      ┌─────────────┐
│   手机端    │ ──────────────►  │   云端      │
│  (截图)     │                  │  (分析)     │
└─────────────┘                  └─────────────┘
      ▲                               │
      │         执行指令               │
      └───────────────────────────────┘
```

---

## 六、参考技术栈

### 6.1 必用技术
- **ADB (Android Debug Bridge)**：连接和控制 Android 设备
- **Python**：主要开发语言
- **FastAPI**：云端 API 服务
- **多模态大模型 API**：通过 API Key 接入，屏幕理解和决策

### 6.2 Python 依赖（API Key 接入）

```python
# 云端服务
fastapi>=0.100.0
uvicorn>=0.23.0
python-multipart>=0.0.6  # 文件上传

# 大模型 SDK（根据选择使用）
openai>=1.0.0          # GPT-4o / GPT-4o-mini
anthropic>=0.20.0      # Claude 3.5 Sonnet
zhipuai>=2.0.0         # GLM-4V
dashscope>=1.10.0      # Qwen-VL
volcengine>=0.0.1      # Doubao-Vision

# 图片处理
Pillow>=9.0.0
base64>=1.0.0          # 内置库，编码图片

# 其他
requests>=2.31.0
python-dotenv>=1.0.0   # 环境变量管理
```

### 6.3 可参考开源项目
- **Scrcpy**：屏幕镜像和控制
- **PhoneLLM/Awesome-LLM-Powered-Phone-GUI-Agents**：LLM 手机控制综述
- **AutoGLM-phone**：智谱 AI 的手机 Agent 方案

### 6.3 可选技术
- **UiAutomatorViewer**：UI 层次结构分析
- **Appium**：移动端自动化测试框架
- **Celery/Redis**：任务队列（如果需要复杂调度）

---

## 七、风险点和应对

| 风险 | 影响 | 应对策略 |
|-----|-----|---------|
| ADB 无线连接不稳定 | 指令执行失败 | USB 连接作为备份，或本地执行轻量化逻辑 |
| 屏幕捕获延迟高 | Agent 决策滞后 | 降低帧率，或在关键决策点主动请求截图 |
| 大模型 API 超时 | 任务卡住 | 设置超时重试，本地 fallback 逻辑 |
| 安全软件拦截 | 功能失效 | 引导用户授权，或使用系统签名 |
| 不同手机兼容性 | 适配工作量大 | 聚焦主流机型，抽象设备层 |

---

## 八、验收标准

### 8.1 必选功能
- [ ] 用户正常使用手机时，agent 能完成一个简单任务（如：打开指定 App、读取内容）
- [ ] 全程不抢焦点、键盘、屏幕
- [ ] 本地可运行（有 README 和演示）

### 8.2 加分功能
- [ ] 能处理更复杂的任务（如：多步骤操作、条件判断）
- [ ] 有较好的冲突处理机制
- [ ] 任务有实际用途（不只是 Demo）

---

## 九、可能的创新方向

1. **预测式执行**：基于用户行为预测，提前准备 agent 操作
2. **分层控制**：用户层和 agent 层完全隔离，通过系统级 API 通信
3. **多模态 + 强化学习**：让 agent 从历史操作中学习更优策略
4. **分布式 Agent**：手机只负责感知和执行，大脑在云端协同多个终端

---

## 十、快速开始清单

### 10.1 环境准备

```bash
# 1. Android 手机设置
- 开启开发者选项
- 启用 USB 调试
- （可选）开启无线调试用于 WiFi 连接

# 2. 安装 ADB 工具
# Windows: 下载 adb.zip，加入 PATH
# 或使用 winget: winget install --id=Google.PlatformTools

# 3. Python 环境
- Python 3.8+
- 建议使用虚拟环境: python -m venv venv && source venv/bin/activate

# 4. 获取大模型 API Key（根据选择的模型）
- OpenAI API Key: https://platform.openai.com/api-keys
- Anthropic API Key: https://console.anthropic.com/settings/keys
- 智谱 AI API Key: https://open.bigmodel.cn/usercenter/apikeys
- 阿里云百炼 API Key: https://dashscope.console.aliyun.com/apiKey
- 字节火山引擎 API Key: https://console.volcengine.com/ark
```

### 10.2 环境变量配置

```bash
# 创建 .env 文件
cat > .env << EOF
# 选择其中一组使用

# 方案一：OpenAI GPT-4o
OPENAI_API_KEY=sk-xxxxx
OPENAI_BASE_URL=https://api.openai.com/v1

# 方案二：Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-xxxxx

# 方案三：智谱 AI GLM-4V（国内推荐）
ZHIPUAI_API_KEY=xxxxx

# 方案四：阿里云 Qwen-VL（国内推荐）
DASHSCOPE_API_KEY=sk-xxxxx

# 方案五：字节 Doubao（国内推荐）
VOLC_ACCESS_KEY=xxxxx
VOLC_SECRET_KEY=xxxxx

# 手机连接方式
ADB_MODE=usb  # 或 wifi
ADB_HOST=192.168.1.100  # 如果用 WiFi 连接
ADB_PORT=5555
EOF
```

### 10.3 基础验证

```bash
# 1. 确认 ADB 连接
adb devices
# 输出应包含: "XXXXXXXX    device"

# 2. 测试截图功能
adb shell screencap /sdcard/screen.png
adb pull /sdcard/screen.png ./screen_test.png

# 3. 测试点击功能
adb shell input tap 500 500

# 4. 验证 Python 环境
python --version  # 应为 3.8+

# 5. 安装依赖
pip install -r requirements.txt

# 6. 测试大模型 API 连接
python -c "from openai import OpenAI; print('OpenAI SDK OK')"
```

