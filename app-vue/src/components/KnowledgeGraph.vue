<template>
  <section v-if="hasGraph" class="knowledge-graph" aria-label="Knowledge graph">
    <div class="graph-header">
      <div class="graph-kicker">{{ graphLabel }}</div>
      <div class="graph-heading">
        <h3>{{ graph.title }}</h3>
        <div class="graph-summary">{{ graph.summary }}</div>
      </div>
    </div>

    <div class="graph-canvas">
      <svg class="graph-edges" viewBox="0 0 100 100" aria-hidden="true">
        <line
          v-for="edge in layoutEdges"
          :key="`${edge.source}-${edge.target}`"
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
        :class="nodeClass(node.type)"
        :style="{ left: `${node.x}%`, top: `${node.y}%` }"
        type="button"
        @click="selectedId = node.id"
      >
        <span class="node-type">{{ typeName(node.type) }}</span>
        <span class="node-label">{{ node.label }}</span>
      </button>
    </div>

    <div v-if="selectedNode" class="graph-detail">
      <div class="detail-type">{{ typeName(selectedNode.type) }}</div>
      <div class="detail-title">{{ selectedNode.label }}</div>
      <p>{{ selectedNode.meta || defaultDetail }}</p>
      <button v-if="selectedNode.page" type="button" class="detail-link" @click="openPage(selectedNode.page)">
        {{ openSourceText }}
      </button>
    </div>

    <div class="graph-legend">
      <span v-for="item in legend" :key="item.type" :class="['legend-item', item.type]">
        <i></i>{{ item.label }}
      </span>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  graph: { type: Object, default: null },
})

const selectedId = ref('root')
const graphLabel = '\u77e5\u8bc6\u56fe\u8c31'
const defaultDetail = '\u4ece\u672c\u8f6e\u95ee\u7b54\u548c\u5f15\u7528\u4e2d\u62bd\u53d6\u7684\u77e5\u8bc6\u8282\u70b9'
const openSourceText = '\u6253\u5f00\u6765\u6e90\u9875'
const typeLabels = {
  material: '\u6750\u6599',
  material_state: '\u72b6\u6001',
  property: '\u6027\u80fd',
  property_value: '\u53c2\u6570',
  process: '\u5de5\u827a',
  condition: '\u6761\u4ef6',
  application: '\u5e94\u7528',
  source: '\u6765\u6e90',
  risk: '\u98ce\u9669',
}

const legend = [
  { type: 'material', label: '\u4e3b\u9898' },
  { type: 'material_state', label: '\u72b6\u6001' },
  { type: 'property_value', label: '\u53c2\u6570' },
  { type: 'process', label: '\u5de5\u827a' },
  { type: 'condition', label: '\u6761\u4ef6' },
  { type: 'application', label: '\u5e94\u7528' },
  { type: 'risk', label: '\u98ce\u9669' },
  { type: 'source', label: '\u6765\u6e90' },
]

const hasGraph = computed(() => (props.graph?.nodes || []).length > 1)

const layoutNodes = computed(() => {
  const nodes = props.graph?.nodes || []
  const root = nodes.find((node) => node.id === 'root') || nodes[0]
  const others = nodes.filter((node) => node.id !== root?.id)
  const topicNodes = others.filter((node) => node.type !== 'source')
  const sourceNodes = others.filter((node) => node.type === 'source')
  const laidOut = []

  if (root) laidOut.push({ ...root, x: 50, y: 48 })

  topicNodes.forEach((node, index) => {
    const total = Math.max(topicNodes.length, 1)
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / total
    laidOut.push({
      ...node,
      x: 50 + Math.cos(angle) * 34,
      y: 48 + Math.sin(angle) * 30,
    })
  })

  sourceNodes.forEach((node, index) => {
    laidOut.push({
      ...node,
      x: 22 + index * 28,
      y: 90,
    })
  })

  return laidOut
})

const layoutEdges = computed(() => {
  const positions = new Map(layoutNodes.value.map((node) => [node.id, node]))
  return (props.graph?.edges || []).map((edge) => {
    const source = positions.get(edge.source)
    const target = positions.get(edge.target)
    if (!source || !target) return null
    return {
      ...edge,
      x1: source.x,
      y1: source.y,
      x2: target.x,
      y2: target.y,
    }
  }).filter(Boolean)
})

const selectedNode = computed(() => {
  const nodes = props.graph?.nodes || []
  return nodes.find((node) => node.id === selectedId.value) || nodes[0]
})

watch(() => props.graph, () => {
  selectedId.value = 'root'
})

function typeName(type) {
  return typeLabels[type] || type
}

function nodeClass(type) {
  return String(type || '').replace(/_/g, '-')
}

function openPage(page) {
  window.open(`/static/pdf-viewer.html?page=${page}`, '_blank')
}
</script>

<style scoped>
.knowledge-graph {
  margin-top: 14px;
  max-width: 100%;
  min-width: 0;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--bg-surface-2);
  overflow: hidden;
}

.graph-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: start;
  gap: 10px;
  padding: 12px 14px 10px;
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-surface);
}

.graph-kicker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-strong);
  background: var(--accent-soft);
  border: 1px solid color-mix(in srgb, var(--accent) 22%, transparent);
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 750;
  line-height: 1.2;
  white-space: nowrap;
}

.graph-heading {
  min-width: 0;
}

.graph-header h3 {
  font-size: 15px;
  line-height: 1.35;
  font-weight: 720;
  color: var(--text-primary);
  overflow-wrap: anywhere;
  text-wrap: pretty;
}

.graph-summary {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.4;
  margin-top: 3px;
  overflow-wrap: anywhere;
}

.graph-canvas {
  position: relative;
  width: 100%;
  max-width: 100%;
  height: 310px;
  min-height: 310px;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 48%, color-mix(in srgb, var(--accent-soft) 72%, transparent) 0 28%, transparent 29%),
    var(--bg-surface-2);
}

.graph-edges {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.graph-edges line {
  stroke: color-mix(in srgb, var(--border-strong) 74%, transparent);
  stroke-width: .55;
}

.graph-node {
  position: absolute;
  width: 118px;
  min-height: 52px;
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
  box-shadow: 0 2px 8px rgba(16, 24, 40, .05);
  transition: border-color .16s ease, background .16s ease, transform .16s ease;
}

.graph-node:hover,
.graph-node:focus-visible {
  border-color: var(--accent);
  background: var(--accent-soft);
  transform: translate(-50%, -50%) translateY(-1px);
}

.graph-node.material {
  width: 142px;
  min-height: 62px;
  border-color: color-mix(in srgb, var(--accent) 46%, var(--border-light));
  background: var(--accent-soft);
}

.graph-node.material-state,
.graph-node.process {
  border-color: color-mix(in srgb, var(--warning) 35%, var(--border-light));
}

.graph-node.property-value,
.graph-node.property {
  border-color: color-mix(in srgb, var(--info) 32%, var(--border-light));
}

.graph-node.condition {
  border-color: color-mix(in srgb, var(--success) 34%, var(--border-light));
}

.graph-node.risk {
  border-color: color-mix(in srgb, var(--danger) 34%, var(--border-light));
}

.graph-node.source {
  width: 94px;
  min-height: 44px;
}

.node-type {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
}

.node-label {
  max-width: 100%;
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.25;
  font-weight: 720;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.graph-detail {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px 10px;
  padding: 10px 14px;
  border-top: 1px solid var(--border-light);
  background: var(--bg-surface);
}

.detail-type {
  color: var(--accent-strong);
  background: var(--accent-soft);
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 750;
}

.detail-title {
  min-width: 0;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 720;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.graph-detail p {
  grid-column: 2 / -1;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.detail-link {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--accent-strong);
  padding: 5px 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.detail-link:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.graph-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 7px 12px;
  padding: 10px 14px 12px;
  color: var(--text-muted);
  font-size: 11px;
  border-top: 1px solid var(--border-light);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.legend-item i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}

.legend-item.material i { background: var(--accent); }
.legend-item.material_state i { background: var(--warning); }
.legend-item.property i { background: var(--info); }
.legend-item.property_value i { background: var(--info); }
.legend-item.process i { background: var(--warning); }
.legend-item.condition i { background: var(--success); }
.legend-item.application i { background: #7c3aed; }
.legend-item.risk i { background: var(--danger); }
.legend-item.source i { background: var(--text-muted); }

@media (max-width: 720px) {
  .graph-header {
    grid-template-columns: 1fr;
    gap: 7px;
  }

  .graph-kicker {
    justify-self: start;
  }

  .graph-detail {
    grid-template-columns: 1fr;
  }

  .graph-canvas {
    height: 330px;
  }

  .graph-node {
    width: 96px;
    min-height: 48px;
    padding: 7px 8px;
  }

  .graph-node.material {
    width: 118px;
    min-height: 56px;
  }

  .graph-node.source {
    width: 84px;
  }

  .node-label {
    font-size: 11px;
  }
}
</style>
