<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="brand-mark">FK</div>
      <div>
        <div class="brand-title">Foundry KB</div>
        <div class="brand-subtitle">AI &#x6280;&#x672F;&#x68C0;&#x7D22;</div>
      </div>
    </div>
    <button class="new-chat-btn" @click="$emit('newChat')" title="&#x65B0;&#x5EFA;&#x5BF9;&#x8BDD;">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
      <span>&#x65B0;&#x5EFA;&#x5BF9;&#x8BDD;</span>
    </button>
    <div class="sidebar-section-title">&#x5386;&#x53F2;&#x5BF9;&#x8BDD;</div>
    <div class="history-list">
      <div v-if="items.length === 0" class="history-empty">
        <span class="empty-line"></span>
        <strong>&#x6682;&#x65E0;&#x5BF9;&#x8BDD;&#x8BB0;&#x5F55;</strong>
        <small>&#x767B;&#x5F55;&#x540E;&#x4F1A;&#x5728;&#x8FD9;&#x91CC;&#x4FDD;&#x5B58;&#x68C0;&#x7D22;&#x8FC7;&#x7A0B;</small>
      </div>
      <button v-for="item in items" :key="item.id" class="history-item" :class="{ active: activeId === item.id }" @click="$emit('select', item.id)">
        <span class="history-dot"></span>
        <span class="history-item-title">{{ item.title || '\u65b0\u5bf9\u8bdd' }}</span>
      </button>
    </div>
  </aside>
</template>
<script setup>
defineProps({ items: { type: Array, default: () => [] }, activeId: { type: Number, default: null } })
defineEmits(['select', 'newChat'])
</script>
<style scoped>
.sidebar { width: 280px; min-width: 280px; height: 100vh; display: flex; flex-direction: column; gap: 12px; padding: 16px 14px; background: var(--bg-sidebar); color: var(--text-inverse); border-right: 1px solid rgba(255,255,255,.08); }
.sidebar-brand { display: flex; align-items: center; gap: 10px; padding: 4px 4px 10px; }
.brand-mark { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid rgba(255,255,255,.18); border-radius: 8px; background: #0f766e; font-size: 12px; font-weight: 800; letter-spacing: 0; }
.brand-title { font-weight: 720; font-size: 14px; letter-spacing: 0; }
.brand-subtitle { color: rgba(248,250,252,.62); font-size: 12px; margin-top: 2px; }
.new-chat-btn { height: 42px; width: 100%; border: 1px solid rgba(255,255,255,.16); border-radius: var(--radius-md); background: rgba(255,255,255,.08); color: var(--text-inverse); display: flex; align-items: center; justify-content: center; gap: 8px; cursor: pointer; transition: background .18s ease, border-color .18s ease; }
.new-chat-btn:hover { background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.28); }
.new-chat-btn svg { width: 16px; height: 16px; stroke: currentColor; stroke-width: 2; fill: none; stroke-linecap: round; }
.sidebar-section-title { margin-top: 8px; padding: 0 6px; color: rgba(248,250,252,.54); font-size: 12px; font-weight: 650; }
.history-list { min-height: 0; flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; padding-right: 2px; }
.history-empty { margin: 16px 4px; padding: 18px 14px; border: 1px dashed rgba(255,255,255,.18); border-radius: var(--radius-md); color: rgba(248,250,252,.72); display: flex; flex-direction: column; gap: 6px; }
.history-empty strong { font-size: 13px; font-weight: 650; }
.history-empty small { font-size: 12px; line-height: 1.5; color: rgba(248,250,252,.5); }
.empty-line { width: 26px; height: 2px; background: var(--accent); border-radius: 999px; }
.history-item { width: 100%; border: 0; border-radius: var(--radius-md); background: transparent; color: rgba(248,250,252,.72); display: flex; align-items: center; gap: 9px; min-height: 36px; padding: 8px 10px; text-align: left; cursor: pointer; transition: background .16s ease, color .16s ease; }
.history-item:hover { background: rgba(255,255,255,.08); color: #fff; }
.history-item.active { background: rgba(20,184,166,.16); color: #fff; }
.history-dot { width: 6px; height: 6px; border-radius: 50%; background: rgba(248,250,252,.34); flex: 0 0 auto; }
.history-item.active .history-dot { background: #14b8a6; }
.history-item-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
@media (max-width: 820px) { .sidebar { width: 232px; min-width: 232px; } }
</style>