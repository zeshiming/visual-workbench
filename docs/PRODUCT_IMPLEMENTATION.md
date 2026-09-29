# AI 图片创作工作台

## 产品实现文档

版本：1.0  
更新时间：2026-09-29

## 1. 产品定位

AI 图片创作工作台是一款面向摄影师、影像工作室和视觉创作者的模块化图片后期工具。

产品将能力分成三类：

1. 确定性图像算法：调色、配对、追色、LUT、批量导出。
2. AI Agent：理解自然语言、分析图片、制定方案、选择工具。
3. AI 图像模型：局部修图、生成填充等复杂语义编辑。

核心流程：

~~~text
导入照片 → 照片理解与选片 → 基础调色 → 追色 / 风格化
        → AI 局部修图 → 结果检查 → 批量导出
~~~

## 2. 信息架构

~~~text
照片
├── 文件夹 / 多文件导入
├── 联系表
├── 客户编号选片
├── 全部照片 / JPG+RAW / 仅 RAW / 仅 JPG
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
├── cube LUT
└── 批量套用

AI 修图
├── Agent
└── Editor
~~~

生成填充暂未接入，必须保持明确的不可用状态。

## 3. 界面结构

~~~text
顶部：项目 / 导入 / 保存 / 撤回 / 导出 / 设置

项目栏 | 工作流入口 | 主工作区 | 当前模式参数面板
       | 照片     | 联系表 / 大图 | 照片选择
       | 调色     | 原图 / 对比  | 调色参数
       | 追色     | 缩略图      | 参考图
       | 风格     | 处理状态    | LUT / 预设
       | AI修图   |             | Agent / Editor
~~~

项目栏只负责项目管理，工作流入口只负责模式切换，右侧面板只显示当前模式工具。

## 4. 非 AI 图像管线

### RAW / JPG

支持 ARW、CR2、CR3、DNG、NEF、ORF、PEF、RAF、RW2、SRW。

同名文件自动配对：

~~~text
DSC03405.JPG + DSC03405.ARW → 同一 pairGroup
~~~

原片不修改，RAW 使用 rawpy / LibRaw 生成 JPEG 预览，同时读取尺寸、ISO、快门、光圈、焦距、镜头和 EXIF。

### 基础调色

调色参数：

~~~text
exposure
contrast
highlights
shadows
saturation
temperature
tint
~~~

拖动时使用预览，松开后生成完整分辨率结果。原图进入撤回历史，编辑版本单独保存。

### 自动白平衡

采用采样后的 Gray World 方法：

1. 忽略透明、极暗和高光溢出像素。
2. 计算 RGB 均值。
3. 估计色温和色调偏移。
4. 通过基础调色管线执行。

### LUT / 风格预设

支持自然、暖胶片、冷电影、柔和人像等预设，以及 cube 3D LUT 三线性采样。

后续可接入 OpenColorIO，统一 ICC、ACES 和不同色彩空间。

### 参考图追色

当前使用 RGB 均值 / 标准差颜色迁移：

~~~text
目标图统计 + 参考图统计
→ 通道颜色迁移
→ 保留目标图结构和构图
~~~

后续升级到 Lab / Oklab 和肤色保护。

## 5. 智能选片

当前评分：

- 清晰度
- 曝光中性度
- 对比度
- 感知哈希相似度

流程：

~~~text
缩略图采样 → 质量评分 → 相似图分组 → 每组保留最高分
~~~

后续增强：

- 人脸检测
- 闭眼检测
- 人脸质量评分
- 连拍时间和 EXIF 辅助分组
- 构图和主体评分

## 6. AI Agent 架构

~~~text
用户需求
  ↓
任务路由器
  ↓
上下文收集
  ↓
结构化计划
  ↓
工具路由器
  ↓
本地算法 / AI Tool / Skill / MCP
  ↓
结果校验
  ↓
重试、人工确认或导出
~~~

本地算法负责确定性操作；AI 负责理解需求、选择工具、识别主体和复杂语义编辑；Skill 固化摄影工作流；MCP 连接外部服务。

### Agent 框架选型

当前项目不直接引入 LangChain 全家桶，而采用与现有 FastAPI / Pydantic / LiteLLM 兼容的分层方案：

```text
PydanticAI       Agent、工具调用、结构化输出和参数校验
LiteLLM           多 Provider / 多模型适配
FastAPI           API、流式进度和权限边界
自定义 Tool      摄影专用本地算法和 AI 工具
LangGraph        后续复杂状态图、人工审批和可恢复流程时再引入
Temporal         后续长时间批处理、断点恢复和可靠重试时再引入
MCP SDK          外部文件、云服务和第三方工具接入
```

选择原则：先用 PydanticAI 做类型安全的 Agent；不为了“使用框架”而引入多 Agent。只有当工作流出现长时间运行、复杂分支或跨会话恢复需求时，才增加 LangGraph / Temporal。

工具注册表：

~~~text
select_assets_by_id
read_asset_metadata
analyze_histogram
estimate_white_balance
apply_adjustments
apply_lut
match_reference_color
score_photo_quality
group_similar_photos
edit_selected_region
generate_fill
export_assets
~~~

示例计划：

~~~json
{
  "task": "batch_photo_processing",
  "steps": [
    {
      "tool": "select_assets_by_id",
      "executor": "local",
      "params": { "ids": ["3405", "3406", "3407"] }
    },
    {
      "tool": "match_reference_color",
      "executor": "local",
      "params": { "referenceId": "reference-1" }
    },
    {
      "tool": "apply_adjustments",
      "executor": "local",
      "params": { "exposure": 8, "highlights": -12 }
    },
    {
      "tool": "export_assets",
      "executor": "local",
      "params": { "format": "zip" }
    }
  ],
  "requiresApproval": true
}
~~~

每次任务需要校验图片是否存在、尺寸是否一致、是否有空文件、是否有失败照片，并支持重试。

## 7. 项目代码结构

~~~text
apps/web/src/
├── components/
│   ├── WorkspaceToolRail.vue
│   ├── AssetLibrary.vue
│   ├── WorkspaceRightSidebar.vue
│   └── WorkspaceImageViewport.vue
├── lib/
│   ├── image-adjustments.ts
│   ├── image-curation.ts
│   ├── workspace-ui-state.ts
│   ├── workspace-mode-state.ts
│   └── api-client.ts
└── views/
    └── WorkspaceView.vue

apps/api/src/
├── routers/
│   ├── assets.py
│   ├── agent.py
│   ├── editor.py
│   └── workspaces.py
├── core/
│   └── orchestration.py
├── agent/
│   ├── state.py
│   ├── router.py
│   ├── planner.py
│   ├── orchestrator.py
│   ├── tools/
│   ├── validators/
│   └── trace.py
├── services/
│   └── ai_client.py
└── models/
    └── settings.py
~~~

Agent 目录是下一阶段的主要工程化改造点：把当前两阶段 Agent 调用升级为 Router → Planner → Tools → Validator，并保留现有 API 兼容层。

## 8. 数据模型

核心对象：

~~~text
Workspace
Asset
AssetPair
AssetMetadata
AdjustmentProfile
StylePreset
ReferenceImage
ProcessingJob
AgentRun
ValidationReport
~~~

每张照片的调色参数需要独立保存：

~~~text
workspace_id
asset_id
exposure
contrast
highlights
shadows
saturation
temperature
tint
lut_id
updated_at
~~~

## 9. 当前实现状态

已实现：

- 项目和素材库
- 文件夹 / 多文件导入
- 联系表和客户编号选片
- JPG / RAW 配对
- RAW 预览和元数据
- 批量调色和 ZIP 导出
- 自动白平衡和直方图
- 风格预设和 cube LUT
- 参考图追色和批量追色
- 智能选片和相似照片分组
- 每张素材独立调色参数
- Agent / Editor 独立入口
- `.cube` LUT 导入和本地风格预设
- 真实 RAW 上传、预览、元数据和 JPG+RAW 配对冒烟验证

后续增强：

- 文件夹索引和重新扫描
- 后端长任务队列、暂停、取消、重试
- Lab / Oklab 和 ICC 色彩管理
- 人脸、闭眼、主体和构图评分
- Agent Router → Planner → Tools → Validator 闭环
- PydanticAI 工具注册和结构化计划
- LangGraph 状态图（仅在需要复杂分支 / 人工审批时）
- Temporal 长任务队列（仅在批处理规模超过单请求能力时）
- 运行 Trace、成本、延迟和成功率评测

## 10. 验收指标

非 AI：

- JPG / RAW 配对准确率
- RAW 预览生成成功率
- 批量处理成功率
- 批量导出成功率
- 调色参数恢复准确率
- 相似照片分组准确率

AI：

- 图片分析 JSON 成功率
- 图片输出成功率
- Agent 计划执行成功率
- 工具调用成功率
- 失败重试成功率
- 平均延迟和 API 成本
- 人工满意度

## 11. 简历定位

> 独立设计并开发面向摄影师的模块化多模态 AI 图片创作工作台，构建从 RAW/JPG 素材管理、智能选片、批量调色、自动白平衡、LUT 风格化、参考图追色到 AI 局部修图的完整工作流；结合本地图像算法、RAW 解码、Agent 工具调用、结构化计划、结果校验和批处理任务，形成可复现的 AI 摄影后期系统。
