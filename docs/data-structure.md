# 数据结构设计文档

本文档维护 Foundry Knowledge Base 的核心数据结构。后续新增功能前，应先更新本文件，再进入代码实现。

## 设计原则

- 先定义稳定的数据对象，再开发前端展示和后端接口。
- 原始对话内容、检索过程、结构化输出分层存储。
- 对话消息保留通用 `metadata`，但重要结构必须有明确 schema。
- 新功能优先通过 `mode` 和 `structured_output` 扩展，避免把所有功能硬塞进单一问答字段。
- 结构化数据应尽量可复用到项目空间、报告生成和知识卡片。

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

第二阶段再增加项目表：

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

### solution_artifacts

用于保存方案草案、选型矩阵、需求澄清结果等结构化产物。

```sql
CREATE TABLE solution_artifacts (
  id SERIAL PRIMARY KEY,
  project_id INT REFERENCES projects(id) ON DELETE CASCADE,
  conversation_id INT REFERENCES conversations(id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  title TEXT DEFAULT '',
  content TEXT DEFAULT '',
  structured_data JSONB DEFAULT '{}',
  citations JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 前端展示策略

第一阶段采用“同一工作台 + 模式切换”：

```text
知识问答 / 需求澄清 / 方案草案
```

原因：

- 对当前架构侵入小。
- 可以复用聊天输入、SSE、历史记录、引用展示。
- 用户能在同一上下文中切换任务。

第二阶段再增加“项目空间”页面：

```text
项目列表 -> 项目详情 -> 需求 / 对话 / 方案 / 引用 / 图谱
```

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
