<template>
  <aside class="project-panel">
    <div class="panel-head">
      <div>
        <div class="panel-kicker">Project Workspace</div>
        <h2>{{ project.name }}</h2>
      </div>
      <button class="panel-close" type="button" @click="$emit('close')" title="关闭项目面板">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg>
      </button>
    </div>

    <div class="project-meta">
      <span>{{ project.status || 'active' }}</span>
      <span>{{ artifactCount }} 个产物</span>
      <span>{{ conversations.length }} 个对话</span>
      <span>{{ citationCount }} 条引用</span>
    </div>

    <div class="panel-body">
      <section class="overview-section">
        <div class="section-title-row">
          <div>
            <div class="section-title">项目概览</div>
            <p>从项目内对话和产物自动归纳出的工程画像</p>
          </div>
          <span class="stage-badge">{{ projectStage }}</span>
        </div>

        <div class="overview-grid">
          <div class="overview-item">
            <span>当前阶段</span>
            <strong>{{ projectStage }}</strong>
          </div>
          <div class="overview-item">
            <span>候选材料 / 工艺</span>
            <strong>{{ overview.materials.length || '待沉淀' }}</strong>
          </div>
          <div class="overview-item">
            <span>风险点</span>
            <strong>{{ overview.risks.length || '待评估' }}</strong>
          </div>
          <div class="overview-item">
            <span>待确认</span>
            <strong>{{ overview.openQuestions.length || '暂无' }}</strong>
          </div>
        </div>

        <div class="overview-blocks">
          <div class="overview-block">
            <div class="mini-label">候选材料 / 工艺</div>
            <div class="chip-row" v-if="overview.materials.length">
              <span v-for="item in overview.materials.slice(0, 8)" :key="item">{{ item }}</span>
            </div>
            <p v-else>保存方案草案或选型矩阵后会自动汇总候选项。</p>
          </div>
          <div class="overview-block">
            <div class="mini-label">关键风险</div>
            <ul v-if="overview.risks.length">
              <li v-for="item in overview.risks.slice(0, 4)" :key="item">{{ item }}</li>
            </ul>
            <p v-else>暂未形成风险清单。</p>
          </div>
          <div class="overview-block">
            <div class="mini-label">待确认问题</div>
            <ul v-if="overview.openQuestions.length">
              <li v-for="item in overview.openQuestions.slice(0, 4)" :key="item">{{ item }}</li>
            </ul>
            <p v-else>暂未形成待确认问题。</p>
          </div>
        </div>
      </section>

      <section class="brief-section">
        <div class="section-title-row">
          <div>
            <div class="section-title">项目简报</div>
            <p>{{ latestBriefArtifact ? '已生成可沉淀的项目简报' : '把需求、依据、方案、比较和风险收束成一页评审摘要' }}</p>
          </div>
          <div class="brief-actions">
            <button class="brief-toggle" type="button" @click="briefOpen = !briefOpen">{{ briefOpen ? '收起' : '预览' }}</button>
            <button class="brief-generate" type="button" :disabled="isGeneratingBrief" @click="$emit('generate-brief')">
              {{ isGeneratingBrief ? '生成中...' : (latestBriefArtifact ? '重新生成' : '生成简报') }}
            </button>
          </div>
        </div>
        <div v-if="briefOpen" class="brief-preview">
          <pre>{{ briefPreview }}</pre>
        </div>
      </section>

      <section class="conversation-section" v-if="conversations.length">
        <div class="section-title">项目内对话</div>
        <button
          v-for="conv in conversations.slice(0, 6)"
          :key="conv.id"
          class="conversation-row"
          type="button"
          @click="$emit('select-conversation', conv.id)"
        >
          <span>{{ conv.title || '新对话' }}</span>
          <time>{{ formatTime(conv.updated_at) }}</time>
        </button>
      </section>

      <section class="artifact-workflow">
        <div class="section-title-row">
          <div>
            <div class="section-title">项目产物</div>
            <p>按解决方案工程流程沉淀五类输出</p>
          </div>
        </div>

        <div class="workflow-list">
          <section v-for="group in artifactGroups" :key="group.type" class="workflow-section">
            <div class="workflow-head">
              <div>
                <span>{{ group.label }}</span>
                <small>{{ group.description }}</small>
              </div>
              <strong>{{ group.items.length }}</strong>
            </div>

            <div v-if="group.items.length" class="artifact-list">
              <article v-for="artifact in group.items.slice(0, 3)" :key="artifact.id" class="artifact-card">
                <div class="artifact-topline">
                  <span>{{ typeText(artifact.type) }}</span>
                  <time>{{ formatTime(artifact.created_at) }}</time>
                </div>
                <h3>{{ artifact.title }}</h3>
                <p>{{ artifact.content }}</p>
                <div class="artifact-foot">
                  <span v-if="artifact.citations?.length">{{ artifact.citations.length }} 条引用</span>
                  <span v-if="artifact.structured_data?.type">结构化</span>
                </div>
              </article>
            </div>

            <div v-else class="workflow-empty">{{ group.empty }}</div>
          </section>
        </div>
      </section>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  project: { type: Object, required: true },
  isGeneratingBrief: { type: Boolean, default: false },
})
defineEmits(['close', 'select-conversation', 'generate-brief'])

const briefOpen = ref(false)
const artifacts = computed(() => props.project.artifacts || [])
const conversations = computed(() => props.project.conversations || [])
const artifactCount = computed(() => props.project.artifact_count ?? artifacts.value.length)
const citationCount = computed(() => artifacts.value.reduce((sum, item) => sum + (item.citations?.length || 0), 0))
const latestBriefArtifact = computed(() => artifacts.value.find((item) => item.type === 'project_brief') || null)

const workflowConfig = [
  { type: 'project_brief', label: '项目简报', description: '客户沟通与内部评审摘要', empty: '还没有生成项目简报。' },
  { type: 'requirement_clarification', label: '需求澄清', description: '客户条件、缺失信息、追问清单', empty: '还没有需求澄清产物。' },
  { type: 'qa', label: '知识依据', description: '标准、手册、材料与工艺依据', empty: '还没有保存知识问答依据。' },
  { type: 'solution_draft', label: '方案草案', description: '材料、工艺、验证路线', empty: '还没有方案草案。' },
  { type: 'selection_matrix', label: '选型矩阵', description: '多候选对比与决策理由', empty: '还没有选型矩阵。' },
  { type: 'defect_diagnosis', label: '缺陷诊断', description: '风险、失效与现场排查', empty: '还没有缺陷诊断记录。' },
]

const artifactGroups = computed(() => workflowConfig.map((group) => ({
  ...group,
  items: artifacts.value.filter((item) => item.type === group.type),
})))

const projectStage = computed(() => {
  const types = new Set(artifacts.value.map((item) => item.type))
  if (types.has('defect_diagnosis')) return '现场诊断 / 风险闭环'
  if (types.has('selection_matrix')) return '选型决策'
  if (types.has('solution_draft')) return '方案形成'
  if (types.has('requirement_clarification')) return '需求澄清'
  if (types.has('qa') || conversations.value.length) return '资料检索'
  return '项目初始化'
})

const overview = computed(() => {
  const materials = []
  const risks = []
  const openQuestions = []
  const recommendations = []
  for (const artifact of artifacts.value) {
    const data = artifact.structured_data || {}
    collect(materials, data.candidate_materials)
    collect(materials, data.recommended_processes)
    collect(materials, data.rows?.map((row) => row.candidate))
    collect(risks, data.risks)
    collect(risks, data.possible_causes?.map((row) => row.cause))
    collect(openQuestions, data.missing_conditions)
    collect(openQuestions, data.questions_to_ask)
    collect(openQuestions, data.open_questions)
    collect(openQuestions, data.missing_field_info)
    collect(recommendations, data.recommendation)
    collect(recommendations, data.preliminary_direction)
  }
  return {
    materials: unique(materials).slice(0, 12),
    risks: unique(risks).slice(0, 10),
    openQuestions: unique(openQuestions).slice(0, 10),
    recommendations: unique(recommendations).slice(0, 6),
  }
})

const projectBrief = computed(() => {
  const lines = [
    `# ${props.project.name}`,
    '',
    `当前阶段：${projectStage.value}`,
    `项目沉淀：${conversations.value.length} 个对话，${artifactCount.value} 个产物，${citationCount.value} 条引用依据`,
    '',
    '## 候选材料 / 工艺',
    bulletLines(overview.value.materials, '暂未沉淀候选项。'),
    '',
    '## 关键风险',
    bulletLines(overview.value.risks, '暂未形成风险清单。'),
    '',
    '## 待确认问题',
    bulletLines(overview.value.openQuestions, '暂未形成待确认问题。'),
    '',
    '## 初步结论',
    bulletLines(overview.value.recommendations, '需要继续通过需求澄清、知识依据和选型矩阵形成结论。'),
  ]
  return lines.join('\n')
})
const briefPreview = computed(() => latestBriefArtifact.value?.content || projectBrief.value)

function collect(target, value) {
  if (Array.isArray(value)) {
    for (const item of value) collect(target, item)
    return
  }
  if (value && typeof value === 'object') {
    const candidate = value.name || value.material || value.process || value.title || value.cause || value.candidate
    if (candidate) target.push(String(candidate))
    return
  }
  if (typeof value === 'string' && value.trim()) target.push(value.trim())
}

function unique(items) {
  const seen = new Set()
  const result = []
  for (const item of items) {
    const text = String(item || '').replace(/\s+/g, ' ').trim()
    if (!text || seen.has(text)) continue
    seen.add(text)
    result.push(text)
  }
  return result
}

function bulletLines(items, fallback) {
  return items.length ? items.slice(0, 6).map((item) => `- ${item}`).join('\n') : `- ${fallback}`
}

function typeText(type) {
  const map = {
    project_brief: '项目简报',
    qa: '知识问答',
    requirement_clarification: '需求澄清',
    solution_draft: '方案草案',
    selection_matrix: '选型矩阵',
    defect_diagnosis: '缺陷诊断',
  }
  return map[type] || '项目产物'
}

function formatTime(value) {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
  } catch {
    return ''
  }
}
</script>

<style scoped>
.project-panel { width: 430px; min-width: 430px; height: 100vh; display: flex; flex-direction: column; background: var(--bg-surface); border-left: 1px solid var(--border-light); color: var(--text-primary); }
.panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 18px 18px 14px; border-bottom: 1px solid var(--border-light); }
.panel-kicker { color: var(--accent-strong); font-family: var(--font-mono); font-size: 11px; font-weight: 780; line-height: 1.3; }
.panel-head h2 { margin-top: 5px; font-size: 18px; line-height: 1.35; font-weight: 780; text-wrap: balance; }
.panel-close { width: 32px; height: 32px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface-2); color: var(--text-secondary); display: grid; place-items: center; cursor: pointer; }
.panel-close:hover { color: var(--text-primary); border-color: var(--border-strong); }
.panel-close svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; }
.project-meta { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 18px 0; }
.project-meta span { border: 1px solid var(--border-light); border-radius: 999px; background: var(--bg-surface-2); color: var(--text-muted); padding: 4px 9px; font-size: 12px; font-weight: 650; }
.panel-body { min-height: 0; flex: 1; overflow-y: auto; padding: 14px 18px 22px; display: flex; flex-direction: column; gap: 14px; }
.overview-section, .brief-section, .conversation-section, .artifact-workflow { border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface-2); padding: 13px; }
.section-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.section-title { color: var(--text-primary); font-size: 13px; font-weight: 780; line-height: 1.35; }
.section-title-row p { margin-top: 3px; color: var(--text-muted); font-size: 12px; line-height: 1.5; }
.stage-badge, .brief-toggle, .brief-generate { flex: 0 0 auto; border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--border-light)); border-radius: 999px; background: var(--accent-soft); color: var(--accent-strong); padding: 4px 9px; font-size: 11px; font-weight: 760; }
.brief-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.brief-toggle, .brief-generate { cursor: pointer; }
.brief-generate { background: var(--accent); color: #fff; border-color: var(--accent); }
.brief-toggle:hover, .brief-generate:hover { border-color: var(--accent); }
.brief-generate:disabled { opacity: .62; cursor: wait; }
.overview-grid { margin-top: 12px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.overview-item { min-width: 0; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); padding: 9px; }
.overview-item span, .mini-label { display: block; color: var(--text-muted); font-size: 11px; font-weight: 720; }
.overview-item strong { display: block; margin-top: 3px; color: var(--text-primary); font-size: 14px; line-height: 1.35; font-weight: 780; }
.overview-blocks { margin-top: 12px; display: flex; flex-direction: column; gap: 9px; }
.overview-block { border-top: 1px solid var(--border-light); padding-top: 9px; }
.overview-block p, .overview-block li { color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
.overview-block ul { margin-top: 6px; padding-left: 16px; }
.chip-row { margin-top: 7px; display: flex; flex-wrap: wrap; gap: 6px; }
.chip-row span { border: 1px solid var(--border-light); border-radius: 999px; background: var(--bg-surface); color: var(--text-secondary); padding: 4px 8px; font-size: 12px; font-weight: 650; }
.brief-preview { margin-top: 10px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); padding: 10px; }
.brief-preview pre { margin: 0; color: var(--text-secondary); font-family: var(--font-mono); font-size: 11px; line-height: 1.65; white-space: pre-wrap; }
.conversation-section { display: flex; flex-direction: column; gap: 7px; }
.conversation-row { width: 100%; min-height: 38px; display: flex; align-items: center; justify-content: space-between; gap: 10px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-secondary); padding: 8px 10px; cursor: pointer; text-align: left; }
.conversation-row:hover { border-color: var(--accent); background: var(--accent-soft); color: var(--text-primary); }
.conversation-row span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 700; }
.conversation-row time { flex: 0 0 auto; color: var(--text-muted); font-size: 11px; }
.workflow-list { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
.workflow-section { border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); overflow: hidden; }
.workflow-head { display: flex; justify-content: space-between; gap: 10px; padding: 10px; border-bottom: 1px solid var(--border-light); }
.workflow-head span { display: block; color: var(--text-primary); font-size: 13px; font-weight: 760; }
.workflow-head small { display: block; margin-top: 2px; color: var(--text-muted); font-size: 11px; line-height: 1.45; }
.workflow-head strong { flex: 0 0 auto; color: var(--accent-strong); font-size: 13px; font-weight: 800; }
.artifact-list { padding: 9px; display: flex; flex-direction: column; gap: 8px; }
.artifact-card { border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface-2); padding: 10px; }
.artifact-topline { display: flex; align-items: center; justify-content: space-between; gap: 8px; color: var(--text-muted); font-size: 11px; font-weight: 700; }
.artifact-card h3 { margin-top: 7px; font-size: 13px; line-height: 1.45; font-weight: 760; }
.artifact-card p { margin-top: 6px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.artifact-foot { margin-top: 8px; display: flex; gap: 7px; color: var(--accent-strong); font-size: 11px; font-weight: 720; }
.workflow-empty { padding: 10px; color: var(--text-muted); font-size: 12px; line-height: 1.6; }
@media (max-width: 1120px) {
  .project-panel { position: fixed; right: 0; top: 0; z-index: 28; box-shadow: var(--shadow-panel); }
}
@media (max-width: 640px) {
  .project-panel { width: min(100vw, 430px); min-width: 0; }
  .overview-grid { grid-template-columns: 1fr; }
}
</style>
