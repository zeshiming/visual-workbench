# 摄影创作工作台：Agent / Harness 现状与生产化设计

版本：2.0

更新时间：2026-10-01

状态：摄影工作台 MVP + 初步 Agent 执行框架；生产化建设中

适用项目：`/Users/zeshiming/Desktop/visual-workbench`

## 1. 文档基线与范围

本文依据当前本地工作区代码修订，包含未提交改动。代码检查可以证明模块和调用关系存在，不能代替浏览器端到端测试、真实供应商联调或故障恢复测试。

撤回旧版“生产级 Harness 核心已完成，剩余只有分布式部署”的结论。执行链、审批绑定、版本存储、恢复和扩展接入仍有核心缺口。构建通过不代表这些能力已经完成。

第 3–4 节描述代码现状与问题；第 5 节起描述目标设计。目标实体、状态机、接口与验收要求不表示已经实现。本轮在核对文档时同步修正了分析快照复用和步骤 checkpoint 的业务代码；每一项完成情况以末尾实施记录和测试证据为准。

关联文档：[生产产品路线图](./PRODUCTION_PRODUCT_ROADMAP.md)。该文档是早期规划，其中“生产级核心已完成”“自动恢复”“所有写操作统一”等表述尚未同步校正；当前完成度和开发优先级以本文为准。

### 1.1 用户目标与约束

- 服务个人摄影师、兼职摄影师，同时形成可演示和解释的 AI Agent 简历项目。
- 支持手动后期与自然语言任务，保留原图及修改历史。
- AI 编辑默认先展示计划，用户确认后执行。
- 使用自定义 Harness；不要求迁移到 LangChain、PydanticAI 等框架。
- 当前不引入 Sandbox，不执行任意第三方代码。
- MCP/Skill 优先完成可添加、启停、发现、调用的机制，不要求安装具体外部服务。
- 批量扩展和模型质量评测暂缓；必要的功能回归与恢复测试仍属于工程验收。
- 本地开发不自动提交或推送。

## 2. 产品定位与入口边界

产品定位：面向摄影师的图片创作工作台，通过多模态理解、确定性摄影工具和生成式编辑完成可追溯的后期任务。

### 2.1 当前界面行为

| 入口 | 当前行为 | 当前限制 |
|---|---|---|
| AI 助理 | 图片问答、文字建议、近期上下文 | 不执行照片库工具；编辑交接主要是复制建议到任务输入框 |
| Agent 执行 | 预览计划、确认、发起本地/混合修图流程 | 新计划有服务端一次性审批、分析快照和运行预算；旧库记录仍有兼容回退 |
| 局部编辑 | 提交圈选区域坐标和描述，调用图片模型 | 有圆形区域外像素保护、EditorRun 和最终校验；复杂蒙版仍有限 |
| 手动工具 | 滑杆、白平衡、LUT、追色等 | 已接入统一 Workspace commit；大图、透明图和连续编辑仍需场景验证 |

### 2.2 建议的目标边界

保留不同操作入口，共用后台执行和版本服务。下表为产品建议，界面改名尚未实施。

| 入口 | 用户意图 | 目标行为 |
|---|---|---|
| AI 助理 | 讨论、分析、连续反馈、整理需求 | 只读问题直接回答；编辑请求在当前面板展示任务计划及确认卡片 |
| 快速修图（现 Agent 执行） | 已经知道要怎么修改 | 直接进入共同的规划与审批流程 |
| 局部编辑 | 明确指定空间区域和修改内容 | 将区域约束转换成编辑任务，确认范围和操作后执行 |

Assistant 不直接写图片，但可以在用户确认后发起 Runtime 任务，无需要求用户反复切换入口。Agent 是后台规划与执行能力。局部编辑可以跳过开放式规划，但必须复用权限、模型适配、校验、版本提交和 Trace。

手动调色由用户直接操作授权，不必每次弹出 Agent 审批；提交结果时仍走统一版本服务。入口可以复用能力，边界按输入、权限和结果定义，不以“功能绝不重合”为目标。

## 3. 当前实现审计

以下 API 路径相对于 `apps/api/src/`，前端路径相对于 `apps/web/src/`。表格是静态代码审计，不宣称已完成全部端到端验收。

| 能力 | 代码入口 | 准确状态 |
|---|---|---|
| 摄影工具 | 前端 `lib/image-adjustments.ts`；API `services/` | 调色、LUT、追色等有实现；大图、透明图和连续编辑仍需场景验证 |
| 客户反馈筛选 | 前端 `components/AssetLibrary.vue`；`routers/assets.py` | 支持按客户/反馈 ID 搜索素材，并将结果作为批量工具输入；已有结构化反馈记录和素材关联，跨项目索引仍待完善 |
| 计划生成 | `core/planner.py`、`core/agent_plan.py` | 结构化模型输出、依赖顺序检查、规则回退已存在 |
| 执行循环 | `core/agent_loop.py`、`core/orchestration.py` | 先调用图片模型，再本地后处理；不是任意逐步工具调度 |
| 工具路由 | `core/agent_tools.py`、`core/tool_registry.py` | 本地同步 Handler 和 MCP/Skill 异步 Handler 已通过统一执行器分派；外部服务仍未联调 |
| 工具策略 | `core/policy.py`、`core/agent_plan.py` | 有长度限制和部分参数检查；超时/幂等性主要是元数据 |
| 人工审批 | `routers/agent.py`、前端右侧面板 | 服务端保存一次性审批记录，绑定图片、Workspace/版本、提示词、模型配置和计划；历史旧记录仅兼容回放 |
| 重试/重规划 | `core/agent_loop.py`、`services/retry.py` | 有限重试；重规划是追加失败提示，未重新观察结果和选择工具 |
| 状态控制 | `routers/agent.py` | 进程内暂停/继续/取消，阶段边界检查；不能立即终止在途模型生成 |
| 持久化 | `models/settings.py` | 保存 AgentRun/AgentStep、Trace 和 Worker 租约；重启标记 interrupted，纯本地计划可按 checkpoint 安全续跑 |
| Trace | `routers/agent.py`、`services/ai_client.py` | 状态/工具事件按序落库；步骤 checkpoint 可供本地恢复，模型步骤不会自动重放 |
| Assistant 记忆 | `routers/assistant.py`、`models/settings.py`、前端 session 层 | 已有后端 Session/Message 和工作区版本绑定；摘要、跨设备冲突和完整 Asset/ImageVersion 关联仍待完善 |
| 图片版本 | `services/workspace_commit.py`、`routers/workspaces.py`、前端历史面板 | 已有持久化版本链、分支父版本、冲突检查和历史恢复；当前仍以 Workspace 粒度为主 |
| 模型适配 | `services/ai_client.py` | Qwen Image 3.0 分支、特定 Responses 路由、LiteLLM；能力注册和原始尺寸审计仍需完善 |
| 图像校验 | `services/image_validation.py` | 解码、尺寸、极端亮度；无身份、背景、构图或指令完成度验证 |
| MCP | `mcp/`、`mcp/adapter.py` | HTTP 客户端、发现和 Registry Handler 已接通；默认无启用服务 |
| Skill | `skills/registry.py` | Manifest 加载与 Planner 上下文已接通；没有任意脚本执行 Handler |

## 4. 优先缺陷与历史结论纠偏

### 4.1 已确认的代码问题

| 编号 | 问题 | 影响 | 修复验收 |
|---|---|---|---|
| P0-01（前端已修复） | handleAgentRun 已先捕获计划再清空展示状态，无计划时禁止调用 | 原来的空计划提交问题已有组件回归覆盖 | 后续服务端绑定集成验收继续见 P0-02 |
| P0-02 | 已有服务端审批记录和上下文哈希；旧库记录可能没有原始分析快照 | 新计划已能阻止图片、提示词、版本和模型配置变化后的旧执行；旧记录兼容回放时会重新分析 | 新预览保存 plan、context hash 和 analysis snapshot；一次性 claim，过期/篡改拒绝 |
| P1-01 | validate_agent_plan_shape 强制恰好一个 apply_ai_edit | 纯本地调色无法独立执行 | 本地任务图片模型调用次数为零 |
| P1-02 | Loop 在遍历计划前先执行图片模型 | 前置本地步骤不能影响模型输入 | 每步消费正确 Artifact，执行顺序符合依赖 |
| P1-03 | 已接通 Registry；未注册 mcp:/skill: 仍需在计划阶段拒绝 | 扩展服务需通过发现、授权和绑定 | 计划阶段拒绝未注册、未启用或未绑定的工具 |
| P1-04 | 新计划已复用冻结分析快照；旧数据库预览因没有 raw 快照而兼容性回退分析 | 新流程不重复支付分析调用；校验失败的受控重试和预算策略仍需独立完善 | 新预览执行时分析调用数为零，并在 Trace 标记 `approved-analysis` |
| P1-05 | Editor 仍是独立入口，但已有 EditorRun、Validator、区域保护和 commit 关联 | 尚未与 Agent Step Registry 完全统一 | 区域编辑和手动提交有明确可追溯记录；统一成本/供应商 Trace 待后续 |
| P1-06 | Agent/Editor 现在先校验原始输出，再归一化并做最终校验；Agent Trace 和 EditorRun 均保存 rawValidation | 供应商原始请求 ID、下载过程和更深层视觉质量仍未纳入统一校验 | 原始输出尺寸、归一化动作和最终校验报告均可追踪；供应商链路审计后再关闭此项 |

### 4.2 需复现验证的稳定性问题

- “调色退出”此前归因于 PNG 内存压力，但缺少崩溃日志或内存证据。JPEG 改动与取消跳首页仅是已实施缓解，不能视为根因已确认；需要连续调色、换图、保存、刷新、大图和路由回归。
- 调色统一转 JPEG 会丢失透明通道并引入有损编码。目标应分离预览与最终输出，保留原始素材、透明度和可用色彩信息，导出格式由用户选择。
- 数据库路径已固定到 apps/api；同时图片目录从 apps/api/src/workspace_images 改到了 apps/api/workspace_images。需验证旧图仍可读取，提供可回滚迁移，健康检查不能证明历史数据完整。
- 保存逻辑存在网络失败后的内存兜底，UI 必须区分“持久化成功”与“仅保存在本次会话”。

## 5. 目标架构：先实现单机可靠性

```text
Vue / Electron
  助理对话 · 快速修图 · 局部编辑 · 手动调色
                ↓
Task / Context API
  图片版本 · 选区 · 参考图 · 用户要求 · 会话关联
                ↓
Custom Harness
  Planner → Policy → Approval → Step Executor → Validator
     ↑                        ↓                    │
     └──── observation / bounded replan ───────────┘
                ↓
Tool Registry → 本地算法 / Provider Adapter / MCP Adapter
                ↓
Artifact Store + Version Service + Run/Event Store
```

Skill 是进入上下文的工作流说明和工具约束，不是读取一个文件就获得了执行能力。

首个生产化里程碑可以采用 SQLite、受控本地文件存储和后台 Worker。生产级判断依据是数据一致性、故障恢复和可验证行为；Postgres、Redis、Temporal 都不是称为生产级的必要条件。

## 6. 上下文、会话与记忆

### 6.1 优先实现的三层

| 层级 | 内容 | 保存与读取 |
|---|---|---|
| 任务上下文 | 图片版本、选区、参考图、目标、预算、工具结果 | 持久化 TaskContext，执行使用冻结快照 |
| 会话记忆 | 用户消息、答复、交接、结果反馈 | 后端 Session/Message；近期消息 + 可追溯摘要 |
| 项目约束 | 身份保持、色调、交付要求、已确认偏好 | 结构化 ProjectPreference，可查看、修改、删除 |

视觉 Embedding、跨项目风格检索和长期学习后置；不把向量数据库作为记忆系统前提。

### 6.2 会话规则

- 消息绑定 asset_id、input_version_id，必要时关联 output_version_id 和 run_id。
- 换图时显示当前目标，跨图引用需显式选择，不能无条件复用“上一张”的上下文。
- 手动改图后通知会话版本变化，不假装模型看过未发送的历史图片。
- 完整记录持久化，模型上下文按预算选取近期消息、摘要和必要预览图。
- 摘要注明来源消息范围；版本服务和运行记录是事实来源。
- 偏好写入需用户确认；会话和偏好有清除、导出及保留策略。
- 运行 Trace 是审计数据，只有经过选择进入上下文后，才成为模型可用的任务记忆。

## 7. 资产与版本：统一提交边界

### 7.1 目标实体

| 实体 | 关键字段 |
|---|---|
| Asset | id、workspace_id、original_artifact_id、元数据 |
| Artifact | id、hash、storage_key、mime、width、height、bytes、created_at |
| ImageVersion | id、asset_id、parent_version_id、artifact_id、operation、run_id |
| AssistantSession | id、workspace_id、active_asset_id、active_version_id |
| AssistantMessage | id、session_id、role、content、version_id、run_id、created_at |
| Task | id、origin、input_version_id、region_ref、reference_refs、constraints |
| Plan / Approval | id、revision、plan_hash、context_hash、approved_at、expires_at |
| AgentRun | id、task_id、approval_id、status、deadline、budget、checkpoint |
| StepRun | id、run_id、step_id、attempt、input_refs、output_refs、真实时间、错误 |
| RunEvent | run_id、sequence、type、payload_ref、created_at |

来源区分 assistant_handoff、direct、editor、manual；origin 只是追踪信息，不赋予执行权限。

### 7.2 提交不变式

1. 原图不可变；编辑在临时 Artifact 上完成。
2. 校验后，用唯一提交键关联 Run、Step、Artifact 和新版本。
3. 文件先落盘；版本和当前指针在数据库事务中提交；失败遗留文件可回收。
4. 当前版本已被其他操作修改时创建分支或报告冲突，不覆盖用户新修改。
5. Undo/Redo 切换版本指针，不删除历史版本。
6. 单父版本已可支持分支 DAG，第一阶段不做自动图像合并。

“单写入者”指统一 Version Service；手动工具和 Editor 不必经过 LLM Planner。

## 8. Planner、审批与逐步执行

### 8.1 计划契约

Planner 输入包含目标、冻结图片版本/选区、分析快照、可用工具 Schema 和预算，只展示已启用且具备 handler 的工具。

支持 local、model、hybrid 计划，允许零次图片模型调用。步骤指定 input_refs、params、depends_on、预期输出和校验规则；检查参数范围、依赖顺序、步骤上限及素材可访问性。

例如：降饱和度使用本地工具；移除物体可选择图片模型；追色缺少参考图时请求补充，不虚构素材引用。

### 8.2 审批契约

服务端保存预览计划和分析快照，返回 plan_id、revision、context_hash。用户确认计划标识，Runtime 从服务端读取计划，不信任前端任意 plan + approved=true。

批准范围绑定输入版本、选区、参考图、参数、模型配置版本和费用上限。输入变化、新增写工具或扩大范围时重新审批；批准范围内的确定性步骤无需重复确认。

### 8.3 执行规则

- 按依赖获取下一步骤，通过 Registry 分派 handler，执行前后写 StepRun。
- 每步消费正确的 Artifact；前置调色影响后续模型实际输入。
- 未执行步骤不能记为成功；依赖失败则停止或标记下游 skipped。
- 策略拒绝发生在收费调用之前。
- 重规划需要观察结果并生成新版计划；追加失败提示只称为提示词重试。
- 复用已经批准的分析结果，不在没有必要时重复分析。

## 9. 恢复、暂停、取消与重试

### 9.1 目标状态

```text
created → planning → awaiting_approval → queued → running
running → pause_requested → paused → running
running → validating → completed / needs_review / failed
非终态 → cancel_requested → cancelled
进程中断 → interrupted → reconciling → 等待确认或恢复
```

状态转换与事件同事务落盘。UI 区分“请求暂停”和“已暂停”。任务独立于流式连接，刷新后按事件序号重连；断开页面不自动取消任务。

### 9.2 检查点与重复执行控制

- 每步保存输入/输出引用、工具版本、attempt、供应商 request/job ID 和状态。
- 重启先核对在途调用，供应商支持查询时继续查询。
- 结果未知且不可查询时进入 needs_review，不盲目重放收费生成。
- 本地确定性步骤可从检查点重跑，版本提交必须幂等。
- 取消后不再调度新步骤；迟到结果作为未应用产物，不自动替换当前图。
- 恢复能力必须通过进程中断测试证明，不能只凭数据库存在 status 字段认定。

### 9.3 重试分类

| 情况 | 默认策略 |
|---|---|
| 参数非法、未授权工具、凭据错误 | 立即失败 |
| 读取/下载暂时失败 | 有上限退避，遵守 Retry-After 和 deadline |
| 生成请求超时、结果未知 | 查询或人工确认，禁止盲重试 |
| 已生成但下载失败 | 只重试下载 |
| 校验不通过 | 保留结果与报告，预算和审批覆盖后才重新生成 |

## 10. 工具、MCP 与 Skill

### 10.1 统一工具协议

ToolDefinition 包含 name/version、input/output JSON Schema、execution_kind、风险、文件/网络范围、timeout、idempotency policy 和 handler。ToolResult 返回结构化状态、Artifact 引用、指标与错误码。

Runtime 实际执行 Schema、超时、权限和预算约束；仅有描述字段不算完成。外部工具输出作为数据处理，不能替代系统规则或审批。

### 10.2 MCP 接入目标

- 持久化配置，支持添加、编辑、删除、启停、连接检测；凭据用 secret_ref。
- 按选定协议版本完成初始化、能力发现、会话生命周期、工具列表及调用。
- 验证 HTTP 传输、SSE/JSON 返回、分页和错误；评估维护中的 SDK，不能把最小 JSON-RPC 客户端当成完整协议实现。
- 发现工具不自动授权，用户选择允许工具和范围后进入 Registry。
- 限制调用时限、返回大小、重定向和目标地址；本机服务可显式配置，凭据不跨目标转发。
- 当前仅接受受控 HTTP 接入，不启动任意本地命令。这是产品范围选择，不代表 stdio 必须依赖 Sandbox。

不要求安装真实第三方服务：用本地测试服务验证添加→发现→授权→执行→Trace→禁用。

### 10.3 Skill 接入目标

- 公开并校验项目 Skill 格式、版本、说明、输入要求与允许工具；当前 manifest.json + skill.md 是项目格式，不宣称兼容全部生态。
- 支持添加路径/包、启停、版本固定和错误反馈，限制文件大小及路径越界。
- 显式选择或意图匹配后，将必要说明加入 Planner 上下文，记录 skill_id/version。
- Skill 不能扩大权限，仅调用已授权工具；不执行任意附带脚本。
- 用测试包验收加载、选择、约束和禁用；具体摄影 Skill 后置。

## 11. Provider 与图像校验

### 11.1 能力契约

按配置声明 text/vision/image_edit/mask_edit、协议、输入格式、尺寸限制、异步查询和幂等支持。通过适配测试验证，避免只按模型名或域名推断能力。

Assistant 只需分析模型配置，不应因未配置修图模型而无法问答。统一返回 Artifact、原始尺寸、供应商请求 ID、耗时、重试次数、已知用量；未知成本标为未知。

局部编辑必须区分“区域提示”与“严格蒙版编辑”。严格模式使用蒙版接口或输出合成保护区域外像素，并检查边缘融合；不支持时明确告知，不能保证全图生成模型绝不改变背景。

### 11.2 校验分层

- 必须：解码、真实 MIME、文件/像素上限、尺寸/比例、Artifact 完整性、版本关联。
- 改进：保留供应商原始输出，尺寸归一化单独记为步骤；极黑/极白结合原图和指令判断。
- 后置：人物身份、背景变化、构图、伪影、审美和指令完成度。

按用户安排，模型质量评测和视觉检索后置；先保留人工接受/拒绝和前后对比。

## 12. Trace、成本与权限

Trace 关联 session/task/run/step/attempt、输入输出版本、批准计划、工具/模型版本、实际起止时间和错误分类。每次模型调用单独记录，不能仅保留最后一次结果。终态和版本提交完成后才向前端报告成功。

默认界面显示步骤、进度、结果、预计消耗和可理解的失败说明；技术细节放在“运行详情”。

当前凭据存在前端配置/请求路径，不能宣称“前端完全接触不到 Key”。目标是后端 Secret Store、供应商引用和脱敏日志；Trace/导出不能包含密钥或完整图片数据。

单机版限制监听地址、允许来源、并发、请求体、图片资源及外部目标访问，并建立本地访问保护。多人版再增加用户认证、Workspace/Asset 所有权、配额和跨用户隔离。

分别限制步骤、Token、图片次数、费用估算和时限，超预算停止并提示。没有供应商用量时只展示有依据的估算。

## 13. 实施顺序与验收门槛

| 阶段 | 交付 | 必须证明的行为 |
|---|---|---|
| P0：主流程修复 | 计划传递、旧审批失效、保存反馈、历史数据核查 | 确认执行不丢计划；改输入不能执行旧计划；连续调色/换图/保存/刷新不丢工作区 |
| P1：统一逐步执行 | Registry 驱动、纯本地/混合计划、Editor 约束 | 本地任务图片模型调用数为零；混合执行顺序正确；未知工具在收费前拒绝 |
| P2：版本与会话 | Artifact、ImageVersion、后端 Session/Message、交接绑定 | 刷新后恢复图与消息；每轮可查输入/输出版本；手动改图后旧交接失效 |
| P3：可靠运行 | 检查点、事件重连、本地恢复、未知结果保护、幂等、预算、Worker 租约 | 本地步骤可从 checkpoint 续跑；模型结果未知时进入人工核对，不盲目重试或覆盖；同一运行不能被两个 Worker 同时接管 |
| P4：扩展机制 | MCP/Skill 安全配置管理与执行接入 | 测试扩展添加、启停和执行全链路；禁用、Schema 错误、超时均正确处理 |
| 后置 | 批量扩展、视觉评测、偏好检索、多人部署 | 另行安排，不阻塞当前单图核心闭环 |

工程验收包含单元契约、API 集成、浏览器工作流和故障注入。受控模型替身可验证调用顺序和次数；真实供应商联调单独记录模型、配置、日期和费用，不能用 Mock 结果证明外部服务已验证。

文档更新、构建通过、类存在或健康检查不足以关闭验收项。每项需保留代码入口、测试或操作证据及限制。

## 14. 数据迁移与部署选择

数据库变更需要版本化迁移，覆盖旧库、重复启动、失败回滚和资产映射。迁移前做一致性备份，不通过删除数据库解决升级问题。

先把单机 Worker 的恢复、并发锁和事务提交做正确。多用户/多实例需求明确后，再选择 Postgres、对象存储、队列或 Temporal。Redis 与 Temporal 不要求同时引入，避免重复调度职责。

## 15. 产品表达与维护

当前可描述为：

> 面向摄影师的多模态图片创作工作台，支持本地后期、自然语言修图、区域引导编辑和图片问答；已实现结构化计划、初步人工确认、基础结果校验与运行记录，正在完善自定义 Agent Harness 的统一执行、版本关联和恢复能力。

完成 P0–P4 并取得证据后，才宣称具备经过验证的单机生产化 Harness。多人能力独立验收；未实施的视觉评测、任意 MCP 兼容或断点续跑不能写为已完成成果。

本次修订只更新本文，不代表上述代码问题已经修复。后续每完成一阶段，同步现状表与关联路线图，保留验收记录。

### 实施记录：P0 第一批

- 确认执行先捕获预览计划，避免清空状态后提交空计划。
- 修改提示词或所选分析/编辑模型立即使预览计划失效。
- 预览中禁止执行；迟到响应会核对原提示词、图片、图片修订号、模型选择及设置快照，输入变化时丢弃。
- 证据：WorkspaceRightSidebar.spec.ts 的 8 项测试通过，包括实际调用参数、改需求失效及迟到预览拒绝；前端生产构建通过。

### 实施记录：照片库反馈 ID 筛选

- Asset Library 支持输入客户反馈 ID，并在前端按文件名/素材标识过滤；后端资产列表和批量任务接口也支持 `feedbackId`。
- 筛选结果可以继续进入素材选择和本地批处理流程，不会改变原始素材。
- 旧素材仍支持字符串兼容匹配；新上传素材和反馈记录使用结构化 feedback_id 关联。

### 实施记录：结构化客户反馈记录

- 新增 `feedback_records` 表和反馈记录接口，保存 workspace、反馈 ID、客户标识、内容和状态。
- Asset 增加可选 feedback_id；上传、素材列表和 Agent context 解析优先使用结构化关联，同时兼容旧素材文件名匹配。
- API Client 暴露 feedbackId 字段和上传关联参数；跨 Workspace 客户实体、权限和全文检索仍待后续。
- 照片库导入和“保存当前”入口增加可选反馈 ID 输入，直接建立素材与反馈记录的关联。
- 首次使用新的反馈 ID 导入素材时，后端自动创建 `open` 状态的反馈记录；重复素材关联复用已有记录。
- 照片库前端筛选同时匹配文件名和结构化 feedback_id，并在素材卡片显示关联反馈 ID。
- 反馈记录支持 `open`、`processing`、`resolved`、`archived` 状态更新，API Client 已暴露列表和更新接口。
- 照片库按反馈 ID 搜索时显示反馈记录和状态下拉框，可直接推进处理状态。
- 限制：这是前端请求链修复，不能代替服务端计划 ID、上下文绑定、审批存储和端到端验收；P0 尚未整体完成。

### 实施记录：P0 服务端预览绑定

- 新增 agent_plans 表，持久化服务端计划、分析快照、输入摘要及 30 分钟有效期。
- 预览返回 approval_id；执行从服务端读取计划，核对图片内容摘要、需求、styles、模型端点/名称及计划参数。
- 原子领取预览记录，保存 approved_at/run_id；重复提交、过期、篡改和输入变化返回 409，发生在修图调用之前。
- 不保存图片 Base64 或凭据，凭据轮换不改变绑定，模型和端点变化需要重新预览。
- 验收：5 项后端临时数据库/API 测试、8 项前端组件回归和生产构建通过；模型使用测试替身，未消耗真实模型。
- 限制：尚未绑定完整的持久化 Asset/Version 实体、预算和区域模型；新预览的分析快照已在正式执行时复用，旧数据库记录因缺少原始 JSON 会兼容回退分析。领取后进程中断会进入人工核对流程；只有纯本地、连续完成的步骤支持显式 `resume-local`，模型步骤不会自动重放。本阶段不会自动重复执行已领取计划。旧客户端须重新预览取得 approval_id。
- P0 保存/刷新/旧数据和浏览器工作流验收仍待完成。

### 实施记录：P0 保存语义

- 显式保存要求后端图片和元数据请求成功；失败抛错，保留工作区草稿和未保存标记，不再以内存兜底冒充持久化成功。
- 只保存元数据时保留未加载图片；仅显式 hasSourceImage=false 才删除图片。
- 保存期间产生新草稿时，旧保存完成不会清除新草稿或未保存标记。
- 旧存储测试过去依赖网络请求失败被吞掉，现改为可读回的后端测试替身；存储、会话和新增失败/竞态测试共 28 项通过。
- 限制：图片和元数据仍是两次请求，尚非原子版本提交；真实浏览器刷新和历史目录迁移仍待验收。其他非显式保存路径中的兜底需要继续收敛。

### 实施记录：P0 历史图片目录兼容

- 默认本地启动增加一次性旧目录复制迁移；显式 DOUSHABAO_DATA_DIR 不导入开发目录内容。
- 仅补齐缺失的工作区 JSON 和 assets 文件，保留源文件、不覆盖当前文件；完整复制后发布文件，失败可重试。
- 完成标记防止后续重启复活已删除图片；旧目录保留供人工回滚，不能直接把旧文件覆盖到新版本。
- 3 项临时目录测试通过，覆盖当前文件优先、删除后重复启动、复制失败后重试。
- 实际目录核查：80 个旧文件在新目录均已有对应文件，本轮新增复制 0 个；161 个现有文件和全部旧文件的校验和保持不变。对应文件存在不意味着内容相同，新目录始终优先。
- 本轮没有启动开发服务；浏览器恢复与原子保存仍待后续验收，P0 尚未整体关闭。

### 实施记录：P0 图片恢复竞态

- WorkspaceView 为每次图片加载分配请求序号，忽略换工作区或新状态更新后的旧响应；组件卸载使在途响应失效。
- 图片读取失败提供错误提示与重试入口，避免停留在不可解释的空白画面。
- 启动同步合并当前缓存，避免等待设置响应期间覆盖用户已完成的新保存。
- 2 项组件恢复测试及 5 项保存测试通过，覆盖旧响应迟到、读取失败重试、启动同步与保存竞态；前端构建通过。
- 本轮没有真实浏览器操作验证，也未启动开发服务；不能据此关闭完整 P0 浏览器验收项。

### 实施记录：P0 统一项目提交

- 新增 `PUT /api/v1/workspaces/{id}/commit`，由后端在一次数据库提交中更新工作区元数据和图片指针；前端显式保存已接入该接口。
- 图片先作为不可变 Artifact 写入，再用 workspace_image_pointers 指向它；提交失败不会改变旧指针和旧元数据。
- 元数据-only 保存不会删除未加载图片；显式 image=null 才清除图片引用。
- 后端统一提交故障测试 3 项、前端持久化与保存流程测试 20 项、前端构建通过。
- 限制：旧的独立图片接口仍保留兼容，清理孤儿 Artifact、跨进程版本冲突和真实浏览器验收仍待后续。

### 实施记录：P1 纯本地 Agent 计划

- AgentPlan 不再强制包含 apply_ai_edit；声明 execution=local 的计划可以只调用确定性工具和 validate_result。
- run_agent 对本地计划不会调用图片生成模型，仍保留分析、计划、工具 Trace 和结果校验。
- 验收覆盖纯本地任务的模型调用断言与政策规则；真实 Planner 产生纯本地计划的 Provider 联调仍待进行。

### 实施记录：P1 Registry 执行绑定

- 本地调色、风格化、参考图追色、AI 编辑记录和结果校验已注册同步 Handler，`execute_plan` 通过 Tool Registry 分派。
- 未注册或只有异步 Handler 的工具不会静默跳过，会生成失败 ToolRun；Planner/Policy 仍在收费调用前拦截未知本地工具。
- Registry 测试和 Agent Loop 回归通过；MCP 可通过 discovery 注册异步执行器，Skill 当前仍是受限上下文说明，不执行任意脚本。

### 实施记录：P1 MCP 发现适配

- 新增 MCP discovery adapter：初始化 Server、发现工具、转换为 namespaced ToolDescriptor，并注册异步 Handler。
- 新增 discovery API；默认没有启用外部 Server，未知或未发现的 mcp:/skill: 工具在计划校验阶段拒绝。
- 测试覆盖 MCP 工具发现、Registry 调用和未注册工具拒绝；没有调用真实外部 MCP 服务。

- Planner 现在接收当前已注册且有 Handler 的扩展工具目录；未注册的 MCP/Skill 不会因为名称前缀出现在计划中。

### 实施记录：P1 异步扩展执行

- Agent Loop 现在使用 async executor；本地同步 Handler 与 MCP/Skill 异步 Handler 共用同一 PlanExecution 和 ToolRun 结构。
- MCP discovery 注册的工具可以进入统一执行器；未绑定扩展仍在执行前失败，不会静默跳过。
- Registry、MCP discovery、纯本地计划和 Agent Loop 回归通过；真实外部 MCP 调用仍未联调。

- 纯本地/扩展计划统一使用 async executor，已验证已注册异步 MCP Handler 能在 Agent plan 中执行并进入 ToolRun；未绑定扩展仍会失败。

### 实施记录：P1 Skill 上下文加载

- 支持通过 DOUSHABAO_SKILLS_DIR 加载 Skill manifest 和说明文件。
- Planner 会接收有上限、不可执行的 Skill 摘要；说明文件不能直接获得工具或系统权限。
- Skill 上下文单测通过；尚未将 Skill 说明映射为实际执行 Handler，仍需经过已注册工具和审批。

### 实施记录：P2 Assistant Session 持久化

- 新增 assistant_sessions 和 assistant_messages 表，Session 绑定 workspace_id、asset_id 和 current_version。
- Assistant 首次发送可创建 Session；后续回复读取服务端历史并写入 user/assistant 两条消息，前端保留 session_id 作为刷新后的句柄。
- 支持读取和删除 Session；API 不保存图片 Base64、API Key 或完整模型请求。
- 后端 Session 测试、前端类型检查和生产构建通过。
- 限制：当前消息仍使用 localStorage 作为离线 UI 缓存；版本/Asset 还未绑定为持久化 ImageVersion，历史摘要和跨设备同步待后续。

### 实施记录：P3 Agent 状态事件

- 新增 AgentEventRecord，持久化 running、paused、cancelling、completed、failed 等状态事件及错误摘要。
- `/runs/{run_id}` 现在返回按时间排序的事件列表，前端断流后会读取这些事件辅助恢复阶段状态。
- 状态事件测试通过；事件序号、增量读取、前端流断开后的结果恢复和纯本地 checkpoint 续跑已接入。

### 实施记录：P3 事件序号与增量读取

- AgentEventRecord 增加每个 run 独立的递增 sequence。
- 新增 `/runs/{run_id}/events?after=N`，只返回 N 之后的事件，支持后续流断线重连。
- 事件序号回归通过；前端已使用持久化事件补放阶段进度，模型步骤检查点续跑仍被策略拒绝。

### 实施记录：P3 Agent 结果持久化

- Agent 完成结果（分析、输出图片引用、计划和工具 Trace）保存为独立结果 Artifact，AgentRun 只保存路径。
- `/runs/{run_id}` 返回可读取的结果内容，为流断开后的恢复提供数据源；结果写入采用原子文件替换。
- Agent 结果持久化测试通过；前端已在流断开后轮询该接口恢复最终结果，纯本地步骤通过显式恢复接口续跑。

- 成功结果现在先完成 Artifact 持久化再发送 result 事件；持久化失败不会向前端报告成功，避免“界面成功、运行记录失败”的不一致。

### 实施记录：P3 前端结果恢复

- NDJSON 流在没有 result 事件、读取异常或连接提前结束时，前端按 run_id 查询持久化运行结果。
- 任务仍在运行时有限轮询；completed 直接恢复结果，failed/cancelled 返回持久化错误，不重新调用模型。
- 流恢复测试和 TypeScript 检查通过；事件序号已用于避免重复补放，跨进程 Worker 和模型供应商任务恢复仍待接入。

### 实施记录：P3 步骤级事件

- Async Tool Executor 每完成一个步骤立即写入 tool 事件并推送流事件，包含 stepId、tool、状态、消息和 details。
- MCP、本地和校验步骤共用同一事件结构，失败步骤也会留下事件。
- 新增步骤级 checkpoint：每个步骤完成后将当时的输出图片以原子文件写入 AgentRun 专属目录，并在 AgentStepRecord 与 tool 事件中保存 artifact 路径。
- 最终 trace 落库会复用已有 checkpoint，不重复创建审计行；断流恢复可以读取 AgentRun、事件、步骤状态和中间产物。
- 纯本地计划现在支持显式从连续完成的 checkpoint 续跑；模型计划仍只能读取 checkpoint 并进入人工核对，跨进程 worker、checkpoint TTL/清理策略和供应商任务查询仍待后续。

### 实施记录：P2 Session 恢复

- 工作区加载后，如果存在 session_id，前端从后端读取 AssistantMessage 并恢复到当前会话；后端不可用时保留本地缓存。
- 清空会话会删除后端 Session 并清除本地消息；新消息创建新 Session。
- Session 历史恢复测试和前端生产构建通过。
- 限制：会话消息已绑定 workspace/current_version 字符串，但尚未绑定完整 Asset 与 ImageVersion 表；历史摘要和跨设备冲突合并仍待后续。

### 实施记录：P2 版本查询接口

- 新增 Workspace 版本列表和版本图片读取 API，版本包含 parentId、artifactId、操作类型和当前指针标记。
- 新增后端版本链回读测试，验证两次图片提交形成 parent → child 且可读取两版内容。
- 前端已提供版本查询 API、版本历史 UI 和恢复为当前草稿的操作；版本分支合并与跨资产合并仍待接入。

### 实施记录：P2 版本历史 UI

- 右侧工作区面板显示持久化版本列表、当前版本标记和 parent 链上的版本 ID。
- 可以读取历史版本并恢复为当前工作区草稿；保存后才创建新的版本，恢复动作不会直接覆盖当前版本。
- 前端类型检查和生产构建通过。
- 限制：当前版本历史是线性列表；尚未显示缩略图、操作详情或提供版本分支/合并 UI。

### 实施记录：P2 Agent 计划版本绑定

- Agent 预览与执行请求现在携带 workspaceId/versionId，计划上下文哈希包含当前版本。
- Assistant、快速修图和保存链路都使用 Workspace 的 currentVersionId；旧版本计划不能直接应用到新版本。
- 前端类型检查、版本冲突测试和 API 编译通过；版本绑定尚未覆盖 Asset 级选区和真正的 ImageVersion 分支合并。

### 实施记录：P2 历史版本分支保存

- 从历史版本恢复后，前端保存草稿会携带 draftParentVersionId。
- 服务端验证父版本属于当前 Workspace，并允许新版本挂到历史节点，形成分支；expectedVersionId 仍用于检测当前 Workspace 是否被其他窗口更新。
- 版本链测试覆盖普通 parent 和历史 parent 分支；Asset 级版本、版本合并和可视化 DAG 仍待后续。

### 实施记录：P2 Workspace Version ID

- 统一 Workspace commit 为每次图片提交创建 workspace_versions 记录，维护 parent_id、artifact_id 和 current_version_id。
- Workspace API 和前端缓存传递 currentVersionId；Assistant 新 Session 绑定实际版本 ID，未提交的新草稿仍使用本地占位值。
- 元数据-only 保存复用当前图片版本，不创建空图片版本；删除图片会清空当前指针。
- 后端版本提交故障测试通过，类型检查通过。
- 限制：当前版本仍以 Workspace 为主要粒度，Asset/版本差异和历史版本查询 API 尚未完成；版本提交后的 Artifact 回收待后续。

### 实施记录：P2 版本冲突

- Workspace commit 支持 expectedVersionId；服务端发现当前版本已变化时返回 409，不覆盖新版本。
- 后端冲突测试验证旧客户端提交被拒绝，当前版本指针保持不变；前端提交会携带当前版本 ID。
- 跨进程锁、冲突详情 UI 和合并策略仍待后续。

### 实施记录：P0 图片文件原子写入

- 工作区图片 JSON 从直接截断写入改为同目录临时文件、flush/fsync、原子替换，失败清理本次临时文件。
- 3 项故障注入测试通过：替换失败保留旧图、刷盘失败后可重试、替换前读者仍看到完整旧文件。
- 只使用临时测试目录，没有覆盖用户图片。此处解决单文件写入完整性，不等于图片与数据库元数据的跨请求事务，也不声明断电场景已完整验收。

### 实施记录：P0 连续保存顺序

- 同一前端进程内按工作区串行显式保存，提交时复制输入快照；排队期间修改原对象不会改变已请求保存的内容。
- 前一个保存失败只向该调用者报告失败，不阻断后续排队保存。
- 存储、会话与持久化测试共 31 项通过，类型检查通过。
- 限制：此队列不提供跨浏览器/跨进程并发控制，服务端版本冲突检查及图片/元数据统一事务仍需实现。

### 实施记录：P0 保存失败可见性

- 已保存项目直接保存失败时，页面独立展示错误与重试入口，不再只把错误传给关闭状态的命名弹窗。
- 保存过程中阻止重复触发界面保存操作；错误提示可关闭，关闭提示不会清除未保存状态。
- App 组件集成测试验证：保存失败可见、dirty 保留、重试后错误消失且 dirty 清除；生产构建通过。测试使用后端替身，不作为真实浏览器验收。

### 实施记录：P0 保存工作流验收补充

- 保存弹窗、已保存项目直接保存、重复命名、上传后保存与未保存关闭流程共 9 项组件测试通过；旧保存测试接入有持久状态的后端替身，不再依赖吞掉网络失败。
- 新增清空全部前端工作区/图片缓存后，从后端替身重新同步并读回标题及图片的恢复测试；存储测试共 8 项通过。
- 检测到已有 8000 端口服务，但浏览器控制工具连续两次在创建页面时进程退出，尚未完成真实浏览器验收；没有因此标记 P0 完成。

### 实施记录：P1 Editor Validator

- 局部编辑 API 现在对模型输出执行统一图像校验；无法解码、尺寸异常或明显异常输出返回 502，不传递到前端。
- 局部编辑 Validator 测试通过，前端类型检查和生产构建通过。
- 区域外像素保护、Editor Run 持久化和正式版本提交已接入；复杂多边形蒙版和更深层视觉校验仍待后续。

### 实施记录：P1 Editor 区域约束

- Editor 后端现在要求至少一个有效圈选区域。
- 模型输出会通过软边缘区域蒙版与原图合成，区域外恢复原图像素；合成后再执行尺寸和图片校验。
- 无效模型输出和无效区域都会在后端拒绝，测试通过。
- 当前实现按圆形标记合成；复杂多边形蒙版和区域变化评估仍待后续。

### 实施记录：P1 Editor Run Trace

- Editor 请求现在创建 EditorRunRecord，保存 workspace_id、input_version_id、状态、错误和校验报告。
- 前端把当前 Workspace 和 currentVersionId 传给 Editor；模型失败、蒙版合成失败和校验失败都会更新失败状态。
- Editor Run 已有数据库集成测试，保存 Workspace、输入版本、状态、校验报告和错误；版本提交关联另有专项记录。

### 实施记录：P1 Editor Run 数据库验收

- 新增 EditorRunRecord 集成测试，覆盖有效输出完成、供应商输出损坏失败两条路径。
- Editor Run 记录 workspace_id、input_version_id、status、错误和校验报告；测试验证成功与失败状态均落库。
- Editor 通过 Workspace commit 生成正式图片版本，EditorRun 会回写 output_version_id；Asset 级合并仍待后续。

### 实施记录：P1 EditorRun → ImageVersion

- EditorRun 请求携带 workspace_id 和 input_version_id；Workspace commit 可携带 editorRunId。
- 提交成功后，EditorRunRecord 写入 output_version_id，版本 operation 标记为 editor；历史版本链可以定位回 Editor Run。
- Editor Run 前端契约和组件测试通过，后端版本/运行记录测试通过；Asset 级关联仍待后续。

### 实施记录：P2 Asset 关联

- WorkspaceVersionRecord 和 EditorRunRecord 增加 asset_id；Editor 请求与统一 commit 会传递当前 active asset。
- 服务端校验 asset 必须属于当前 Workspace，跨 Workspace 的素材不会被写入版本链。
- 版本查询响应带 assetId，EditorRun 可以追溯到 Workspace、Asset、输入版本和输出版本。

### 实施记录：P2 Asset 版本筛选

- 版本历史面板按当前 active asset 筛选带 asset_id 的版本，同时保留 Workspace 级版本。
- 旧数据库迁移补齐 EditorRun 输出版本、EditorRun/WorkspaceVersion asset 列；类型检查和编译通过。
- 当前是单资产历史恢复，跨资产合并和资产批量版本操作待后续。
- 类型检查和后端编译通过；资产批量版本合并和资产级历史 UI 仍待后续。

### 实施记录：P1 分析快照复用

- Agent 预览现在把结构化分析和原始分析 JSON 一并保存到服务端审批记录。
- 正式执行领取审批计划后，复用该分析快照，不再次调用分析模型；Trace 标记 `approved-analysis`，保留原始快照内容。
- 对升级前只保存结构化摘要的旧审批记录保留兼容回放，并明确回退为重新分析；新流程不走该回退。
- 新增测试验证已批准分析不会触发第二次分析调用；后端编译和现有数据库测试通过。
- 限制：校验失败的受控图片重试仍可能产生新的生成调用；模型能力声明和供应商异步查询仍属于后续工作。

### 实施记录：P1 原始图像输出校验

- 图片模型返回后先对原始 data URL 做解码、亮度和完整性检查，并记录供应商原始宽高；之后才归一化到原图尺寸，再由最终步骤执行同尺寸校验。
- Agent 的 `aiCalls` Trace 保存 `rawValidation`，避免把归一化后的尺寸误认为供应商原始尺寸。
- Editor 也会拒绝无法解码、全黑或全白的原始输出，之后才进入区域合成和最终校验。
- 新增测试覆盖“原始尺寸可记录但最终尺寸仍需单独校验”；EditorRun 增加 raw_validation_json，响应同时返回 rawOutput 与 finalOutput。

### 实施记录：P3 中断安全核对

- Agent 启动时先持久化计划；进程重启后运行会被标记为 `interrupted`，查询接口会返回计划、步骤状态、checkpoint 路径和事件。
- 新增 `POST /api/v1/agent/runs/{run_id}/reconcile`：只把中断任务转为 `needs_review` 并记录事件，不自动重放图片模型调用，避免未知供应商结果导致重复付费或覆盖当前图。
- `needs_review` 是明确的人工决策状态；用户检查 checkpoint 后应重新走计划审批，再创建新的运行。
- 回归测试验证中断核对会写入状态事件且 `replayed=false`；纯本地恢复测试通过，供应商 job 查询和跨进程 Worker 仍待后续。

### 实施记录：P3 事件断线重连

- Agent 的 progress/tool 事件现在持久化 sequence，并将 sequence 随 NDJSON 流返回。
- 前端流中断后轮询 AgentRun，按最后已收到的 sequence 补放持久化 progress 事件，再读取最终结果；不会重新发起 Agent 请求。
- 前后端专项测试验证断流后可以恢复 edit 阶段提示，前端生产构建通过。
- 限制：当前只恢复进度事件和最终结果，工具详情的可视化重放、跨进程实时 Worker 和供应商异步 job 查询仍待后续。

### 实施记录：P3 纯本地 checkpoint 续跑

- 新增 `POST /api/v1/agent/runs/{run_id}/resume-local`，要求客户端重新提交与原审批完全一致的图片、提示词和模型配置。
- 服务端只接受不含 `apply_ai_edit` 的 local 计划，并只跳过连续存在且可读取的已完成 checkpoint；其余步骤从最后一个可靠图片产物继续执行。
- 包含图片模型的计划会被明确拒绝，不会因为“恢复”而重复调用付费模型；中断任务仍可通过 `reconcile` 进入 `needs_review`。
- 回归测试覆盖已完成步骤跳过、checkpoint 读取和本地恢复入口；跨进程 Worker、供应商异步 job 查询和 checkpoint 清理策略仍待后续。

### 实施记录：P3 供应商未知结果保护

- 新增 `ProviderResultUnknown`，区分“明确失败”和“请求可能已被供应商接受但结果未知”。
- 图片模型连接超时、连接中断等未知结果不会进入 Agent Loop 的自动重试，而是将运行置为 `needs_review`，Trace 保留 provider、requestId（如有）和 `resultState=unknown`。
- 明确的参数、授权或模型响应错误仍按普通失败处理；图片下载失败与生成请求分开处理，避免重复生成。
- 已接入运行级幂等键和未知结果保护；仍未接入具体供应商的异步 job 查询，因此未知结果需要人工核对。

### 实施记录：P3 needs_review 前端恢复

- 前端流恢复现在识别 `needs_review` 终态，直接显示人工核对原因，不再把未知模型结果继续轮询到连接超时。
- 新增前端专项测试覆盖断流后读取 `needs_review`；不会重新发起模型请求。

### 实施记录：P3 checkpoint 跳过状态展示

- 工具轨迹新增 `skipped` 状态，恢复本地计划时明确显示“已跳过”，不再误显示为重新执行完成。
- 前端类型检查通过；跳过状态只表示复用 checkpoint，不代表本次重新运行了该工具。

### 实施记录：前端全量回归收口

- 修复后端不可用/无 URL 的测试环境下，Workspace 本地缓存保存被错误阻断的问题；真实网络失败仍会向调用者报告。
- 修复 Agent 运行包装器在无可选参数时改变旧调用契约的问题。
- 前端完整单测 31 个测试文件、131 项测试通过；后端 17 项测试通过。

### 实施记录：P3 图片请求幂等键

- Agent 和 Editor 的图片请求现在使用不包含图片内容或提示词的本地运行 ID 派生幂等键，例如 `doushabao-{run_id}-image-edit`。
- Qwen Images 直连适配器通过 `Idempotency-Key` 发送；OpenAI 兼容 LiteLLM 路径通过 `extra_headers` 传递；Trace 同时保存幂等键和供应商 request ID（如果有）。
- 该机制只提供请求关联和对支持该协议的供应商的去重提示，不能声称所有中转服务都会执行去重；未知结果仍进入 `needs_review`。

### 实施记录：P3 运行预算与截止时间

- Agent 请求增加服务端校验的 `deadline_seconds`（30–3600 秒）和 `max_image_calls`（1–3 次），并纳入审批上下文哈希。
- 运行超时会进入 `needs_review`，而不是继续等待或自动重放；图片模型重试次数受 `max_image_calls` 限制。
- 预算快照写入 AgentRun 请求摘要，Trace 可区分正常失败、未知结果和 `DEADLINE_EXCEEDED`。
- 当前预算是运行级硬上限，尚未接入供应商真实费用/Token 账单；无可靠用量数据时不会伪造费用。

### 实施记录：P3 跨进程 Worker 租约

- AgentRunRecord 增加 `lease_owner` 和 `lease_expires_at`，恢复任务采用数据库条件更新抢占租约，而不是只依赖进程内 `_AGENT_CONTROLS`。
- 租约由运行事件续期，终态释放；进程启动把旧运行标记为 `interrupted` 并清空旧租约，允许人工确认后接管。
- 第二个 Worker 在租约有效期内无法恢复同一个 run；专项测试覆盖重复接管被拒绝。
- 当前仍是单机 SQLite 租约，未实现多实例时钟偏差、心跳服务和外部队列；多人部署前需要升级数据库事务和 Worker 调度层。

### 实施记录：P4 MCP/Skill 扩展管理入口

- 新增 MCP Server 的添加、更新、启用、禁用、删除接口；添加默认保持禁用，stdio 在无 Sandbox 运行时不能启用。
- 新增 Skill Manifest 的添加、启用、禁用、删除接口；Skill 只进入受限 Planner 上下文，不执行 manifest 附带脚本。
- 扩展管理与发现/执行 Registry 共用同一实例，禁用后的 MCP/Skill 不会继续作为可用扩展暴露。
- MCP/Skill 配置现在持久化到 SQLite，应用启动时恢复；Registry 行为和持久化专项测试通过。
- MCP 配置增加经过校验的 `secret_ref` 元数据，但当前只保存引用名，不自动读取或发送本机环境密钥；配置表不保存 API Key。
- 权限分级、配置迁移版本、凭据轮换和真实外部 MCP 联调仍待后续，避免未经明确授权向任意外部地址注入凭据。

### 实施记录：P4 扩展执行约束

- Tool Registry 对带 JSON Schema 的扩展输入执行实际校验，而不是只把 Schema 传给 Planner。
- 异步扩展 Handler 通过 descriptor 的 `timeout_seconds` 强制超时，超时转为结构化 ToolRegistryError，进入 Agent 的失败/审计链路。
- MCP discovery 产生的工具仍需先注册、启用并经过计划策略；Skill Manifest 不会因为注册就获得脚本执行权限。

### 实施记录：P4 MCP 工具显式授权

- MCP Server 增加 `allowed_tools` 白名单；发现接口只读取远端工具列表，不再自动把未授权工具绑定到 Agent Registry。
- 新增 allow-tool/deny-tool 管理接口；只有显式加入白名单的远端工具才会生成可执行 Handler。
- 白名单随 MCP 配置持久化，禁用 Server 或移除工具后不能继续执行。
- 回归测试覆盖“发现但未授权不可执行”；真实服务的工具权限语义、凭据 secret_ref 和多用户权限仍待联调。

### 实施记录：P4 扩展管理 UI

- 设置页新增 Agent 扩展区，可添加/启停/删除 HTTP MCP 与 Skill Manifest。
- UI 不接收或展示 API Key；MCP 默认关闭，工具白名单仍由后端控制。
- 前端 API 类型、设置页交互和生产构建通过；工具发现、连接检测和授权选择器已接入。

### 实施记录：P4 MCP 发现与授权 UI

- 设置页支持对已启用的 HTTP MCP 发起工具发现，并逐个勾选允许执行的远端工具。
- 发现结果只是能力列表；未勾选的工具不会进入 Agent Registry，勾选状态由后端白名单持久化。
- 前端类型检查、生产构建和后端回归测试通过；连接检测依赖用户配置的外部服务，真实供应商协议变体仍待联调。

### 实施记录：P4 MCP 连接检测

- 设置页的“测试并发现”先调用 MCP `initialize` 检查连接和协议响应，再读取工具列表。
- 连接失败只返回可理解的错误，不改变 Server 启用状态或工具授权白名单。
- 前端类型检查、生产构建和后端回归测试通过；检测使用用户配置的 HTTP MCP 地址，未宣称兼容所有传输变体。

### 实施记录：P4 Skill Manifest 编辑

- 设置页添加 Skill 时可填写名称、描述和受限说明，内容会持久化并进入启用后的 Planner 上下文。
- 说明字段只作为数据和约束提示，不会触发脚本或任意代码执行。
- 前端类型检查和生产构建通过；Skill 与具体工具的结构化绑定仍需后续按实际摄影工作流设计。

### 实施记录：P2 版本历史缩略图

- 版本历史面板现在为最近版本加载缩略图，显示操作类型、当前状态和恢复入口。
- 缩略图读取失败不会影响版本恢复；前端对缩略图数量设有限制，避免打开历史面板时一次性加载过多原图。
- 前端类型检查和生产构建通过；版本 DAG 可视化、差异对比和跨资产合并仍待后续。

### 实施记录：P2 版本 A/B 对比

- 版本历史面板新增“对比”入口，将选定历史版本与当前草稿并排展示。
- 对比只读取版本图片，不改变当前版本指针、草稿内容或版本链；关闭后恢复原工作区状态。
- 前端类型检查和生产构建通过；像素级差异热图、版本 DAG 和跨资产合并仍待后续。

### 实施记录：P2 版本差异热图

- A/B 对比面板新增浏览器本地像素差异热图，用于快速定位历史版本与当前草稿的变化区域。
- 差异计算只在当前浏览器 Canvas 中进行，不上传图片，不修改版本和草稿。
- 前端类型检查和生产构建通过；复杂对齐、结构感知差异和跨资产合并仍待后续。

### 实施记录：P2 版本父子关系提示

- 版本历史列表显示每个版本的父版本短 ID，历史恢复后可识别其分支来源。
- 当前仍是列表化的 DAG 提示，不是可拖拽的图形化 DAG；自动合并和跨资产合并仍待后续。

### 实施记录：电影感快捷预设

- 风格化面板新增通用「电影感」本地预设，不绑定玫瑰或具体花种。
- 预设组合暗调曝光、对比度、冷阴影、暖高光、饱和度和色调，直接复用基础调色算法，不调用 AI。
- 仍保留自然、暖胶片、冷电影和柔和人像等其他预设；用户可以实时预览、应用并保存为新版本。
