# 摄影多模态 Agent 工作台：生产级产品开发文档

版本：1.0  
状态：生产级核心已完成，生产化待办路线图  
更新时间：2026-10-01  
项目：`/Users/zeshiming/Desktop/visual-workbench`

关联架构文档：[PRODUCTION_AGENT_HARNESS.md](./PRODUCTION_AGENT_HARNESS.md)

## 1. 产品定位

本产品面向个人摄影师、兼职摄影师和小型后期团队，提供从照片导入、筛选、基础调色、参考图追色、AI 修图到版本交付的一体化工作台。

核心不是客服机器人，也不是单纯的图片生成器，而是一个以照片版本和 Agent 任务为中心的创作系统：

```text
照片 / 项目
  → 用户意图
  → AI 助理理解或直接进入 Agent
  → Agent 计划与审批
  → 本地算法 / AI 模型 / MCP / Skill 执行
  → 图片质量校验
  → 新图片版本
  → 继续修改 / 回退 / 导出
```

## 2. 三种产品入口边界

三个入口共享同一个版本系统和运行时，但不能各自实现一套修图逻辑。

| 入口 | 主要职责 | 输入 | 输出 | 是否写图 |
|---|---|---|---|---|
| AI 助理 | 对话、分析、解释、整理任务、交接 | 当前图片 + 用户消息 + 会话上下文 | 回答、建议、HandoffIntent | 否 |
| Agent 执行 | 计划、审批、工具选择、执行、校验 | 明确任务或 Assistant Handoff | AgentPlan、ToolRun、Trace、新版本 | 是 |
| 局部编辑 | 圈选区域后的直接编辑 | 区域标记 + 局部要求 | 局部编辑版本 + 校验结果 | 是 |

### 2.1 AI 助理

AI 助理只负责理解和建议：

- 分析当前照片的问题。
- 解释基础调色、追色和 AI 修图的区别。
- 将自然语言整理为明确的修图任务。
- 回答“为什么这样处理”和“下一步应该做什么”。
- 提供 `assistant_handoff`，交给 Agent 预览执行计划。

AI 助理在对话阶段不能直接调用图片生成模型、修改图片或伪造执行结果。

### 2.2 Agent 执行

Agent 是唯一的任务执行引擎：

```text
Context → Plan → Policy → Approval → Execute → Validate → Version
```

Agent 可以调用基础调色、LUT、参考图追色、Qwen Image 3.0、其他 Provider、MCP、Skill、照片库查询、批量和导出工具。所有写操作必须通过 Agent Runtime，原图不可被覆盖。

### 2.3 局部编辑

局部编辑不参与开放式对话和复杂规划，只处理用户在画布上明确圈选的区域。它可以复用图片模型适配器和 Validator，但不复用 Assistant 会话或 Agent Planner。

## 3. 当前完成度

### 3.1 已完成的生产级核心

- 照片库、工作区和资产选择。
- 基础调色、自动白平衡、LUT 和参考图追色。
- Agent 分析、结构化计划、人工确认和执行。
- Agent 状态：运行、暂停、恢复、取消、失败和恢复标记。
- Tool Registry、工具风险、参数策略和幂等性描述。
- Qwen Image 3.0 与 OpenAI-compatible / Responses 模型适配。
- 结果尺寸、解码、黑图和白图检查。
- 有限重试、失败重规划和失败 Trace。
- AgentRun / AgentStep 持久化。
- MCP HTTP Client 和 Skill Manifest Loader 接口。
- AI 助理入口、Assistant → Agent 交接和工作区本地会话记录。

### 3.2 待完成的生产化方向

| 方向 | 当前状态 | 生产版目标 |
|---|---|---|
| Assistant 记忆 | 浏览器本地保存最近消息 | 后端持久化 Session / Message / Version 关系 |
| 项目记忆 | 工作区、参数和部分历史 | 摄影师偏好、客户偏好、项目规范 |
| 视觉记忆 | 当前图和当前版本 | Embedding、相似照片和风格检索 |
| 版本管理 | 线性撤销和部分历史 | 内容寻址的版本 DAG、分支、标签 |
| 质量评估 | 基础确定性校验 | 语义、身份、构图、指令完成度评估 |
| MCP / Skill | 注册和接口 | 真实 Handler、权限、超时、审计和输出清洗 |
| 生产部署 | FastAPI + SQLite + asyncio | Postgres / Redis / 对象存储 / Worker |
| 安全与成本 | 输入边界和本地 Key 配置 | 鉴权、限流、预算、密钥轮换、审计 |
| 观测能力 | 模型和工具 Trace | 指标、告警、关联日志、成本看板 |

## 4. 记忆系统设计

本产品不需要客服机器人式的无限聊天记忆，但需要分层的创作上下文。

```text
Working Memory：当前一步正在做什么
Task Memory：本次 Agent 任务的计划、工具、错误和结果
Project Memory：项目、客户、照片和交付约束
Procedural Memory：工具、Skill、MCP 和摄影动作词汇
Visual Memory：图片特征、版本关系、相似图和风格参考
```

### 4.1 记忆规则

- 不把所有历史消息无上限地发送给模型。
- 使用最近消息 + 历史摘要 + 当前图片版本上下文。
- 图片使用对象引用、缩略图或 Embedding，不重复传输全部原图。
- 用户可以清空 Assistant 会话。
- API Key、原图 Base64 和敏感信息不得写入普通 Trace。

### 4.2 生产数据实体

```text
Workspace
  ├── ProjectMemory
  ├── Asset
  ├── AssistantSession
  │     └── AssistantMessage[]
  ├── AgentRun
  │     └── AgentStepRun[]
  └── ImageVersion DAG
```

建议实体字段：

```text
AssistantSession
- id, workspace_id, asset_id, current_version_id, status, timestamps

AssistantMessage
- id, session_id, role, content, intent, handoff_json, created_at

ImageVersion
- id, workspace_id, asset_id, parent_version_id
- source_type, artifact_uri, adjustment_json, run_id, created_at

AgentRun
- id, origin, session_id, input_version_id, output_version_id
- status, plan_json, trace_json, error, timestamps
```

## 5. 版本系统与运行时

### 5.1 版本不变式

- 原图永远不可覆盖。
- 每次编辑产生新的 `ImageVersion`。
- Undo 是导航到 parent version，不是删除版本。
- Assistant 的每次交接必须绑定当前 version。
- Agent 重试不得覆盖失败版本。
- 每个输出版本都能追溯到 run、model、tool 和 prompt。

### 5.2 生产 Agent Loop

```text
collect_context
  → classify_intent
  → create_or_update_plan
  → validate_policy
  → request_approval
  → execute_next_step
  → capture_snapshot
  → validate_result
  → retry / replan / needs_review
  → commit_new_version
  → publish_trace
```

### 5.3 三种 Run Origin

```text
direct
  用户直接进入 Agent 执行

assistant_handoff
  AI 助理整理需求后交给 Agent

editor
  用户圈选区域后进入局部编辑
```

三种 origin 共用版本、Trace 和 Validator，但使用不同的输入契约。

### 5.4 单写入者原则

所有会改变图片的操作必须通过同一个版本提交边界：

```python
commit_version(parent_version, output_artifact, run_id, validation_report)
```

Assistant、MCP、Skill 和前端组件都不能绕过该边界直接覆盖原图。

## 6. MCP 与 Skill 生产化

每个工具统一提供：

```text
name
source: native | model | mcp | skill
description
input_schema
output_schema
risk_level
timeout_seconds
idempotent
requires_approval
handler
```

### MCP 要求

- Server 白名单和启用状态。
- 工具名和参数校验。
- 超时、返回大小和速率限制。
- 返回内容清洗。
- 请求 ID、耗时和错误 Trace。
- 写操作人工确认。
- 当前无 Sandbox，不执行任意本地进程。

### Skill 要求

Skill 是可版本化的摄影工作流说明，不是任意代码入口：

```text
portrait-retouch/
  manifest.json
  skill.md
```

Skill 只能调用注册工具，不能直接访问数据库、文件系统或网络。

## 7. Validator 与质量评估

### 7.1 确定性校验

- 图片可解码。
- MIME 类型正确。
- 尺寸和宽高比不变。
- 输出不是空图、黑图或白图。
- 原图和新版本关系正确。

### 7.2 摄影质量校验

后续增加：

- 人物身份相似度。
- 人脸结构变化。
- 主体数量变化。
- 构图变化比例。
- 曝光、高光、阴影变化。
- 色偏和肤色异常。
- AI 伪影和边缘异常。

### 7.3 指令完成度

```text
用户要求：提亮人物脸部，不改变背景

检查：
- 人物区域亮度是否提升
- 背景变化是否在阈值内
- 人物身份是否保持
- 输出尺寸是否一致
```

## 8. 安全、成本与部署

### 8.1 安全与权限

- API Key 只存在后端配置或密钥存储。
- 前端不记录完整 Key。
- Trace 不保存完整图片 Base64。
- Workspace 和 Asset 绑定用户权限。
- MCP Server 使用白名单和权限范围。
- 高风险工具必须人工确认。

### 8.2 成本控制

每个 AgentRun 增加：

- 最大步骤数、重试次数和图片像素数。
- 最大并发数和运行截止时间。
- 预计模型成本、日/月预算和额度。
- 图片生成类模型默认不自动重复重试，避免重复计费。

### 8.3 部署迁移

```text
当前本地版：Vue + FastAPI + SQLite + asyncio + 本地图片存储

多人生产版：
Vue / Electron → API Gateway → FastAPI
                         ├── Postgres：元数据
                         ├── Redis：队列、锁、实时事件
                         ├── S3 / OSS：图片和 Artifact
                         ├── Worker / Temporal：长任务
                         └── OpenTelemetry：Trace、指标和告警
```

Sandbox 不作为当前核心依赖。只有未来执行任意第三方代码、不可信 Skill 或命令时才引入隔离环境。

## 9. 分阶段开发计划

### Phase 1：当前已完成

- 本地照片工作区、基础调色、LUT、追色。
- AI 助理、Agent 计划、人工审批和执行。
- 局部编辑。
- Tool Registry、MCP/Skill 接口。
- AgentRun、AgentStep、Trace、Retry、Replan。

### Phase 2：本地生产体验

1. 后端 `AssistantSession / AssistantMessage` 持久化。
2. `ImageVersion` DAG 和版本详情页。
3. AgentRun 与版本、消息、Asset 的完整关联。
4. Assistant 历史摘要和项目级摄影偏好。
5. 失败任务恢复和历史任务重新执行。
6. Tool Snapshot 和前后对比。
7. 各接入一个真实摄影 MCP 与 Skill。

验收标准：

- 刷新应用后可以继续同一个 Assistant Session。
- 可以查看照片所有版本和来源。
- 每个版本可以定位到 AgentRun 和 ToolRun。
- Agent 失败后可从失败步骤继续。
- MCP / Skill 经过审批、超时和 Trace。

### Phase 3：摄影质量和个性化

1. 视觉 Embedding 和相似照片检索。
2. 摄影师风格偏好。
3. 客户 / 项目级色彩规范。
4. 人像、风景、建筑专用 Skill。
5. 质量 Validator 和人工复核队列。
6. 真实图片回归测试集。

验收标准：

- Agent 能基于历史偏好提出一致的调色建议。
- 质量检查能发现身份、构图和伪影问题。
- 更换模型或 Prompt 后能比较质量、成本和延迟。

### Phase 4：多人生产部署

1. 用户鉴权和 Workspace 权限。
2. Postgres、Redis、对象存储。
3. Worker / Temporal 长任务编排。
4. 成本、限流、配额和密钥轮换。
5. OpenTelemetry、日志、指标和告警。
6. 数据保留、删除和隐私策略。

## 10. 推荐开发顺序

```text
1. AssistantSession / AssistantMessage 后端持久化
2. ImageVersion DAG 和版本详情
3. AgentRun 与版本、消息的关联
4. 失败任务恢复和继续执行
5. MCP / Skill 真实示例
6. 摄影质量 Validator
7. 风格偏好与视觉检索
8. 多人生产基础设施
```

暂时不要优先做：

- 泛化客服聊天。
- 无限上下文记忆。
- 没有统一 Adapter 的模型堆叠。
- 没有权限和验证的 MCP 扩张。
- 没有版本关系的批量生成。

## 11. 最终产品形态

```text
照片工作区
├── AI 助理：理解和建议
├── Agent 执行：计划和执行
├── 局部编辑：圈选和精修
├── 基础调色：确定性本地处理
├── 版本 DAG：原图、分支、结果和回退
├── Trace：模型、工具、审批和验证
└── 照片库：资产、反馈、批量和交付
```

最终简历表述：

> 独立设计并实现面向摄影创作的多模态 Agent Harness，将 AI 助理、任务规划 Agent、局部编辑器和确定性摄影工具统一到可追踪的图片版本工作流中；支持人工审批、Provider Adapter、Tool Registry、MCP/Skill 扩展、失败重规划、视觉校验和可恢复的 AgentRun 执行。

## 12. 外部参考项目

- [ImageAgent](https://github.com/josefdc/ImageAgent)：参考 AI Assistant 与传统图片编辑入口的分离方式。
- [PhotoAgent](https://github.com/mdyao/PhotoAgent)：参考 Perceiver、Planner、Executor、Evaluator 和闭环视觉反馈。
- [Chemigram](https://github.com/chipi/chemigram)：参考摄影引擎与 Agent 编排分离、摄影动作词汇、版本 DAG 和单写入者原则。
- [GIMP MCP](https://github.com/maorcc/gimp-mcp)：参考 MCP 工具、实时图像快照和编辑后验证循环。
- [AWS Image Editing AgentCore Harness](https://github.com/aws-samples/sample-serverless-image-editing-agent-bedrock-agentcore-harness)：参考生产部署中的会话记忆、MCP Gateway、模型切换、Trace 和对象存储。
- [picture-it](https://github.com/geongeorge/picture-it)：参考小粒度、可组合图片工具以及生成模型保真风险控制。
