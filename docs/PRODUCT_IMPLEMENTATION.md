# AI 图片创作工作台

## 阶段性产品开发文档

版本：1.1（MVP + Agent 原型）
更新时间：2026-09-30
项目路径：`/Users/zeshiming/Desktop/visual-workbench`

## 1. 当前阶段结论

本项目目前是一个可以运行和演示的摄影后期 AI 工作台。核心非 AI 摄影功能已经完成，AI 图片分析、Agent 计划、Tool Runner、批处理任务和 Qwen Image 3.0 修图链路已经接入。

当前准确定位是：

```text
摄影后期产品 MVP
  + 多模态图片分析
  + Agent 计划与工具执行骨架
  + 本地图像算法工具链
  + Qwen Image 3.0 图片编辑
```

当前 Agent 主要是：

```text
图片分析 → 生成计划 → 调用修图模型 → 本地工具收尾 → 结果校验
```

还没有完全实现：

```text
LLM Planner → 动态工具选择 → 多轮执行 → 失败重规划 → 人工审批 → 评测闭环
```

## 2. 产品定位

AI 图片创作工作台面向摄影师、影像工作室和视觉创作者，解决照片导入、筛选、调色、风格化、参考图追色、AI 修图和批量交付问题。

产品将能力分为三层：

1. 确定性图像算法：调色、白平衡、LUT、追色、选片、批量导出。
2. AI Agent：理解用户需求、分析图片、生成结构化计划、选择工具。
3. 图片生成与编辑模型：执行复杂语义编辑，例如人物、背景、服装和局部内容修改。

核心流程：

```text
导入照片
  ↓
照片库 / 客户反馈 ID / 智能选片
  ↓
基础调色 / 白平衡 / LUT / 参考图追色
  ↓
Agent 分析和规划
  ↓
本地工具或 Qwen Image 3.0 修图
  ↓
尺寸与结果校验
  ↓
保存编辑版本 / 批量导出
```

生成填充目前没有接入，界面和产品文档必须保持明确的不可用状态。

## 3. 信息架构

```text
照片
├── 项目和工作区
├── 文件夹 / 多文件导入
├── 联系表
├── 客户反馈 ID 搜索
├── 全部照片
├── JPG + RAW
├── 仅 RAW
├── 仅 JPG
├── 已选择
└── 智能选片

调色
├── 曝光 / 对比度
├── 高光 / 阴影
├── 饱和度 / 色温 / 色调
├── 自动白平衡
├── 直方图
└── 批量应用

追色
├── 导入参考图
├── 当前照片追色
└── 批量追色

风格化
├── 内置风格预设
├── .cube LUT
└── 批量套用

AI 修图
├── Agent：分析、规划、自动修图
└── Editor：局部区域标注和定向修图
```

## 4. 界面与交互

```text
顶部栏：项目名称 / 文件 / 视图 / 编辑 / 设置
左侧栏：项目列表
工具栏：照片 / 调色 / 追色 / 生成填充 / 风格化 / AI 修图
中央区：联系表、图片预览、前后对比、分割对比
右侧栏：当前模式的参数和 AI 工具
```

已完成：

- 原图 / 分割对比 / 调整后模式切换
- 分割对比线拖动
- 适合窗口
- 25%、50%、75%、100%、150%、200% 缩放选择
- 鼠标滚轮和触控板缩放 / 平移
- Editor 模式局部区域绘制与移动
- AI 运行状态、计划和工具执行轨迹展示
- Agent 执行日志展开和重新执行入口

## 5. 非 AI 图像管线

### 5.1 RAW / JPG

支持：

```text
ARW / CR2 / CR3 / DNG / NEF / ORF / PEF
RAF / RW2 / SRW
```

同名文件自动配对：

```text
DSC03405.JPG + DSC03405.ARW → 同一 pairGroup
```

原片不修改。RAW 使用 `rawpy / LibRaw` 生成 JPEG 预览，并读取尺寸、ISO、快门、光圈、焦距、镜头和 EXIF 信息。

### 5.2 基础调色

```text
exposure / contrast / highlights / shadows
saturation / temperature / tint
```

浏览器端支持即时预览，松开滑杆后生成完整结果。每张素材独立保存调色参数，原图进入撤回历史，编辑版本作为新资产保存。后端 Tool Runner 同样支持这些参数，并可批量处理素材。

### 5.3 自动白平衡

采用采样后的 Gray World 方法：忽略透明、极暗和高光溢出像素，计算 RGB 均值，推断色温和色调偏移，再进入基础调色管线执行。

### 5.4 LUT / 风格预设

已支持自然、暖胶片、冷电影、柔和人像等预设，以及 `.cube` LUT 解析、三线性采样、当前照片应用和批量应用。

### 5.5 参考图追色

当前使用 RGB 均值 / 标准差颜色迁移：

```text
目标图统计 + 参考图统计
  ↓
通道颜色迁移
  ↓
保留目标图结构、构图和透明度
```

后续可升级到 Lab / Oklab，并加入肤色保护和局部保护。

## 6. 照片库、客户 ID 与批处理

照片库 Agent Context 支持：

- 选中素材 ID
- 客户反馈 ID
- 参考图资产 ID
- RAW / JPG 配对
- 元数据和图片地址
- 单次最多 200 张素材

批处理支持：

- 基础调色
- 自动白平衡
- 风格预设
- `.cube` LUT
- 参考图追色
- NDJSON 实时进度
- 暂停、继续、取消
- 失败素材单独重试
- SQLite 保存进度、成功素材和失败素材
- 默认 2 个 Worker
- 高 / 普通 / 低优先级

当前队列是单进程内存 Worker + SQLite 状态持久化。应用重启后可以识别中断任务并继续未处理素材，但还不是 Redis / Temporal 级别的跨进程可靠队列。

## 7. 当前 AI Agent 架构

### 7.1 已实现执行链

```text
用户修图需求
  ↓
图片分析模型
  ↓
AgentImageAnalysis
  ↓
确定性 AgentPlan
  ↓
AI 图片编辑
  ↓
本地调色 / 风格 / 追色工具
  ↓
结果尺寸校验
  ↓
保存图片和 Tool Trace
```

### 7.2 AgentPlan

`apps/api/src/core/agent_plan.py` 定义了：

- 计划版本
- 任务目标
- 执行模式：`ai / local / hybrid`
- 工具步骤
- 参数
- 步骤依赖
- 计划结构校验

当前计划生成主要是确定性规则：根据图片分析结果和问题描述推断保守的调色参数。它还不是由 LLM 完全自主生成的 Planner。

### 7.3 当前工具目录

```text
apply_adjustments
apply_style
match_reference_color
apply_ai_edit
validate_result
```

工具执行状态：

```text
executed  已执行
deferred  已进入计划但处理器暂未接入
failed    执行失败
```

### 7.4 AI 模型分工

```text
分析模型：gpt-6-astra / 其他视觉语言模型
  → 理解图片、识别问题、生成修图指令

本地算法：Pillow / Canvas
  → 基础调色、白平衡、LUT、追色

图片编辑模型：Qwen Image 3.0
  → 图生图和复杂语义编辑
```

Qwen Image 3.0 已加入专用适配器：

```text
百炼 OpenAI 兼容 Host
  → /images/generations
  → 顶层 image 字段
  → 下载返回的图片 URL
  → 转为项目 Data URL
  → 尺寸校验
```

配置支持模型级 Host / Key 覆盖，因此可以同时配置：

```text
gpt-6-astra      → 中转或其他分析服务
qwen-image-3.0   → 阿里百炼图片编辑服务
```

尚未接入：

- FLUX Kontext
- GPT Image
- GLM Image
- PydanticAI 真正的 LLM Planner
- MCP 外部工具

### 7.5 当前还不能称为完整 Agent 的原因

目前是：

```text
分析 → 计划 → 执行 → 校验
```

完整 Agent 还需要：

```text
LLM Planner
  ↓
动态选择工具
  ↓
执行一个步骤
  ↓
读取工具结果
  ↓
重新规划或重试
  ↓
人工审批 / 最终交付
```

当前缺少动态 Planner、多轮 Replan Loop、工具权限确认、Agent 长期记忆和 Agent 专用评测集。

## 8. 模型和 Provider 配置

Provider 提供默认 Host / Key，单个模型可以覆盖自己的 Host / Key：

```text
Provider 默认配置
  ↓
模型专用配置优先
  ↓
生成最终运行配置
```

示例：

```text
分析模型：gpt-6-astra
模型专用 Host：中转 Responses 地址
用途：分析

修图模型：qwen-image-3.0
模型专用 Host：阿里百炼 compatible-mode/v1 地址
用途：修图
```

## 9. 当前实现状态

### 已完成并可演示

- 摄影工作台 UI
- 中文产品界面
- 项目、照片库和工作流工具栏
- 客户反馈 ID 选择
- RAW / JPG 配对和元数据
- 基础调色和自动白平衡
- LUT、风格预设和参考图追色
- 智能选片和相似照片分组
- 批处理、任务队列和失败重试
- Agent / Editor 双入口
- AgentPlan 和 Tool Trace
- Qwen Image 3.0 修图适配
- 前后对比和可拖动分割线
- 百分比缩放控制
- README、Logo 和产品开发文档

### 已接入但需要继续验证

- 百炼不同地域和 Workspace 配置
- Qwen Image 3.0 / Pro 的尺寸和多图输入
- 多张照片批量 AI 修图
- 失败任务跨进程恢复
- 不同模型的提示词和图片保真度

### 尚未完成

- 完整自主 Agent Engine
- Responses API 统一迁移
- FLUX / GPT Image / GLM Image Provider
- Agent 评测和回归测试
- 成本、延迟、Token、模型质量统计
- 生产级鉴权、限流、审计和隐私保护
- Redis / Temporal 等跨进程任务队列

## 10. 下一阶段开发顺序

### P0：先保证 AI 闭环稳定

1. 完成 Qwen Image 3.0 不同场景的真实测试。
2. 为分析和修图增加请求超时、失败状态和可读错误。
3. 增加图片下载失败、尺寸不一致和空响应处理。
4. 保存模型、Provider、耗时、任务 ID 和结果状态。

### P1：完成真正 Agent Engine

1. 使用结构化输出生成 AgentPlan。
2. 建立统一 Tool Registry。
3. 实现 Planner → Executor → Validator → Replanner 循环。
4. 为 AI 修图和批处理增加人工确认节点。
5. 对每一步保存输入、输出、参数和失败原因。

### P2：补齐简历级工程能力

1. 建立 20～50 张测试图片的评测集。
2. 统计分析 JSON 成功率、图片输出成功率和工具调用成功率。
3. 统计延迟、成本、失败重试率和人工满意度。
4. 增加 Docker 部署和 API 文档。
5. 增加不同图片模型的效果对比页面。

## 11. 验收指标

非 AI：

- JPG / RAW 配对准确率
- RAW 预览生成成功率
- 批量处理成功率
- 批量导出成功率
- 调色参数恢复准确率
- 相似照片分组准确率

AI：

- 图片分析结构化输出成功率
- 图片编辑输出成功率
- 原图尺寸保持率
- 人物 / 构图保持率
- Agent 计划执行成功率
- 工具调用成功率
- 失败重试成功率
- 平均延迟和 API 成本
- 人工满意度

## 12. 简历定位

推荐表述：

> 独立设计并开发面向摄影师的模块化多模态 AI 图片创作工作台，构建从 RAW/JPG 素材管理、客户反馈 ID 选片、基础调色、LUT 风格化、参考图追色到 Qwen Image 3.0 AI 修图的完整工作流；实现 AgentPlan、Tool Runner、批处理队列、任务持久化、结果校验和多模型 Provider 配置，形成可复现的 AI 摄影后期应用原型。

当前不建议表述为：

```text
完整自主 Agent 平台
大模型训练系统
生产级分布式 AI 基础设施
```

在完成 Planner → Executor → Validator → Replanner、多模型评测和生产部署后，再升级为完整 Agent 平台定位。
