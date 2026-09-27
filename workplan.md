# Workplan：Wellphone 执行计划

> 本文是**简要执行计划**：怎么干、按什么顺序干、每步做到什么程度算过关。
> 架构细节见 `docs/workplan_outline.md`；技术原语与坑见 `docs/research.md`；同类项目对照见 `docs/research_else.md`；面向题方的方向说明见 `docs/suggestion.md`。
> 制定日期：2026-09-27。

---

## 1. 目标与交付清单

| 交付物 | 要求（来自题目） | 我们的对应 |
|---|---|---|
| 可运行的系统 | 用户正常用机时，agent 同时把真实任务办完，主屏零打扰 | scrcpy 虚拟屏 + AutoGLM 决策 + LangGraph 编排 + take_over_gate |
| GitHub 仓库 | commit 清晰、README 一页内（架构图 + 部署步骤 + 环境变量） | D6 完成 |
| 1–2 分钟演示视频 | 镜头同框：用户主屏 + 任务完成 | 虚拟屏投第二窗口，双画面录制 |
| 技术选型说明 | 可放 README | `docs/tech_choices.md` 提炼 |
| 答辩（30 分钟） | 架构决策、技术细节、困难与解决、Vibe Coding 协作 | D7 准备 |

## 2. 定稿技术栈

| 层 | 选型 |
|---|---|
| 平行空间 | scrcpy `--new-display`（路径 B；备选：路径 C 自研 shell APK、路径 D App+Shizuku） |
| 感知 | **主路径：scrcpy 视频流抽帧**（`screencap -d` 实测大概率无效）+ 按 displayId 过滤 UI 树 + OCR 兜底 |
| 决策 | AutoGLM-Phone 云端 API（`model_provider` 抽象，可换本地 vLLM / dLLM） |
| 编排 | LangGraph 状态机：`perceive → decide → guard → execute → verify` |
| 执行 | `input -d <displayId>` 事件注入 + 文本三级降级（`ACTION_SET_TEXT` → 剪贴板 → keyevent） |
| 安全 | `take_over_gate`：付款 / 密码 / 验证码，规则 + 模型双判定，独立于模型输出 |

## 3. 仓库结构规划

```
wellphone/
├── wellphone/                  # 主包（snake_case）
│   ├── device/                 # L0-L1：virtual_display_runner / adb_client / frame_source / ui_reader / ocr_fallback
│   ├── executor/               # L2：action_executor / input_channel
│   ├── guard/                  # L3：take_over_gate
│   ├── agent/                  # L4-L5：vlm_agent / action_space / model_provider / mission_plan
│   ├── config/settings.py      # ADB_SERIAL / VLM_BASE_URL / VLM_API_KEY / VLM_MODEL / DISPLAY_SIZE
│   └── main.py                 # 入口，支持 --dry-run
├── docs/                       # 本目录：调研与设计文档
├── scripts/                    # 环境检查、启停脚本
└── README.md
```

## 4. 阶段计划（D1–D7）

> 每阶段记录实际产出与卡点到 `docs/feasibility.md`。D1 是**唯一关键路径**。

| 阶段 | 目标 | 关键动作 | 出口标准 |
|---|---|---|---|
| **D1** | 虚拟屏可行性打通 | 装 adb/scrcpy；`scrcpy --new-display=1080x1920 --start-app=com.tencent.mm --display-ime-policy=local --keep-active`；逐条过 `docs/research.md` 第 9 节 12 项实测清单；验证 `input -d` 与 scrcpy 抽帧感知；记录编码器占用（≤2 块副屏） | 用户主屏正常打字/滑动/切 App，微信在虚拟屏稳定运行；`docs/feasibility.md` 有结论 |
| **D2** | 执行层 | `action_executor` + `input_channel`：封装 `input -d`，注入前断言 `display_id != 0`；中文三级降级；实测 ADBKeyboard 广播是否落虚拟屏 | 命令行可驱动虚拟屏内微信完成"点开 → 输入 → 发送" |
| **D3** | 感知 + 决策 | `frame_source`（scrcpy 流抽帧，坐标 display-local）+ `vlm_agent` 单步 ReAct 接 AutoGLM API；`--dry-run` 调试模式 | 端到端单步循环在虚拟屏跑通 1 个简单任务 |
| **D4** | 安全 + 冲突 | `take_over_gate`（规则 + 模型双判定）；实测主屏/虚拟屏同 App 并存、剪贴板串行化、敏感页黑屏规避 | 敏感动作 100% 被拦截交还用户；冲突场景实测记录 |
| **D5** | 编排 + 任务 | `mission_plan`（LangGraph）；先跑通 phase_1（微信回复消息），再上 phase_2（美团下单至付款前触发 take_over） | phase_1 成功率稳定；phase_2 无论成败均有可讲内容 |
| **D6** | 交付物 | 双画面录制（`scrcpy --display-id=<id>` 投虚拟屏 + 实拍主屏）；README 一页；分主题 commit | 三项交付物齐备 |
| **D7** | 答辩 | 四问演练（架构决策 / 技术细节 / 困难与解决 / 如何引导和审查 AI 代码）；整理失败卡点清单 | 答辩材料就绪 + buffer |

## 5. 关键检查点（贯穿全程）

1. **主屏零参与**：任何注入前断言 `display_id != 0`；演示时主屏全程留给用户。
2. **坐标纪律**：全部 display-local；禁止用投屏预览像素或主屏状态栏修正。
3. **不点开主屏上正在被自动化的 App**（会被拉出虚拟屏导致任务中断）。
4. **演示规避**：敏感页投屏可能黑屏，脚本提前避开，镜头不对准它。
5. **失败不耦合**：phase_1 与 phase_2 独立可降级；卡点如实记录（题目明确认可其价值）。
6. **机型实测矩阵**：优先小米 HyperOS / Pixel；lichj06（vivo/Android 16）与 Umbra 的结论可作参照，但结论以自己实测为准。
7. **留证据**：每阶段截图/日志进 `docs/feasibility.md`，答辩直接引用。

## 6. 演示任务设计

- **phase_1（低风险，达标线）**：微信回复一条消息——全程无敏感节点。
- **phase_2（高价值，体现深度）**：美团点单至付款前停下，触发 `take_over_gate` 交还用户。
- 两段任务互不依赖；视频叙事采用"双画面同框"：左侧用户主屏，右侧 agent 虚拟屏。

## 7. 文档索引

| 文档 | 用途 |
|---|---|
| `homework.md`（根目录） | 题目原文 |
| `workplan.md`（本文件） | 执行计划（顺序、出口标准、检查点） |
| `docs/workplan_outline.md` | 架构与模块设计（详细版） |
| `docs/research.md` | 平台原语、三条建屏路径、论文与待验证清单 |
| `docs/research_else.md` | GitHub 同类项目调研与差异化定位 |
| `docs/suggestion.md` | 面向题方的技术方向建议（提交物素材） |
| `docs/feasibility.md` | D1 实测结论与逐阶段卡点记录（待产出） |
| `docs/tech_choices.md` | 技术选型论证（待产出，答辩核心） |
