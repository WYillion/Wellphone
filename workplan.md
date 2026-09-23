# Wellphone Workplan

> 端到端手机 Agent 实战题：在手机主人正用着这台手机时，agent 同时用这台手机把任务办完，且全程不打扰用户。
> 状态：方案已定稿，待执行。后续工作按本文档推进。

---

## 一、题目本质与验收标准

### 本质：资源隔离（resource isolation）

手机从设计上假设「一个人、一块屏、一个焦点、一个 IME」。本任务要求 agent 与用户**共用同一台物理设备**，但不共享执行上下文。

核心工作：把 agent 的执行上下文从「用户正在用的那块屏」搬到一个**用户看不见、也不共享焦点/IME 的平行空间**，同时保证任务仍然作用在**真实的 App、真实的账号、真实的数据**上。

> 题目明确「选哪条路本身就是题目」。绝大多数人会选「无障碍服务 + 主屏模拟点击」，那条路必然抢焦点，是陷阱。

### 验收标准

| 编号 | 标准 | 判定方式 |
|---|---|---|
| 1 | 用户在用手机时，任务真的办完 | 演示时用户正常操作，agent 期间完成任务 |
| 2 | 用户屏幕全程是自己的 | 不抢焦点、不抢键盘、不跳画面、不卡顿 |
| 3 | 可演示部署 | 至少一台 Android 真机跑起来 |
| 4 | GitHub 仓库 | commit message 清晰，README 一页以内（架构图 + 部署步骤 + 环境变量） |

### 加分项

- 任务本身有真实价值，不是玩具。
- 把「抢资源」的冲突处理干净（一个键盘、一个焦点，两边互不干扰）。
- 撑得起复杂任务，不只是点一两下。

---

## 二、外部调研结论

### 1. whaletech.ai（公司本体）

dLLM（扩散语言模型）方向，W1-4B-dLLM，主打**并行生成 + 自我修正**、极致速度与低价格。团队 Harvard / MIT 背景。

**对设计的启示**：其 agent 决策模型可能用自家 dLLM，设计上应体现「决策模型可替换、对低步数/高吞吐友好」。

### 2. phone.whaletech.site（WhalePhone 产品页）—— 最关键线索

公司自家手机 Agent 产品，页面直接暴露了标准架构：

| 页面原话 | 技术含义 |
|---|---|
| 「任务在后台的私有虚拟屏幕里运行，你照常用手机」 | Android VirtualDisplay，与主屏独立 |
| 「在一块你看不到的独立屏幕上读取当前画面」 | 感知源 = 虚拟屏帧缓冲，不是主屏 |
| 「每次只想一步，只根据刚看到的画面决定下一步」 | Step-wise VLM 决策（单步，非长规划） |
| 「到了付款这一步，停下来等你」 | Human-in-the-loop / Take-over |
| 「只有你明确要求才在真实屏幕打开 App」 | 默认不触碰 display 0 |
| 适配 OPPO(ColorOS) / 小米(HyperOS) / Pixel | 虚拟屏 + 输入注入存在机型适配问题 |

**结论**：题目故意不给方向，但产品页把「虚拟显示器」这条路摆在明面上。走这条路风险最低、最贴近公司内部认知、最容易通过答辩。

### 3. scrcpy（Genymobile）—— 实现虚拟屏的现成工具

scrcpy 本质是「ADB shell 权限的 Android 客户端 + 推送到设备的 server.jar」，通过 `app_process` 以 shell 身份运行，**不需要 root、不在设备上装 App**。

关键能力（已核实）：

- `--new-display=1920x1080[/420]`：新建独立虚拟显示器，退出即销毁
- `--start-app=org.videolan.vlc`：把 App 启动到虚拟屏上
- `--flex-display` / `-x`：虚拟屏随窗口自适应
- `--display-ime-policy=local`：**虚拟屏的输入法出现在虚拟屏上，而非主屏**（键盘不被抢的关键开关）
- `--no-vd-system-decorations` / `--no-vd-destroy-content`：关闭虚拟屏系统装饰 / 关闭退出即销毁
- `--keyboard=uhid --mouse=uhid`：物理 HID 模拟注入输入，完全绕过 IME
- `--keep-active --stay-awake --screen-off-timeout`：防止息屏打断任务
- `--video-codec=h265 -b16M`：虚拟屏画质/码率可调
- `--display-id`：指定 mirror 的 display，控制通道随之绑定

### 4. AutoGLM-Phone（智谱 BigModel）—— 现成的 VLM 决策大脑

- 输入：自然语言任务指令；输出：任务动作
- 操作集合：`Launch / Tap / Type / Swipe / Back / Home / Long Press / Double Tap / Wait / Take_over`
- 架构：多模态 VLM + ADB 设备控制，端到端
- 部署：Python 3.10 + ADB + 设备开 USB 调试 + 安装 ADBKeyboard.apk（广播注入文本，不弹输入法）
- 开源：`github.com/zai-org/Open-AutoGLM`
- 支持 50+ 中文 App（微信 / 美团 / 淘宝 / 携程 / 小红书…）

**关键判断**：AutoGLM-Phone 默认把动作注入主屏（display 0），恰恰会抢焦点。其价值在于**决策层可直接复用**，只需把「执行层」从主屏重定向到虚拟屏。

### 5. Awesome-LLM-Powered-Phone-GUI-Agents（TMLR 2025 survey）

分类学：Prompt Engineering / Training-based / Datasets / Benchmarks；框架分 Single-Agent、Multi-Agent、Plan-then-Act。

值得答辩引用的代表工作：Mobile-Agent-v2、AppAgent / AppAgent v2、UI-TARS、OS-ATLAS / SeeClick、AutoGLM、Mobile-Agent-E。

**结论**：不要从零写 VLM 决策循环，复用成熟范式（单步 VLM + 动作空间 + 记忆），把创新点放在「平行执行空间」与安全边界上。

---

## 三、技术栈定稿

| 层 | 选型 | 说明 |
|---|---|---|
| 平行空间 | scrcpy `--new-display`（ADB shell 权限） | 焦点 / 键盘 / 画面三重隔离 |
| 感知 | 虚拟屏抓帧（scrcpy 流 / `screencap -d <id>`） | 绝不读主屏（display 0） |
| 大脑 | AutoGLM-Phone 云端 API，抽象 `model_provider` 预留替换 | 单步 VLM 决策 |
| 编排 | LangGraph 状态机 | `perceive → decide → guard → execute → verify` |
| 执行 | ADB Keyboard 广播注入文本 + 带 `display_id` 的事件注入 | 不唤起 IME |
| 安全 | `take_over_gate` 拦截付款 / 密码 / 验证码 | 对齐 WhalePhone 的 take-over 承诺 |

**平台**：Android 真机（优先小米 HyperOS / OPPO ColorOS / Pixel，与 WhalePhone 适配机型一致）。
**不做 iOS**：无 ADB / 虚拟屏等价能力，需 XCUITest + WebDriverAgent，风险极高。

---

## 四、核心技术矛盾拆解

「不打扰」需同时满足 4 个维度的隔离，缺一个就会露馅：

| 维度 | 冲突点 | 解法 |
|---|---|---|
| 画面 (display) | agent 操作会改变主屏内容 | VirtualDisplay，agent 窗口栈与主屏完全分离 |
| 焦点 (focus) | 点击 / 启动 App 会抢窗口焦点 | Android focus 是 per-display 的，虚拟屏有独立 focus |
| 键盘 (IME) | 输入文本会弹出输入法覆盖用户 | `--display-ime-policy=local` + ADB Keyboard 广播 / uhid，完全不唤起 IME |
| 输入事件 (input) | 注入事件默认打到 display 0 | 事件必须带 display id 注入到虚拟屏 |

### 关键技术判断（必须写进 README / 答辩）

> 普通第三方 App（即使有 AccessibilityService）**无法创建虚拟显示器**——`DisplayManager.createVirtualDisplay` 需要系统级权限。所以纯「装个 App 到手机」的路线走不通。
>
> 唯一可行的是通过 **ADB shell 身份**（scrcpy 的 `app_process` 方案，或 `adb shell cmd display`）创建虚拟屏。题目 FAQ 明确「连着电脑跑不算作弊，架构本来就是手机做手脚、大脑在云端」，正是为这条路线开的口子。

---

## 五、候选路线对比（选路即答案）

| 路线 | 方案 | 能否不打扰 | 风险 | 评价 |
|---|---|---|---|---|
| A（推荐） | scrcpy 虚拟屏 + 云端 VLM + Python 编排 | 是，焦点/键盘/画面全隔离 | 低，原型当天可跑 | 最贴公司产品思路，答辩最稳 |
| B | 自研 Android App（AccessibilityService + MediaProjection 虚拟屏） | 否，无法创建独立可跑 App 的虚拟屏 | 高 | 技术死路，可作答辩对比素材 |
| C | 多用户 / 工作资料分身 | 否，同一物理屏，仍抢焦点 | 中 | 隔离的是数据不是显示 |
| D | 主屏时间片轮转 + 状态保存/恢复 | 否，用户会看到跳屏 | 低但错 | 反面教材 |
| E | 绕开 UI，走 App 的 API / Intent / 深链 | 是，零打扰 | 中，覆盖率低 | 作为 A 的补充 |

**最终路线 = A 为主干 + E 为优化 + 「关键操作交还用户」为安全边界。**

差异化点：**不打扰是架构保证的，不是靠运气。**

---

## 六、架构设计

### 6.1 演示任务（跨 App）

```
mission_plan（微信回复 → 美团下单）
        │
   ┌────┴────┐  每个 sub_mission 独立可验证、独立可降级
   ▼         ▼
phase_1    phase_2
微信回复    美团下单 → 到付款停
（低风险，先做） （高价值，触发 take_over）
        │
        ▼
  vlm_agent（单步循环 + memory）
        │
  take_over_gate ── 敏感动作 ──▶ 暂停 / 通知用户
        │
  action_executor ──▶ 注入到 virtual_display（display_id 绑定）
```

### 6.2 风险控制原则

题目认可「记录卡点比硬凑半成品更有价值」，因此演示设计成**分段可成立**：

- phase_1（微信回复，低风险）成功即算达标。
- phase_2（美团下单，高价值、触发 take-over）无论成败都能讲出内容。
- **绝不让两个 App 的失败耦合在一起。**

### 6.3 目录结构（snake_case）

```
wellphone/
├─ README.md                     # 一页：架构图 + 部署 + 环境变量 + 选型说明
├─ docs/
│  ├─ architecture.md
│  ├─ feasibility.md             # D1 机型 / App 兼容性实测
│  ├─ conflict_analysis.md       # 焦点 / 键盘 / 画面冲突分析
│  └─ tech_choices.md            # 为什么不选无障碍路线（答辩核心）
├─ config/settings.py            # ADB_SERIAL / VLM_BASE_URL / VLM_API_KEY / VLM_MODEL / DISPLAY_SIZE
├─ wellphone/
│  ├─ device/    virtual_display_runner.py · adb_client.py · frame_source.py
│  ├─ agent/     vlm_agent.py · action_space.py · memory.py · mission_plan.py
│  ├─ executor/  action_executor.py · input_channel.py
│  ├─ guard/     take_over_gate.py
│  └─ main.py
├─ scripts/  start_virtual_display.sh · demo_dual_view.sh
└─ tests/
```

---

## 七、Workplan（D1–D7）

> 相对天数，从收到题目起算。截止时间为收到题目后第 7 天 23:59。

### D1｜打通「平行空间」（最高优先级，关键路径）

1. 环境：Android 真机（优先小米 HyperOS 或 Pixel）、开 USB 调试、`adb` 可用、Python 3.10。
2. 跑通：
   ```bash
   scrcpy --new-display=1080x1920 --start-app=com.tencent.mm \
          --display-ime-policy=local --keep-active
   ```
3. 用第二路 scrcpy 把虚拟屏 mirror 到电脑窗口 → **演示视频的双画面来源**（左：用户手机屏；右：agent 虚拟屏），直接解决「镜头同时看到用户屏幕和任务完成」。
4. 出口标准：**主屏此时仍能被正常滑动 / 打字，微信跑在虚拟屏上。**
5. 输出：`docs/feasibility.md`，记录机型、Android 版本、哪些 App 在虚拟屏跑不起来。

### D2｜执行层（action_executor + input_channel）

1. 把动作注入从主屏重定向到虚拟屏：动作需携带 `display_id`（scrcpy 控制通道天然绑定被 mirror 的 display；必要时 `adb shell input -d <id>`）。
2. 文本输入走 ADB Keyboard 广播（不弹 IME），或 uhid 物理键盘路径，二选一并记录取舍。
3. 动作空间对齐 AutoGLM：`launch / tap / type / swipe / back / home / long_press / double_tap / wait / take_over`。
4. 出口标准：单元测试验证事件路由正确、不落到 display 0。

### D3｜感知 + 大脑（frame_source + vlm_agent）

1. 感知：从虚拟屏抓帧（scrcpy 视频流或 `adb exec-out screencap -d <id>`）。
2. 决策：单步 VLM 循环（看当前帧 → 输出一个动作 → 执行 → 再看）。先接 `autoglm-phone` API（BigModel）跑通；预留 `base_url / model / apikey` 环境变量，便于换成自建 vllm。
3. 加轻量记忆（历史动作 + 已达成子目标），避免长任务迷路（参考 Mobile-Agent-v2 的导航 agent 思路）。
4. 出口标准：能完成「打开微信 → 找到对话」；`--dry-run` 模式可只输出动作不执行。

### D4｜安全边界与冲突处理（take_over_gate，加分项）

1. 敏感动作白名单拦截：付款、密码、验证码、删除、同意协议、发敏感内容 → 暂停并通知用户接管。
2. 冲突处理策略：虚拟屏是否独占某 App 进程？用户同时在主屏打开同一 App 会怎样（同 package 双实例 / Activity 复用）？记录现象与规避方案。
3. 输出：`take_over_gate.py` + `docs/conflict_analysis.md`。

### D5｜任务编排 + 端到端跑通

1. 编排层用 LangGraph 串成状态机：`perceive → decide → guard → execute → verify → loop / notify`。
2. 先跑通 phase_1（微信回复），再上 phase_2（美团下单）。
3. 出口标准：`main.py` 一条命令启动全流程。

### D6｜打磨演示 + 写 README

1. 录 1–2 分钟视频，双画面：手机主屏持续被操作 + 电脑窗口里虚拟屏上任务推进，结尾展示「办好了」的真实结果。
2. README 一页以内：架构图 + 部署步骤 + 环境变量（`ADB_SERIAL` / `VLM_BASE_URL` / `VLM_API_KEY` / `VLM_MODEL` / `DISPLAY_SIZE`）+ 技术选型说明。
3. commit message 清晰、分主题提交。

### D7｜答辩准备 + 兜底

1. 准备答辩四问：
   - 为什么选虚拟屏不选无障碍？
   - 怎么保证不抢键盘？
   - 冲突怎么处理？
   - 用了哪些 AI 辅助、怎么审查的？
2. 诚实记录失败：虚拟屏跑不起来的 App、机型差异、`input -d` 版本兼容问题 → 写成「尝试与卡点」清单。
3. 留 1 天 buffer 给突发问题（USB 授权、scrcpy server 推包失败、VLM 限流）。

---

## 八、风险清单

| 风险 | 影响 | 应对 |
|---|---|---|
| 虚拟屏兼容性 | 部分国产 App 在 secondary display 上黑屏 / 崩溃 / 拒绝运行 | D1 必须实测；必要时降级为「支持 API 的走 API，其余走虚拟屏 UI」 |
| 输入注入的 display 绑定 | `input -d` 在低版本 Android 不支持 | 优先走 scrcpy 控制通道 |
| VLM 延迟 / 限流 | 单步决策每步 1–3 秒，长任务耗时长 | 限制步数、加 wait / verify、必要时换本地模型 |
| 跨 App 任务耦合失败 | 演示整体失败 | 分段可成立，phase_1 独立达标 |
| iOS 无等价能力 | 方案不可行 | 明确只做 Android |

---

## 九、交付物清单

1. GitHub 仓库链接（确保对方有访问权限）。
2. 1–2 分钟演示视频（双画面：用户屏幕 + 任务完成）。
3. README 中的简要技术选型说明（一页以内）。
4. 提交入口：`assignment.whaletech.site`
5. 面试预约：Google Calendar 链接（见 homework.md）。

---

## 十、答辩要点速查

- **核心论点**：不打扰是架构保证的，不是靠运气。
- **技术死路对比**：第三方 App 无法创建虚拟显示器（需系统权限），故必须走 ADB shell 路线。
- **四重隔离**：画面 / 焦点 / 键盘 / 输入事件，逐一说明。
- **安全边界**：敏感动作一律经 `take_over_gate`，对齐 WhalePhone 的产品承诺。
- **失败清单**：诚实记录卡点，比硬凑半成品更有价值。
