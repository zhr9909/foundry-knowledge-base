const PROPERTY_KEYWORDS = [
  '\u6297\u62c9\u5f3a\u5ea6',
  '\u5c48\u670d\u5f3a\u5ea6',
  '\u4f38\u957f\u7387',
  '\u526a\u5207\u5f3a\u5ea6',
  '\u786c\u5ea6',
  '\u75b2\u52b3',
  '\u97e7\u6027',
  '\u65ad\u88c2\u97e7\u6027',
  '\u8010\u8150\u8680',
  '\u5bfc\u70ed',
  '\u5bc6\u5ea6',
]

const PROCESS_KEYWORDS = [
  'O',
  'T4',
  'T6',
  'T651',
  '\u9000\u706b',
  '\u56fa\u6eb6',
  '\u65f6\u6548',
  '\u6dec\u706b',
  '\u56de\u706b',
  '\u6b63\u706b',
  '\u70ed\u5904\u7406',
  '\u94f8\u9020',
  '\u710a\u63a5',
  '\u953b\u9020',
  '\u6324\u538b',
  '\u673a\u52a0\u5de5',
]

const APPLICATION_KEYWORDS = [
  '\u98de\u673a',
  '\u822a\u7a7a',
  '\u6c7d\u8f66',
  '\u8239\u8236',
  '\u6d77\u6d0b',
  '\u7ed3\u6784',
  '\u9600',
  '\u7ba1',
  '\u70ed\u4ea4\u6362',
  '\u6a21\u5177',
  '\u8f74',
]

const TYPE_LABELS = {
  material: '\u6750\u6599',
  property: '\u6027\u80fd',
  process: '\u5de5\u827a',
  condition: '\u6761\u4ef6',
  application: '\u5e94\u7528',
  source: '\u6765\u6e90',
}

function compactText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function uniqueByLabel(items) {
  const seen = new Set()
  return items.filter((item) => {
    const key = item.label.toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function makeId(type, label) {
  return `${type}_${label}`.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '_').replace(/^_|_$/g, '')
}

function detectRoot(question, answer) {
  const text = `${question || ''} ${answer || ''}`
  const patterns = [
    /(?:\u94dd\u5408\u91d1|Alloy\s*)?(6061|6082|6069|6351|7075)/i,
    /(17-4\s*PH|15-5\s*PH|PH\s*13-8\s*Mo)/i,
    /(\u4e0d\u9508\u94a2|\u94dd\u5408\u91d1|\u94dc\u5408\u91d1|\u949b\u5408\u91d1|\u94a2\u94c1|\u9a6c\u6c0f\u4f53\u4e0d\u9508\u94a2|\u5965\u6c0f\u4f53\u4e0d\u9508\u94a2)/,
  ]
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match) {
      const label = match[1] || match[0]
      if (/^\d{4}$/.test(label)) return `\u94dd\u5408\u91d1 ${label}`
      return label.replace(/\s+/g, ' ')
    }
  }
  const fallback = compactText(question || answer).slice(0, 18)
  return fallback || '\u77e5\u8bc6\u4e3b\u9898'
}

function detectTemperatureNodes(answer) {
  const text = String(answer || '')
  const matches = text.match(/-?\d{2,4}\s*(?:\u00b0?\s*C|\u2103|\u00b0?\s*F|\u2109)/g) || []
  return uniqueByLabel(matches.slice(0, 5).map((label) => ({
    id: makeId('condition', label),
    label: label.replace(/\s+/g, ''),
    type: 'condition',
    meta: '\u6e29\u5ea6\u6761\u4ef6',
  })))
}

function detectKeywordNodes(answer, keywords, type, meta) {
  const text = String(answer || '')
  return uniqueByLabel(keywords
    .filter((keyword) => new RegExp(keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i').test(text))
    .slice(0, type === 'property' ? 6 : 5)
    .map((keyword) => ({
      id: makeId(type, keyword),
      label: keyword,
      type,
      meta,
    })))
}

function buildSourceNodes(citations) {
  return (citations || []).slice(0, 3).map((citation, index) => {
    const page = citation.page || '?'
    const section = compactText(citation.section || '').slice(0, 12)
    return {
      id: `source_${index + 1}`,
      label: `pg.${page}`,
      type: 'source',
      meta: section || TYPE_LABELS.source,
      page,
      citationIndex: index + 1,
    }
  })
}

export function buildKnowledgeGraph(question, answer, citations = []) {
  const rootLabel = detectRoot(question, answer)
  const root = {
    id: 'root',
    label: rootLabel,
    type: 'material',
    meta: '\u4e2d\u5fc3\u4e3b\u9898',
  }

  const propertyNodes = detectKeywordNodes(answer, PROPERTY_KEYWORDS, 'property', '\u5173\u952e\u6027\u80fd')
  const processNodes = detectKeywordNodes(answer, PROCESS_KEYWORDS, 'process', '\u5de5\u827a\u6216\u72b6\u6001')
  const conditionNodes = detectTemperatureNodes(answer)
  const applicationNodes = detectKeywordNodes(answer, APPLICATION_KEYWORDS, 'application', '\u5e94\u7528\u573a\u666f')
  const sourceNodes = buildSourceNodes(citations)

  const topicNodes = uniqueByLabel([
    ...propertyNodes,
    ...processNodes,
    ...conditionNodes,
    ...applicationNodes,
  ]).slice(0, 10)

  const nodes = [root, ...topicNodes, ...sourceNodes]
  const edges = [
    ...topicNodes.map((node) => ({
      source: root.id,
      target: node.id,
      label: node.type === 'condition' ? '\u53d7\u6761\u4ef6\u5f71\u54cd' : '\u5173\u8054',
    })),
    ...sourceNodes.map((node) => ({
      source: node.id,
      target: root.id,
      label: '\u4f9d\u636e',
    })),
  ]

  return {
    title: `${rootLabel} \u601d\u7ef4\u56fe\u8c31`,
    summary: `${topicNodes.length}\u4e2a\u77e5\u8bc6\u8282\u70b9 / ${sourceNodes.length}\u4e2a\u5f15\u7528\u6765\u6e90`,
    nodes,
    edges,
  }
}
