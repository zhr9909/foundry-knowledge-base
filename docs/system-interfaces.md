# 系统接口设计文档

本文档维护 Foundry Knowledge Base 的系统接口、SSE 事件契约和前后端交互约定。后续新增功能前，应先更新本文件，再进入代码实现。

## 接口设计原则

- 保持现有问答接口兼容。
- 新能力优先通过 `mode` 参数扩展，而不是新增大量重复接口。
- SSE 事件必须稳定、可增量渲染、可记录到历史。
- 结构化输出通过 `structured_output` 返回，普通正文仍使用 `answer`。
- 检索过程通过 `retrieval` 返回，供前端诊断面板展示。
- 后端接口应能支持未来“项目空间”，但第一版不强依赖项目表。

## 当前接口概览

| 方法 | 路径 | 用途 | 状态 |
| --- | --- | --- | --- |
| `GET` | `/` | 跳转到静态前端 | 已有 |
| `GET` | `/health` | 健康检查 | 已有 |
| `GET` | `/sections` | 文档章节列表 | 已有 |
| `POST` | `/chat` | 非流式问答 | 已有但前端主要不用 |
| `GET` | `/chat/stream` | SSE 流式问答 | 主要接口 |
| `GET` | `/pdf/{source_id}` | PDF 文件查看 | 已有 |
| `POST` | `/api/auth/register` | 注册 | 已有 |
| `POST` | `/api/auth/login` | 登录 | 已有 |
| `GET` | `/api/auth/me` | 当前用户 | 已有 |
| `GET` | `/api/conversations` | 对话列表 | 已有 |
| `POST` | `/api/conversations` | 新建对话 | 已有 |
| `GET` | `/api/conversations/{id}` | 对话详情 | 已有 |
| `PUT` | `/api/conversations/{id}` | 更新标题 | 已有 |
| `DELETE` | `/api/conversations/{id}` | 删除对话 | 已有 |
| `POST` | `/api/conversations/{id}/messages` | 保存消息 | 已有 |

## 任务模式接口约定

下一步新增任务模式参数：

```ts
type TaskMode =
  | "qa"
  | "requirement_clarification"
  | "solution_draft"
  | "selection_matrix"
  | "defect_diagnosis"
```

未来扩展：

```ts
type TaskMode =
  | "qa"
  | "requirement_clarification"
  | "solution_draft"
  | "selection_matrix"
  | "defect_diagnosis"
  | "material_card"
```

### `GET /chat/stream`

当前参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `query` | string | 是 | 用户输入 |
| `section` | string | 否 | 章节过滤 |
| `conv_id` | string | 否 | 对话 ID |
| `token` | string | 否 | 登录 token |
| `history` | JSON string | 否 | 最近历史消息 |

新增参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | TaskMode | 否 | `qa` | 当前任务模式 |
| `project_id` | number | 否 | 无 | 当前项目空间 ID |

`project_id` 当前已启用：当前端选中项目且本轮没有已有 `conv_id` 时，后端自动创建的新对话会写入该项目。已有 `conv_id` 的连续追问沿用原对话归属。

请求示例：

```text
/chat/stream?query=客户想做耐腐蚀泵体&mode=requirement_clarification
```

方案草案示例：

```text
/chat/stream?query=海水泵体，80℃，预算中等&mode=solution_draft
```

### 后端处理规则

| mode | 后端策略 |
| --- | --- |
| `qa` | 现有 RAG 问答流程 |
| `requirement_clarification` | 需求理解 + 必要 RAG + 结构化澄清输出 |
| `solution_draft` | 需求理解 + RAG 检索 + 方案草案输出 |
| `selection_matrix` | 多候选材料/工艺检索 + 选型矩阵输出 |
| `defect_diagnosis` | 缺陷原因检索 + 诊断步骤输出 |
| `material_card` | 材料信息聚合 + 知识卡片输出 |

### 模式隔离规则

`mode` 不是简单的前端展示标签，而是工作流边界：

- 前端按 `TaskMode` 维护独立 session，发送 `history` 时只发送当前模式的消息。
- `qa` 用于精确知识问答，查询拆解以材料、牌号、工艺、性能指标为中心。
- `requirement_clarification` 用于客户需求澄清，查询拆解以工况、缺失条件、风险维度、追问方向为中心。
- `solution_draft` 用于方案草案，查询拆解以候选材料、工艺路线、性能对比、验证风险为中心。
- `selection_matrix` 用于工程选型决策，查询拆解以候选项、评价维度、工况约束和证据覆盖为中心。
- `defect_diagnosis` 用于铸造缺陷和失效诊断，查询拆解以缺陷类型、材料/工艺、症状、检查步骤和纠正措施为中心。
- `retrieval.search_queries` 必须统一语言；当前知识库文档主要为英文，所以实际检索语句统一规范化为英文，禁止中英文混杂。
- 网关从数据库恢复历史时按 `metadata.mode` 过滤；旧消息缺少 `mode` 时视为 `qa`。
- 检索诊断中的 `retrieval.mode`、`retrieval.context_scope` 和 `retrieval.task_intent` 用于解释本轮工作流。

## SSE 事件契约

### 通用事件格式

```json
{
  "type": "log",
  "message": "正在检索知识库...",
  "level": "info"
}
```

或：

```json
{
  "step": "searched",
  "count": 20,
  "retrieval": {}
}
```

### 事件类型

| 事件 | 字段 | 说明 |
| --- | --- | --- |
| `conv_id` | `conv_id` | 后端自动创建或确认会话 |
| `log` | `message`, `level` | 日志 |
| `rewritten` | `queries`, `retrieval` | 查询拆解完成 |
| `searched` | `count`, `retrieval` | 候选召回完成 |
| `context_ready` | `count`, `retrieval` | 上下文精选完成 |
| `repair_planned` | `queries`, `retrieval` | ReAct 检索修复规划完成 |
| `checked` | `score` | 质量检查完成 |
| `structured` | `structured_output` | 结构化输出准备好，可选 |
| `result` | `data` | 最终结果 |
| `error` | `message` | 错误 |
| `done` | 无 | 流结束 |

### `result` 事件结构

```json
{
  "type": "result",
  "data": {
    "answer": "Markdown 正文",
    "citations": [],
    "thinking": "",
    "graph": {},
    "retrieval": {},
    "mode": "qa",
    "structured_output": null
  }
}
```

兼容策略：

- 旧前端只读取 `answer`、`citations`、`graph`、`retrieval` 也能正常显示。
- 新前端根据 `mode` 和 `structured_output.type` 决定是否展示结构化卡片。

## 检索诊断接口字段

后端 `retrieval` 应逐步稳定为：

```json
{
  "original_query": "用户原始问题",
  "resolved_query": "上下文解析后问题",
  "core_entity": ["钛合金", "铝合金"],
  "filter_rule": "对比实体：钛合金、铝合金",
  "search_queries": ["titanium alloy properties", "aluminum alloy properties"],
  "search_priority": "语义均衡",
  "mode": "solution_draft",
  "context_scope": "mode:solution_draft",
  "task_intent": "draft engineering solution",
  "used_history": false,
  "candidate_count": 20,
  "selected_count": 12,
  "top_hits": [
    {
      "page": 337,
      "score": 0.0157,
      "section": "Forging of Titanium Alloys",
      "reason": "语义/关键词混合命中"
    }
  ],
  "repair_reason": "上一轮回答判断信息不足，改用更贴近 ASM 章节标题的检索词。",
  "repair_history": [],
  "rerank": {
    "enabled": true,
    "strategy": "cross_encoder",
    "model": "ms-marco-MiniLM-L-6-v2"
  }
}
```

## 需求澄清模式接口

### 请求

```text
GET /chat/stream?mode=requirement_clarification&query=客户想做一个耐腐蚀泵体，用在海水环境，温度80℃，预算中等
```

## 选型矩阵模式接口

### 请求

```text
GET /chat/stream?mode=selection_matrix&query=海水泵体材料怎么选，80℃，预算中等
```

或：

```text
GET /chat/stream?mode=selection_matrix&query=钛合金、铝合金、铁合金之间怎么选
```

### 结果

```json
{
  "type": "result",
  "data": {
    "answer": "中文决策摘要",
    "mode": "selection_matrix",
    "structured_output": {
      "type": "selection_matrix",
      "requirement_summary": ["海水环境", "80℃", "预算中等"],
      "criteria": ["耐腐蚀", "强度", "铸造/加工适配", "成本", "证据充分度"],
      "rows": [
        {
          "candidate": "候选材料或工艺路线",
          "category": "material",
          "fit_score": 78,
          "criteria_scores": {
            "耐腐蚀": "high",
            "成本": "medium"
          },
          "advantages": ["优势"],
          "risks": ["风险"],
          "process_fit": "工艺适配说明",
          "cost_level": "medium",
          "evidence": ["检索依据，保留引用编号"],
          "citations": [1, 2]
        }
      ],
      "recommendation": "推荐路线",
      "decision_notes": ["决策说明"],
      "open_questions": ["仍需确认的问题"]
    }
  }
}
```

### 检索规则

- 显式多候选提问时，对每个候选材料/工艺单独生成英文检索语句。
- 模糊工况提问时，生成围绕应用、环境、性能目标、工艺适配的英文检索语句。
- 不允许把单一候选材料的上下文污染到其他候选行。
- 候选行没有证据时应标注证据不足，而不是给出确定结论。

## 缺陷诊断模式接口

### 请求

```text
GET /chat/stream?mode=defect_diagnosis&query=铝合金铸件出现气孔，浇注后表面有针孔，怎么排查
```

或：

```text
GET /chat/stream?mode=defect_diagnosis&query=热处理后硬度不够，可能是什么原因
```

### 结果

```json
{
  "type": "result",
  "data": {
    "answer": "中文诊断摘要",
    "mode": "defect_diagnosis",
    "structured_output": {
      "type": "defect_diagnosis",
      "symptom_summary": ["铸件出现气孔", "表面针孔"],
      "possible_causes": [
        {
          "cause": "可能原因",
          "likelihood": "high",
          "evidence": "检索依据，保留引用编号",
          "inspection_method": "建议检查方式",
          "corrective_action": "纠正措施",
          "citations": [1]
        }
      ],
      "inspection_steps": ["现场排查步骤"],
      "process_checks": ["工艺参数或过程检查点"],
      "corrective_actions": ["纠正或预防措施"],
      "missing_field_info": ["还需要补充的现场信息"],
      "severity": "unknown"
    }
  }
}
```

### 检索规则

- 显式缺陷类型优先：porosity、shrinkage、hot tearing、cracking、inclusions、hardness failure 等。
- 同时保留材料和工艺上下文，例如 `aluminum alloy casting porosity`。
- 检索语句必须全英文。
- 不确定缺陷类型时，按症状和工艺阶段检索，并在 `missing_field_info` 中要求补充现场信息。

### 结果

```json
{
  "type": "result",
  "data": {
    "mode": "requirement_clarification",
    "answer": "结构化 Markdown 总结",
    "structured_output": {
      "type": "requirement_clarification",
      "known_conditions": [],
      "missing_conditions": [],
      "risks": [],
      "questions_to_ask": [],
      "preliminary_direction": [],
      "next_steps": []
    },
    "citations": [],
    "retrieval": {}
  }
}
```

### 前端展示

建议使用专门的卡片组件：

```text
需求澄清结果
- 已知条件
- 缺失条件
- 风险点
- 追问清单
- 初步方向
- 下一步
```

## 方案草案模式接口

### 请求

```text
GET /chat/stream?mode=solution_draft&query=海水泵体，80℃，预算中等，需要耐腐蚀
```

### 结果

```json
{
  "type": "result",
  "data": {
    "mode": "solution_draft",
    "answer": "方案草案 Markdown",
    "structured_output": {
      "type": "solution_draft",
      "requirement_summary": "",
      "operating_conditions": [],
      "candidate_materials": [],
      "recommended_processes": [],
      "risks": [],
      "alternatives": [],
      "evidence": [],
      "open_questions": [],
      "next_steps": []
    },
    "citations": [],
    "retrieval": {}
  }
}
```

### 前端展示

建议使用方案视图：

```text
方案草案
1. 需求摘要
2. 工况分析
3. 候选材料
4. 推荐工艺
5. 风险分析
6. 替代方案
7. 引用依据
8. 待确认事项
9. 下一步行动
```

## 会话接口扩展

当前：

```http
POST /api/conversations
```

建议扩展 body：

```json
{
  "mode": "qa",
  "project_id": null,
  "title": ""
}
```

为了兼容旧接口，body 可选。

返回：

```json
{
  "conversation": {
    "id": 1,
    "title": "",
    "mode": "qa",
    "project_id": null,
    "created_at": "",
    "updated_at": ""
  }
}
```

## 消息保存接口扩展

当前：

```http
POST /api/conversations/{conv_id}/messages
```

请求：

```json
{
  "role": "assistant",
  "content": "Markdown 正文",
  "metadata": {
    "schema_version": "1.0",
    "mode": "solution_draft",
    "retrieval": {},
    "structured_output": {},
    "citations": []
  }
}
```

## 项目空间接口

项目空间第一版已实现。所有接口均需要登录态，通过 `Authorization: Bearer <token>` 鉴权。

### 项目列表

```http
GET /api/projects
```

返回：

```json
{
  "projects": [
    {
      "id": 1,
      "name": "海水泵体材料选型",
      "customer_name": "某客户",
      "description": "80℃海水环境，预算中等",
      "status": "active",
      "artifact_count": 3,
      "conversation_count": 5,
      "created_at": "",
      "updated_at": ""
    }
  ]
}
```

### 新建项目

```http
POST /api/projects
```

请求：

```json
{
  "name": "海水泵体材料选型",
  "customer_name": "某客户",
  "description": "80℃海水环境，预算中等"
}
```

### 项目详情

```http
GET /api/projects/{project_id}
```

返回：

```json
{
  "project": {
    "id": 1,
    "name": "海水泵体材料选型",
    "customer_name": "某客户",
    "description": "80℃海水环境，预算中等",
    "status": "active",
    "artifact_count": 2,
    "artifacts": [
      {
        "id": 10,
        "project_id": 1,
        "type": "solution_draft",
        "title": "海水泵体初步材料与工艺方案",
        "content": "Markdown 正文",
        "structured_data": {},
        "citations": [],
        "metadata": {}
      }
    ],
    "conversations": [
      {
        "id": 12,
        "title": "海水泵体材料选型",
        "project_id": 1,
        "created_at": "",
        "updated_at": ""
      }
    ]
  }
}
```

### 更新项目

```http
PUT /api/projects/{project_id}
```

请求：

```json
{
  "name": "海水泵体耐腐蚀方案",
  "customer_name": "某客户",
  "description": "80℃海水环境，预算中等",
  "status": "active"
}
```

所有字段均可选。当前前端第一版主要使用 `name`，用于侧栏双击重命名。

### 保存项目产物

```http
POST /api/projects/{project_id}/artifacts
```

请求：

```json
{
  "type": "solution_draft",
  "title": "海水泵体初步材料与工艺方案",
  "content": "Markdown 正文",
  "structured_data": {},
  "citations": [],
  "metadata": {
    "question": "海水环境泵体，80℃，中等预算，帮我出方案草案",
    "retrieval": {},
    "graph": {},
    "mode": "solution_draft"
  }
}
```

返回：

```json
{
  "artifact": {
    "id": 10,
    "project_id": 1,
    "type": "solution_draft",
    "title": "海水泵体初步材料与工艺方案",
    "content": "Markdown 正文",
    "structured_data": {},
    "citations": [],
    "metadata": {},
    "created_at": "",
    "updated_at": ""
  }
}
```

### 生成项目简报

```http
POST /api/projects/{project_id}/brief
```

后端会读取当前项目的：

- 项目基础信息。
- 项目内对话列表。
- 已保存项目产物。
- 结构化输出。
- 引用来源。

然后调用 LLM 生成 Markdown 项目简报，并保存为 `project_artifacts` 中的 `project_brief` 类型产物。

返回：

```json
{
  "artifact": {
    "id": 20,
    "project_id": 1,
    "type": "project_brief",
    "title": "海水泵体耐腐蚀方案 - 项目简报",
    "content": "# 项目简报\n...",
    "structured_data": {
      "type": "project_brief",
      "format": "markdown",
      "generated_by": "llm"
    },
    "citations": [],
    "metadata": {
      "source": "project_brief_generator"
    }
  },
  "project": {}
}
```

如果 LLM 调用失败，后端会使用项目中已有结构化字段生成基础版简报，并将 `generated_by` 标记为 `fallback`。

## 前端路由与页面策略

第一阶段不建议拆成多个大页面，而是在现有工作台内增加任务模式。

建议结构：

```text
ChatLayout
  Sidebar
  Topbar
  ModeSwitcher
  ChatArea
    MessageItem
      RetrievalPanel
      StructuredOutputRenderer
      KnowledgeGraph
      CitationList
  ChatInput
```

原因：

- 当前系统对话、历史、SSE 都已围绕 ChatLayout 建立。
- 需求澄清和方案草案仍然可以视为“对话驱动任务”。
- 第一版不需要大改路由和数据库。

第二阶段再新增：

```text
/projects
/projects/:id
/artifacts/:id
```

## 开发流程约定

新增功能必须遵守：

1. 先更新 `docs/data-structure.md`。
2. 再更新 `docs/system-interfaces.md`。
3. 然后实现后端 schema、接口、Agent 逻辑。
4. 最后实现前端状态、组件和展示。
5. 每次完成后补充验证记录。

## 第一版开发任务拆分

### Step 1：任务模式

- 前端增加 `currentMode`。
- UI 增加模式切换：知识问答 / 需求澄清 / 方案草案。
- `/chat/stream` 增加 `mode` 参数。
- 消息 metadata 写入 `mode`。

### Step 2：后端 Agent 模式路由

- `agent_chat` 接收 `mode`。
- `stream_chat` 透传 `mode`。
- `qa` 走现有流程。
- `requirement_clarification` 使用澄清 Prompt 和结构化输出 schema。
- `solution_draft` 使用方案 Prompt 和结构化输出 schema。

### Step 3：结构化输出渲染

- 前端新增 `StructuredOutputRenderer`。
- 根据 `structured_output.type` 渲染不同卡片。
- 未知类型降级为普通 Markdown。

### Step 4：历史兼容

- 旧消息没有 `mode` 时视为 `qa`。
- 旧消息没有 `structured_output` 时只显示正文。
- 历史会话加载不应报错。
