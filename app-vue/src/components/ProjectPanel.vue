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

        <div class="project-focus">
          <div>
            <span class="mini-label">项目主线</span>
            <strong>{{ projectFocus.problem }}</strong>
            <p>{{ projectFocus.basis }}</p>
          </div>
          <span class="focus-source">{{ projectFocus.source }}</span>
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
            <p>{{ briefEvidenceHint }}</p>
          </div>
          <div class="brief-actions">
            <span class="brief-evidence-badge">{{ reportEvidenceCards.length }} 条报告证据</span>
            <button class="brief-toggle" type="button" @click="briefOpen = !briefOpen">{{ briefOpen ? '收起' : '预览' }}</button>
            <button class="brief-generate" type="button" :disabled="isGeneratingBrief" @click="$emit('generate-brief')">
              {{ isGeneratingBrief ? '生成中...' : (latestBriefArtifact ? '重新生成' : '生成简报') }}
            </button>
          </div>
        </div>
        <div v-if="savedEvidenceCards.length && !reportEvidenceCards.length" class="brief-notice">
          已有 {{ savedEvidenceCards.length }} 张证据卡，但还没有勾选“可用于报告”。生成简报会退回使用普通引用线索。
        </div>
        <div v-if="briefOpen" class="brief-preview">
          <div class="brief-markdown answer-text" v-html="renderMarkdown(briefPreview)"></div>
        </div>
      </section>

      <section class="document-import-section">
        <div class="section-title-row">
          <div>
            <div class="section-title">工程文档导入</div>
            <p>上传现场记录、实验报告或工艺脑图，沉淀为项目内工程案例。</p>
          </div>
          <span class="evidence-count">{{ localEngineeringDocuments.length }} 个文档</span>
        </div>

        <div class="document-import-controls">
          <select v-model="engineeringDocumentKind" :disabled="isUploadingEngineeringDocument" aria-label="文档类型">
            <option value="engineering_case">实验 / 现场记录</option>
            <option value="process_mindmap">工艺脑图</option>
            <option value="customer_note">客户资料</option>
            <option value="validation_report">验证报告</option>
          </select>
          <label class="file-picker">
            <input
              type="file"
              accept=".docx,.txt,.md,.markdown,.png,.jpg,.jpeg"
              :disabled="isUploadingEngineeringDocument"
              @change="onEngineeringFileChange"
            />
            <span>{{ selectedEngineeringFile ? selectedEngineeringFile.name : '选择文件' }}</span>
          </label>
          <button type="button" :disabled="!selectedEngineeringFile || isUploadingEngineeringDocument" @click="uploadEngineeringDocument">
            {{ isUploadingEngineeringDocument ? '导入中...' : '导入' }}
          </button>
        </div>
        <p v-if="engineeringUploadMessage" class="document-import-message">{{ engineeringUploadMessage }}</p>

        <div v-if="localEngineeringDocuments.length" class="document-list">
          <article
            v-for="doc in localEngineeringDocuments.slice(0, 4)"
            :key="doc.id"
            class="document-card"
            role="button"
            tabindex="0"
            @click="openDocumentArtifact(doc)"
            @keydown.enter="openDocumentArtifact(doc)"
          >
            <div>
              <strong>{{ doc.title }}</strong>
              <span>{{ documentKindText(doc.document_kind) }} · {{ formatFileSize(doc.file_size) }} · {{ documentStatsText(doc) }}</span>
            </div>
            <time>{{ formatTime(doc.created_at) }}</time>
          </article>
        </div>
      </section>

      <section class="conversation-section" v-if="conversations.length">
        <div class="conversation-head">
          <div>
            <div class="section-title">项目内对话</div>
            <p>当前项目下保存的检索与方案讨论</p>
          </div>
          <button
            v-if="conversations.length > conversationPreviewLimit"
            class="conversation-toggle"
            type="button"
            @click="showAllConversations = !showAllConversations"
          >
            {{ showAllConversations ? '收起' : `全部 ${conversations.length}` }}
          </button>
        </div>
        <button
          v-for="conv in visibleConversations"
          :key="conv.id"
          class="conversation-row"
          type="button"
          @click="$emit('select-conversation', conv.id)"
        >
          <span>{{ conv.title || '新对话' }}</span>
          <time>{{ formatTime(conv.updated_at) }}</time>
        </button>
      </section>

      <section class="evidence-section">
        <div class="section-title-row">
          <div>
            <div class="section-title">引用依据</div>
            <p>从项目产物中自动沉淀可追溯证据，按页码和内容去重</p>
          </div>
          <span class="evidence-count">{{ filteredEvidenceItems.length }} / {{ evidenceItems.length }}</span>
        </div>

        <div v-if="evidenceItems.length" class="evidence-tools">
          <label class="evidence-search">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21 21-4.3-4.3M10.8 18a7.2 7.2 0 1 1 0-14.4 7.2 7.2 0 0 1 0 14.4Z" /></svg>
            <input v-model.trim="evidenceSearch" type="search" placeholder="搜索材料、工艺、页码或来源..." />
          </label>
          <div class="evidence-tags" role="list" aria-label="证据标签筛选">
            <button
              type="button"
              :class="{ active: evidenceTag === '全部' }"
              @click="evidenceTag = '全部'"
            >全部</button>
            <button
              v-for="tag in evidenceTags"
              :key="tag"
              type="button"
              :class="{ active: evidenceTag === tag }"
              @click="evidenceTag = tag"
            >{{ tag }}</button>
          </div>
        </div>

        <div v-if="savedEvidenceCards.length" class="confirmed-evidence">
          <div class="mini-label">已确认证据</div>
          <article v-for="card in savedEvidenceCards" :key="card.id" class="confirmed-card">
            <div class="confirmed-head">
              <div>
                <strong>{{ card.title }}</strong>
                <span>pg.{{ card.page || '?' }} · {{ evidenceLevelText(card.metadata?.evidence_level) }}</span>
                <em>{{ evidenceSourceText(card) }}</em>
              </div>
              <button type="button" @click="openPdf(card)" title="打开原文">原文</button>
            </div>
            <p>{{ card.quote || '暂无摘录文本。' }}</p>
            <div class="confirmed-controls">
              <label>
                <input
                  type="checkbox"
                  :checked="card.usable_in_report"
                  @change="updateEvidenceCard(card, { usable_in_report: $event.target.checked, status: $event.target.checked ? 'confirmed' : card.status })"
                />
                可用于报告
              </label>
              <select :value="card.reliability" @change="updateEvidenceCard(card, { reliability: $event.target.value })">
                <option value="high">高可靠</option>
                <option value="medium">中可靠</option>
                <option value="low">待核实</option>
              </select>
              <button
                type="button"
                class="danger-text danger-icon-btn"
                title="删除证据"
                aria-label="删除证据"
                @click.stop="requestDeleteEvidenceCard(card)"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M4 7h16" />
                  <path d="M10 11v6M14 11v6" />
                  <path d="M6 7l1 14h10l1-14" />
                  <path d="M9 7V4h6v3" />
                </svg>
              </button>
            </div>
            <textarea
              :value="card.note"
              rows="2"
              placeholder="补充工程师备注，例如适用条件、限制、报告用法..."
              @change="updateEvidenceCard(card, { note: $event.target.value })"
            ></textarea>
          </article>
        </div>

        <div v-if="filteredEvidenceItems.length" class="evidence-list">
          <article
            v-for="item in filteredEvidenceItems.slice(0, 12)"
            :key="item.key"
            class="evidence-card"
            :title="`打开原文 pg.${item.page || '?'}`"
          >
            <div class="evidence-card-head">
              <span class="evidence-page">pg.{{ item.page || '?' }}</span>
              <span>{{ item.sourceLabel }}</span>
              <span>{{ item.evidenceLabel }}</span>
            </div>
            <p>{{ item.text || '暂无摘录文本。' }}</p>
            <div class="evidence-card-foot">
              <span>{{ item.artifactTypeText }}</span>
              <strong>{{ item.sourceHint }}</strong>
            </div>
            <div v-if="item.tags.length" class="evidence-card-tags">
              <span v-for="tag in item.tags.slice(0, 3)" :key="tag">{{ tag }}</span>
            </div>
            <div class="evidence-actions">
              <button type="button" @click="openPdf(item)">查看原文</button>
              <button
                type="button"
                :disabled="isEvidenceSaved(item) || savingEvidenceKey === item.key"
                @click="saveEvidenceItem(item)"
              >{{ isEvidenceSaved(item) ? '已保存' : (savingEvidenceKey === item.key ? '保存中...' : '保存证据') }}</button>
            </div>
          </article>
        </div>

        <div v-else class="evidence-empty">
          <strong>{{ evidenceItems.length ? '没有匹配的证据' : '还没有沉淀引用依据' }}</strong>
          <p>{{ evidenceItems.length ? '换个关键词或切换标签再试。' : '把回答保存到项目后，引用来源会自动汇总在这里。' }}</p>
        </div>
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
              <article
                v-for="artifact in group.items.slice(0, 3)"
                :key="artifact.id"
                class="artifact-card"
                role="button"
                tabindex="0"
                @click="openArtifact(artifact)"
                @keydown.enter="openArtifact(artifact)"
              >
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

            <div v-else class="workflow-empty">
              <p>{{ group.empty }}</p>
              <button
                v-if="group.type === 'project_brief'"
                type="button"
                @click="$emit('generate-brief')"
              >生成项目简报</button>
              <button
                v-else-if="group.mode"
                type="button"
                @click="$emit('start-workflow', group.mode)"
              >{{ group.action }}</button>
            </div>
          </section>
        </div>
      </section>

      <section v-if="selectedArtifact" class="artifact-detail" ref="detailSection">
        <div class="detail-head">
          <div>
            <div class="section-title">{{ selectedArtifact.title }}</div>
            <p>{{ typeText(selectedArtifact.type) }} · {{ formatTime(selectedArtifact.created_at) }}</p>
          </div>
          <button class="detail-close" type="button" @click="selectedArtifact = null">关闭</button>
        </div>

        <div class="detail-actions">
          <button type="button" @click="copyArtifactMarkdown">{{ copied ? '已复制' : '复制 Markdown' }}</button>
          <button type="button" @click="exportArtifactMarkdown">导出 .md</button>
          <button type="button" :disabled="pdfExporting" @click="exportArtifactPdf">{{ pdfExporting ? '生成中...' : '导出 PDF' }}</button>
        </div>

        <div class="detail-block">
          <div class="mini-label">正文</div>
          <pre>{{ selectedArtifact.content || '暂无正文内容。' }}</pre>
        </div>

        <div v-if="hasStructuredData(selectedArtifact)" class="detail-block">
          <div class="mini-label">结构化数据</div>
          <pre>{{ formatJson(selectedArtifact.structured_data) }}</pre>
        </div>

        <div v-if="selectedArtifact.citations?.length" class="detail-block">
          <div class="mini-label">引用来源</div>
          <a
            v-for="(citation, index) in selectedArtifact.citations"
            :key="index"
            class="detail-citation"
            :href="pdfViewerUrl(citation)"
            target="_blank"
            rel="noopener"
          >
            <strong>pg.{{ citation.page || '?' }}</strong>
            <span>{{ citation.section || '引用依据' }}</span>
            <p>{{ citation.text || '' }}</p>
          </a>
        </div>
      </section>
    </div>
    <Teleport to="body">
      <div
        v-if="pendingDeleteEvidenceCard"
        class="confirm-backdrop"
        role="presentation"
        @click.self="cancelDeleteEvidenceCard"
      >
        <section
          class="confirm-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="deleteEvidenceTitle"
        >
          <button
            class="confirm-close"
            type="button"
            :disabled="!!deletingEvidenceId"
            aria-label="关闭"
            @click="cancelDeleteEvidenceCard"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
          <div class="confirm-kicker">删除证据</div>
          <h3 id="deleteEvidenceTitle">确认删除这条证据？</h3>
          <p>删除后，这条证据不会再出现在项目证据库、项目简报和报告候选中。</p>
          <div class="confirm-preview">
            <strong>{{ pendingDeleteEvidenceCard.title || `证据 pg.${pendingDeleteEvidenceCard.page || '?'}` }}</strong>
            <span>{{ pendingDeleteEvidenceCard.quote || pendingDeleteEvidenceCard.summary || '暂无摘录文本。' }}</span>
          </div>
          <div class="confirm-actions">
            <button type="button" class="confirm-secondary" :disabled="!!deletingEvidenceId" @click="cancelDeleteEvidenceCard">取消</button>
            <button type="button" class="confirm-danger" :disabled="!!deletingEvidenceId" @click="confirmDeleteEvidenceCard">
              {{ deletingEvidenceId ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </section>
      </div>
    </Teleport>
  </aside>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { api } from '../utils/api.js'

const props = defineProps({
  project: { type: Object, required: true },
  isGeneratingBrief: { type: Boolean, default: false },
})
defineEmits(['close', 'select-conversation', 'generate-brief', 'start-workflow'])

const briefOpen = ref(false)
const showAllConversations = ref(false)
const copied = ref(false)
const detailSection = ref(null)
const pdfExporting = ref(false)
const selectedArtifact = ref(null)
const localArtifacts = ref([])
const localEngineeringDocuments = ref([])
const artifacts = computed(() => localArtifacts.value)
const conversations = computed(() => props.project.conversations || [])
const conversationPreviewLimit = 6
const visibleConversations = computed(() => showAllConversations.value ? conversations.value : conversations.value.slice(0, conversationPreviewLimit))
const artifactCount = computed(() => Math.max(Number(props.project.artifact_count || 0), artifacts.value.length))
const latestBriefArtifact = computed(() => artifacts.value.find((item) => item.type === 'project_brief') || null)
const evidenceSearch = ref('')
const evidenceTag = ref('全部')
const savedEvidenceCards = ref([])
const savingEvidenceKey = ref('')
const pendingDeleteEvidenceCard = ref(null)
const deletingEvidenceId = ref(null)
const selectedEngineeringFile = ref(null)
const engineeringDocumentKind = ref('engineering_case')
const isUploadingEngineeringDocument = ref(false)
const engineeringUploadMessage = ref('')

watch(
  () => [props.project.id, props.project.artifacts],
  () => {
    localArtifacts.value = Array.isArray(props.project.artifacts) ? [...props.project.artifacts] : []
  },
  { immediate: true, deep: true },
)

watch(
  () => props.project.id,
  () => {
    showAllConversations.value = false
  },
)

watch(
  () => [props.project.id, props.project.engineering_documents],
  () => {
    localEngineeringDocuments.value = Array.isArray(props.project.engineering_documents) ? [...props.project.engineering_documents] : []
  },
  { immediate: true, deep: true },
)

watch(
  () => [props.project.id, props.project.evidence_cards],
  () => {
    savedEvidenceCards.value = Array.isArray(props.project.evidence_cards) ? [...props.project.evidence_cards] : []
  },
  { immediate: true, deep: true },
)

const workflowConfig = [
  { type: 'project_brief', label: '项目简报', description: '客户沟通与内部评审摘要', empty: '还没有生成项目简报。' },
  { type: 'requirement_clarification', mode: 'requirement_clarification', label: '需求澄清', description: '客户条件、缺失信息、追问清单', empty: '在“需求澄清”模式里输入客户现场条件、约束和缺失信息后，会沉淀到这里。', action: '去做需求澄清' },
  { type: 'qa', mode: 'qa', label: '知识依据', description: '标准、手册、材料与工艺依据', empty: '在知识问答里得到有价值回答后，点击回答下方“保存到项目”，会进入这里。', action: '去问知识依据' },
  { type: 'engineering_case', label: '工程案例', description: '现场记录、实验结果与工艺脑图', empty: '在上方“工程文档导入”上传现场记录、实验报告或脑图后，会进入这里。' },
  { type: 'solution_draft', mode: 'solution_draft', label: '方案草案', description: '材料、工艺、验证路线', empty: '在“方案草案”模式里描述目标、候选材料和工艺约束后，会生成方案草案。', action: '去写方案草案' },
  { type: 'selection_matrix', mode: 'selection_matrix', label: '选型矩阵', description: '多候选对比与决策理由', empty: '在“选型矩阵”模式里提出候选材料/工艺的对比问题，例如“铜合金、铝合金和钛合金怎么选”，会生成矩阵。', action: '去做选型矩阵' },
  { type: 'defect_diagnosis', mode: 'defect_diagnosis', label: '缺陷诊断', description: '风险、失效与现场排查', empty: '在“缺陷诊断”模式里描述缺陷现象、工况和材料工艺后，会形成诊断记录。', action: '去做缺陷诊断' },
]

const artifactGroups = computed(() => workflowConfig.map((group) => ({
  ...group,
  items: artifacts.value.filter((item) => item.type === group.type),
})))

const evidenceItems = computed(() => {
  const seen = new Set()
  const items = []
  for (const artifact of artifacts.value) {
    const citations = Array.isArray(artifact.citations) ? artifact.citations : []
    for (const citation of citations) {
      const text = compactText(citation.text || citation.content || citation.snippet || '')
      const page = citation.page || citation.page_no || citation.pageNumber || ''
      const sourceId = citation.source_id || citation.sourceId || citation.document_id || citation.doc_id || 2
      const key = `${sourceId}:${page}:${text.slice(0, 180).toLowerCase()}`
      if (!text && !page) continue
      if (seen.has(key)) continue
      seen.add(key)
      const tags = inferEvidenceTags({ ...citation, text, artifact })
      items.push({
        ...citation,
        key,
        page,
        source_id: sourceId,
        text,
        tags,
        sourceLabel: sourceTypeText(citation.source_type || citation.sourceType),
        evidenceLabel: evidenceLevelText(citation.evidence_level || citation.evidenceLevel),
        artifactId: artifact.id,
        artifactTitle: artifact.title || '未命名产物',
        artifactTypeText: typeText(artifact.type),
        question: artifact.metadata?.question || artifact.structured_data?.question || '',
        sourceHint: evidenceSourceHint(artifact),
        createdAt: artifact.created_at,
        searchText: compactText([
          text,
          citation.section,
          citation.source_type,
          citation.evidence_level,
          artifact.title,
          artifact.metadata?.question,
          typeText(artifact.type),
          tags.join(' '),
          page ? `pg.${page}` : '',
        ].filter(Boolean).join(' ')).toLowerCase(),
      })
    }
  }
  return items
})
const citationCount = computed(() => evidenceItems.value.length)
const evidenceTags = computed(() => {
  const counts = new Map()
  for (const item of evidenceItems.value) {
    for (const tag of item.tags) counts.set(tag, (counts.get(tag) || 0) + 1)
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'zh-CN'))
    .map(([tag]) => tag)
    .slice(0, 8)
})
const filteredEvidenceItems = computed(() => {
  const q = compactText(evidenceSearch.value).toLowerCase()
  return evidenceItems.value.filter((item) => {
    const tagOk = evidenceTag.value === '全部' || item.tags.includes(evidenceTag.value)
    const searchOk = !q || item.searchText.includes(q)
    return tagOk && searchOk
  })
})
const reportEvidenceCards = computed(() => savedEvidenceCards.value.filter((card) => card.usable_in_report))
const briefEvidenceHint = computed(() => {
  if (latestBriefArtifact.value) {
    const count = latestBriefArtifact.value.structured_data?.report_evidence_count ?? latestBriefArtifact.value.metadata?.report_evidence_count
    return count ? `已生成项目简报，上次使用 ${count} 条已确认证据` : '已生成项目简报，可用已确认证据重新生成'
  }
  if (reportEvidenceCards.value.length) return `将优先使用 ${reportEvidenceCards.value.length} 条已确认证据生成简报`
  return '把需求、依据、方案、比较和风险收束成一页评审摘要'
})
const savedEvidenceKeys = computed(() => {
  const keys = new Set()
  for (const card of savedEvidenceCards.value) {
    const key = card.metadata?.source_key || evidenceKeyFromCard(card)
    if (key) keys.add(key)
  }
  return keys
})

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

const projectFocus = computed(() => {
  const requirement = latestArtifactByType('requirement_clarification')
  const solution = latestArtifactByType('solution_draft')
  const matrix = latestArtifactByType('selection_matrix')
  const diagnosis = latestArtifactByType('defect_diagnosis')
  const sourceArtifact = requirement || solution || matrix || diagnosis || latestBriefArtifact.value
  const projectDescription = compactText(props.project.description || props.project.summary || '')
  const latestQuestion = compactText(conversations.value[0]?.title || '')
  const artifactQuestion = compactText(sourceArtifact?.metadata?.question || '')
  const artifactContent = compactText(sourceArtifact?.content || '')
  const problem = projectDescription
    || artifactQuestion
    || latestQuestion
    || '尚未确定核心问题'
  let basis = '建议先用“需求澄清”沉淀客户场景、失效/目标、约束条件和评价指标。'
  let source = '待确认'
  if (requirement) {
    basis = compactText(requirement.content).slice(0, 120) || '已存在需求澄清产物，可作为项目主线依据。'
    source = '来自需求澄清'
  } else if (solution || matrix || diagnosis) {
    basis = artifactContent.slice(0, 120) || '已存在方案/矩阵/诊断产物，暂作为项目主线依据。'
    source = `来自${typeText(sourceArtifact.type)}`
  } else if (latestQuestion) {
    basis = '当前仅能从最近项目对话推断，建议补一次需求澄清，避免项目主题被零散问答带偏。'
    source = '来自最近对话'
  }
  return { problem, basis, source }
})

const projectBrief = computed(() => {
  const lines = [
    `# ${props.project.name}`,
    '',
    `当前阶段：${projectStage.value}`,
    `项目沉淀：${conversations.value.length} 个对话，${artifactCount.value} 个产物，${citationCount.value} 条引用依据，${reportEvidenceCards.value.length} 条报告证据`,
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
    '',
    '## 引用依据',
    bulletLines(reportEvidenceCards.value.map((card) => `pg.${card.page || '?'} ${card.title || card.section || '已确认证据'}：${compactText(card.summary || card.quote).slice(0, 120)}`), '暂未选择可用于报告的证据卡。'),
  ]
  return lines.join('\n')
})
const briefPreview = computed(() => latestBriefArtifact.value?.content || projectBrief.value)

function renderMarkdown(text) {
  if (!text) return ''
  const tableBlocks = []
  let result = String(text).replace(/((?:\|.*\|(?:\r?\n|$)){2,})/g, (match) => {
    tableBlocks.push(renderMarkdownTable(match))
    return `\x00T${tableBlocks.length - 1}\x00`
  })
  result = escapeHtml(result)
  result = result
    .replace(/^###\s+(.*?)$/gm, '<h4>$1</h4>')
    .replace(/^##\s+(.*?)$/gm, '<h3>$1</h3>')
    .replace(/^#\s+(.*?)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
  result = result.replace(/\x00T(\d+)\x00/g, (_, id) => tableBlocks[Number(id)] || '')

  const blocks = result.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean)
  return blocks.map((block) => {
    if (/^<h[2-4]/.test(block) || block.startsWith('<table')) return block
    if (/^(?:-\s+.*(?:\n|$))+/.test(block)) {
      const items = block.split('\n')
        .filter((line) => line.trim().startsWith('- '))
        .map((line) => `<li>${line.replace(/^-\s+/, '')}</li>`)
        .join('')
      return `<ul>${items}</ul>`
    }
    return `<p>${block.replace(/\n/g, '<br>')}</p>`
  }).join('')
}

function renderMarkdownTable(markdown) {
  const rows = markdown.trim().split(/\r?\n/).filter((line) => line.trim().startsWith('|'))
  if (!rows.length) return escapeHtml(markdown)
  const hasSeparator = rows.length > 1 && /\|?\s*:?-{3,}:?\s*\|/.test(rows[1])
  const headerCells = splitTableRow(rows[0])
  const bodyRows = rows.slice(hasSeparator ? 2 : 1).map(splitTableRow).filter((cells) => cells.length)
  let html = '<table>'
  if (hasSeparator) {
    html += `<thead><tr>${headerCells.map((cell) => `<th>${escapeHtml(cell)}</th>`).join('')}</tr></thead>`
  } else if (headerCells.length) {
    bodyRows.unshift(headerCells)
  }
  html += `<tbody>${bodyRows.map((cells) => `<tr>${cells.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table>`
  return html
}

function splitTableRow(row) {
  return row.split('|').map((cell) => cell.trim()).filter(Boolean)
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function latestArtifactByType(type) {
  return artifacts.value.find((item) => item.type === type) || null
}

function evidenceSourceHint(artifact) {
  const question = compactText(artifact?.metadata?.question || '')
  if (question) return `来自问题：${question}`
  return `${typeText(artifact?.type)}：${artifact?.title || '未命名产物'}`
}

function evidenceSourceText(card) {
  const question = compactText(card?.metadata?.question || '')
  if (question) return `来源问题：${question}`
  const title = compactText(card?.metadata?.artifact_title || card?.metadata?.artifactTitle || '')
  const type = compactText(card?.metadata?.artifact_type_text || card?.metadata?.artifactTypeText || '')
  if (title) return `来源：${type ? `${type} · ` : ''}${title}`
  return '来源：项目证据池'
}

function openArtifact(artifact) {
  selectedArtifact.value = artifact
  copied.value = false
  nextTick(() => detailSection.value?.scrollIntoView({ block: 'start', behavior: 'smooth' }))
}

function artifactMarkdown(artifact) {
  if (!artifact) return ''
  const lines = [
    `# ${artifact.title || '未命名产物'}`,
    '',
    `- 类型：${typeText(artifact.type)}`,
    `- 创建时间：${formatTime(artifact.created_at) || '未知'}`,
    '',
    artifact.content || '',
  ]
  if (hasStructuredData(artifact)) {
    lines.push('', '## 结构化数据', '', '```json', formatJson(artifact.structured_data), '```')
  }
  if (artifact.citations?.length) {
    lines.push('', '## 引用来源')
    for (const citation of artifact.citations) {
      const section = citation.section ? ` ${citation.section}` : ''
      const text = citation.text ? `：${String(citation.text).slice(0, 220)}` : ''
      lines.push(`- pg.${citation.page || '?'}${section}${text}`)
    }
  }
  return lines.join('\n')
}

async function copyArtifactMarkdown() {
  const text = artifactMarkdown(selectedArtifact.value)
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => { copied.value = false }, 1600)
  } catch {
    copied.value = fallbackCopyText(text)
    if (copied.value) setTimeout(() => { copied.value = false }, 1600)
  }
}

function exportArtifactMarkdown() {
  const text = artifactMarkdown(selectedArtifact.value)
  if (!text) return
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${safeFileName(selectedArtifact.value?.title || 'project-artifact')}.md`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

async function exportArtifactPdf() {
  const artifact = selectedArtifact.value
  if (!artifact || !props.project.id) return
  pdfExporting.value = true
  try {
    const blob = await api.downloadProjectArtifactPdf(props.project.id, artifact.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${safeFileName(artifact.title || 'project-artifact')}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (error) {
    window.alert(error?.message || 'PDF 导出失败')
  } finally {
    pdfExporting.value = false
  }
}

function safeFileName(value) {
  return String(value || 'project-artifact').replace(/[\\/:*?"<>|]/g, '_').slice(0, 80)
}

function fallbackCopyText(text) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  try {
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    textarea.remove()
  }
}

function hasStructuredData(artifact) {
  const data = artifact?.structured_data
  return !!data && typeof data === 'object' && Object.keys(data).length > 0
}

function formatJson(value) {
  try {
    return JSON.stringify(value || {}, null, 2)
  } catch {
    return '{}'
  }
}

function pdfViewerUrl(citation) {
  const page = citation?.page || 1
  const sourceId = citation?.source_id || citation?.sourceId || citation?.document_id || 2
  return `/static/pdf-viewer.html?file=${encodeURIComponent(`/pdf/${sourceId}`)}&page=${encodeURIComponent(page)}`
}

function openPdf(item) {
  window.open(pdfViewerUrl(item), '_blank', 'noopener')
}

function evidenceKeyFromCard(card) {
  const text = compactText(card.quote || card.text || '')
  return `${card.document_id || card.source_id || card.sourceId || 2}:${card.page || ''}:${text.slice(0, 180).toLowerCase()}`
}

function isEvidenceSaved(item) {
  return savedEvidenceKeys.value.has(item.key)
}

function evidencePayloadFromItem(item, patch = {}) {
  const tags = Array.isArray(patch.tags) ? patch.tags : (item.tags || [])
  const quote = patch.quote ?? item.quote ?? item.text ?? ''
  return {
    title: patch.title ?? `${item.artifactTypeText || '项目'}依据 pg.${item.page || '?'}`,
    evidence_type: patch.evidence_type ?? tags[0] ?? 'general',
    page: patch.page ?? item.page ?? null,
    section: patch.section ?? item.section ?? '',
    quote,
    summary: patch.summary ?? item.summary ?? compactText(quote).slice(0, 80),
    tags,
    reliability: patch.reliability ?? item.reliability ?? 'medium',
    note: patch.note ?? item.note ?? '',
    status: patch.status ?? item.status ?? 'confirmed',
    usable_in_report: patch.usable_in_report ?? item.usable_in_report ?? false,
    source_id: patch.source_id ?? item.source_id ?? item.sourceId ?? item.document_id ?? null,
    document_id: patch.document_id ?? item.document_id ?? item.source_id ?? item.sourceId ?? null,
    artifact_id: patch.artifact_id ?? item.artifactId ?? item.artifact_id ?? null,
    metadata: {
      ...(item.metadata || {}),
      ...(patch.metadata || {}),
      source_key: item.key || evidenceKeyFromCard(item),
      source_type: item.source_type || item.sourceType || null,
      evidence_level: item.evidence_level || item.evidenceLevel || null,
      artifact_title: item.artifactTitle || null,
      artifact_type_text: item.artifactTypeText || null,
      question: item.question || item.metadata?.question || null,
      source_hint: item.sourceHint || null,
    },
  }
}

async function saveEvidenceItem(item) {
  if (!props.project.id || isEvidenceSaved(item)) return
  savingEvidenceKey.value = item.key
  try {
    const res = await api.createProjectEvidence(props.project.id, evidencePayloadFromItem(item))
    if (res?.evidence_card) {
      savedEvidenceCards.value = [res.evidence_card, ...savedEvidenceCards.value]
    }
  } catch (error) {
    window.alert(error?.message || '保存证据失败')
  } finally {
    savingEvidenceKey.value = ''
  }
}

async function updateEvidenceCard(card, patch) {
  if (!props.project.id || !card?.id) return
  const payload = evidencePayloadFromItem({
    ...card,
    key: card.metadata?.source_key || evidenceKeyFromCard(card),
    text: card.quote,
    source_id: card.document_id,
    artifactId: card.artifact_id,
  }, { ...card, ...patch })
  try {
    const res = await api.updateProjectEvidence(props.project.id, card.id, payload)
    if (res?.evidence_card) {
      savedEvidenceCards.value = savedEvidenceCards.value.map((item) => item.id === card.id ? res.evidence_card : item)
    }
  } catch (error) {
    window.alert(error?.message || '更新证据失败')
  }
}

async function deleteEvidenceCard(card) {
  if (!props.project.id || !card?.id) return false
  try {
    await api.deleteProjectEvidence(props.project.id, card.id)
    savedEvidenceCards.value = savedEvidenceCards.value.filter((item) => item.id !== card.id)
    return true
  } catch (error) {
    window.alert(error?.message || '删除证据失败')
    return false
  }
}

function requestDeleteEvidenceCard(card) {
  pendingDeleteEvidenceCard.value = card
}

function cancelDeleteEvidenceCard() {
  if (deletingEvidenceId.value) return
  pendingDeleteEvidenceCard.value = null
}

async function confirmDeleteEvidenceCard() {
  const card = pendingDeleteEvidenceCard.value
  if (!card?.id || deletingEvidenceId.value) return
  deletingEvidenceId.value = card.id
  try {
    const deleted = await deleteEvidenceCard(card)
    if (deleted) pendingDeleteEvidenceCard.value = null
  } finally {
    deletingEvidenceId.value = null
  }
}

function onEngineeringFileChange(event) {
  selectedEngineeringFile.value = event.target.files?.[0] || null
  engineeringUploadMessage.value = ''
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const value = String(reader.result || '')
      resolve(value.includes(',') ? value.split(',')[1] : value)
    }
    reader.onerror = () => reject(reader.error || new Error('读取文件失败'))
    reader.readAsDataURL(file)
  })
}

async function uploadEngineeringDocument() {
  if (!props.project.id || !selectedEngineeringFile.value) return
  isUploadingEngineeringDocument.value = true
  engineeringUploadMessage.value = ''
  try {
    const file = selectedEngineeringFile.value
    const contentBase64 = await fileToBase64(file)
    const result = await api.uploadEngineeringDocument(props.project.id, {
      filename: file.name,
      mime_type: file.type || '',
      document_kind: engineeringDocumentKind.value,
      source_type: 'current_project',
      content_base64: contentBase64,
    })
    if (result.document) {
      localEngineeringDocuments.value = [result.document, ...localEngineeringDocuments.value.filter((item) => item.id !== result.document.id)]
    }
    if (result.artifact) {
      localArtifacts.value = [result.artifact, ...localArtifacts.value.filter((item) => item.id !== result.artifact.id)]
    }
    selectedEngineeringFile.value = null
    engineeringUploadMessage.value = '已导入，并生成工程案例产物。'
  } catch (error) {
    engineeringUploadMessage.value = error?.message || '导入工程文档失败'
  } finally {
    isUploadingEngineeringDocument.value = false
  }
}

function openDocumentArtifact(doc) {
  const artifactId = Number(doc?.artifact_id || 0)
  if (!artifactId) return
  const artifact = artifacts.value.find((item) => Number(item.id) === artifactId)
  if (artifact) openArtifact(artifact)
}

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
    const text = compactText(item)
    if (!text || seen.has(text)) continue
    seen.add(text)
    result.push(text)
  }
  return result
}

function compactText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function inferEvidenceTags(item) {
  const text = compactText([
    item.text,
    item.section,
    item.artifact?.title,
    item.artifact?.content,
  ].filter(Boolean).join(' ')).toLowerCase()
  const rules = [
    ['材料', /(alloy|aluminum|aluminium|steel|stainless|copper|titanium|iron|nickel|magnesium|铝|钢|铜|钛|铁|镍|镁|合金)/],
    ['性能', /(strength|tensile|yield|elongation|hardness|modulus|fatigue|mechanical|抗拉|屈服|延伸|硬度|疲劳|力学)/],
    ['热处理', /(heat treatment|anneal|aging|solution|quench|temper|t6|t4|退火|时效|固溶|淬火|回火|热处理)/],
    ['铸造工艺', /(casting|foundry|mold|mould|solidification|pouring|die cast|sand cast|铸造|砂型|压铸|凝固|浇注|模具)/],
    ['腐蚀', /(corrosion|oxidation|passivation|rust|salt spray|腐蚀|氧化|钝化|锈)/],
    ['缺陷风险', /(defect|porosity|crack|shrinkage|inclusion|failure|risk|缺陷|气孔|裂纹|缩孔|夹杂|失效|风险)/],
    ['标准依据', /(asm|handbook|standard|specification|astm|标准|规范|手册)/],
  ]
  const tags = []
  for (const [tag, pattern] of rules) {
    if (pattern.test(text)) tags.push(tag)
  }
  return tags.length ? tags : ['通用依据']
}

function sourceTypeText(value) {
  const map = {
    standard_manual: '标准手册',
    enterprise_project: '企业项目',
    current_project: '当前项目',
    structured_asset: '结构化资产',
  }
  return map[value] || '知识来源'
}

function evidenceLevelText(value) {
  const map = {
    standard: '标准依据',
    validated_project: '已验证',
    project_note: '项目记录',
    unverified: '待验证',
  }
  return map[value] || '引用依据'
}

function bulletLines(items, fallback) {
  return items.length ? items.slice(0, 6).map((item) => `- ${item}`).join('\n') : `- ${fallback}`
}

function typeText(type) {
  const map = {
    project_brief: '项目简报',
    qa: '知识问答',
    requirement_clarification: '需求澄清',
    engineering_case: '工程案例',
    solution_draft: '方案草案',
    selection_matrix: '选型矩阵',
    defect_diagnosis: '缺陷诊断',
  }
  return map[type] || '项目产物'
}

function documentKindText(kind) {
  const map = {
    engineering_case: '实验 / 现场记录',
    process_mindmap: '工艺脑图',
    customer_note: '客户资料',
    validation_report: '验证报告',
  }
  return map[kind] || '工程文档'
}

function formatFileSize(size) {
  const bytes = Number(size || 0)
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function documentStatsText(doc) {
  const stats = doc?.structured_data?.statistics || doc?.metadata?.statistics || {}
  const chunkIndex = doc?.chunk_index || doc?.metadata?.chunk_index || {}
  const tableCount = Number(stats.table_count || 0)
  const imageCount = Number(stats.image_count || 0)
  const blockCount = Number(stats.block_count || 0)
  const chunkCount = Number(chunkIndex.chunk_count || 0)
  const parts = [doc?.parse_status || 'stored']
  if (chunkCount) parts.push(`${chunkCount} 块入库`)
  if (blockCount) parts.push(`${blockCount} 块`)
  if (tableCount) parts.push(`${tableCount} 表`)
  if (imageCount) parts.push(`${imageCount} 图`)
  return parts.join(' · ')
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
.overview-section, .brief-section, .document-import-section, .conversation-section, .evidence-section, .artifact-workflow { border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface-2); padding: 13px; }
.section-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.section-title { color: var(--text-primary); font-size: 13px; font-weight: 780; line-height: 1.35; }
.section-title-row p { margin-top: 3px; color: var(--text-muted); font-size: 12px; line-height: 1.5; }
.stage-badge, .brief-toggle, .brief-generate, .brief-evidence-badge { flex: 0 0 auto; border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--border-light)); border-radius: 999px; background: var(--accent-soft); color: var(--accent-strong); padding: 4px 9px; font-size: 11px; font-weight: 760; }
.brief-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.brief-evidence-badge { background: var(--bg-surface); color: var(--text-muted); border-color: var(--border-light); }
.brief-toggle, .brief-generate { cursor: pointer; }
.brief-generate { background: var(--accent); color: #fff; border-color: var(--accent); }
.brief-toggle:hover, .brief-generate:hover { border-color: var(--accent); }
.brief-generate:disabled { opacity: .62; cursor: wait; }
.brief-notice { margin-top: 10px; border: 1px solid color-mix(in srgb, var(--warning, #f59e0b) 26%, var(--border-light)); border-radius: var(--radius-sm); background: color-mix(in srgb, var(--warning, #f59e0b) 10%, var(--bg-surface)); color: var(--text-secondary); padding: 8px 10px; font-size: 12px; line-height: 1.55; }
.overview-grid { margin-top: 12px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.overview-item { min-width: 0; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); padding: 9px; }
.overview-item span, .mini-label { display: block; color: var(--text-muted); font-size: 11px; font-weight: 720; }
.overview-item strong { display: block; margin-top: 3px; color: var(--text-primary); font-size: 14px; line-height: 1.35; font-weight: 780; }
.project-focus { margin-top: 12px; display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--border-light)); border-radius: var(--radius-sm); background: color-mix(in srgb, var(--accent) 7%, var(--bg-surface)); padding: 10px; }
.project-focus strong { display: block; margin-top: 4px; color: var(--text-primary); font-size: 13px; line-height: 1.5; font-weight: 800; text-wrap: pretty; }
.project-focus p { margin-top: 5px; color: var(--text-secondary); font-size: 12px; line-height: 1.65; }
.focus-source { flex: 0 0 auto; border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border-light)); border-radius: 999px; background: var(--bg-surface); color: var(--accent-strong); padding: 3px 8px; font-size: 11px; font-weight: 760; white-space: nowrap; }
.overview-blocks { margin-top: 12px; display: flex; flex-direction: column; gap: 9px; }
.overview-block { border-top: 1px solid var(--border-light); padding-top: 9px; }
.overview-block p, .overview-block li { color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
.overview-block ul { margin-top: 6px; padding-left: 16px; }
.chip-row { margin-top: 7px; display: flex; flex-wrap: wrap; gap: 6px; }
.chip-row span { border: 1px solid var(--border-light); border-radius: 999px; background: var(--bg-surface); color: var(--text-secondary); padding: 4px 8px; font-size: 12px; font-weight: 650; }
.brief-preview { margin-top: 10px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); padding: 10px; }
.brief-markdown { color: var(--text-secondary); font-size: 12px; line-height: 1.72; }
.brief-markdown :deep(h2) { margin: 0 0 10px; color: var(--text-primary); font-size: 16px; line-height: 1.45; font-weight: 820; }
.brief-markdown :deep(h3) { margin: 14px 0 7px; color: var(--text-primary); font-size: 14px; line-height: 1.5; font-weight: 780; }
.brief-markdown :deep(h4) { margin: 12px 0 6px; color: var(--text-primary); font-size: 13px; line-height: 1.45; font-weight: 760; }
.brief-markdown :deep(p) { margin: 0 0 9px; }
.brief-markdown :deep(ul) { margin: 7px 0 10px; padding-left: 18px; }
.brief-markdown :deep(li) { margin: 3px 0; }
.brief-markdown :deep(strong) { color: var(--text-primary); font-weight: 760; }
.brief-markdown :deep(code) { border: 1px solid var(--border-light); border-radius: 5px; background: var(--bg-surface-2); padding: 1px 5px; font-family: var(--font-mono); font-size: 11px; }
.brief-markdown :deep(table) { width: 100%; margin: 9px 0 12px; border-collapse: separate; border-spacing: 0; overflow: hidden; border: 1px solid var(--border-light); border-radius: var(--radius-sm); font-size: 11px; }
.brief-markdown :deep(th), .brief-markdown :deep(td) { border-right: 1px solid var(--border-light); border-bottom: 1px solid var(--border-light); padding: 6px 7px; text-align: left; vertical-align: top; }
.brief-markdown :deep(th) { background: var(--bg-surface-2); color: var(--text-primary); font-weight: 760; }
.brief-markdown :deep(th:last-child), .brief-markdown :deep(td:last-child) { border-right: 0; }
.brief-markdown :deep(tr:last-child td) { border-bottom: 0; }
.document-import-controls { margin-top: 12px; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.35fr) auto; gap: 8px; align-items: center; }
.document-import-controls select,
.file-picker,
.document-import-controls button { min-height: 36px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-secondary); font-size: 12px; font-weight: 700; }
.document-import-controls select { min-width: 0; padding: 0 9px; outline: none; }
.document-import-controls select:focus,
.file-picker:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 14%, transparent); }
.file-picker { min-width: 0; display: flex; align-items: center; padding: 0 10px; cursor: pointer; }
.file-picker input { position: absolute; inline-size: 1px; block-size: 1px; opacity: 0; pointer-events: none; }
.file-picker span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.document-import-controls button { flex: 0 0 auto; padding: 0 13px; color: #fff; background: var(--accent); border-color: var(--accent); cursor: pointer; }
.document-import-controls button:disabled { opacity: .55; cursor: default; }
.document-import-message { margin-top: 8px; color: var(--accent-strong); font-size: 12px; line-height: 1.5; }
.document-list { margin-top: 11px; display: flex; flex-direction: column; gap: 7px; }
.document-card { display: flex; justify-content: space-between; gap: 10px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); padding: 9px 10px; cursor: pointer; transition: border-color .16s ease, background .16s ease; }
.document-card:hover, .document-card:focus-visible { border-color: var(--accent); background: var(--accent-soft); outline: none; }
.document-card strong { display: block; color: var(--text-primary); font-size: 12px; line-height: 1.4; font-weight: 760; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.document-card span { display: block; margin-top: 3px; color: var(--text-muted); font-size: 11px; line-height: 1.35; }
.document-card time { flex: 0 0 auto; color: var(--text-muted); font-size: 11px; white-space: nowrap; }
.conversation-section { display: flex; flex-direction: column; gap: 7px; }
.conversation-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 3px; }
.conversation-head p { margin-top: 3px; color: var(--text-muted); font-size: 12px; line-height: 1.45; }
.conversation-toggle { flex: 0 0 auto; border: 1px solid var(--border-light); border-radius: 999px; background: var(--bg-surface); color: var(--text-secondary); padding: 4px 8px; font-size: 11px; font-weight: 760; cursor: pointer; }
.conversation-toggle:hover { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-strong); }
.conversation-row { width: 100%; min-height: 38px; display: flex; align-items: center; justify-content: space-between; gap: 10px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-secondary); padding: 8px 10px; cursor: pointer; text-align: left; }
.conversation-row:hover { border-color: var(--accent); background: var(--accent-soft); color: var(--text-primary); }
.conversation-row span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 700; }
.conversation-row time { flex: 0 0 auto; color: var(--text-muted); font-size: 11px; }
.evidence-count { flex: 0 0 auto; border: 1px solid var(--border-light); border-radius: 999px; background: var(--bg-surface); color: var(--text-muted); padding: 4px 8px; font-size: 11px; font-family: var(--font-mono); font-weight: 720; }
.evidence-tools { margin-top: 12px; display: flex; flex-direction: column; gap: 9px; }
.evidence-search { height: 36px; display: flex; align-items: center; gap: 8px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-muted); padding: 0 10px; }
.evidence-search:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 16%, transparent); }
.evidence-search svg { width: 15px; height: 15px; flex: 0 0 auto; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; }
.evidence-search input { width: 100%; min-width: 0; border: 0; outline: none; background: transparent; color: var(--text-primary); font-size: 12px; }
.evidence-search input::placeholder { color: var(--text-muted); opacity: 1; }
.evidence-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.evidence-tags button { border: 1px solid var(--border-light); border-radius: 999px; background: var(--bg-surface); color: var(--text-secondary); padding: 4px 8px; font-size: 11px; font-weight: 700; cursor: pointer; }
.evidence-tags button:hover, .evidence-tags button.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-strong); }
.confirmed-evidence { margin-top: 12px; border-top: 1px solid var(--border-light); padding-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.confirmed-card { border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border-light)); border-radius: var(--radius-sm); background: color-mix(in srgb, var(--accent) 8%, var(--bg-surface)); padding: 10px; }
.confirmed-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.confirmed-head strong { display: block; color: var(--text-primary); font-size: 13px; line-height: 1.4; font-weight: 780; }
.confirmed-head span { display: block; margin-top: 3px; color: var(--text-muted); font-family: var(--font-mono); font-size: 11px; }
.confirmed-head em { display: block; margin-top: 4px; color: var(--text-secondary); font-style: normal; font-size: 11px; line-height: 1.45; }
.confirmed-head button, .evidence-actions button { flex: 0 0 auto; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-secondary); padding: 5px 8px; font-size: 11px; font-weight: 720; cursor: pointer; }
.confirmed-head button:hover, .evidence-actions button:hover { border-color: var(--accent); color: var(--accent-strong); background: var(--accent-soft); }
.confirmed-card p { margin-top: 7px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.confirmed-controls { margin-top: 9px; display: flex; flex-wrap: wrap; align-items: center; gap: 7px; }
.confirmed-controls label { display: inline-flex; align-items: center; gap: 5px; color: var(--text-secondary); font-size: 11px; font-weight: 720; }
.confirmed-controls input { accent-color: var(--accent); }
.confirmed-controls select { min-height: 28px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-secondary); padding: 0 7px; font-size: 11px; outline: none; }
.confirmed-controls select:focus { border-color: var(--accent); }
.confirmed-controls .danger-text {
  margin-left: auto;
  border-color: transparent;
  background: transparent;
  color: var(--text-muted);
}
.confirmed-controls .danger-text:hover {
  border-color: color-mix(in srgb, #ef4444 26%, var(--border-light));
  background: color-mix(in srgb, #ef4444 8%, var(--bg-surface));
  color: #dc2626;
}
.danger-icon-btn {
  width: 30px;
  height: 30px;
  display: inline-grid;
  place-items: center;
  padding: 0;
}
.danger-icon-btn svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.confirmed-card textarea { width: 100%; margin-top: 8px; resize: vertical; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); padding: 7px 8px; font-size: 12px; line-height: 1.5; outline: none; }
.confirmed-card textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 14%, transparent); }
.evidence-list { margin-top: 11px; display: flex; flex-direction: column; gap: 8px; }
.evidence-card { display: block; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: inherit; text-decoration: none; padding: 10px; transition: border-color .16s ease, background .16s ease; }
.evidence-card:hover { border-color: var(--accent); background: var(--accent-soft); }
.evidence-card-head { display: flex; align-items: center; gap: 7px; color: var(--text-muted); font-family: var(--font-mono); font-size: 11px; line-height: 1.3; }
.evidence-page { color: var(--accent-strong); font-weight: 820; }
.evidence-card p { margin-top: 6px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.evidence-card-foot { margin-top: 8px; display: flex; align-items: center; gap: 7px; min-width: 0; color: var(--text-muted); font-size: 11px; }
.evidence-card-foot span { flex: 0 0 auto; border: 1px solid var(--border-light); border-radius: 999px; padding: 2px 6px; }
.evidence-card-foot strong { min-width: 0; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 720; }
.evidence-card-tags { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 5px; }
.evidence-card-tags span { border-radius: 999px; background: color-mix(in srgb, var(--accent) 12%, var(--bg-surface-2)); color: var(--accent-strong); padding: 3px 7px; font-size: 11px; font-weight: 720; }
.evidence-actions { margin-top: 9px; display: flex; justify-content: flex-end; gap: 7px; }
.evidence-actions button:last-child { border-color: color-mix(in srgb, var(--accent) 36%, var(--border-light)); color: var(--accent-strong); }
.evidence-actions button:disabled { opacity: .55; cursor: default; }
.evidence-empty { margin-top: 11px; border: 1px dashed var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); padding: 16px 12px; text-align: center; }
.evidence-empty strong { display: block; color: var(--text-secondary); font-size: 13px; }
.evidence-empty p { margin-top: 5px; color: var(--text-muted); font-size: 12px; line-height: 1.55; }
.workflow-list { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
.workflow-section { border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); overflow: hidden; }
.workflow-head { display: flex; justify-content: space-between; gap: 10px; padding: 10px; border-bottom: 1px solid var(--border-light); }
.workflow-head span { display: block; color: var(--text-primary); font-size: 13px; font-weight: 760; }
.workflow-head small { display: block; margin-top: 2px; color: var(--text-muted); font-size: 11px; line-height: 1.45; }
.workflow-head strong { flex: 0 0 auto; color: var(--accent-strong); font-size: 13px; font-weight: 800; }
.artifact-list { padding: 9px; display: flex; flex-direction: column; gap: 8px; }
.artifact-card { border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface-2); padding: 10px; cursor: pointer; transition: border-color .16s ease, background .16s ease; }
.artifact-card:hover, .artifact-card:focus-visible { border-color: var(--accent); background: var(--accent-soft); outline: none; }
.artifact-topline { display: flex; align-items: center; justify-content: space-between; gap: 8px; color: var(--text-muted); font-size: 11px; font-weight: 700; }
.artifact-card h3 { margin-top: 7px; font-size: 13px; line-height: 1.45; font-weight: 760; }
.artifact-card p { margin-top: 6px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.artifact-foot { margin-top: 8px; display: flex; gap: 7px; color: var(--accent-strong); font-size: 11px; font-weight: 720; }
.workflow-empty { padding: 10px; color: var(--text-muted); font-size: 12px; line-height: 1.6; }
.workflow-empty p { margin: 0; }
.workflow-empty button { margin-top: 9px; min-height: 30px; border: 1px solid color-mix(in srgb, var(--accent) 32%, var(--border-light)); border-radius: var(--radius-sm); background: var(--accent-soft); color: var(--accent-strong); padding: 0 10px; font-size: 12px; font-weight: 760; cursor: pointer; }
.workflow-empty button:hover { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 14%, var(--bg-surface)); }
.artifact-detail { border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--border-light)); border-radius: var(--radius-md); background: var(--bg-surface-2); padding: 13px; }
.detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.detail-head p { margin-top: 3px; color: var(--text-muted); font-size: 12px; line-height: 1.5; }
.detail-close { flex: 0 0 auto; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-secondary); padding: 5px 9px; font-size: 12px; font-weight: 700; cursor: pointer; }
.detail-close:hover { border-color: var(--accent); color: var(--text-primary); }
.detail-actions { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 7px; }
.detail-actions button { border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--border-light)); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--accent-strong); padding: 7px 10px; font-size: 12px; font-weight: 750; cursor: pointer; }
.detail-actions button:hover { background: var(--accent-soft); border-color: var(--accent); }
.detail-block { margin-top: 12px; border-top: 1px solid var(--border-light); padding-top: 10px; }
.detail-block pre { margin: 7px 0 0; max-height: 360px; overflow: auto; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-secondary); padding: 10px; font-family: var(--font-mono); font-size: 11px; line-height: 1.65; white-space: pre-wrap; }
.detail-citation { display: block; margin-top: 7px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: inherit; padding: 9px; text-decoration: none; }
.detail-citation:hover { border-color: var(--accent); background: var(--accent-soft); }
.detail-citation strong { color: var(--accent-strong); font-family: var(--font-mono); font-size: 11px; }
.detail-citation span { margin-left: 7px; color: var(--text-muted); font-size: 11px; }
.detail-citation p { margin-top: 5px; color: var(--text-secondary); font-size: 12px; line-height: 1.55; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.confirm-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 22px;
  background: rgba(2, 6, 23, .66);
}
.confirm-dialog {
  width: min(430px, 100%);
  position: relative;
  border: 1px solid color-mix(in srgb, #ef4444 28%, var(--border-light));
  border-radius: var(--radius-md);
  background: var(--bg-panel);
  color: var(--text-primary);
  padding: 22px;
  box-shadow: var(--shadow-panel);
}
.confirm-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 34px;
  height: 34px;
  display: inline-grid;
  place-items: center;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-muted);
  cursor: pointer;
}
.confirm-close svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
}
.confirm-close:hover { border-color: var(--accent); color: var(--text-primary); }
.confirm-kicker {
  color: #fca5a5;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 820;
  letter-spacing: .04em;
}
.confirm-dialog h3 {
  margin-top: 8px;
  padding-right: 44px;
  color: var(--text-primary);
  font-size: 19px;
  line-height: 1.35;
  font-weight: 820;
}
.confirm-dialog p {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}
.confirm-preview {
  margin-top: 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  padding: 11px 12px;
}
.confirm-preview strong {
  display: block;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.45;
  font-weight: 780;
}
.confirm-preview span {
  display: -webkit-box;
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.6;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.confirm-actions {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
.confirm-actions button {
  min-height: 36px;
  border-radius: var(--radius-sm);
  padding: 0 14px;
  font-size: 12px;
  font-weight: 780;
  cursor: pointer;
}
.confirm-secondary {
  border: 1px solid var(--border-light);
  background: var(--bg-surface);
  color: var(--text-secondary);
}
.confirm-secondary:hover { border-color: var(--accent); color: var(--text-primary); }
.confirm-danger {
  border: 1px solid color-mix(in srgb, #ef4444 72%, #7f1d1d);
  background: #dc2626;
  color: #fff;
}
.confirm-danger:hover {
  background: #b91c1c;
  border-color: #ef4444;
}
.confirm-actions button:disabled,
.confirm-close:disabled {
  opacity: .6;
  cursor: wait;
}
@media (max-width: 1120px) {
  .project-panel { position: fixed; right: 0; top: 0; z-index: 28; box-shadow: var(--shadow-panel); }
}
@media (max-width: 640px) {
  .project-panel { width: min(100vw, 430px); min-width: 0; }
  .overview-grid { grid-template-columns: 1fr; }
  .document-import-controls { grid-template-columns: 1fr; }
  .confirm-dialog { padding: 18px; }
  .confirm-actions { flex-direction: column-reverse; }
  .confirm-actions button { width: 100%; }
}
</style>
