# 数据结构设计文档

本文档维护 Foundry Knowledge Base 的核心数据结构。后续新增功能前，应先更新本文件，再进入代码实现。

## 设计原则

- 先定义稳定的数据对象，再开发前端展示和后端接口。
- 原始对话内容、检索过程、结构化输出分层存储。
- 对话消息保留通用 `metadata`，但重要结构必须有明确 schema。
- 新功能优先通过 `mode` 和 `structured_output` 扩展，避免把所有功能硬塞进单一问答字段。
- 结构化数据应尽量可复用到项目空间、报告生成和知识卡片。

## 多知识源基础结构

当前系统已开始从单一 ASM 手册知识库升级为多知识源架构。第一步先兼容现有数据，不拆分 chunk 表。

核心原则：

- 文档源、业务资产、项目产物分表存储。
- 检索 chunk 统一保存在 `chunks` 表。
- 通过 `source_type`、`source_id`、`document_id`、`evidence_level` 区分来源和可信度。

当前已落地：

| 表 / 字段 | 用途 | 当前状态 |
| --- | --- | --- |
| `knowledge_sources` | 知识源总表 | 已新增 |
| `document_sources.source_type` | 文档来源类型 | 已新增，现有 ASM 文档为 `standard_manual` |
| `chunks.source_type` | chunk 来源类型 | 已新增，现有 33037 条 chunk 为 `standard_manual` |
| `chunks.document_id` | 未来文档语义 ID | 已新增，当前回填为 `source_id` |
| `chunks.evidence_level` | 证据可信层级 | 已新增，当前为 `standard` |
| `evidence_cards` | 项目证据卡片 | 已新增空表，后续项目证据库使用 |

当前默认知识源：

```text
knowledge_sources.name = ASM Handbook Vol.2
knowledge_sources.source_type = standard_manual
knowledge_sources.visibility = public
```

后续新增企业历史项目知识库时，不再新建独立 chunk 表，而是写入统一 `chunks` 表，并设置：

```text
source_type = enterprise_project
evidence_level = validated_project / project_note / unverified
```

## 任务模式

第一阶段建议支持 4 个模式：

```ts
type TaskMode =
  | "qa"
  | "requirement_clarification"
  | "solution_draft"
  | "selection_matrix"
  | "defect_diagnosis"
```

后续可扩展：

```ts
type TaskMode =
  | "qa"
  | "requirement_clarification"
  | "solution_draft"
  | "selection_matrix"
  | "defect_diagnosis"
  | "material_card"
```

模式含义：

| mode | 含义 | 首期是否实现 |
| --- | --- | --- |
| `qa` | 普通知识库问答 | 已有 |
| `requirement_clarification` | 客户需求澄清 | 建议下一步实现 |
| `solution_draft` | 方案草案生成 | 建议下一步实现 |
| `selection_matrix` | 材料/工艺选型矩阵 | 首期实现 |
| `defect_diagnosis` | 缺陷与失效诊断 | 首期实现 |
| `material_card` | 材料知识卡片 | 后续 |

## 前端状态结构

### ChatState

```ts
interface ChatState {
  messages: ChatMessage[]
  modeSessions: Record<TaskMode, ModeSession>
  conversations: ConversationSummary[]
  currentConvId: number | null
  currentMode: TaskMode
  isProcessing: boolean
  showProgress: boolean
  progressSteps: ProgressSteps
  logs: ProcessLog[]
}
```

当前系统已有 `messages`、`conversations`、`currentConvId`、`isProcessing`、`progressSteps`、`logs`。下一步需要增加：

```ts
currentMode: TaskMode
```

### ModeSession

三种任务模式必须隔离短期上下文，避免知识问答中的材料实体污染需求澄清或方案草案：

```ts
interface ModeSession {
  messages: ChatMessage[]
  currentConvId: number | null
  showProgress: boolean
  progressSteps: ProgressSteps
  logs: ProcessLog[]
}
```

规则：

- `qa`、`requirement_clarification`、`solution_draft`、`selection_matrix`、`defect_diagnosis` 各维护一份 `ModeSession`。
- 切换模式时只切换当前工作区，不把其他模式的 `messages` 作为 `history` 发送。
- 新建对话只清空当前模式的 session。
- 历史消息通过 `metadata.mode` 恢复到对应模式。
- 旧消息没有 `metadata.mode` 时按 `qa` 兼容。

### ChatMessage

```ts
interface ChatMessage {
  role: "user" | "assistant" | "system"
  content: string
  metadata: MessageMetadata
}
```

### MessageMetadata

```ts
interface MessageMetadata {
  schema_version?: "1.0"
  mode?: TaskMode
  question?: string
  citations?: Citation[]
  thinking?: string
  graph?: KnowledgeGraph
  logs?: ProcessLog[]
  retrieval?: RetrievalTrace
  structured_output?: StructuredOutput
}
```

说明：

- `content` 用于人类可读正文。
- `structured_output` 用于方案、澄清清单、选型矩阵等可结构化渲染内容。
- `metadata.mode` 决定前端使用哪种展示组件。

## 检索过程结构

### RetrievalTrace

```ts
interface RetrievalTrace {
  original_query: string
  resolved_query: string
  core_entity: string[]
  filter_rule: string
  search_queries: string[]
  search_priority: "关键词优先" | "语义均衡" | string
  mode?: TaskMode
  context_scope?: string
  task_intent?: string
  used_history: boolean
  candidate_count?: number
  selected_count?: number
  top_hits?: RetrievalHit[]
  repair_reason?: string
  repair_history?: RepairAttempt[]
  rerank?: RerankTrace
}
```

### RetrievalHit

```ts
interface RetrievalHit {
  page: number | null
  score: number
  section: string
  reason: string
}
```

### RepairAttempt

```ts
interface RepairAttempt {
  attempt: number
  reason: string
  previous_queries: string[]
  search_queries: string[]
  candidate_count: number
  selected_count: number
}
```

### RerankTrace

```ts
interface RerankTrace {
  enabled: boolean
  strategy: "cross_encoder" | "preserve_multi_entity" | "entity_quota" | string
  reason?: string
  model?: string
}
```

当前多实体比较会跳过全局 reranker，后续建议升级为 `entity_quota`。

## 引用结构

### Citation

```ts
interface Citation {
  index?: number
  chunk_id?: string
  source_id?: number
  page?: number
  type?: string
  text?: string
  score?: number
  section?: string
}
```

引用应满足：

- 可定位 PDF。
- 可展示片段。
- 可回溯到检索 query 和上下文选择过程。

后续可扩展：

```ts
interface Citation {
  matched_query?: string
  rerank_score?: number
  highlight_text?: string
  source_title?: string
}
```

## 结构化输出

### StructuredOutput

```ts
type StructuredOutput =
  | RequirementClarificationOutput
  | SolutionDraftOutput
  | SelectionMatrixOutput
  | DefectDiagnosisOutput
  | MaterialCardOutput
```

### RequirementClarificationOutput

用于客户需求澄清模式。

```ts
interface RequirementClarificationOutput {
  type: "requirement_clarification"
  known_conditions: RequirementCondition[]
  missing_conditions: MissingCondition[]
  risks: RiskItem[]
  questions_to_ask: ClarificationQuestion[]
  preliminary_direction: DirectionItem[]
  next_steps: string[]
}
```

```ts
interface RequirementCondition {
  field: string
  value: string
  confidence: "high" | "medium" | "low"
  evidence?: string
}
```

```ts
interface MissingCondition {
  field: string
  reason: string
  priority: "high" | "medium" | "low"
}
```

```ts
interface ClarificationQuestion {
  question: string
  why_it_matters: string
  priority: "high" | "medium" | "low"
}
```

### SolutionDraftOutput

用于方案草案模式。

```ts
interface SolutionDraftOutput {
  type: "solution_draft"
  requirement_summary: string
  operating_conditions: RequirementCondition[]
  candidate_materials: CandidateMaterial[]
  recommended_processes: ProcessRecommendation[]
  risks: RiskItem[]
  alternatives: AlternativeOption[]
  evidence: Citation[]
  open_questions: ClarificationQuestion[]
  next_steps: string[]
}
```

```ts
interface CandidateMaterial {
  name: string
  reason: string
  advantages: string[]
  limitations: string[]
  confidence: "high" | "medium" | "low"
  citations?: number[]
}
```

```ts
interface ProcessRecommendation {
  process: string
  reason: string
  parameters?: string[]
  citations?: number[]
}
```

```ts
interface RiskItem {
  risk: string
  impact: string
  mitigation: string
  priority: "high" | "medium" | "low"
  citations?: number[]
}
```

```ts
interface AlternativeOption {
  option: string
  when_to_choose: string
  tradeoff: string
}
```

### SelectionMatrixOutput

用于材料/工艺选型矩阵。它不是普通问答正文，而是面向工程决策的候选项对比表。

```ts
interface SelectionMatrixOutput {
  type: "selection_matrix"
  requirement_summary: string[]
  criteria: string[]
  rows: SelectionMatrixRow[]
  recommendation: string
  decision_notes: string[]
  open_questions: string[]
}
```

```ts
interface SelectionMatrixRow {
  candidate: string
  category?: "material" | "process" | "material_process" | "unknown"
  fit_score?: number // 0-100
  criteria_scores?: Record<string, "high" | "medium" | "low" | "unknown">
  advantages: string[]
  risks: string[]
  process_fit: string
  cost_level: "low" | "medium" | "high" | "unknown"
  evidence: string[]
  citations?: number[]
}
```

显示规则：

- `criteria` 作为矩阵列或评估维度。
- `rows` 作为候选材料/工艺路线。
- `fit_score` 不存在时前端显示 `待评估`，不能用模型臆造分数。
- `evidence` 必须保留引用编号或页码描述。
- `open_questions` 用于提示工程师继续补充约束。

### DefectDiagnosisOutput

用于缺陷与失效诊断。它面向铸造现场问题排查，不是单纯解释缺陷定义。

```ts
interface DefectDiagnosisOutput {
  type: "defect_diagnosis"
  symptom_summary: string[]
  possible_causes: DefectCause[]
  inspection_steps: string[]
  process_checks: string[]
  corrective_actions: string[]
  missing_field_info: string[]
  severity?: "high" | "medium" | "low" | "unknown"
}
```

```ts
interface DefectCause {
  cause: string
  likelihood: "high" | "medium" | "low"
  evidence: string
  inspection_method?: string
  corrective_action?: string
  citations?: number[]
}
```

显示规则：

- `possible_causes` 以诊断表展示，不能只罗列原因名。
- `inspection_steps` 用于现场排查顺序。
- `process_checks` 用于工艺参数、熔炼、浇注、热处理、模具/砂型等检查点。
- `corrective_actions` 用于改进建议。
- `missing_field_info` 必须列出还需要用户补充的现场信息。

### MaterialCardOutput

后续用于材料知识卡片。

```ts
interface MaterialCardOutput {
  type: "material_card"
  material_name: string
  composition?: string[]
  mechanical_properties?: string[]
  heat_treatment?: string[]
  casting_or_processing_fit?: string[]
  applications?: string[]
  advantages?: string[]
  limitations?: string[]
  citations?: number[]
}
```

## 数据库现状

当前已有核心表：

### users

用户表。

核心字段：

- `id`
- `email`
- `username`
- `password_hash`
- `email_verified`
- `created_at`
- `last_login`
- `is_active`

### conversations

对话表。

核心字段：

- `id`
- `user_id`
- `title`
- `created_at`
- `updated_at`

### conversation_messages

消息表。

核心字段：

- `id`
- `conversation_id`
- `role`
- `content`
- `metadata JSONB`
- `created_at`

当前建议暂时继续使用 `metadata JSONB` 承载模式和结构化输出，不立刻拆表。

## 数据库扩展建议

第一阶段可以仅扩展现有表：

```sql
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'qa';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS project_id INT;
```

消息结构继续写入：

```json
{
  "schema_version": "1.0",
  "mode": "solution_draft",
  "retrieval": {},
  "structured_output": {}
}
```

项目空间第一版已落地，项目表用于承载客户项目、工程主题和后续报告沉淀：

### projects

```sql
CREATE TABLE projects (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  customer_name TEXT DEFAULT '',
  description TEXT DEFAULT '',
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### conversations.project_id

对话历史现在支持绑定到项目空间。未指定项目时保持 `NULL`，兼容原来的普通知识问答历史。

```sql
ALTER TABLE conversations ADD COLUMN project_id INT;
CREATE INDEX idx_conv_project ON conversations(project_id);
```

约定：

- 用户选中项目后，新建对话会自动写入当前 `project_id`。
- 已存在的对话继续使用原有 `project_id`，不会因为前端切换项目被中途改绑。
- 项目详情会返回该项目下的对话列表，方便从项目空间恢复检索过程。

### solution_artifacts

旧设计中曾使用 `solution_artifacts` 作为命名。当前实现统一为更通用的 `project_artifacts`，用于保存知识问答、需求澄清、方案草案、选型矩阵、缺陷诊断等结构化产物。

```sql
CREATE TABLE project_artifacts (
  id SERIAL PRIMARY KEY,
  project_id INT REFERENCES projects(id) ON DELETE CASCADE,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  artifact_type TEXT NOT NULL DEFAULT 'qa',
  title TEXT NOT NULL DEFAULT '未命名产物',
  content TEXT NOT NULL DEFAULT '',
  structured_data JSONB DEFAULT '{}',
  citations JSONB DEFAULT '[]',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

字段约定：

- `artifact_type`：对应前端/Agent 的任务模式或项目级产物，如 `qa`、`requirement_clarification`、`solution_draft`、`selection_matrix`、`defect_diagnosis`、`project_brief`。
- `content`：回答正文 Markdown。
- `structured_data`：结构化输出，例如方案步骤、选型矩阵、缺陷诊断表。
- `citations`：引用来源卡片数据。
- `metadata`：保存原问题、检索解释、知识图谱等辅助信息。

## 前端展示策略

第一阶段采用“同一工作台 + 模式切换”：

```text
知识问答 / 需求澄清 / 方案草案
```

原因：

- 对当前架构侵入小。
- 可以复用聊天输入、SSE、历史记录、引用展示。
- 用户能在同一上下文中切换任务。

项目空间当前采用“同一工作台 + 右侧项目面板”：

```text
侧栏项目列表 -> 右侧项目详情面板 -> 项目概览 / 项目简报 / 项目内对话 / 五类产物分区
```

项目概览第一版不新增持久化表，而是由前端根据 `project_artifacts` 的 `artifact_type`、`structured_data`、`citations` 和项目内 `conversations` 派生：

- 当前阶段：根据已沉淀产物类型判断为项目初始化、资料检索、需求澄清、方案形成、选型决策或现场诊断。
- 候选材料 / 工艺：来自方案草案的 `candidate_materials`、`recommended_processes` 和选型矩阵的候选项。
- 关键风险：来自 `risks`、缺陷诊断 `possible_causes`。
- 待确认问题：来自 `missing_conditions`、`questions_to_ask`、`open_questions`、`missing_field_info`。
- 项目简报预览：由当前项目名称、阶段、产物数量、候选项、风险、待确认问题和初步结论拼装生成。
- 正式项目简报：调用项目级 LLM 生成接口后，以 `project_brief` 类型保存回 `project_artifacts`。

### 项目证据库 V1

第一版项目证据库不新增后端表，由前端在项目详情面板中从 `project_artifacts.citations` 派生：

```text
project_artifacts[] -> citations[] -> evidence items
```

派生规则：

- 遍历当前项目下所有产物的 `citations`。
- 按 `source_id + page + text[:180]` 去重，避免同一手册页片段在多个回答里重复堆叠。
- 保留来源产物标题、产物类型、页码、引用片段、`source_type`、`evidence_level`。
- 根据引用片段和产物内容推断标签：材料、性能、热处理、铸造工艺、腐蚀、缺陷风险、标准依据。
- 点击证据卡片打开 PDF 查看器，并定位到对应页。

V1 的定位是“项目内证据聚合视图”，不允许用户手动编辑证据。后续若需要人工确认、备注、可靠性评级和跨项目复用，再升级为持久化的 `evidence_cards`。

### Evidence Cards V2

第二版项目证据库开始使用持久化 `evidence_cards`，用于把自动引用升级为工程师确认过的项目依据。

```sql
CREATE TABLE evidence_cards (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  project_id INT REFERENCES projects(id) ON DELETE CASCADE,
  knowledge_source_id INT REFERENCES knowledge_sources(id),
  document_id INT,
  artifact_id INT REFERENCES project_artifacts(id) ON DELETE SET NULL,
  title TEXT NOT NULL DEFAULT '未命名证据',
  evidence_type TEXT NOT NULL DEFAULT 'general',
  page INT,
  section TEXT DEFAULT '',
  quote TEXT NOT NULL DEFAULT '',
  summary TEXT DEFAULT '',
  tags JSONB DEFAULT '[]',
  reliability TEXT DEFAULT 'medium',
  note TEXT DEFAULT '',
  status TEXT DEFAULT 'draft',
  usable_in_report BOOLEAN DEFAULT FALSE,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

字段约定：

- `quote`：来自手册、项目文档或结构化资产的原始依据片段。
- `summary`：证据摘要，便于报告和项目简报引用。
- `note`：工程师备注，例如适用边界、限制条件、现场判断。
- `reliability`：`high`、`medium`、`low`。
- `status`：`draft`、`confirmed`、`archived`。
- `usable_in_report`：是否允许进入项目简报/报告生成。
- `metadata.source_key`：前端从 `source_id + page + quote` 生成的去重键，用于判断自动引用是否已保存。

当前前端策略：

- “引用依据”仍显示自动聚合的 citations。
- 点击“保存证据”后写入 `evidence_cards`。
- 已保存卡片展示在“已确认证据”区。
- 用户可以调整可靠性、备注和“可用于报告”。

项目简报使用策略：

- `usable_in_report = true` 的证据卡会优先进入项目简报生成上下文。
- 项目简报保存为 `project_artifacts` 时，会在 `structured_data.report_evidence_count` 和 `metadata.report_evidence_count` 中记录使用的证据数量。
- `metadata.citation_source = evidence_cards` 表示本次简报优先使用了已确认证据。
- 若没有可用于报告的证据卡，生成链路回退到项目产物中的普通 `citations`。

## 开发约定

新增功能前必须先更新：

1. 本文档的数据结构。
2. `docs/system-interfaces.md` 中的接口契约。
3. 如涉及页面和交互，再更新产品或前端设计文档。

代码实现时必须保证：

- 旧 `qa` 模式兼容。
- 历史消息能加载旧 metadata。
- 新字段全部可选。
- 前端渲染遇到未知 `structured_output.type` 时降级为普通 Markdown。
## Engineering Documents V1

第一版工程文档导入用于把解决方案工程师的现场记录、实验记录、验证报告、工艺脑图等材料先挂到当前项目下面，而不是立即进入全局知识库检索。

### engineering_documents

```sql
CREATE TABLE engineering_documents (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  project_id INT REFERENCES projects(id) ON DELETE CASCADE,
  artifact_id INT REFERENCES project_artifacts(id) ON DELETE SET NULL,
  title TEXT NOT NULL DEFAULT '未命名工程文档',
  original_filename TEXT NOT NULL DEFAULT '',
  document_kind TEXT NOT NULL DEFAULT 'engineering_case',
  source_type TEXT NOT NULL DEFAULT 'current_project',
  storage_backend TEXT NOT NULL DEFAULT 'local',
  bucket TEXT NOT NULL DEFAULT '',
  object_key TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT '',
  mime_type TEXT DEFAULT '',
  file_size BIGINT DEFAULT 0,
  parse_status TEXT DEFAULT 'pending',
  extracted_text TEXT DEFAULT '',
  structured_data JSONB DEFAULT '{}',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

字段约定：
- `storage_backend`：当前为 `local`，后续可切换为 `minio` 或 `s3`。
- `bucket/object_key`：保留对象存储契约，避免以后从本地迁到 MinIO 时改业务表。
- `content_hash`：SHA-256，用于去重、审计和后续文件一致性检查。
- `document_kind`：`engineering_case`、`process_mindmap`、`customer_note`、`validation_report`。
- `source_type`：当前项目内资料先使用 `current_project`，未来历史项目库可使用 `enterprise_project`。
- `parse_status`：`parsed` 表示已抽取文本，`stored` 表示已保存原文件但暂未 OCR/解析。
- `artifact_id`：导入后自动生成的 `project_artifacts.engineering_case` 产物。

`structured_data` 当前保存确定性解析结果和工程语义初筛：
- `raw_blocks`：按 Word 原始顺序抽取的标题、段落、列表项、表格、图片块。
- `tables`：表格行列结构，保留 `row_text`、`headers`、行数、列数。
- `images`：Word 内图片关系和文件名，当前不做 OCR。
- `outline`：根据 Word heading 样式或大纲级别识别出的标题层级。
- `statistics`：块数量、表格数量、图片数量、标题数量。
- `experiment_conditions / observations / conclusions / variables`：基于规则从原文和表格中抽出的工程初筛字段。

Word 解析不依赖 LLM，使用 `.docx` 内部的 Office Open XML：

```text
word/document.xml        正文块、段落、表格、图片引用
word/styles.xml          标题样式和段落样式
word/_rels/*.rels        图片和外部关系
```

后续 LLM 只在 `raw_blocks/tables` 的基础上做工程语义归纳，不直接替代确定性解析。

### 本地对象存储约定

当前简单版不依赖 MinIO，文件保存到：

```text
storage/objects/projects/{project_id}/engineering_cases/original/{yyyy}/{mm}/{dd}/{hash}-{filename}
```

`storage/` 已加入 `.gitignore`，原始工程文件不进入 Git。
