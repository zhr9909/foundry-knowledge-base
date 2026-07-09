<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <button class="new-chat-btn" @click="('newChat')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        + ??
      </button>
    </div>
    <div class="sidebar-title">????</div>
    <div class="history-list">
      <div v-if="items.length === 0" class="history-empty">??????</div>
      <div v-for="item in items" :key="item.id"
        class="history-item"
        :class="{ active: activeId === item.id }"
        @click="('select', item.id)">
        <span class="history-item-title">{{ item.title || '???' }}</span>
      </div>
    </div>
  </aside>
</template>
<script setup>
defineProps({ items: { type: Array, default: () => [] }, activeId: { type: Number, default: null } })
defineEmits(['select', 'newChat'])
</script>
<style scoped>
.sidebar { width: 240px; min-width: 240px; background: var(--bg-sidebar); border-right: 1px solid var(--border-light); display: flex; flex-direction: column; overflow: hidden; }
.sidebar-header { padding: 12px; }
.new-chat-btn { width: 100%; padding: 8px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-main); cursor: pointer; font-size: 13px; display: flex; align-items: center; justify-content: center; gap: 6px; color: var(--text-primary); transition: border-color .2s; }
.new-chat-btn:hover { border-color: var(--border-focus); }
.sidebar-title { padding: 8px 12px; font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }
.history-list { flex: 1; overflow-y: auto; padding: 0 8px; }
.history-empty { text-align: center; padding: 24px 12px; font-size: 13px; color: var(--text-muted); }
.history-item { padding: 8px 12px; border-radius: var(--radius-sm); cursor: pointer; font-size: 13px; color: var(--text-secondary); transition: all .15s; margin-bottom: 2px; }
.history-item:hover { background: var(--bg-sub); }
.history-item.active { background: var(--bg-main); color: var(--text-primary); font-weight: 500; border: 1px solid var(--border-light); }
.history-item-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }
</style>
