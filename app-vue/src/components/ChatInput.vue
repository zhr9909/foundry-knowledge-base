<template>
  <div class="chat-input">
    <div class="input-row">
      <textarea ref="textarea" v-model="text" :placeholder="placeholder" @keydown.enter.exact.prevent="submit" @input="autoResize" :disabled="disabled" rows="1"></textarea>
      <button class="send-btn" :disabled="!text.trim() || disabled" @click="submit" title="&#x53D1;&#x9001;"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 2 11 13" /><path d="m22 2-7 20-4-9-9-4 20-7Z" /></svg></button>
    </div>
    <div class="input-footer"><span>{{ footerText }}</span></div>
  </div>
</template>
<script setup>
import { ref, nextTick } from 'vue'
const text = ref('')
const textarea = ref(null)
const placeholder = '\u8f93\u5165\u91d1\u5c5e\u6750\u6599\u3001\u94f8\u9020\u5de5\u827a\u76f8\u5173\u95ee\u9898...'
const footerText = 'AI \u56de\u7b54\u53ef\u80fd\u4e0d\u51c6\u786e\uff0c\u8bf7\u6838\u5b9e\u5173\u952e\u6570\u636e'
const props = defineProps({ disabled: Boolean })
const emit = defineEmits(['send'])
function autoResize() { const el = textarea.value; if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 132) + 'px' } }
function submit() { if (!text.value.trim() || props.disabled) return; emit('send', text.value.trim()); text.value = ''; nextTick(() => { if (textarea.value) textarea.value.style.height = 'auto' }) }
</script>
<style scoped>
.chat-input { border-top: 1px solid var(--border-light); background: color-mix(in srgb, var(--bg-main) 88%, white); padding: 14px 18px 12px; }
.input-row { width: min(920px, calc(100% - 48px)); margin: 0 auto; display: flex; align-items: flex-end; gap: 10px; }
textarea { min-height: 46px; max-height: 132px; flex: 1; resize: none; border: 1px solid var(--border-light); border-radius: 12px; background: var(--bg-surface); color: var(--text-primary); padding: 12px 14px; line-height: 1.55; font-size: 14px; box-shadow: var(--shadow-control); transition: border-color .16s ease, box-shadow .16s ease; }
textarea::placeholder { color: #6b7788; }
textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); outline: none; }
textarea:disabled { opacity: .7; cursor: not-allowed; }
.send-btn { width: 46px; height: 46px; border: 0; border-radius: 12px; background: var(--accent); color: #fff; display: grid; place-items: center; cursor: pointer; transition: background .16s ease, transform .16s ease, opacity .16s ease; }
.send-btn:hover:not(:disabled) { background: var(--accent-strong); }
.send-btn:active:not(:disabled) { transform: translateY(1px); }
.send-btn:disabled { opacity: .4; cursor: not-allowed; }
.send-btn svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.input-footer { margin-top: 8px; text-align: center; color: var(--text-muted); font-size: 12px; }
@media (max-width: 820px) { .input-row { width: min(100% - 24px, 920px); } }
</style>