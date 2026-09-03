import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import { marked } from 'marked'

const TYPE_LABELS = {
  run_start:     '🚀 RUN_START',
  run_end:       '✅ RUN_END',
  plan_start:    '📋 PLAN_START',
  plan_done:     '📋 PLAN_DONE',
  task_dispatch: '📤 DISPATCH',
  task_start:    '▶ TASK_START',
  task_done:     '✔ TASK_DONE',
  tool_call:     '🔧 TOOL_CALL',
  tool_result:   '📥 TOOL_RESULT',
  synthesize:    '✍ SYNTHESIZE',
  citation:      '🔍 CITATION',
  error:         '❌ ERROR',
}

export const useResearchStore = defineStore('research', () => {
  const question  = ref('')
  const profile   = ref('standard')
  const useMock   = ref(false)
  const running   = ref(false)
  const runId     = ref('')
  const traces    = ref([])
  const report    = ref('')
  const stats     = ref(null)
  const history   = ref([])
  const meta      = reactive({ tokens: 0, workers: 0, cache_hit_rate: 0 })

  let startMs = 0
  let es = null

  const statusDot  = computed(() => running.value ? 'running' : report.value ? 'done' : '')
  const statusText = computed(() => running.value ? '研究中…' : report.value ? '已完成' : '等待')
  const renderedReport = computed(() => report.value ? marked.parse(report.value) : '')

  function fmtTs(iso) {
    if (!iso || !startMs) return '+0s'
    try { return '+' + Math.floor((new Date(iso) - startMs) / 1000) + 's' } catch { return '' }
  }

  function parseTrace(ev) {
    const d   = ev.data || {}
    const key = ev.event_type || ''
    const label = TYPE_LABELS[key] || key.toUpperCase()
    let msg = ''
    if      (key === 'run_start')     msg = `"${(d.question || '').substring(0, 60)}"`
    else if (key === 'plan_done')     msg = `${d.count || 0} 个子课题 — ${(d.subtasks || []).slice(0, 2).join(' | ')}`
    else if (key === 'task_dispatch') msg = `${(d.queries || []).length} 个任务并行`
    else if (key === 'task_start')    msg = `[${ev.agent_id || '?'}] ${(d.query || '').substring(0, 60)}`
    else if (key === 'task_done')     msg = `[${ev.agent_id || '?'}] 完成`
    else if (key === 'tool_call')     msg = `${d.tool || ''} — ${JSON.stringify(d.args || {}).substring(0, 80)}`
    else if (key === 'tool_result')   msg = `${d.tool || ''} → ${String(d.result || '').substring(0, 80)}`
    else if (key === 'synthesize')    msg = '合并所有发现，生成报告…'
    else if (key === 'run_end') {
      msg = `Workers:${d.total_workers || 0} · Tokens:${(d.tokens_used || 0).toLocaleString()} · 引用率:${((d.citation_support_rate || 0) * 100).toFixed(0)}%`
      meta.tokens = d.tokens_used || 0
      meta.workers = d.total_workers || 0
      meta.cache_hit_rate = d.cache_hit_rate || 0
    }
    else if (key === 'error') msg = d.message || ''
    else msg = JSON.stringify(d).substring(0, 100)
    return { key, label, msg }
  }

  async function startResearch() {
    if (!question.value.trim() || running.value) return
    running.value = true
    traces.value = []
    report.value = ''
    stats.value = null
    meta.tokens = 0
    meta.workers = 0
    meta.cache_hit_rate = 0
    startMs = Date.now()

    try {
      const res = await fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question.value, profile: profile.value, mock: useMock.value }),
      })
      const data = await res.json()
      runId.value = data.run_id

      es = new EventSource(`/api/research/${data.run_id}/stream`)

      es.addEventListener('trace', e => {
        const ev = JSON.parse(e.data)
        const { key, label, msg } = parseTrace(ev)
        traces.value.push({ ts: fmtTs(ev.timestamp), key, label, msg })
      })

      es.addEventListener('report', e => {
        report.value = JSON.parse(e.data).content
      })

      es.addEventListener('done', e => {
        const d = JSON.parse(e.data)
        meta.tokens = d.tokens_used || meta.tokens
        meta.workers = d.workers || meta.workers
        meta.cache_hit_rate = d.cache_hit_rate || meta.cache_hit_rate
        running.value = false
        es?.close()
        loadStats(data.run_id)
      })

      es.addEventListener('error', e => {
        try {
          const d = JSON.parse(e.data)
          traces.value.push({ ts: '+?s', key: 'error', label: '❌ ERROR', msg: d.message })
        } catch {}
        running.value = false
        es?.close()
      })

      es.onerror = () => { running.value = false; es?.close() }

    } catch (err) {
      running.value = false
      traces.value.push({ ts: '+0s', key: 'error', label: '❌ ERROR', msg: String(err) })
    }
  }

  async function loadStats(id) {
    try {
      const r = await fetch(`/api/research/${id}/stats`)
      if (r.ok) stats.value = await r.json()
    } catch {}
  }

  async function loadHistory() {
    try {
      const r = await fetch('/api/research/history')
      if (r.ok) { const d = await r.json(); history.value = d.runs || [] }
    } catch {}
  }

  async function loadRun(id) {
    runId.value = id
    await loadStats(id)
    try {
      const r = await fetch(`/api/research/${id}/report`)
      if (r.ok) { const d = await r.json(); report.value = d.content }
    } catch {}
  }

  return {
    question, profile, useMock, running, runId,
    traces, report, stats, history, meta,
    statusDot, statusText, renderedReport,
    startResearch, loadHistory, loadRun,
  }
})
