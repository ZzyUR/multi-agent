<template>
  <div class="hitl-overlay">
    <div class="hitl-modal">
      <div class="hitl-header">
        <div class="hitl-badge">⏸ HITL</div>
        <div class="hitl-title-block">
          <div class="hitl-title">{{ typeLabel }}</div>
          <div class="hitl-sub">研究已暂停，等待您的确认后继续</div>
        </div>
      </div>

      <!-- Intent clarification -->
      <template v-if="type === 'intent'">
        <div class="hitl-prompt-label">Agent 的问题：</div>
        <div class="hitl-prompt">{{ prompt }}</div>
        <textarea
          v-model="answer"
          class="hitl-ta"
          placeholder="输入澄清后的研究意图（留空则保持原始问题不变）"
          rows="3"
        />
        <div class="hitl-actions">
          <button class="hitl-abort ds-btn" @click="$emit('abort')">中止研究</button>
          <button class="hitl-skip ds-btn" @click="$emit('confirm', prompt)">保持原问题</button>
          <button class="hitl-confirm ds-btn" :disabled="!answer.trim()" @click="$emit('confirm', answer)">
            确认意图 →
          </button>
        </div>
      </template>

      <!-- Plan review -->
      <template v-else-if="type === 'plan'">
        <div class="hitl-prompt-label">Agent 规划了以下子课题（可编辑）：</div>
        <div class="hitl-plan-list">
          <div v-for="(task, i) in editPlan" :key="i" class="hitl-plan-item">
            <span class="hitl-plan-num">{{ i + 1 }}</span>
            <input v-model="editPlan[i]" class="hitl-plan-input" />
          </div>
        </div>
        <div class="hitl-actions">
          <button class="hitl-abort ds-btn" @click="$emit('abort')">中止研究</button>
          <button class="hitl-skip ds-btn" @click="$emit('confirm', 'ok')">批准计划 →</button>
          <button class="hitl-confirm ds-btn" @click="$emit('confirm', JSON.stringify(editPlan))">
            修改后确认 →
          </button>
        </div>
      </template>

      <!-- Generic / abort check -->
      <template v-else>
        <div class="hitl-prompt">{{ prompt }}</div>
        <div class="hitl-actions">
          <button class="hitl-abort ds-btn" @click="$emit('abort')">中止研究</button>
          <button class="hitl-confirm ds-btn" @click="$emit('confirm', 'ok')">继续 →</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  type:   { type: String, default: 'intent' },
  prompt: { type: String, default: '' },
  plan:   { type: Array,  default: () => [] },
})

defineEmits(['confirm', 'abort'])

const answer   = ref('')
const editPlan = ref([...(props.plan)])

watch(() => props.plan, v => { editPlan.value = [...(v || [])] }, { immediate: true })

const typeLabel = computed(() => ({
  intent: '意图澄清 (Intent Clarification)',
  plan:   '计划审核 (Plan Review)',
})[props.type] || 'Human-in-the-Loop 干预')
</script>

<style scoped>
.hitl-overlay {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(11, 18, 32, 0.72);
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(3px);
  animation: ds-up 0.18s ease both;
}

.hitl-modal {
  background: #fff; border-radius: 20px;
  width: min(580px, 94vw);
  padding: 32px 36px;
  box-shadow: rgba(11,18,32,.5) 0 32px 80px -20px;
}

.hitl-header {
  display: flex; align-items: flex-start; gap: 14px; margin-bottom: 22px;
}
.hitl-badge {
  flex: none;
  background: rgb(254, 243, 199); color: rgb(146, 64, 14);
  border: 1px solid rgb(252, 211, 77); border-radius: 10px;
  font-size: 13px; font-weight: 800; padding: 6px 12px; letter-spacing: .03em;
}
.hitl-title      { font-weight: 800; font-size: 18px; line-height: 1.2; }
.hitl-sub        { font-size: 13.5px; color: var(--c-text-3); margin-top: 2px; }

.hitl-prompt-label { font-size: 13px; font-weight: 700; color: var(--c-text-3); margin-bottom: 6px; }
.hitl-prompt {
  background: var(--c-card-bg); border: 1px solid var(--c-card-border);
  border-radius: 11px; padding: 14px 16px;
  font-size: 15px; color: var(--c-text); line-height: 1.6; margin-bottom: 16px;
}

.hitl-ta {
  width: 100%; border: 1.5px solid var(--c-divider-2); border-radius: 11px;
  padding: 12px 14px; font-family: inherit; font-size: 15px; resize: vertical;
  outline: none; color: var(--c-text);
  transition: border-color 0.15s;
}
.hitl-ta:focus { border-color: var(--c-blue); }

.hitl-plan-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.hitl-plan-item { display: flex; align-items: center; gap: 10px; }
.hitl-plan-num {
  width: 26px; height: 26px; border-radius: 8px; flex: none;
  background: var(--c-blue-light); color: var(--c-blue);
  font-size: 12px; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
}
.hitl-plan-input {
  flex: 1; border: 1.5px solid var(--c-divider-2); border-radius: 9px;
  padding: 9px 12px; font-family: inherit; font-size: 14px;
  outline: none; color: var(--c-text);
}
.hitl-plan-input:focus { border-color: var(--c-blue); }

.hitl-actions {
  display: flex; justify-content: flex-end; align-items: center;
  gap: 10px; margin-top: 20px; flex-wrap: wrap;
}
.hitl-abort {
  border: 1px solid rgb(252,165,165); background: rgb(254,242,242); color: rgb(185,28,28);
  font-weight: 600; font-size: 13px; padding: 9px 14px; border-radius: 9px;
  margin-right: auto;
}
.hitl-skip {
  border: 1px solid var(--c-divider-2); background: #fff; color: var(--c-text-2);
  font-weight: 600; font-size: 13.5px; padding: 10px 16px; border-radius: 10px;
}
.hitl-confirm {
  border: none; background: var(--c-blue); color: #fff;
  font-weight: 700; font-size: 14px; padding: 11px 20px; border-radius: 10px;
  box-shadow: rgba(37,99,235,.5) 0 8px 20px -8px;
}
.hitl-confirm:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
</style>
