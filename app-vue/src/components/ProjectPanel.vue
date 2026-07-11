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
    </div>

    <div v-if="project.customer_name || project.description" class="project-note">
      <strong v-if="project.customer_name">{{ project.customer_name }}</strong>
      <p v-if="project.description">{{ project.description }}</p>
    </div>

    <div class="panel-section" v-if="conversations.length">
      <div class="section-title">项目内对话</div>
      <button
        v-for="conv in conversations"
        :key="conv.id"
        class="conversation-row"
        type="button"
        @click="$emit('select-conversation', conv.id)"
      >
        <span>{{ conv.title || '新对话' }}</span>
        <time>{{ formatTime(conv.updated_at) }}</time>
      </button>
    </div>

    <div class="artifact-list">
      <article v-for="artifact in artifacts" :key="artifact.id" class="artifact-card">
        <div class="artifact-topline">
          <span>{{ typeText(artifact.type) }}</span>
          <time>{{ formatTime(artifact.created_at) }}</time>
        </div>
        <h3>{{ artifact.title }}</h3>
        <p>{{ artifact.content }}</p>
        <div v-if="artifact.citations?.length" class="artifact-foot">
          {{ artifact.citations.length }} 条引用依据
        </div>
      </article>

      <div v-if="artifacts.length === 0" class="artifact-empty">
        <span></span>
        <strong>还没有保存产物</strong>
        <p>在任意 AI 回答右下角点击“保存到项目”，就会沉淀到这里。</p>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ project: { type: Object, required: true } })
defineEmits(['close', 'select-conversation'])

const artifacts = computed(() => props.project.artifacts || [])
const conversations = computed(() => props.project.conversations || [])
const artifactCount = computed(() => props.project.artifact_count ?? artifacts.value.length)

function typeText(type) {
  const map = {
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
.project-panel { width: 340px; min-width: 340px; height: 100vh; display: flex; flex-direction: column; background: var(--bg-surface); border-left: 1px solid var(--border-light); box-shadow: var(--shadow-panel); color: var(--text-primary); }
.panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 18px 18px 14px; border-bottom: 1px solid var(--border-light); }
.panel-kicker { color: var(--accent-strong); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
.panel-head h2 { margin-top: 5px; font-size: 18px; line-height: 1.35; font-weight: 780; }
.panel-close { width: 32px; height: 32px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface-2); color: var(--text-secondary); display: grid; place-items: center; cursor: pointer; }
.panel-close:hover { color: var(--text-primary); border-color: var(--border-strong); }
.panel-close svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; }
.project-meta { display: flex; gap: 8px; padding: 12px 18px 0; }
.project-meta span { border: 1px solid var(--border-light); border-radius: 999px; background: var(--bg-surface-2); color: var(--text-muted); padding: 4px 9px; font-size: 12px; font-weight: 650; }
.project-note { margin: 12px 18px 0; padding: 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface-2); }
.project-note strong { display: block; margin-bottom: 4px; font-size: 13px; }
.project-note p { color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
.panel-section { padding: 14px 18px 0; }
.section-title { margin-bottom: 8px; color: var(--text-muted); font-size: 12px; font-weight: 760; }
.conversation-row { width: 100%; min-height: 38px; display: flex; align-items: center; justify-content: space-between; gap: 10px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface-2); color: var(--text-secondary); padding: 8px 10px; cursor: pointer; text-align: left; }
.conversation-row + .conversation-row { margin-top: 6px; }
.conversation-row:hover { border-color: var(--accent); background: var(--accent-soft); color: var(--text-primary); }
.conversation-row span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 700; }
.conversation-row time { flex: 0 0 auto; color: var(--text-muted); font-size: 11px; }
.artifact-list { min-height: 0; flex: 1; overflow-y: auto; padding: 14px 18px 20px; display: flex; flex-direction: column; gap: 10px; }
.artifact-card { border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface-2); padding: 12px; }
.artifact-topline { display: flex; align-items: center; justify-content: space-between; gap: 8px; color: var(--text-muted); font-size: 11px; font-weight: 700; }
.artifact-card h3 { margin-top: 8px; font-size: 14px; line-height: 1.45; font-weight: 760; }
.artifact-card p { margin-top: 7px; color: var(--text-secondary); font-size: 12px; line-height: 1.65; display: -webkit-box; -webkit-line-clamp: 5; -webkit-box-orient: vertical; overflow: hidden; }
.artifact-foot { margin-top: 9px; color: var(--accent-strong); font-size: 12px; font-weight: 700; }
.artifact-empty { margin-top: 16px; padding: 20px 14px; border: 1px dashed var(--border-light); border-radius: var(--radius-md); text-align: center; color: var(--text-muted); }
.artifact-empty span { display: block; width: 28px; height: 3px; margin: 0 auto 12px; border-radius: 999px; background: var(--accent); }
.artifact-empty strong { display: block; color: var(--text-secondary); font-size: 13px; }
.artifact-empty p { margin-top: 6px; font-size: 12px; line-height: 1.6; }
@media (max-width: 1120px) {
  .project-panel { position: fixed; right: 0; top: 0; z-index: 28; }
}
@media (max-width: 640px) {
  .project-panel { width: min(100vw, 340px); min-width: 0; }
}
</style>
