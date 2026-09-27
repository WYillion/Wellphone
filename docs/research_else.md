# Research Else：GitHub 同类项目调研（Wellphone 对照）

> 目的：在 GitHub 上系统检索与 Wellphone（手机并行后台 Agent：用户正常用机的同时，agent 在不打扰用户的前提下把任务办完）**相似的项目**，评估「这条路是否有人走过、走到哪一步」，并提取可借鉴的实测经验。
> 调研日期：2026-09-27。工具：GitHub Search API（repositories 搜索，按 stars 排序）+ 重点仓库 README 核实。
> 配套文档：`research.md`（平台原语与实现调研，其中 ShadowAuto / OpenCyvis 已深入调研，本文不重复展开）。

---

## 1. 调研方法与相似度分级

### 1.1 搜索词（GitHub Search API，`sort=stars`）

| 查询词 | 命中数 | 有效性 |
|---|---|---|
| `virtual display android automation` | 2 | 极高（两个结果全部命中第一梯队） |
| `虚拟屏 agent`（中文） | 2 | 极高（命中 SameWindow、Umbra） |
| `phone agent adb automation` | 23 | 中高（ghost-in-the-droid 等） |
| `android llm gui agent` | 15 | 中（框架/评测类） |
| `scrcpy automation` | 77 | 低-中（多为游戏 bot 与工具） |
| `app_process android shell` | 3 | 低（root 工具类） |

### 1.2 相似度分级标准

以本题三个核心特征为标尺：
- **A 同时性**：agent 干活时用户可继续使用主屏；
- **B 隔离**：显示 / 焦点 / 输入法 / 输入事件的系统级隔离（而非"避让"策略）；
- **C 决策**：LLM/VLM 自主决策 + 敏感动作 take_over。

| 梯队 | 定义 |
|---|---|
| 第一梯队 | A + B 兼备（虚拟屏 + 不打扰主屏），部分含 C |
| 第二梯队 | 有 C（LLM/VLM 手机自动化框架），无 B（直接操作主屏） |
| 第三梯队 | 思路/生态相似（共处理念、仿真评测、scrcpy 通道复用） |

---

## 2. 结论摘要

| 问题 | 结论 |
|---|---|
| 这条路是否有人走过 | **是**。第一梯队存在 4 个公开项目（ShadowAuto、Umbra、lichj06/android-virtual-display、OpenCyvis），且都很新（2026-07 至 2026-09） |
| 与本题最像的项目 | **Umbra-phone-agent**（App + Shizuku 虚拟屏 + Take_over）与 **lichj06/android-virtual-display**（纯 shell 脚手架）；两者 README 与本题要求高度同构，疑似同类作业/候选作品 |
| 我们的方案是否仍有差异化 | 有。公开项目均未同时做到「四重隔离 + 云端 VLM 编排 + take_over_gate + 双画面演示」的完整闭环；且可吸收它们踩过的坑 |
| 最重要的实测修正 | lichj06 在 vivo/Android 16 实测：**`screencap -d <虚拟屏id>` 无效**（报 "Display Id is not valid"）；`uiautomator dump` 只读焦点窗口、不能按 display 指定；多副屏受硬件编码器数量限制（建议 ≤2） |

---

## 3. 第一梯队：直接同类（A 同时性 + B 隔离）

### 3.1 Umbra-phone-agent（`lorz0619-cell/Umbra-phone-agent`）

- 基本信息：Kotlin，Apache-2.0，2026-08-31 创建，v2.1.0，1★。
- 定位（README 原话）："运行在真实 Android 手机上的任务型 Agent。它既可以直接在主屏上完成任务，也可以通过 **Shizuku** 在独立虚拟屏中执行任务，让用户不受影响得继续使用主屏。"
- 架构要点：
  - **主屏 / 虚拟屏双模式**：无 Shizuku 时降级为主屏执行；有 Shizuku 时虚拟屏执行；
  - **混合感知**：截图 + 无障碍树 + 前台包名；
  - **强类型动作空间**：`Launch / Tap / Type / Swipe / Back / Wait / Take_over`（与 AutoGLM-Phone 动作空间几乎一致）；
  - **后置验证**：视觉、语义树、包名与输入验证；子任务级反思、**重复动作检测**、候选路径重规划、终局裁决；
  - **接管体验**：虚拟屏统一接管确认、顶部接管通知、离线中文语音；
  - 环境变量 `VLM_API_KEY / VLM_BASE_URL / VLM_MODEL / MAX_ACTION_STEPS`（默认接 DeepSeek 视觉模型）；
  - **自带 52 条真机 benchmark**（8 条冒烟集）与三轮结果报告。
- 部署形态：Android 12+ App，需启用无障碍服务；虚拟屏模式需 Shizuku 授权。
- **对本项目的价值**：
  1. 证明「App 形态 + Shizuku（shell 权限）+ 虚拟屏」路线可行，是 **路径 C（自研 shell APK）之外的另一条获取 shell 能力的路径（记为路径 D）**；
  2. 其"后置验证 + 重复动作检测 + 重规划"是我们的 `verify` 环节可借鉴的成熟做法；
  3. 其任务描述、动作空间、take_over 与本题要求高度同构，**答辩时可引用为"同类工作"以论证方案合理性**，也提示本题可能已有其他候选者采用类似路线——我们的差异化要落在架构完整性与演示质量上。

### 3.2 lichj06/android-virtual-display（`lichj06/android-virtual-display`）

- 基本信息：Shell 脚本，MIT，2026-09-25 创建（比本次调研早两天），0★。
- 定位（README 原话）："一块不需要 root 的虚拟副屏。你看着主屏刷视频，AI 在副屏里点开 App、读界面、填内容——主屏一次都不会被抢走。"
- 技术路线：**Termux 内 adb → 无线调试回环（127.0.0.1）连本机 → scrcpy `--new-display`（经 app_process）建副屏 → `input -d` 注入 → `uiautomator dump` 读树**；附 `agent.sh` 文件驱动执行器（写命令文件 → 执行 → 读结果文件），任何程序/AI 可驱动。
- **真机实测数据（vivo iQOO 15 / Android 16 / 无 root / 未解锁 BL）**：
  - 副屏创建 ✓、App（到梦空间/系统设置）启动运行 ✓、控件树读取 ✓（43 KB）、`input -d` 点击滑动 ✓、**主屏全程不被抢** ✓；
  - CPU ≈ 0%（硬件编码 `c2.qti.avc.encoder`）、内存 130–330 MB、**可同时开 2 块副屏**（每块占一个硬件编码器，手机一般只有 2–4 个）。
- **实测坑清单（对 D1 最有价值）**：
  1. **`screencap -d <副屏id>` 对虚拟显示无效**（"Display Id is not valid"）→ 画面获取应走 **scrcpy 视频流抽帧**（或 shell 进程内 `ImageReader`，即 ShadowAuto 路线）；
  2. `uiautomator dump` 只读"有焦点的窗口"，**不能按 display 指定** → 多副屏需轮流让目标屏拿焦点；读不到控件树的 App（WebView/加固/游戏）改用视频流 + OCR；
  3. scrcpy `--new-display` 与 `--no-video` **互斥**；SDL 无窗口环境会报错（细节在 `docs/pitfalls.md`）；
  4. 无线调试重启后端口会变，需重新 connect；
  5. Termux 后台执行可能被厂商限制。
- 其"为什么不用其它方案"对比表（KernelSU 需解 BL；Shizuku 还需另写 App；无障碍必须占前台；scrcpy 镜像主屏会被看到）与我们 `docs/tech_choices.md` 的论证框架一致，可直接对照引用。
- **对本项目的价值**：最接近我们 D1 的"可行性验证脚手架"，且实测结论直接**修正 `research.md` 中 `screencap -d` 可用的假设**（见第 7 节行动项）。

### 3.3 已在 `research.md` 深入调研的第一梯队项目（此处仅列索引）

| 项目 | 一句话 | 与本题的关系 |
|---|---|---|
| **ShadowAuto**（`android-notes/ShadowAuto`，56★，Java，Apache-2.0） | shell 进程建虚拟屏 + MediaCodec 投屏 + UiAutomation/OCR 感知 + setDisplayId 注入 + ReAct tool-call 循环 | 本题的工程化完整参照（路径 C），README 描述与本题几乎一致 |
| **OpenCyvis**（`opencyvis/opencyvis-phone`） | AOSP 集成 + privileged 权限，Task Reparenting 迁移已有窗口，Safety Guards / Takeover | 系统级方案的天花板与前瞻风险参照 |

---

## 4. 第二梯队：LLM 手机自动化框架（有 C，无 B——直接操作主屏）

这些项目验证了"VLM + ADB 决策执行"范式的成熟度，但**都没有解决隔离问题**（动作全部落在 display 0），因此不满足本题"不打扰"约束；其价值在工程细节借鉴。

| 项目 | Stars / 语言 | 核心思路 | 可借鉴点 |
|---|---|---|---|
| **ghost-in-the-droid/android-agent** | 368★ / Python / MIT | "驱动真实手机的 AI agent 框架"：Android over ADB、iPhone over WebDriverAgent、**62 个 MCP tools**、Python skills、Vue 面板、本地/云端 LLM 可换 | MCP 工具化封装动作空间；skills 组织；多设备（含 iOS WDA）扩展 |
| **DeepAgents-AutoGLM** | 121★ / Python / Apache-2.0 | 把 Open-AutoGLM 的 Android/iOS GUI 自动化接入 DeepAgents-CLI（**LangChain Middleware**），LLM 编排 + 视觉 GUI 控制 | 与我们「LangGraph 编排 + AutoGLM 决策」同构，可参考其集成方式 |
| **HusxGLM** | 36★ / Kotlin | 火山引擎 VLM 驱动的 Android GUI Agent（自然语言控制） | App 形态 VLM 决策参考 |
| **ZTRRTUO/Jev-PhoneControl** | 少量★ | 三 agent 协作：vision + 文本 supervisor + TypeSafe JEV，ADB 执行 + 本地 web 控制台 | 多 agent 分工（对应综述 Multi-Agent 范式）的工程样例 |
| **ArtemisAI/pi-droid** | 11★ / TypeScript | pi-agent 的 Android 控制插件：36 个工具，ADB 感知/触摸/自动化 | 工具粒度设计 |
| **HangHang04/android-harness** | 4★ / Python | Agent-friendly 的 ADB harness（检视与控制真机） | harness 抽象层设计 |
| **hjjtt/AndroidAgent** | 1★ / Kotlin | Kotlin + Compose 的 GUI Agent，双协议 LLM 流式（Kimi/DeepSeek/GLM） | 模型多供应商接入 |
| **multilogin/multilogin-cloud-phone-agent** | 9★ / Python | 云手机 ADB 自动化示例（start → boot → ADB → actions → always-stop） | 云手机可作为无真机演示的备选环境 |
| **SanjayKumaran2805/JARVIS** | 6★ / Python | Gemini Live + ADB 手机控制 + 语音 + 多 agent | 语音交互形态 |
| **GeorgeKnerr/Android_Phone_Control_Agent** | 3★ / Python | Qwen3-VL 视觉理解 + ADB 控制 | Qwen-VL 决策参考 |

---

## 5. 第三梯队：思路相似与生态

| 项目 | Stars | 与本题的关系 |
|---|---|---|
| **Yinglianchun/SameWindow** | 42★ / JS | "人和 AI 共用浏览器，即时一起逛"：**虚拟屏幕 + 本地反向隧道双入口**。虽是浏览器而非手机，但核心理念与本题同源——**人与 AI 同时共处一个界面、各自入口互不干扰**，是"共处而非接管"的另一个实现样本 |
| **Purewhiter/mobilegym** | 801★ / Python / EMNLP 2026 | 浏览器内安卓模拟器 + 可验证评测 + 在线 RL 的 GUI Agent 研究平台。其 "parallel" 指并行仿真（非用户并行），但可作为我们**任务自测与回归评测**的环境 |
| **AlLongley/py-scrcpy**（archived） | 52★ / Python | 纯 Python 的 scrcpy 客户端实现——若想不依赖 scrcpy 二进制、直接在 Python 内建虚拟屏与收流，可参考其协议实现 |
| **italks/scrcpy-claw** | 9★ | ADB + scrcpy 的 AI 自动化"技能包"（触摸/键盘/镜像/录制回放），OpenClaw 生态 |
| 游戏自动化 bot（wordscapes-bot、eatventure-bot、whiteout-survival-bot 等） | — | scrcpy + OpenCV/OCR 的固定脚本自动化，说明 scrcpy 作为"主屏通道"已被广泛复用——但它们都**没有虚拟屏隔离与 LLM 决策** |
| **solo0430/Android-Anti-Detection-Automation** | 5★ | scrcpy + xdotool 的主屏自动化（反检测打卡），验证了 scrcpy 输入通道的稳定性，但同样无隔离 |

---

## 6. 对比矩阵：Wellphone 与代表项目

| 维度 | **Wellphone（我们的方案）** | ShadowAuto | Umbra | lichj06 | OpenCyvis | ghost-in-the-droid/android-agent |
|---|---|---|---|---|---|---|
| 部署形态 | PC Python + scrcpy/shell | shell APK（app_process） | Android App + Shizuku | Termux shell 脚本 | AOSP 集成 | PC 框架（FastAPI） |
| 建屏路径 | B（scrcpy `--new-display`），备 C | C（自研 shell 进程） | D（Shizuku） | B（经 Termux adb） | 系统签名 | 无（主屏直控） |
| 显示/焦点/IME 隔离 | 四重隔离（架构保证） | 虚拟屏 OWN_FOCUS | 虚拟屏 | 虚拟屏（IME 策略未提及） | TRUSTED + 迁移 | ✗ |
| 感知 | scrcpy 帧 + 按 display 过滤 UI 树 + OCR | UiAutomation 按 display + OCR | 截图 + 无障碍树 + 前台包名 | uiautomator dump（焦点窗口）+ 视频流抽帧 | 多模块 | 截图/uiautomator（主屏） |
| 决策 | AutoGLM-Phone API + LangGraph 编排（`model_provider` 可换） | 模型 tool call（约 20 工具） | VLM 强类型动作 + 反思/重规划 | 无内置（命令接口，AI 外接） | 有 | 62 MCP tools，LLM 可换 |
| take_over | `take_over_gate`（规则 + 模型双判定） | 未强调 | ✓（接管确认 + 通知 + 语音） | ✗ | ✓（Takeover） | ✗ |
| 用户同时使用主屏 | ✓（核心目标） | ✓ | ✓ | ✓ | ✓ | ✗（必抢屏） |
| 评测 | 计划自建 phase_1/phase_2 | — | 52 条真机 benchmark | 真机实测清单 | — | — |
| 成熟度 | 进行中 | ★★★★（原型完整） | ★★★（可安装 APK + benchmark） | ★★（脚手架，但实测数据翔实） | ★★★（系统级） | ★★★★（生态化） |

---

## 7. 对 Wellphone 的启示与行动项

### 7.1 必须吸收的实测修正（影响 D1）

1. **感知主路径调整**：`screencap -d <虚拟屏id>` 在 vivo/Android 16 实测无效。D1 实测清单（`research.md` 第 9 节第 6 条）优先级提高，且**主感知路径应为 scrcpy 视频流抽帧**（或路径 C 的 `ImageReader`），`screencap -d` 仅作为可选项实测。
2. **UI 树读取区分两条路**：纯 shell 的 `uiautomator dump` 只读焦点窗口、不能按 display 指定——多副屏或后台读取不可靠；可靠路线是**shell 进程内的 `UiAutomation.getWindowsOnAllDisplays()`（ShadowAuto / 路径 C）**，或直接走 scrcpy 流 + OCR。
3. **副屏数量 ≤ 2**：每块虚拟屏占一个硬件编码器（手机一般 2–4 个）。我们只开 1 块，无冲突，但演示机编码器占用情况需在 D1 记录。
4. **scrcpy 参数交互**：`--new-display` 与 `--no-video` 互斥；若要在无头环境跑，需保留视频输出（可录至 `/dev/null`，磁盘零开销、CPU ≈ 0%）。

### 7.2 可借鉴的设计

- **路径 D（Shizuku）**：作为路径 B/C 之外的备选——App 形态 + shell 权限 + 虚拟屏。若 D1 发现目标机型 scrcpy 输入注入不稳定，Shizuku 是免编译 ROM 的中间态（Umbra 已验证）。
- **Umbra 的后置验证体系**：视觉/语义树/包名/输入四路验证 + 重复动作检测 + 候选路径重规划，可充实我们的 `verify` 环节设计。
- **Umbra 的 52 条真机 benchmark 形态**：为我们的任务集设计提供模板（冒烟集 + 全量 + 多轮结果）。
- **ghost-in-the-droid 的 MCP 工具化**：把动作空间封装为 MCP tools，可提升 README 与答辩中"工程化程度"的印象分。
- **SameWindow 的"共处"叙事**：双入口、人与 AI 即时共处——可作为我们演示视频的叙事框架（左：用户主屏；右：agent 虚拟屏，双画面同框）。

### 7.3 答辩中的差异化定位

- GitHub 上"虚拟屏 + agent + 不打扰主屏"**已非无人区**（4 个公开项目，均为 2026 年新项目），但公开项目**没有一个同时做到**：四重隔离 + 云端 VLM 编排 + 独立于模型输出的 take_over 闸门 + 跨 App 双画面演示。
- 因此答辩叙事建议：不宣称"首创虚拟屏方案"，而是强调**"同时性 + 架构级隔离 + 安全边界的完整闭环"**，并把第一梯队项目作为"同类工作"引用，展示我们做过充分调研与对比——这本身就是判断力的加分项。
- 需要留意：Umbra 的任务描述与本题高度同构（疑似同类作业/候选作品），若答辩中被问及"与 XX 的区别"，直接以第 6 节矩阵作答。

---

## 8. 搜索日志

| 时间 | 动作 | 结果 |
|---|---|---|
| 2026-09-27 | GitHub API：`virtual display android automation` | 2 结果：ShadowAuto、lichj06/android-virtual-display |
| 2026-09-27 | GitHub API：`虚拟屏 agent` | 2 结果：SameWindow、Umbra-phone-agent |
| 2026-09-27 | GitHub API：`phone agent adb automation` | 23 结果：ghost-in-the-droid/android-agent（368★）、pi-droid、multilogin、JARVIS 等 |
| 2026-09-27 | GitHub API：`android llm gui agent` | 15 结果：mobilegym（801★）、DeepAgents-AutoGLM（121★）、HusxGLM 等 |
| 2026-09-27 | GitHub API：`scrcpy automation` | 77 结果：py-scrcpy、scrcpy-claw、游戏 bot 等 |
| 2026-09-27 | GitHub API：`app_process android shell` | 3 结果（root 工具类，低相关） |
| 2026-09-27 | README 核实：Umbra-phone-agent、lichj06/android-virtual-display（raw.githubusercontent） | 已核实架构、实测数据与坑清单 |
