<template>
  <section v-if="isDefectDiagnosis" class="structured-output diagnosis-output">
    <div class="structured-head">
      <div>
        <div class="structured-kicker">Defect Diagnosis</div>
        <h3>铸造缺陷诊断报告</h3>
      </div>
      <span class="structured-badge">{{ severityText }}</span>
    </div>
    <div v-if="symptomSummary.length" class="matrix-summary">
      <span v-for="(item, index) in symptomSummary" :key="index">{{ item }}</span>
    </div>
    <div v-if="causeRows.length" class="diagnosis-table-wrap">
      <table class="diagnosis-table">
        <thead>
          <tr>
            <th>可能原因</th>
            <th>可能性</th>
            <th>证据</th>
            <th>检查方法</th>
            <th>纠正措施</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in causeRows" :key="index">
            <td><strong>{{ row.cause || '待确认原因' }}</strong></td>
            <td><span class="score-pill" :class="criterionTone(row.likelihood)">{{ likelihoodText(row.likelihood) }}</span></td>
            <td>{{ row.evidence || '证据不足，需进一步确认' }}</td>
            <td>{{ row.inspection_method || '待补充检查方法' }}</td>
            <td>{{ row.corrective_action || '待确认后制定措施' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="matrix-footer">
      <section v-if="inspectionSteps.length">
        <div class="section-label">现场排查顺序</div>
        <ol><li v-for="(item, index) in inspectionSteps" :key="index">{{ item }}</li></ol>
      </section>
      <section v-if="processChecks.length">
        <div class="section-label">工艺检查点</div>
        <ul><li v-for="(item, index) in processChecks" :key="index">{{ item }}</li></ul>
      </section>
      <section v-if="correctiveActions.length">
        <div class="section-label">纠正措施</div>
        <ul><li v-for="(item, index) in correctiveActions" :key="index">{{ item }}</li></ul>
      </section>
      <section v-if="missingFieldInfo.length">
        <div class="section-label">还需补充</div>
        <ul><li v-for="(item, index) in missingFieldInfo" :key="index">{{ item }}</li></ul>
      </section>
    </div>
  </section>
  <section v-else-if="isSelectionMatrix" class="structured-output matrix-output">
    <div class="structured-head">
      <div>
        <div class="structured-kicker">Selection Matrix</div>
        <h3>材料与工艺选型矩阵</h3>
      </div>
      <span class="structured-badge">工程决策</span>
    </div>
    <div v-if="requirementSummary.length" class="matrix-summary">
      <span v-for="(item, index) in requirementSummary" :key="index">{{ item }}</span>
    </div>
    <div class="matrix-table-wrap">
      <table class="matrix-table">
        <thead>
          <tr>
            <th>候选项</th>
            <th>评分</th>
            <th v-for="criterion in matrixCriteria" :key="criterion">{{ criterion }}</th>
            <th>优势</th>
            <th>风险</th>
            <th>工艺适配</th>
            <th>成本</th>
            <th>证据</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in matrixRows" :key="index">
            <td><strong>{{ row.candidate || '未命名候选' }}</strong><small>{{ categoryLabel(row.category) }}</small></td>
            <td><span class="fit-score" :class="scoreTone(row.fit_score)">{{ scoreText(row.fit_score) }}</span></td>
            <td v-for="criterion in matrixCriteria" :key="criterion">
              <span class="score-pill" :class="criterionTone(row.criteria_scores?.[criterion])">{{ criterionText(row.criteria_scores?.[criterion]) }}</span>
            </td>
            <td><ul><li v-for="(item, i) in toItems(row.advantages)" :key="i">{{ item }}</li></ul></td>
            <td><ul><li v-for="(item, i) in toItems(row.risks)" :key="i">{{ item }}</li></ul></td>
            <td>{{ row.process_fit || '待确认' }}</td>
            <td>{{ costText(row.cost_level) }}</td>
            <td><ul><li v-for="(item, i) in toItems(row.evidence)" :key="i">{{ item }}</li></ul></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="matrix-footer">
      <section v-if="output.recommendation">
        <div class="section-label">推荐结论</div>
        <p>{{ output.recommendation }}</p>
      </section>
      <section v-if="decisionNotes.length">
        <div class="section-label">决策说明</div>
        <ul><li v-for="(item, index) in decisionNotes" :key="index">{{ item }}</li></ul>
      </section>
      <section v-if="openQuestions.length">
        <div class="section-label">待确认问题</div>
        <ul><li v-for="(item, index) in openQuestions" :key="index">{{ item }}</li></ul>
      </section>
    </div>
  </section>
  <section v-else-if="sections.length" class="structured-output">
    <div class="structured-head">
      <div>
        <div class="structured-kicker">{{ modeLabel }}</div>
        <h3>{{ title }}</h3>
      </div>
      <span class="structured-badge">{{ badgeText }}</span>
    </div>
    <div class="structured-grid">
      <section v-for="section in sections" :key="section.key" class="structured-section" :class="section.tone">
        <div class="section-label">{{ section.label }}</div>
        <ul>
          <li v-for="(item, index) in section.items" :key="index">{{ item }}</li>
        </ul>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  output: { type: Object, default: null },
})

const fieldMap = {
  requirement_clarification: [
    ['known_conditions', '已明确条件', 'steady'],
    ['missing_conditions', '待补充条件', 'warning'],
    ['risks', '工程风险', 'danger'],
    ['questions_to_ask', '追问清单', 'info'],
    ['preliminary_direction', '初步方向', 'steady'],
    ['next_steps', '下一步', 'info'],
  ],
  solution_draft: [
    ['requirement_summary', '需求归纳', 'steady'],
    ['operating_conditions', '工况约束', 'steady'],
    ['candidate_materials', '候选材料', 'info'],
    ['recommended_processes', '推荐路线', 'steady'],
    ['risks', '技术风险', 'danger'],
    ['alternatives', '备选方案', 'warning'],
    ['evidence', '检索依据', 'info'],
    ['open_questions', '待确认问题', 'warning'],
    ['next_steps', '验证步骤', 'info'],
  ],
}

const type = computed(() => props.output?.type || '')
const isSelectionMatrix = computed(() => type.value === 'selection_matrix')
const isDefectDiagnosis = computed(() => type.value === 'defect_diagnosis')
const title = computed(() => type.value === 'solution_draft' ? '方案草案' : '需求澄清工作单')
const modeLabel = computed(() => type.value === 'solution_draft' ? 'Solution Draft' : 'Requirement Clarification')
const badgeText = computed(() => type.value === 'solution_draft' ? '工程建议' : '需求分析')

function toItems(value) {
  if (Array.isArray(value)) return value.map((item) => String(item || '').trim()).filter(Boolean)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

const sections = computed(() => {
  const output = props.output || {}
  const config = fieldMap[type.value] || []
  return config
    .map(([key, label, tone]) => ({ key, label, tone, items: toItems(output[key]) }))
    .filter((section) => section.items.length)
})
const output = computed(() => props.output || {})
const matrixCriteria = computed(() => toItems(output.value.criteria).slice(0, 6))
const matrixRows = computed(() => Array.isArray(output.value.rows) ? output.value.rows : [])
const requirementSummary = computed(() => toItems(output.value.requirement_summary))
const decisionNotes = computed(() => toItems(output.value.decision_notes))
const openQuestions = computed(() => toItems(output.value.open_questions))
const symptomSummary = computed(() => toItems(output.value.symptom_summary))
const causeRows = computed(() => Array.isArray(output.value.possible_causes) ? output.value.possible_causes : [])
const inspectionSteps = computed(() => toItems(output.value.inspection_steps))
const processChecks = computed(() => toItems(output.value.process_checks))
const correctiveActions = computed(() => toItems(output.value.corrective_actions))
const missingFieldInfo = computed(() => toItems(output.value.missing_field_info))
const severityText = computed(() => ({ high: '高风险', medium: '中风险', low: '低风险', unknown: '待定风险' }[output.value.severity] || '待定风险'))

function scoreText(score) {
  return Number.isFinite(Number(score)) ? `${Math.round(Number(score))}` : '待评估'
}
function scoreTone(score) {
  const value = Number(score)
  if (!Number.isFinite(value)) return 'unknown'
  if (value >= 80) return 'high'
  if (value >= 60) return 'medium'
  return 'low'
}
function criterionText(value) {
  return ({ high: '高', medium: '中', low: '低', unknown: '未知' }[value] || '未知')
}
function criterionTone(value) {
  return ['high', 'medium', 'low'].includes(value) ? value : 'unknown'
}
function categoryLabel(value) {
  return ({ material: '材料', process: '工艺', material_process: '材料+工艺', unknown: '候选' }[value] || '候选')
}
function costText(value) {
  return ({ low: '低', medium: '中', high: '高', unknown: '未知' }[value] || '未知')
}
function likelihoodText(value) {
  return ({ high: '高', medium: '中', low: '低', unknown: '未知' }[value] || '未知')
}
</script>

<style scoped>
.structured-output {
  margin-bottom: 14px;
  border: 1px solid color-mix(in srgb, var(--accent) 22%, var(--border-light));
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, color-mix(in srgb, var(--accent-soft) 48%, var(--bg-surface)) 0%, var(--bg-surface) 100%);
  overflow: hidden;
}
.structured-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 14px 11px;
  border-bottom: 1px solid var(--border-light);
}
.structured-kicker {
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 760;
  line-height: 1.3;
}
.structured-head h3 {
  margin-top: 2px;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.35;
  font-weight: 780;
}
.structured-badge {
  flex: 0 0 auto;
  border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
  border-radius: 999px;
  color: var(--accent-strong);
  background: var(--bg-surface);
  padding: 4px 9px;
  font-size: 11px;
  font-weight: 720;
}
.structured-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  background: var(--border-light);
}
.structured-section {
  min-width: 0;
  padding: 12px 14px;
  background: var(--bg-surface);
}
.section-label {
  margin-bottom: 7px;
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 760;
}
.structured-section ul {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-left: 17px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
}
.structured-section li::marker { color: var(--accent); }
.structured-section.warning .section-label { color: var(--warning); }
.structured-section.danger .section-label { color: var(--danger); }
.structured-section.info .section-label { color: var(--info); }
.matrix-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  padding: 11px 14px;
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-surface);
}
.matrix-summary span {
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: var(--bg-surface-2);
  color: var(--text-secondary);
  padding: 4px 9px;
  font-size: 12px;
  font-weight: 650;
}
.matrix-table-wrap {
  overflow-x: auto;
  background: var(--bg-surface);
}
.matrix-table {
  width: 100%;
  min-width: 980px;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 12px;
}
.matrix-table th,
.matrix-table td {
  border-bottom: 1px solid var(--border-light);
  border-right: 1px solid var(--border-light);
  padding: 9px 10px;
  vertical-align: top;
  text-align: left;
}
.matrix-table th {
  position: sticky;
  top: 0;
  background: var(--bg-surface-2);
  color: var(--text-muted);
  font-weight: 760;
  white-space: nowrap;
}
.matrix-table th:last-child,
.matrix-table td:last-child { border-right: 0; }
.matrix-table tr:last-child td { border-bottom: 0; }
.matrix-table strong {
  display: block;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.35;
}
.matrix-table small {
  display: block;
  margin-top: 3px;
  color: var(--text-muted);
}
.matrix-table ul {
  margin: 0;
  padding-left: 16px;
  color: var(--text-secondary);
  line-height: 1.55;
}
.fit-score,
.score-pill {
  display: inline-flex;
  min-width: 34px;
  min-height: 24px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid var(--border-light);
  background: var(--bg-surface-2);
  color: var(--text-secondary);
  font-weight: 760;
}
.score-pill { min-width: 30px; font-size: 11px; }
.fit-score.high,
.score-pill.high { border-color: color-mix(in srgb, var(--success) 32%, transparent); color: var(--success); background: color-mix(in srgb, var(--success) 10%, var(--bg-surface)); }
.fit-score.medium,
.score-pill.medium { border-color: color-mix(in srgb, var(--warning) 32%, transparent); color: var(--warning); background: color-mix(in srgb, var(--warning) 10%, var(--bg-surface)); }
.fit-score.low,
.score-pill.low { border-color: color-mix(in srgb, var(--danger) 32%, transparent); color: var(--danger); background: color-mix(in srgb, var(--danger) 9%, var(--bg-surface)); }
.matrix-footer {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1px;
  background: var(--border-light);
  border-top: 1px solid var(--border-light);
}
.matrix-footer section {
  background: var(--bg-surface);
  padding: 12px 14px;
}
.matrix-footer p,
.matrix-footer ul {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
}
.matrix-footer ul { padding-left: 17px; }
.matrix-footer ol {
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
}
.diagnosis-table-wrap {
  overflow-x: auto;
  background: var(--bg-surface);
}
.diagnosis-table {
  width: 100%;
  min-width: 860px;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 12px;
}
.diagnosis-table th,
.diagnosis-table td {
  border-bottom: 1px solid var(--border-light);
  border-right: 1px solid var(--border-light);
  padding: 10px 11px;
  vertical-align: top;
  text-align: left;
  line-height: 1.55;
}
.diagnosis-table th {
  background: var(--bg-surface-2);
  color: var(--text-muted);
  font-weight: 760;
  white-space: nowrap;
}
.diagnosis-table th:last-child,
.diagnosis-table td:last-child { border-right: 0; }
.diagnosis-table tr:last-child td { border-bottom: 0; }
.diagnosis-table strong {
  color: var(--text-primary);
  font-size: 13px;
}
@media (max-width: 820px) {
  .structured-grid { grid-template-columns: 1fr; }
  .structured-head { flex-direction: column; }
}
</style>
