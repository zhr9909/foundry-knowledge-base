const PROPERTY_PATTERNS = [
  { key: 'uts', name: '抗拉强度', pattern: /抗拉强度[^，。；;\n]{0,24}?(-?\d+(?:\.\d+)?)\s*(MPa|ksi|GPa)/gi },
  { key: 'ys', name: '屈服强度', pattern: /屈服强度[^，。；;\n]{0,24}?(-?\d+(?:\.\d+)?)\s*(MPa|ksi|GPa)/gi },
  { key: 'shear', name: '剪切强度', pattern: /剪切强度[^，。；;\n]{0,24}?(-?\d+(?:\.\d+)?)\s*(MPa|ksi|GPa)/gi },
  { key: 'elongation', name: '伸长率', pattern: /伸长率[^，。；;\n]{0,24}?(-?\d+(?:\.\d+)?)\s*(%)/gi },
  { key: 'hardness', name: '硬度', pattern: /硬度[^，。；;\n]{0,24}?((?:HB|HRC|HV|HRB)\s*-?\d+(?:\.\d+)?|-?\d+(?:\.\d+)?\s*(?:HB|HRC|HV|HRB))/gi },
  { key: 'fatigue', name: '疲劳', pattern: /疲劳[^，。；;\n]{0,24}?(-?\d+(?:\.\d+)?)\s*(MPa|ksi)/gi },
]

const STATE_KEYWORDS = ['O态', 'T4', 'T451', 'T6', 'T651', '固溶态', '时效态', '退火态', '淬火态', '回火态', '焊接态']
const PROCESS_KEYWORDS = ['热处理', '退火', '固溶', '时效', '淬火', '回火', '正火', '铸造', '焊接', '锻造', '挤压', '机加工']
const APPLICATION_KEYWORDS = ['航空', '飞机', '汽车', '船舶', '海洋', '结构件', '阀', '管', '热交换', '模具', '轴']
const RISK_KEYWORDS = ['腐蚀', '开裂', '疲劳', '脆性', '变形', '残余应力', '过时效', '晶间腐蚀']

function compactText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function makeId(type, label) {
  return `${type}_${label}`.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '_').replace(/^_|_$/g, '').slice(0, 48)
}

function uniqueByLabel(items) {
  const seen = new Set()
  return items.filter((item) => {
    const key = `${item.type}:${item.label}`.toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function sentenceFor(text, keyword) {
  const source = String(text || '')
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = source.match(new RegExp(`[^。；;\\n]{0,42}${escaped}[^。；;\\n]{0,64}`, 'i'))
  return compactText(match?.[0] || '').slice(0, 96)
}

function detectRoot(question, answer) {
  const text = `${question || ''} ${answer || ''}`
  const patterns = [
    /(?:铝合金|Alloy\s*)?(6061|6082|6069|6351|7075)/i,
    /(17-4\s*PH|15-5\s*PH|PH\s*13-8\s*Mo)/i,
    /(不锈钢|铝合金|铜合金|钛合金|钢铁|马氏体不锈钢|奥氏体不锈钢)/,
  ]
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match) {
      const label = match[1] || match[0]
      if (/^\d{4}$/.test(label)) return `铝合金 ${label}`
      return label.replace(/\s+/g, ' ')
    }
  }
  return compactText(question || answer).slice(0, 18) || '知识主题'
}

function detectPropertyValues(answer) {
  const nodes = []
  for (const item of PROPERTY_PATTERNS) {
    for (const match of String(answer || '').matchAll(item.pattern)) {
      const value = compactText(match[1])
      const unit = compactText(match[2] || '')
      const label = `${item.name} ${value}${unit ? ` ${unit}` : ''}`
      nodes.push({
        id: makeId('property_value', `${item.key}_${value}_${unit}`),
        label,
        type: 'property_value',
        meta: sentenceFor(answer, item.name) || '从答案中识别出的性能参数',
      })
    }
  }
  return uniqueByLabel(nodes).slice(0, 6)
}

function detectTemperatureNodes(answer) {
  const matches = String(answer || '').match(/-?\d{2,4}\s*(?:°?\s*C|℃|°?\s*F|℉)/g) || []
  return uniqueByLabel(matches.map((label) => {
    const normalized = label.replace(/\s+/g, '')
    return {
      id: makeId('condition', normalized),
      label: normalized,
      type: 'condition',
      meta: sentenceFor(answer, normalized) || '测试或处理温度条件',
    }
  })).slice(0, 5)
}

function detectKeywordNodes(answer, keywords, type, meta) {
  const text = String(answer || '')
  return uniqueByLabel(keywords
    .filter((keyword) => new RegExp(keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i').test(text))
    .map((keyword) => ({
      id: makeId(type, keyword),
      label: keyword,
      type,
      meta: sentenceFor(answer, keyword) || meta,
    }))).slice(0, 5)
}

function buildSourceNodes(citations) {
  return (citations || []).slice(0, 3).map((citation, index) => {
    const page = citation.page || '?'
    const section = compactText(citation.section || '').slice(0, 18)
    return {
      id: `source_${index + 1}`,
      label: `pg.${page}`,
      type: 'source',
      meta: section || compactText(citation.text || '').slice(0, 48) || '引用来源',
      page,
      source_id: citation.source_id || 2,
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
    meta: '本轮问答的中心材料或主题',
  }

  const stateNodes = detectKeywordNodes(answer, STATE_KEYWORDS, 'material_state', '材料状态或热处理状态')
  const propertyNodes = detectPropertyValues(answer)
  const processNodes = detectKeywordNodes(answer, PROCESS_KEYWORDS, 'process', '工艺或处理过程')
  const conditionNodes = detectTemperatureNodes(answer)
  const applicationNodes = detectKeywordNodes(answer, APPLICATION_KEYWORDS, 'application', '应用场景')
  const riskNodes = detectKeywordNodes(answer, RISK_KEYWORDS, 'risk', '使用或工艺风险')
  const sourceNodes = buildSourceNodes(citations)

  const topicNodes = uniqueByLabel([
    ...stateNodes,
    ...propertyNodes,
    ...processNodes,
    ...conditionNodes,
    ...applicationNodes,
    ...riskNodes,
  ]).slice(0, 12)

  const nodes = [root, ...topicNodes, ...sourceNodes]
  const edges = [
    ...topicNodes.map((node) => ({
      source: root.id,
      target: node.id,
      label: node.type === 'property_value' ? '具有' : node.type === 'condition' ? '受条件影响' : '关联',
    })),
    ...sourceNodes.flatMap((source) => topicNodes.slice(0, 3).map((node) => ({
      source: source.id,
      target: node.id,
      label: '来源支持',
    }))),
  ]

  return {
    title: `${rootLabel} 工程知识图谱`,
    summary: `从材料状态、工艺条件、性能参数和证据来源中抽取 ${topicNodes.length} 个知识点`,
    nodes,
    edges,
  }
}
