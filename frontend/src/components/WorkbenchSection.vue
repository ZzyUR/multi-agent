<template>
  <section id="workbench" class="workbench-section">
    <div class="section-inner">
      <div class="workbench-card">
        <!-- Input area -->
        <div class="input-area">
          <el-input
            v-model="store.question"
            type="textarea"
            :rows="3"
            placeholder="输入你的研究问题，例如：分析 2024 年 AI Agent 领域的主要技术突破和代表性项目…"
            :disabled="store.running"
          />
          <div class="input-row">
            <div class="input-controls">
              <el-select v-model="store.profile" placeholder="研究深度" style="width:150px">
                <el-option label="快速模式" value="fast" />
                <el-option label="标准模式" value="standard" />
                <el-option label="深度模式" value="deep" />
              </el-select>
              <label class="mock-toggle">
                <el-switch v-model="store.useMock" />
                <span class="mock-label">Mock 模式</span>
              </label>
            </div>
            <button
              class="run-btn ds-btn"
              :class="{ running: store.running }"
              :disabled="store.running || !store.question.trim()"
              @click="store.startResearch()"
            >
              <span v-if="store.running" class="run-dot"></span>
              {{ store.running ? '研究中…' : '▶ 开始研究' }}
            </button>
          </div>
        </div>

        <!-- Status bar -->
        <div class="status-bar" v-if="store.running || store.traces.length">
          <span class="status-dot" :class="store.statusDot"></span>
          <span class="status-text">{{ store.statusText }}</span>
          <span class="status-meta mono" v-if="store.meta.tokens">
            Tokens: {{ store.meta.tokens.toLocaleString() }} · Workers: {{ store.meta.workers }}
          </span>
        </div>

        <!-- Tabs -->
        <el-tabs v-model="activeTab" class="workbench-tabs" v-if="store.traces.length || store.report">
          <!-- Trace tab -->
          <el-tab-pane name="trace">
            <template #label>
              <span class="tab-label">
                执行 Trace
                <span class="tab-badge" v-if="store.traces.length">{{ store.traces.length }}</span>
              </span>
            </template>
            <div class="trace-list" ref="traceList">
              <div
                v-for="(t, i) in store.traces" :key="i"
                class="trace-item"
                :class="'trace-' + t.key"
              >
                <span class="trace-ts mono">{{ t.ts }}</span>
                <span class="trace-label">{{ t.label }}</span>
                <span class="trace-msg">{{ t.msg }}</span>
              </div>
            </div>
          </el-tab-pane>

          <!-- Report tab -->
          <el-tab-pane name="report" label="研究报告">
            <div
              v-if="store.report"
              class="report-body"
              v-html="store.renderedReport"
            />
            <div v-else class="empty-tip">报告生成中，请稍候…</div>
          </el-tab-pane>

          <!-- Stats tab -->
          <el-tab-pane name="stats" label="统计">
            <div v-if="store.stats" class="stats-grid">
              <div v-for="s in statItems" :key="s.label" class="stat-card">
                <div class="stat-val">{{ s.val }}</div>
                <div class="stat-key">{{ s.label }}</div>
              </div>
            </div>
            <div v-else class="empty-tip">研究完成后显示统计信息</div>
          </el-tab-pane>

          <!-- History tab -->
          <el-tab-pane name="history" label="历史">
            <div class="history-controls">
              <button class="hist-refresh ds-btn" @click="store.loadHistory()">刷新</button>
            </div>
            <div v-if="store.history.length" class="history-list">
              <div
                v-for="h in store.history" :key="h.run_id"
                class="history-item ds-hover-lift"
                @click="loadHistoryRun(h.run_id)"
              >
                <div class="history-q">{{ h.question }}</div>
                <div class="history-meta mono">
                  {{ h.run_id.substring(0, 8) }} · {{ fmtDate(h.created_at) }}
                </div>
              </div>
            </div>
            <div v-else class="empty-tip">暂无历史研究记录</div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useResearchStore } from '../stores/research.js'

const store = useResearchStore()
const activeTab = ref('trace')
const traceList = ref(null)

const statItems = computed(() => {
  if (!store.stats) return []
  const s = store.stats
  return [
    { label: '总 Tokens', val: (s.tokens_used || 0).toLocaleString() },
    { label: 'Worker 数', val: s.total_workers || 0 },
    { label: '引用支持率', val: ((s.citation_support_rate || 0) * 100).toFixed(1) + '%' },
    { label: '缓存命中率', val: ((s.cache_hit_rate || 0) * 100).toFixed(1) + '%' },
    { label: '耗时 (s)', val: s.duration_seconds?.toFixed(1) || '--' },
    { label: '子任务数', val: s.subtask_count || '--' },
  ]
})

watch(() => store.traces.length, async () => {
  await nextTick()
  if (traceList.value) {
    traceList.value.scrollTop = traceList.value.scrollHeight
  }
})

watch(() => store.report, val => {
  if (val) activeTab.value = 'report'
})

function loadHistoryRun(id) {
  store.loadRun(id)
  activeTab.value = 'report'
}

function fmtDate(iso) {
  if (!iso) return ''
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}
</script>

<style scoped>
.workbench-section {
  background: #fff;
  padding: 80px 40px;
  border-top: 1px solid var(--c-divider);
}
.section-inner { max-width: 1100px; margin: 0 auto; }
.section-hd { text-align: center; margin-bottom: 44px; }

.workbench-card {
  background: var(--c-card-bg);
  border: 1px solid var(--c-card-border);
  border-radius: 22px;
  padding: 32px;
}

.input-area { margin-bottom: 18px; }
.input-row {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 14px; gap: 14px;
}
.input-controls { display: flex; align-items: center; gap: 14px; }
.mock-toggle { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.mock-label { font-size: 13.5px; color: var(--c-text-3); font-weight: 600; }

.run-btn {
  border: none; background: var(--c-blue); color: #fff;
  font-weight: 700; font-size: 15px; padding: 12px 24px;
  border-radius: 10px; display: flex; align-items: center; gap: 8px;
  box-shadow: rgba(37,99,235,.55) 0 8px 22px -8px;
  flex-shrink: 0;
}
.run-btn:disabled { opacity: 0.55; cursor: not-allowed; transform: none !important; }
.run-btn.running { background: var(--c-text-3); box-shadow: none; }
.run-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #fff;
  animation: ds-blink 1s ease infinite;
}

.status-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; border-radius: 10px;
  background: var(--c-blue-light); border: 1px solid var(--c-blue-border);
  margin-bottom: 18px;
  font-size: 13.5px; font-weight: 600;
}
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.running { background: var(--c-blue); animation: ds-blink 1s ease infinite; }
.status-dot.done    { background: var(--c-green); }
.status-text { color: var(--c-text-2); }
.status-meta { color: var(--c-text-4); font-size: 12px; margin-left: auto; }

.workbench-tabs { margin-top: 8px; }

.tab-label { display: flex; align-items: center; gap: 7px; }
.tab-badge {
  background: var(--c-blue); color: #fff;
  font-size: 10px; font-weight: 700; padding: 1px 6px;
  border-radius: 99px; min-width: 18px; text-align: center;
}

.trace-list {
  height: 340px; overflow-y: auto;
  display: flex; flex-direction: column; gap: 5px;
  padding: 8px 4px;
}
.trace-item {
  display: flex; gap: 10px; align-items: flex-start;
  font-size: 12.5px; padding: 6px 10px;
  border-radius: 7px; background: var(--c-card-bg);
  border: 1px solid var(--c-card-border); line-height: 1.5;
}
.trace-ts     { color: var(--c-text-4); flex-shrink: 0; width: 50px; }
.trace-label  { font-weight: 700; flex-shrink: 0; width: 140px; }
.trace-msg    { color: var(--c-text-2); word-break: break-all; }
.trace-run_start .trace-label { color: var(--c-blue); }
.trace-run_end   .trace-label { color: var(--c-green); }
.trace-error     .trace-label { color: var(--c-red); }
.trace-task_start .trace-label, .trace-task_done .trace-label { color: rgb(124,58,237); }
.trace-tool_call  .trace-label { color: rgb(217,119,6); }

.report-body {
  padding: 8px 4px; line-height: 1.75;
  color: var(--c-text); max-height: 500px; overflow-y: auto;
}
.report-body :deep(h1), .report-body :deep(h2), .report-body :deep(h3) {
  font-weight: 800; margin: 22px 0 10px; letter-spacing: -0.02em;
}
.report-body :deep(h1) { font-size: 24px; }
.report-body :deep(h2) { font-size: 20px; }
.report-body :deep(h3) { font-size: 17px; }
.report-body :deep(p)  { margin: 10px 0; }
.report-body :deep(ul), .report-body :deep(ol) { padding-left: 20px; margin: 10px 0; }
.report-body :deep(li) { margin: 5px 0; }
.report-body :deep(blockquote) {
  border-left: 3px solid var(--c-blue-border);
  padding: 8px 16px; margin: 12px 0;
  background: var(--c-blue-light); border-radius: 0 8px 8px 0;
  color: var(--c-text-2); font-size: 14px;
}
.report-body :deep(code) {
  font-family: 'SF Mono', 'JetBrains Mono', monospace;
  background: var(--c-card-bg); padding: 2px 6px; border-radius: 4px;
  font-size: 13px; color: rgb(124,58,237);
}
.report-body :deep(pre) {
  background: var(--c-dark); padding: 16px; border-radius: 10px;
  overflow-x: auto; margin: 14px 0;
}
.report-body :deep(pre code) { background: none; color: rgb(203,213,225); padding: 0; }

.stats-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; padding: 8px 4px;
}
.stat-card {
  background: var(--c-card-bg); border: 1px solid var(--c-card-border);
  border-radius: 12px; padding: 18px; text-align: center;
}
.stat-val { font-size: 26px; font-weight: 800; color: var(--c-text); }
.stat-key { font-size: 12.5px; color: var(--c-text-3); margin-top: 4px; font-weight: 600; }

.history-controls { margin-bottom: 14px; }
.hist-refresh {
  border: 1px solid var(--c-card-border); background: #fff;
  padding: 7px 16px; border-radius: 8px; font-weight: 700;
  font-size: 13px; color: var(--c-text-2);
}
.history-list { display: flex; flex-direction: column; gap: 10px; }
.history-item {
  background: var(--c-card-bg); border: 1px solid var(--c-card-border);
  border-radius: 12px; padding: 16px 18px; cursor: pointer;
}
.history-q { font-weight: 700; font-size: 14px; color: var(--c-text); margin-bottom: 6px; }
.history-meta { font-size: 12px; color: var(--c-text-4); }

.empty-tip {
  padding: 40px 0; text-align: center;
  font-size: 14px; color: var(--c-text-4); font-weight: 600;
}

@media (max-width: 700px) {
  .workbench-section { padding: 56px 20px; }
  .workbench-card { padding: 20px; }
  .input-row { flex-direction: column; align-items: stretch; }
  .run-btn { width: 100%; justify-content: center; }
  .stats-grid { grid-template-columns: 1fr 1fr; }
}
</style>
