# Suggestion：本题目技术方向建议与实现路径推荐

> 本文基于题目说明及其列出的参考资料，梳理这道题自然指向的技术主线，并给出**推荐的技术方向、实现路径与风险提示**，供参考与讨论。
> 文中所有外部信息均来自公开可访问的页面与文档；涉及本方案的判断部分，均标注为"建议"或"推荐"，不代表唯一解。

---

## 0. 结论摘要

这道题的核心不在于"写一个点击脚本"，而在于**资源隔离**：手机的系统假设是"一个人、一块屏、一个焦点、一个 IME"，要让 agent 与用户**同时**使用同一台设备而互不干扰，需要在显示、焦点、输入法、输入事件四个层面分别建立隔离。

题目给出的参考资料指向同一条技术主线，可以概括为一句话：

> **独立虚拟屏（平行执行空间）+ 视觉决策模型 + 绑定 displayId 的输入注入 + 敏感动作交还用户。**

其中 scrcpy 提供了建屏与注入的原语，AutoGLM-Phone 提供了可直接复用的决策层，WhalePhone 的公开产品说明则印证了"后台私有虚拟屏 + 关键步骤交还用户"这一形态的可行性。下文按"资料调研 → 推荐方向 → 实现路径 → 风险提示"展开。

---

## 1. 参考资料调研摘要

### 1.1 资料总表

| # | 资料 | 类型 | 可从中获取的技术信息 |
|---|---|---|---|
| 1 | `whaletech.ai` | 公司主页 | 公司技术方向（dLLM）与产品矩阵 |
| 2 | `phone.whaletech.site` | 产品页 | WhalePhone 公开的实现思路与安全边界 |
| 3 | `github.com/Genymobile/scrcpy` | 开源工具 | 虚拟显示、IME 策略、指定 display 投屏等原语 |
| 4 | `docs.bigmodel.cn/.../autoglm-phone` | 模型文档 | 多模态 VLM 决策 + ADB 执行的动作空间与部署方式 |
| 5 | `github.com/PhoneLLM/Awesome-LLM-Powered-Phone-GUI-Agents` | 学术综述 | 手机 GUI Agent 的三大框架范式全景 |
| 6 | `youtube.com/watch?v=MmXhbuoDQgg` | 演示视频 | AutoGLM-Phone-9B 端到端真机实操效果 |
| 7 | `assignment.whaletech.site` | 提交入口 | 作业提交表单（无技术信息） |
| 8 | `calendar.google.com/...` | 面试预约 | 面试时间预约（无技术信息） |

### 1.2 逐条调研

#### (1) `whaletech.ai` —— 公司技术方向

- 公司定位：2025 年 5 月成立的基础大模型公司，方向为 **dLLM（Diffusion Language Model，扩散语言模型）**。
- 主页标语：`Extreme speed. Ultra-low cost. Self-correcting. Parallel generation.`；旗舰模型 `W1-4B-dLLM`，强调**潜在推理（Latent Reasoning）**、**变长生成（Variable Length）**、**并行生成与自我修正（Parallel Generation · Correction）**。
- 一个具体主张：同样 100 个代码 token，传统 LLM 需要 100 步，dLLM 只需 15 步；单张消费级 4090 可达到 500+ effective TPS。
- 产品矩阵中，**Whale Phone 被定位为 "AI-Native Mobile OS"**。

**对本题的参考价值**：
- 从公司技术取向看，推理效率与架构设计是被重视的方向。因此方案中若体现**决策模型可替换**（provider 抽象）与**对低步数、高吞吐友好**（压缩每步上下文、减少无意义往返），会与整体技术风格更契合。
- 一个每步全量重传截图、缺乏上下文管理的朴素实现，在工程完成度上会显得偏弱。

#### (2) `phone.whaletech.site` —— WhalePhone 的公开实现说明

WhalePhone 是已发布的产品，其公开说明中对实现方式的描述与本题方向高度一致，可作为**方向性参考**：

| 产品页公开描述 | 对应的技术含义 |
|---|---|
| "任务在**后台的私有虚拟屏幕**里运行，你照常用手机" | 独立 VirtualDisplay，主屏不参与任务执行 |
| "在**一块你看不到的独立屏幕上**读取当前画面" | 感知源为虚拟屏帧缓冲，而非主屏 |
| "**每次只想一步**，只根据刚看到的画面决定下一步" | 单步（step-wise）VLM 决策循环 |
| "在你手机里已有的 App 上点击、输入、滑动，和你自己操作一样" | 基于真实 App 的 UI 自动化，不依赖 App 开放 API |
| "到了付款这一步，**停下来等你**" | Human-in-the-loop / take-over 机制 |
| "密码、支付、验证码……从不代你输入" | 安全边界以产品承诺形式显式实现 |
| 支持 OPPO（ColorOS）、小米（HyperOS）、Google Pixel；Android 9+ | 机型与版本适配是真实存在的约束 |
| 演示任务：美团点咖啡（到付款停下）、微信提醒同事、高德导航 | 任务形态：跨 App、有实际价值、包含敏感节点 |

**对本题的参考价值**：
- WhalePhone 以 App 形态交付，通过**无障碍权限**完成操作。而在本题中，题目 FAQ 明确"连着电脑跑并不违背思路、不算作弊"，这意味着在 App 形态之外，还可以采用 **ADB / shell 权限**，从而获得 App 形态不易获得的虚拟显示与指定 display 注入能力。
- 因此，**用 shell 权限换取更强的隔离能力**，是本题相较一般 App 方案更具可行性的路径，也是值得在方案中重点论证的部分。

#### (3) `scrcpy` —— 与本题需求高度匹配的原语工具

scrcpy 恰好覆盖了"平行执行空间"所需的多个原语，且无需 root、无需安装 App：

| scrcpy 能力 | 对应本题需求 |
|---|---|
| `--new-display=WxH[/dpi]` | 新建独立虚拟显示器（退出即销毁） |
| `--start-app=<pkg>` | 将目标 App 启动到虚拟屏，而非主屏 |
| `--display-id=<id>` | 投出已存在的虚拟屏（便于演示双画面） |
| `--display-ime-policy=local` | 虚拟屏 IME 不抢占主屏键盘 |
| `--keyboard=uhid --mouse=uhid` | 物理 HID 注入，绕过 IME |
| `--no-vd-destroy-content` | 退出时不销毁虚拟屏内的 App |
| `--keep-active` / `--stay-awake` | 避免息屏打断长任务 |

**对本题的参考价值**：scrcpy 以 `app_process` + **shell 身份**运行，同时解决了"创建虚拟屏"与"向指定 display 注入"两件事，是**零 Android 开发**即可验证可行性的入口，建议作为第一阶段的首选。

#### (4) `AutoGLM-Phone` —— 决策层可复用，执行层需改造

- 架构：**多模态 VLM 理解屏幕 → 输出动作 → ADB 执行 → 循环**。
- 动作空间：`Launch / Tap / Type / Swipe / Back / Home / Long Press / Double Tap / Wait / Take_over`。
- **内置 `Take_over`（请求人工接管）**，与 WhalePhone"付款时停下来交给你"的安全边界思路一致。
- 官方推荐场景与本题目高度接近：外卖下单、再来一单、订酒店、跨 App 差旅（飞书发消息 → 携程订票）。
- 部署依赖：Python 3.10 + ADB + **ADBKeyboard.apk**；支持云端 API（`open.bigmodel.cn`）或本地 vLLM / SGLang 部署 9B。
- **需要注意的差异**：AutoGLM-Phone 默认将动作注入 **display 0（主屏）**，与本题"不打扰用户"的要求存在冲突。

**对本题的参考价值**：决策层可以直接复用，节省大量提示词工程；而**执行层需要整体重定向到虚拟屏**。建议将工程重心放在这一层的隔离改造上，这也是本题的主要区分点。

#### (5) `Awesome-LLM-Powered-Phone-GUI-Agents` —— 框架范式全景

TMLR 2025 综述（arXiv 2504.19838）将手机 GUI Agent 的框架归纳为三大范式：

| 范式 | 代表工作 | 特点 | 对本项目的适配 |
|---|---|---|---|
| **Single-Agent** | AppAgent、AutoDroid、MobileVLM | 单模型 Observe→Act 循环 | 实现最简，适合先跑通 |
| **Multi-Agent** | Mobile-Agent-v2（planning / decision / reflection 三 agent + memory） | 分工与纠错，长任务提升显著 | 复杂跨 App 任务的上限更高 |
| **Plan-Then-Act** | Ponder & Press、ClickAgent、UGround | 先规划再执行，适合长程任务 | 依赖稳定的视觉 grounding |

此外还收录了训练侧路线（SFT / RL，如 UI-TARS、GUI-R1）与数据集、评测榜单（AndroidWorld、SPA-Bench 等）。

**对本题的参考价值**：建议采用组合式设计——**以 Single-Agent 单步循环保证可运行性，再叠加轻量 planning / reflection 以支撑复杂任务**，并在答辩中说明范式取舍理由。

#### (6) YouTube 演示视频

- 实际内容：`AutoGLM Phone 9B: An AI Phone Agent for Android: Full Hands-on Demo`（作者 Fahd Mirza）。
- 价值：可直观看到 **AutoGLM-Phone-9B 单模型端到端**在真机上的实际表现与常见卡点，用于校准对模型能力边界的预期。

#### (7)(8) 提交入口与面试预约

- `assignment.whaletech.site`：姓名 + 手机号 + 压缩包 / 网页链接的私密提交表单，无技术信息。
- `calendar.google.com/...`：面试时间预约，无技术信息。

---

## 2. 推荐技术方向

### 2.1 技术主线：四层资源隔离

手机系统假设"一个人、一块屏、一个焦点、一个 IME"。要让 agent 与用户同时使用且互不打扰，建议在四层分别建立隔离：

| 资源 | 冲突表现 | 推荐隔离手段 |
|---|---|---|
| 显示 display | agent 启动 App 覆盖用户画面 | VirtualDisplay（独立窗口栈 + 独立 Surface） |
| 焦点 focus | agent 点击导致用户正在输入的框失焦 | 虚拟屏独立焦点（hidden flag `OWN_FOCUS`） |
| 输入法 IME | agent 打字弹出软键盘遮挡用户 | `setDisplayImePolicy(displayId, LOCAL)` |
| 输入事件 input | 注入的 tap / key 默认落到 display 0 | `InputEvent#setDisplayId(displayId)` 后再注入 |
| 感知 perception | 截图 / UI dump 默认读取主屏 | `screencap -d <id>` / 按 displayId 过滤窗口 |

**推荐原则**：将"不打扰"作为**架构层面的保证**，而非"检测到用户在输入就避让"的概率性策略。前者在演示中稳定可复现，后者存在较大不确定性。

### 2.2 分层推荐技术栈

| 层 | 推荐选型 | 依据 |
|---|---|---|
| 平行空间 | scrcpy `--new-display` + `--display-ime-policy=local`（shell 权限） | 原语完整、免 root、零 Android 开发 |
| 感知 | 虚拟屏抓帧（`screencap -d <id>` / scrcpy 流），不读主屏 | 保证感知源与执行目标同屏 |
| 决策 | AutoGLM-Phone API，抽象 `model_provider` 接口 | 决策层可复用，且便于替换为本地 vLLM / 自研 dLLM |
| 执行 | 带 `display_id` 的事件注入 + ADB Keyboard 文本注入 | 所有动作显式绑定虚拟屏 |
| 安全 | `take_over_gate`：拦截付款 / 密码 / 验证码 | 与产品级的 take-over 安全边界保持一致 |
| 编排 | 状态机：`perceive → decide → guard → execute → verify` | 流程清晰、便于插桩与调试 |

### 2.3 题目说明中值得关注的取向

以下三点来自题目原文，建议在方案与答辩中主动回应：

1. **鼓励独立思考**：题目明确"找到一条我们没想到的路并且跑通，是这道题最高的结果"。
2. **重视判断力与过程**：答辩说明"记录下你尝试了什么、卡在哪里，这比硬凑一个半成品更有价值"。
3. **鼓励与 AI 高效协作**：需要能够说明"如何引导 AI、如何审查 AI 生成的代码"。

---

## 3. 实现路径建议（分层落地）

### 3.1 平行空间层：先建立隔离

**原则**：主屏（display 0）自始至终不参与 agent 的任何操作。

- 首选路径（零 Android 开发，快速验证）：
  ```bash
  scrcpy --new-display=1080x1920 --start-app=com.tencent.mm \
         --display-ime-policy=local --keep-active
  ```
- 备选路径（可控性更强）：shell APK + `app_process`，以 shell 身份运行（Android 10+ 免 root），可自行控制虚拟屏 flags。
- 对照实验：`adb shell settings put global overlay_display_devices "1920x1080/200"`（最轻量，但只能创建一个屏）。

**阶段性验收标准**：用户在主屏正常打字、滑动、切换 App 的同时，目标 App 稳定运行于虚拟屏，**主屏画面、焦点与键盘均不受影响**。

### 3.2 感知层：只读虚拟屏，坐标保持 display-local

- 抓帧：`screencap -d <displayId>` 或 scrcpy 视频流；不建议用主屏截图代替。
- UI 树：`UiAutomation` 按 `displayId` 过滤窗口；自绘页面（电商、地图类）建议以 OCR 兜底。
- **坐标系一致性（常见问题点）**：
  - 所有点击坐标应为**虚拟屏 display-local 坐标**；
  - 不要用投屏预览窗口的像素坐标作为点击坐标；
  - 不要用主屏状态栏高度修正虚拟屏坐标。

### 3.3 决策层：复用 AutoGLM，抽象 provider

- 单步循环：`截图 → VLM 理解 → 输出一个动作 → 执行 → 再截图`。
- 动作空间对齐 AutoGLM：`Launch / Tap / Type / Swipe / Back / Home / Long Press / Double Tap / Wait / Take_over`。
- 抽象 `model_provider` 接口：默认接入 AutoGLM-Phone 云端 API，同时预留本地 vLLM 或自研 dLLM 的替换位。
- 上下文管理：仅传当前步 + 必要历史摘要，避免每步全量重传，兼顾成本与低步数、高吞吐需求。

### 3.4 执行层：所有动作绑定 displayId

```bash
adb shell input -d <displayId> tap <x> <y>
adb shell input -d <displayId> swipe <x1> <y1> <x2> <y2> <ms>
adb shell input -d <displayId> keyevent 4        # BACK
```

- 中文输入（`input text` 仅支持 ASCII）建议三级降级：`ACTION_SET_TEXT` → 剪贴板粘贴 → keyevent（仅 ASCII）。
- ADB Keyboard 广播是否能正确落到虚拟屏的输入框，建议先实测再依赖。
- 执行器建议加入通用兜底（不针对特定 App 写死）：模型聚焦输入框但未输入时补一次 `input_text`；UI 节点为空时先尝试 OCR / 等待 / 滚动，而非直接返回。

### 3.5 安全层：take_over_gate 建议作为必备组件

WhalePhone 将"密码、支付、验证码永不代输"作为公开承诺，AutoGLM 也提供 `Take_over` 动作。建议：

- 在动作执行前加入**规则 + 模型双重判定**的闸门；
- 命中付款 / 密码 / 验证码 / 删除 / 同意协议时暂停任务，提示用户接管，接管完成后可继续执行；
- 闸门判定**独立于模型输出**，不完全依赖 VLM 自行判断某一步是否敏感。

### 3.6 编排与任务设计：分段可成立

- 状态机：`perceive → decide → guard → execute → verify`。
- 任务选型建议贴近产品级场景（跨 App、有实际价值、包含敏感节点）：
  - **phase_1（低风险）**：微信回复一条消息，成功即可作为阶段性成果；
  - **phase_2（高价值，触发 take_over）**：美团下单至付款前停下，无论成败都有可讨论的内容。
- **风险控制建议**：两个 App 的失败不相互耦合，phase_1 可独立降级，phase_2 可独立演示。这与题目"记录卡点比硬凑半成品更有价值"的说明一致。

---

## 4. 与交付要求、加分项的对应关系

| 题目要求 | 建议的对应设计 |
|---|---|
| 有人正用手机时把任务办完 | 虚拟屏独立执行，主屏零参与 |
| 不打扰用户屏幕 | display / focus / IME / input 四重隔离 |
| 方法自选 | 采用 shell 权限获取虚拟显示能力，并在文档中论证取舍 |
| 可演示部署 | 本地一台 Android 手机 + scrcpy + Python 编排 |
| GitHub 仓库（README 一页内） | 架构图 + 部署步骤 + 环境变量 + 技术选型说明 |
| 1–2 分钟演示（同框双画面） | 虚拟屏投屏至第二窗口，同时拍摄用户主屏与 agent 虚拟屏 |
| 加分：任务有意思 | 跨 App 真实任务（微信 → 美团） |
| 加分：冲突处理干净 | 以架构隔离替代"避让"式策略 |
| 加分：支撑复杂任务 | 状态机 + 多步任务 + take_over 后续跑 |

---

## 5. 技术风险与规避建议

1. **不建议以"检测用户输入后避让"作为隔离手段**：该策略具有概率性，演示中不易稳定复现。
2. **避免向主屏注入事件**：`adb shell input tap` 不带 `-d` 时会落到 display 0，导致抢焦点与跳屏。ADB 本身只是通道，不提供隔离能力。
3. **UiAutomator / AccessibilityService 的作用范围有限**：二者通常作用于当前聚焦的 display，且第三方 App 一般无法创建虚拟屏，建议仅作为辅助手段。
4. **避免在主屏打开正在被自动化的 App**：可能导致该 App 从虚拟屏被拉走，任务中断。
5. **敏感页面投屏可能黑屏**（支付密码类）：演示脚本建议提前规避，避免镜头对准此类页面。
6. **多任务并行时剪贴板可能互相覆盖**：必要时对剪贴板加锁。
7. **机型与版本差异是真实约束**：hidden API、shell 权限、scrcpy 输入注入在部分机型上表现不稳定，建议在第一阶段逐条实测，并将结论沉淀为 `feasibility.md`。

---

## 6. 一页速查

- **技术主线**：资源隔离（display / focus / IME / input 四重），而非点击脚本。
- **方向参考**：后台私有虚拟屏 + 单步 VLM 决策 + 真实 App 操作 + 敏感动作交还用户。
- **技术底座**：scrcpy `--new-display`（平行空间）+ AutoGLM-Phone（决策）+ `input -d <id>`（执行）+ `take_over_gate`（安全）。
- **建议务必做到**：主屏零参与；坐标统一为 display-local；敏感动作由独立于模型的判定拦截。
- **期望达成的效果**：一条可稳定演示、可解释、可复现的路径，并能清楚说明"为什么选这条、为什么不选那条"。
