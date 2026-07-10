<template>
  <section v-if="hasGraph" class="knowledge-graph" aria-label="Knowledge graph">
    <div class="graph-header">
      <div>
        <div class="graph-kicker">知识图谱</div>
        <h3>{{ graphTitle }}</h3>
      </div>
      <div class="graph-meta">
        <span>{{ factNodes.length }} 个知识点</span>
        <span>{{ semanticEdges.length }} 条关系</span>
      </div>
    </div>

    <p v-if="graphSummary" class="graph-summary">{{ graphSummary }}</p>

    <div class="insight-strip">
      <button
        v-for="node in primaryFacts"
        :key="node.id"
        type="button"
        class="insight-chip"
        :class="{ active: selectedId === node.id }"
        @click="selectNode(node.id)"
      >
        <span>{{ typeName(node.type) }}</span>
        <strong>{{ node.label }}</strong>
      </button>
    </div>

    <div class="graph-body">
      <div class="graph-map">
        <svg class="graph-edges" viewBox="0 0 100 100" aria-hidden="true">
          <line
            v-for="edge in layoutEdges"
            :key="`${edge.source}-${edge.target}-${edge.label}`"
            :x1="edge.x1"
            :y1="edge.y1"
            :x2="edge.x2"
            :y2="edge.y2"
          />
        </svg>

        <button
          v-for="node in layoutNodes"
          :key="node.id"
          class="graph-node"
          :class="[nodeClass(node.type), { active: selectedId === node.id }]"
          :style="{ left: `${node.x}%`, top: `${node.y}%` }"
          type="button"
          @click="selectNode(node.id)"
        >
          <span class="node-type">{{ typeName(node.type) }}</span>
          <span class="node-label">{{ node.label }}</span>
        </button>
      </div>

      <aside class="graph-detail">
        <div class="detail-type">{{ typeName(selectedNode.type) }}</div>
        <h4>{{ selectedNode.label }}</h4>
        <p>{{ selectedNode.meta || defaultDetail }}</p>

        <div v-if="selectedRelations.length" class="relation-list">
          <div class="detail-label">关联关系</div>
          <button
            v-for="relation in selectedRelations"
            :key="`${relation.source}-${relation.target}-${relation.label}`"
            type="button"
            class="relation-item"
            @click="selectNode(relation.other.id)"
          >
            <span>{{ relation.label }}</span>
            <strong>{{ relation.other.label }}</strong>
          </button>
        </div>

        <div v-if="evidenceNodes.length" class="evidence-list">
          <div class="detail-label">证据来源</div>
          <button
            v-for="source in evidenceNodes"
            :key="source.id"
            type="button"
            class="evidence-item"
            @click="source.page ? openPage(source.page, source.source_id || source.sourceId) : selectNode(source.id)"
          >
            <span>{{ source.label }}</span>
            <small>{{ source.meta || '引用片段' }}</small>
          </button>
        </div>
      </aside>
    </div>

    <div class="category-rail">
      <button
        v-for="group in groupedFacts"
        :key="group.type"
        type="button"
        class="category-card"
        :class="nodeClass(group.type)"
        @click="selectNode(group.nodes[0].id)"
      >
        <span>{{ typeName(group.type) }}</span>
        <strong>{{ group.nodes.length }}</strong>
        <em>{{ group.nodes.slice(0, 2).map((node) => node.label).join(' / ') }}</em>
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  graph: { type: Object, default: null },
})

const selectedId = ref('root')
const defaultDetail = '从本轮问答和引用中抽取的工程知识节点'

const typeLabels = {
  material: '材料',
  material_state: '状态',
  property: '性能',
  property_value: '参数',
  process: '工艺',
  condition: '条件',
  application: '应用',
  source: '来源',
  risk: '风险',
}

const typeOrder = [
  'material_state',
  'property_value',
  'property',
  'process',
  'condition',
  'application',
  'risk',
  'source',
]

const hasGraph = computed(() => (props.graph?.nodes || []).length > 1)

const graphNodes = computed(() => props.graph?.nodes || [])
const graphEdges = computed(() => props.graph?.edges || [])
const rootNode = computed(() => graphNodes.value.find((node) => node.id === 'root') || graphNodes.value[0] || {})
const sourceNodes = computed(() => graphNodes.value.filter((node) => node.type === 'source'))
const factNodes = computed(() => graphNodes.value.filter((node) => node.id !== rootNode.value.id && node.type !== 'source'))
const semanticEdges = computed(() => graphEdges.value.filter((edge) => edge.source && edge.target))
const graphTitle = computed(() => props.graph?.title || `${rootNode.value.label || '材料知识'}图谱`)
const graphSummary = computed(() => props.graph?.summary || '')

const primaryFacts = computed(() => {
  const priority = new Map(typeOrder.map((type, index) => [type, index]))
  return [...factNodes.value]
    .sort((a, b) => (priority.get(a.type) ?? 99) - (priority.get(b.type) ?? 99))
    .slice(0, 4)
})

const groupedFacts = computed(() => {
  const groups = new Map()
  for (const node of factNodes.value) {
    if (!groups.has(node.type)) groups.set(node.type, [])
    groups.get(node.type).push(node)
  }
  return typeOrder
    .filter((type) => groups.has(type))
    .map((type) => ({ type, nodes: groups.get(type) }))
})

const layoutNodes = computed(() => {
  const laidOut = []
  if (rootNode.value?.id) laidOut.push({ ...rootNode.value, x: 50, y: 50 })

  const rows = [
    { types: ['material_state', 'process'], y: 20, limit: 3 },
    { types: ['property_value', 'property'], y: 40, limit: 4 },
    { types: ['condition', 'application', 'risk'], y: 70, limit: 3 },
  ]

  for (const row of rows) {
    const nodes = factNodes.value.filter((node) => row.types.includes(node.type)).slice(0, row.limit)
    nodes.forEach((node, index) => {
      const total = Math.max(nodes.length, 1)
      const span = total === 1 ? 0 : 58
      laidOut.push({
        ...node,
        x: 50 - span / 2 + (span * index) / Math.max(total - 1, 1),
        y: row.y,
      })
    })
  }

  sourceNodes.value.slice(0, 3).forEach((node, index) => {
    laidOut.push({ ...node, x: 26 + index * 24, y: 88 })
  })

  return laidOut
})

const layoutEdges = computed(() => {
  const positions = new Map(layoutNodes.value.map((node) => [node.id, node]))
  const preferred = semanticEdges.value.length
    ? semanticEdges.value
    : factNodes.value.map((node) => ({ source: rootNode.value.id, target: node.id, label: '关联' }))

  return preferred
    .map((edge) => {
      const source = positions.get(edge.source)
      const target = positions.get(edge.target)
      if (!source || !target || edge.source === edge.target) return null
      return { ...edge, x1: source.x, y1: source.y, x2: target.x, y2: target.y }
    })
    .filter(Boolean)
})

const selectedNode = computed(() => {
  return graphNodes.value.find((node) => node.id === selectedId.value) || rootNode.value || graphNodes.value[0] || {}
})

const selectedRelations = computed(() => {
  const nodeMap = new Map(graphNodes.value.map((node) => [node.id, node]))
  return semanticEdges.value
    .map((edge) => {
      if (edge.source === selectedNode.value.id) return { ...edge, other: nodeMap.get(edge.target) }
      if (edge.target === selectedNode.value.id) return { ...edge, other: nodeMap.get(edge.source) }
      return null
    })
    .filter((edge) => edge?.other && edge.other.type !== 'source')
    .slice(0, 5)
})

const evidenceNodes = computed(() => {
  if (selectedNode.value.type === 'source') return [selectedNode.value]
  const linkedSources = semanticEdges.value
    .filter((edge) => edge.source === selectedNode.value.id || edge.target === selectedNode.value.id)
    .map((edge) => graphNodes.value.find((node) => node.id === edge.source || node.id === edge.target))
    .filter((node) => node?.type === 'source')

  return (linkedSources.length ? linkedSources : sourceNodes.value).slice(0, 3)
})

watch(() => props.graph, () => {
  selectedId.value = 'root'
})

function typeName(type) {
  return typeLabels[type] || type || '节点'
}

function nodeClass(type) {
  return String(type || '').replace(/_/g, '-')
}

function selectNode(id) {
  selectedId.value = id
}

function openPage(page, sourceId = 2) {
  const file = encodeURIComponent(`/pdf/${sourceId || 2}`)
  window.open(`/static/pdf-viewer.html?file=${file}&page=${encodeURIComponent(page)}`, '_blank')
}
</script>

<style scoped>
.knowledge-graph {
  container-type: inline-size;
  margin-top: 16px;
  max-width: 100%;
  min-width: 0;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  overflow: hidden;
}

.graph-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 15px 16px 10px;
  border-bottom: 1px solid var(--border-light);
}

.graph-kicker {
  width: max-content;
  color: var(--accent-strong);
  font-size: 12px;
  font-weight: 760;
  line-height: 1.2;
}

.graph-header h3 {
  margin-top: 5px;
  color: var(--text-primary);
  font-size: 16px;
  line-height: 1.35;
  font-weight: 760;
  text-wrap: balance;
}

.graph-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  flex: 0 0 auto;
}

.graph-meta span {
  border: 1px solid var(--border-light);
  border-radius: 999px;
  padding: 4px 8px;
  color: var(--text-secondary);
  background: var(--bg-surface-2);
  font-size: 11px;
  font-weight: 700;
}

.graph-summary {
  margin: 0;
  padding: 0 16px 12px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
}

.insight-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(138px, 1fr));
  gap: 8px;
  padding: 0 16px 14px;
}

.insight-chip {
  min-width: 0;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface-2);
  color: var(--text-primary);
  padding: 9px 10px;
  text-align: left;
  cursor: pointer;
  transition: border-color .16s ease, background .16s ease;
}

.insight-chip:hover,
.insight-chip.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.insight-chip span,
.detail-label {
  display: block;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 740;
}

.insight-chip strong {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.graph-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 28%);
  min-height: 330px;
  border-top: 1px solid var(--border-light);
}

.graph-map {
  position: relative;
  min-width: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--accent-soft) 82%, transparent) 0 18%, transparent 19%),
    linear-gradient(180deg, var(--bg-surface-2), var(--bg-surface));
}

.graph-edges {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.graph-edges line {
  stroke: color-mix(in srgb, var(--border-strong) 72%, transparent);
  stroke-width: .48;
}

.graph-node {
  position: absolute;
  width: 118px;
  min-height: 48px;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 3px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: 8px 10px;
  cursor: pointer;
  text-align: left;
  transition: border-color .16s ease, background .16s ease, transform .16s ease;
}

.graph-node:hover,
.graph-node:focus-visible,
.graph-node.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  transform: translate(-50%, -50%) translateY(-1px);
}

.graph-node.material {
  width: 150px;
  min-height: 62px;
  border-color: color-mix(in srgb, var(--accent) 54%, var(--border-light));
  background: var(--accent-soft);
}

.graph-node.material-state,
.graph-node.process {
  border-color: color-mix(in srgb, var(--warning) 34%, var(--border-light));
}

.graph-node.property-value,
.graph-node.property {
  border-color: color-mix(in srgb, var(--info) 34%, var(--border-light));
}

.graph-node.condition,
.graph-node.application {
  border-color: color-mix(in srgb, var(--success) 32%, var(--border-light));
}

.graph-node.risk {
  border-color: color-mix(in srgb, var(--danger) 36%, var(--border-light));
}

.graph-node.source {
  width: 92px;
  min-height: 40px;
}

.node-type {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 720;
}

.node-label {
  max-width: 100%;
  overflow: hidden;
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.25;
  font-weight: 760;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.graph-detail {
  min-width: 0;
  border-left: 1px solid var(--border-light);
  background: var(--bg-surface);
  padding: 14px;
}

.detail-type {
  width: max-content;
  border-radius: 999px;
  padding: 3px 8px;
  color: var(--accent-strong);
  background: var(--accent-soft);
  font-size: 11px;
  font-weight: 760;
}

.graph-detail h4 {
  margin-top: 9px;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.35;
  font-weight: 760;
  overflow-wrap: anywhere;
}

.graph-detail p {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.relation-list,
.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 14px;
}

.relation-item,
.evidence-item {
  display: block;
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface-2);
  color: var(--text-primary);
  padding: 8px 9px;
  text-align: left;
  cursor: pointer;
  transition: border-color .16s ease, background .16s ease;
}

.relation-item:hover,
.evidence-item:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.relation-item span,
.evidence-item small {
  display: block;
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.35;
}

.relation-item strong,
.evidence-item span {
  display: block;
  margin-top: 3px;
  overflow: hidden;
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.35;
  font-weight: 740;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-rail {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
  gap: 8px;
  padding: 12px 16px 15px;
  border-top: 1px solid var(--border-light);
  background: var(--bg-surface-2);
}

.category-card {
  min-width: 0;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: 8px 9px;
  text-align: left;
  cursor: pointer;
}

.category-card span {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 740;
}

.category-card strong {
  margin-left: 6px;
  color: var(--accent-strong);
  font-size: 13px;
}

.category-card em {
  display: block;
  margin-top: 5px;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 11px;
  font-style: normal;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 820px) {
  .graph-header {
    flex-direction: column;
  }

  .graph-meta {
    justify-content: flex-start;
  }

  .graph-body {
    grid-template-columns: 1fr;
  }

  .graph-map {
    min-height: 340px;
  }

  .graph-detail {
    border-left: 0;
    border-top: 1px solid var(--border-light);
  }

  .graph-node {
    width: 96px;
    min-height: 46px;
    padding: 7px 8px;
  }

  .graph-node.material {
    width: 120px;
  }

  .node-label {
    font-size: 11px;
  }
}

@container (max-width: 680px) {
  .graph-header {
    flex-direction: column;
  }

  .graph-meta {
    justify-content: flex-start;
  }

  .insight-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .graph-body {
    grid-template-columns: 1fr;
  }

  .graph-map {
    min-height: 360px;
  }

  .graph-detail {
    border-left: 0;
    border-top: 1px solid var(--border-light);
  }

  .graph-node {
    width: 88px;
    min-height: 44px;
    padding: 7px 8px;
  }

  .graph-node.material {
    width: 118px;
    min-height: 56px;
  }

  .graph-node.source {
    width: 82px;
  }

  .node-label {
    font-size: 11px;
  }
}
</style>
