import { defineStore, acceptHMRUpdate } from 'pinia'
import { ref, reactive, computed } from 'vue'
import { marked } from 'marked'

const PRESET_META = {
  fast:     { name:'快速', desc:'低成本、快出结论', breadth:2, depth:1, meta:'breadth 2 · depth 1 轮' },
  standard: { name:'标准', desc:'成本与质量平衡（推荐）', breadth:3, depth:2, meta:'breadth 3 · depth 2 轮' },
  deep:     { name:'深度', desc:'更全面、烧更多 token', breadth:5, depth:3, meta:'breadth 5 · depth 3 轮' },
}

const KIND_COLORS = {
  Reason:'#2563EB', Plan:'#7C3AED', Act:'#0891B2', Observe:'#0EA5E9',
  Assess:'#D97706', Synthesize:'#16A34A', Cite:'#DB2777', Human:'#E11D48',
}

const TRACE_TAG_COLORS = {
  Reason:'#60A5FA', Plan:'#A78BFA', Act:'#22D3EE', Observe:'#38BDF8',
  Assess:'#FBBF24', Synthesize:'#4ADE80', Cite:'#F472B6',
  MCP:'#22D3EE', FS:'#94A3B8', A2A:'#60A5FA', Dispatch:'#A78BFA', Human:'#FB7185',
  RUN_START:'#60A5FA', PLAN_DONE:'#A78BFA', TASK_DISPATCH:'#22D3EE',
  TASK_START:'#38BDF8', TOOL_CALL:'#FBBF24', TOOL_RESULT:'#4ADE80',
  TASK_DONE:'#4ADE80', SYNTHESIZE:'#4ADE80', CITATION_CHECK:'#F472B6',
  HUMAN_INTERVENE:'#FB7185', RUN_END:'#60A5FA', ERROR:'#F87171',
}

const WORKER_STATUS = {
  queued:    { label:'排队中',  color:'#94A3B8', bg:'#F1F5F9', border:'#E6ECF5' },
  searching: { label:'检索中',  color:'#2563EB', bg:'#EAF1FE', border:'#C7DBFB' },
  reading:   { label:'读取中',  color:'#0891B2', bg:'#E0F7FB', border:'#A5E8F0' },
  done:      { label:'完成',    color:'#16A34A', bg:'#ECFDF5', border:'#BBF7D0' },
}

const EXAMPLES = [
  { label:'2026 新能源汽车竞争格局', q:'分析 2026 新能源汽车行业竞争格局' },
  { label:'国产大模型商业化现状',    q:'调研 2026 国产大模型商业化落地现状与盈利模式' },
  { label:'具身智能机器人产业链',    q:'梳理具身智能 / 人形机器人产业链与投资机会' },
]

function _generateClarifyQuestions(q) {
  const lo = q.toLowerCase()

  const isEV      = /新能源|电动车|电动汽车|充电桩|锂电池/.test(lo)
  const isAuto    = /汽车|车企|整车|车市/.test(lo)
  const isAI      = /大模型|人工智能|llm|gpt|claude|deepseek|ai应用|ai落地/.test(lo)
  const isRobot   = /机器人|具身|人形|智能体/.test(lo)
  const isSemi    = /芯片|半导体|晶圆|光刻|封装|存储/.test(lo)
  const isMedical = /医疗|医药|生物|制药|医院|健康/.test(lo)
  const isFinance = /金融|银行|保险|券商|基金|理财/.test(lo)
  const isRealty  = /房地产|地产|楼市|房价|开发商/.test(lo)
  const isConsume = /消费|电商|零售|品牌|快消/.test(lo)
  const isGlobal  = /出海|海外|全球|国际|跨境/.test(lo)
  const isPolicy  = /政策|监管|法规|补贴|合规/.test(lo)

  const yearMatch = q.match(/20\d\d/)
  const year = yearMatch ? yearMatch[0] : null

  let dims
  if (isEV || (isAuto && !isFinance)) {
    dims = [
      { id:'d0', label:'市场份额与销量' },
      { id:'d1', label:'技术路线对比（纯电/插混/增程）' },
      { id:'d2', label:'政策与补贴动向' },
      { id:'d3', label:'供应链与上游成本' },
      { id:'d4', label:'头部玩家财务与战略' },
      { id:'d5', label:'海外扩张与出海' },
    ]
  } else if (isAI) {
    dims = [
      { id:'d0', label:'技术架构与能力对比' },
      { id:'d1', label:'商业化落地路径' },
      { id:'d2', label:'主要玩家竞争格局' },
      { id:'d3', label:'应用场景与行业覆盖' },
      { id:'d4', label:'成本结构与定价' },
      { id:'d5', label:'监管政策与合规' },
    ]
  } else if (isRobot) {
    dims = [
      { id:'d0', label:'核心零部件与技术路线' },
      { id:'d1', label:'产业链全景' },
      { id:'d2', label:'头部玩家竞争格局' },
      { id:'d3', label:'应用场景与量产进展' },
      { id:'d4', label:'投融资与估值动态' },
    ]
  } else if (isSemi) {
    dims = [
      { id:'d0', label:'产业链关键环节' },
      { id:'d1', label:'主要玩家市占率' },
      { id:'d2', label:'技术节点与制程路线' },
      { id:'d3', label:'地缘政治与供应链风险' },
      { id:'d4', label:'国产替代进展' },
    ]
  } else if (isMedical) {
    dims = [
      { id:'d0', label:'市场规模与疾病负担' },
      { id:'d1', label:'技术路线与在研管线' },
      { id:'d2', label:'政策与医保准入' },
      { id:'d3', label:'主要厂商格局' },
      { id:'d4', label:'临床数据与安全性' },
    ]
  } else if (isFinance) {
    dims = [
      { id:'d0', label:'市场规模与增速' },
      { id:'d1', label:'监管政策动向' },
      { id:'d2', label:'主要机构竞争对比' },
      { id:'d3', label:'数字化转型进展' },
      { id:'d4', label:'风险因素与压力' },
    ]
  } else if (isRealty) {
    dims = [
      { id:'d0', label:'政策调控动向' },
      { id:'d1', label:'销售与库存数据' },
      { id:'d2', label:'头部房企格局' },
      { id:'d3', label:'区域市场分化' },
      { id:'d4', label:'资金流动性风险' },
    ]
  } else if (isConsume) {
    dims = [
      { id:'d0', label:'市场规模与增速' },
      { id:'d1', label:'用户画像与需求变化' },
      { id:'d2', label:'渠道结构演变' },
      { id:'d3', label:'品牌竞争格局' },
      { id:'d4', label:'价格带与利润分布' },
    ]
  } else {
    dims = [
      { id:'d0', label:'市场规模与现状' },
      { id:'d1', label:'竞争格局与主要玩家' },
      { id:'d2', label:'发展趋势与前景' },
      { id:'d3', label:'机会与风险' },
    ]
    if (isGlobal) dims.push({ id:'d4', label:'全球视角与跨境对比' })
    if (isPolicy) dims.push({ id:'d5', label:'政策监管环境' })
  }

  const timeOpts = year
    ? [
        { id:'t0', label:`${parseInt(year) - 1}–${year}（近期）` },
        { id:'t1', label:`仅 ${year} 最新数据` },
        { id:'t2', label:'近 5 年趋势' },
      ]
    : [
        { id:'t0', label:'最近 1–2 年' },
        { id:'t1', label:'近半年最新' },
        { id:'t2', label:'近 5 年趋势' },
      ]

  return [
    { id:'depth', title:'研究深度', multi:false, options:[
      { id:'overview', label:'概览级 · 5–8 来源' },
      { id:'std',      label:'标准级 · 15–20 来源（推荐）' },
      { id:'deep',     label:'深度级 · 30+ 来源' },
    ]},
    { id:'dims', title:'重点关注维度', multi:true, options: dims.slice(0, 6) },
    { id:'time', title:'时间范围', multi:false, options: timeOpts },
    { id:'output', title:'报告侧重', multi:false, options:[
      { id:'o0', label:'给投资决策' },
      { id:'o1', label:'给产品策略' },
      { id:'o2', label:'给行业入门' },
    ]},
  ]
}

function nowTs() {
  const d = new Date()
  const p = x => (x < 10 ? '0' : '') + x
  return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds())
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const view  = ref('landing')
  const phase = ref('input')  // input | clarify | running | report

  const query  = ref('')
  const preset = ref('standard')
  const clarify = reactive({ depth:'std', dims:[], time:'t0', output:'o2' })

  const clarifyLoading   = ref(false)
  const clarifyQuestions = ref([])

  // running state
  const leadLog   = ref([])
  const workers   = ref([])
  const trace     = ref([])
  const tokens    = ref(0)
  const runDone   = ref(false)
  const machinePhase = ref('PLAN')
  const rightTab  = ref('trace')

  // live run state
  const runId      = ref('')
  const liveReport = ref('')
  const statsData  = ref(null)
  const history    = ref([])
  const apiError   = ref('')
  const showHistory = ref(false)

  // HITL state
  const hitlPending = ref(false)
  const hitlType    = ref('intent')
  const hitlPrompt  = ref('')
  const hitlPlan    = ref([])

  let _es        = null
  let _workerMap = {}

  // ── navigation ──────────────────────────────────────────────────────────────
  function goApp() {
    view.value = 'app'
    phase.value = 'input'
    window.scrollTo(0, 0)
  }
  function goLanding() {
    _closeSSE()
    view.value = 'landing'
    window.scrollTo(0, 0)
  }
  async function goClarify() {
    if (!query.value.trim()) return
    clarifyLoading.value = true
    clarifyQuestions.value = []
    phase.value = 'clarify'
    window.scrollTo(0, 0)

    // 第一层：通用控制项（与主题无关的系统参数，固定）
    const depthCard = { id:'depth', title:'研究深度', multi:false, fixed:true, options:[
      { id:'overview', label:'概览级 · 5–8 来源' },
      { id:'std',      label:'标准级 · 15–20 来源（推荐）' },
      { id:'deep',     label:'深度级 · 30+ 来源' },
    ]}
    const ym = query.value.match(/20\d\d/)
    const timeOpts = ym
      ? [ { id:'t0', label:`${parseInt(ym[0]) - 1}–${ym[0]}（近期）` },
          { id:'t1', label:`仅 ${ym[0]} 最新` },
          { id:'t2', label:'近 5 年趋势' } ]
      : [ { id:'t0', label:'最近 1–2 年' },
          { id:'t1', label:'近半年最新' },
          { id:'t2', label:'近 5 年趋势' } ]
    const timeCard = { id:'time', title:'时间范围', multi:false, fixed:true, options: timeOpts }

    // 第二层：主题专属澄清问题（由 Agent 实时生成 —— ReAct 的第一个 Reason）
    let dynamic = []
    try {
      const res = await fetch('/api/clarify', {
        method:'POST', headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({ question: query.value }),
      })
      const data = await res.json()
      dynamic = (data.clarifications || []).map((c, i) => ({
        id: `c${i}`, title: c.question, reason: c.reason || '', multi: !!c.multi,
        options: (c.options || []).map((label, j) => ({ id:`c${i}_${j}`, label })),
      })).filter(q => q.options.length >= 2)
    } catch (e) { /* 网络失败走 fallback */ }

    if (!dynamic.length) {
      dynamic = [{ id:'c0', title:'重点关注维度', reason:'聚焦研究范围', multi:true, options:[
        { id:'c0_0', label:'市场规模与现状' }, { id:'c0_1', label:'竞争格局与玩家' },
        { id:'c0_2', label:'发展趋势与前景' }, { id:'c0_3', label:'机会与风险' },
      ]}]
    }

    clarifyQuestions.value = [depthCard, ...dynamic, timeCard]

    // 初始化默认答案
    clarify.depth = 'std'
    clarify.time  = timeOpts[0].id
    for (const q of dynamic) {
      if (q.multi) clarify[q.id] = [q.options[0].id, q.options[1]?.id].filter(Boolean)
      else clarify[q.id] = q.options[0].id
    }
    clarifyLoading.value = false
  }
  function restart() {
    _closeSSE()
    phase.value = 'input'
    runDone.value = false
    hitlPending.value = false
    apiError.value = ''
    liveReport.value = ''
    statsData.value = null
  }

  // ── clarify options ──────────────────────────────────────────────────────────
  function pickPreset(id) {
    preset.value = id
    clarify.depth = id === 'fast' ? 'overview' : id === 'deep' ? 'deep' : 'std'
  }
  function pickExample(q) { query.value = q }
  function toggleOpt(qid, oid, multi) {
    if (multi) {
      const arr = clarify[qid] || []
      const i = arr.indexOf(oid)
      if (i >= 0) { arr.splice(i, 1) } else { arr.push(oid) }
    } else {
      clarify[qid] = oid
      if (qid === 'depth') {
        preset.value = oid === 'overview' ? 'fast' : oid === 'deep' ? 'deep' : 'standard'
      }
    }
  }

  // ── Reset ────────────────────────────────────────────────────────────────────
  function _resetRunState() {
    leadLog.value  = []
    workers.value  = []
    trace.value    = []
    tokens.value   = 0
    runDone.value  = false
    machinePhase.value = 'PLAN'
    rightTab.value = 'trace'
    apiError.value = ''
    hitlPending.value = false
    liveReport.value  = ''
    statsData.value   = null
    _workerMap = {}
  }

  function _closeSSE() {
    if (_es) { _es.close(); _es = null }
  }

  // 把用户的澄清选择拼进研究问题，让澄清真正影响后端 plan
  function _enhancedQuestion() {
    const prefs = []
    for (const q of clarifyQuestions.value) {
      if (q.id === 'depth') continue   // 深度→profile，不拼进文本
      const sel = clarify[q.id]
      const ids = Array.isArray(sel) ? sel : (sel ? [sel] : [])
      const labels = ids
        .map(id => q.options.find(o => o.id === id)?.label)
        .filter(Boolean)
      if (labels.length) prefs.push(`${q.title}：${labels.join('、')}`)
    }
    return prefs.length ? `${query.value}（${prefs.join('；')}）` : query.value
  }

  // ── Start research ────────────────────────────────────────────────────────────
  async function startRun() {
    _closeSSE()
    _resetRunState()
    phase.value = 'running'

    let rId
    try {
      const res = await fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: _enhancedQuestion(), profile: preset.value }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      rId = data.run_id
      runId.value = rId
    } catch (err) {
      apiError.value = String(err)
      runDone.value = true
      return
    }

    _es = new EventSource(`/api/research/${rId}/stream`)

    _es.addEventListener('trace', e => {
      try { _handleSSETrace(JSON.parse(e.data)) } catch {}
    })
    _es.addEventListener('report', e => {
      try { liveReport.value = JSON.parse(e.data).content || '' } catch {}
    })
    _es.addEventListener('done', e => {
      try {
        const d = JSON.parse(e.data)
        tokens.value = d.tokens_used || tokens.value
      } catch {}
      runDone.value = true
      machinePhase.value = 'DONE'
      _closeSSE()
      if (rId) _loadStats(rId)
    })
    _es.addEventListener('error', e => {
      try {
        const d = JSON.parse(e.data)
        apiError.value = d.message || '连接错误'
        trace.value.push({ ts: nowTs(), tag: 'ERROR', text: d.message || '错误' })
      } catch {}
      runDone.value = true
      _closeSSE()
    })
    _es.onerror = () => {
      if (_es?.readyState === EventSource.CLOSED) {
        runDone.value = true
        _closeSSE()
      }
    }
  }

  // ── SSE trace handler ─────────────────────────────────────────────────────────
  function _handleSSETrace(ev) {
    const etype = ev.event_type || ''
    const data  = ev.data || {}
    const agent = ev.agent_id || data.agent_id || ''

    trace.value.push({ ts: nowTs(), tag: etype.toUpperCase(), text: _traceMsg(etype, data, agent) })
    tokens.value += 200

    if (etype === 'run_start') {
      leadLog.value.push({ kind:'Reason', text:`意图分析：${data.question || query.value}` })
      machinePhase.value = 'PLAN'

    } else if (etype === 'plan_done') {
      const subs = data.subtasks || []
      leadLog.value.push({ kind:'Plan', text:`规划 ${subs.length} 个子课题：${subs.slice(0,2).join('、')}${subs.length > 2 ? '…' : ''}` })

    } else if (etype === 'task_dispatch') {
      const count   = data.count || (data.queries || []).length || 1
      const queries = data.queries || []
      leadLog.value.push({ kind:'Act', text:`A2A 并行扇出：向 ${count} 个研究子 Agent 派发隔离任务。` })
      machinePhase.value = 'DISPATCH'
      // 多轮(depth>1)时累积追加本轮 worker，不清空已完成的卡片
      const base = workers.value.length
      for (let i = 0; i < count; i++) {
        const q = queries[i] || `子课题 ${base + i + 1}`
        workers.value.push({
          id: base + i + 1, title: q.substring(0, 40),
          sub: `子 Agent W${base + i + 1}`, q, agent: null,
          summary:'', status:'queued', progress:0, currentTool:'等待分配…',
        })
      }

    } else if (etype === 'task_start') {
      let wi = agent ? _workerMap[agent] : undefined
      if (wi === undefined) {
        // 绑定到第一个尚未被任何 agent 认领的排队卡片
        wi = workers.value.findIndex(w => w.status === 'queued' && !w.agent)
        if (wi < 0) {
          wi = workers.value.length
          workers.value.push({
            id: wi + 1, title: (data.query || `子课题 ${wi + 1}`).substring(0, 40),
            sub: `子 Agent ${agent || wi + 1}`, q: data.query || '', agent: null,
            summary:'', status:'queued', progress:0, currentTool:'等待分配…',
          })
        }
        if (agent) { _workerMap[agent] = wi; workers.value[wi].agent = agent }
      }
      const w = workers.value[wi]
      if (w) {
        w.status = 'searching'
        w.progress = 15
        w.currentTool = data.query ? `检索："${data.query.substring(0, 50)}"` : '初始化…'
        if (data.query && !w.q) w.q = data.query
      }

    } else if (etype === 'tool_call') {
      const wi = agent ? _workerMap[agent] : undefined
      if (wi !== undefined && workers.value[wi]) {
        const tool = data.tool || ''
        workers.value[wi].currentTool = `${tool}(${JSON.stringify(data.args || {}).substring(0, 50)})`
        workers.value[wi].status = tool.includes('search') ? 'searching' : 'reading'
        workers.value[wi].progress = Math.min(workers.value[wi].progress + 12, 80)
      }

    } else if (etype === 'tool_result') {
      const wi = agent ? _workerMap[agent] : undefined
      if (wi !== undefined && workers.value[wi]) {
        workers.value[wi].progress = Math.min(workers.value[wi].progress + 8, 88)
      }

    } else if (etype === 'task_done') {
      let wi = agent ? _workerMap[agent] : undefined
      if (wi === undefined || wi < 0) wi = workers.value.findIndex(w => w.agent === agent && w.status !== 'done')
      if (wi === undefined || wi < 0) wi = workers.value.findIndex(w => w.status === 'searching' || w.status === 'reading')
      if (wi === undefined || wi < 0) wi = workers.value.findIndex(w => w.status !== 'done')
      if (wi !== undefined && wi >= 0 && workers.value[wi]) {
        workers.value[wi].status      = 'done'
        workers.value[wi].progress    = 100
        workers.value[wi].currentTool = '完成 · 已回传摘要'
        workers.value[wi].summary     = data.summary || '已完成子课题研究'
      }
      leadLog.value.push({ kind:'Observe', text:`子 Agent [${agent || wi + 1}] 完成，摘要已回传给 Lead。` })

    } else if (etype === 'synthesize') {
      leadLog.value.push({ kind:'Synthesize', text:'沿任务树聚合所有发现，生成综合报告…' })
      machinePhase.value = 'SYNTHESIZE'

    } else if (etype === 'citation_check' && data.stage === 'done') {
      const rate = ((data.support_rate || 0) * 100).toFixed(0)
      leadLog.value.push({ kind:'Cite', text:`CitationAgent 完成：${rate}% 有来源支撑，移除未支撑论断。` })
      machinePhase.value = 'CITE'

    } else if (etype === 'run_end') {
      leadLog.value.push({ kind:'Reason', text:`研究完成。Workers: ${data.total_workers || 0} · Tokens: ${(data.tokens_used || 0).toLocaleString()}` })
      tokens.value = data.tokens_used || tokens.value
      machinePhase.value = 'DONE'

    } else if (etype === 'human_intervene') {
      hitlType.value    = data.type    || 'intent'
      hitlPrompt.value  = data.prompt  || ''
      hitlPlan.value    = data.subtasks || []
      hitlPending.value = true
      leadLog.value.push({ kind:'Human', text:`⏸ HITL 干预点：${data.type || 'intent'} — 等待人工确认。` })
      machinePhase.value = 'HITL'
    }
  }

  function _traceMsg(etype, data, agent) {
    const s = v => String(v || '').substring(0, 70)
    if (etype === 'run_start')       return `"${s(data.question)}" [${data.profile || ''}]`
    if (etype === 'plan_done')       return `${data.count || 0} 个子课题: ${(data.subtasks || []).slice(0,2).join('、')}`
    if (etype === 'task_dispatch')   return `${data.count || 0} 个并行任务`
    if (etype === 'task_start')      return `[${agent}] ${s(data.query)}`
    if (etype === 'tool_call')       return `${data.tool || ''}(${JSON.stringify(data.args || {}).substring(0,60)})`
    if (etype === 'tool_result')     return `${data.tool || ''} → ${data.success ? '✓' : '✗'} (${data.duration_ms || 0}ms)`
    if (etype === 'task_done')       return `[${agent}] 完成 · tokens=${data.tokens || 0}`
    if (etype === 'synthesize')      return '合并发现，生成报告…'
    if (etype === 'citation_check')  return `${data.stage || ''} · 支撑率=${(data.support_rate || 0)*100|0}%`
    if (etype === 'run_end')         return `Workers:${data.total_workers || 0} · Tokens:${(data.tokens_used||0).toLocaleString()}`
    if (etype === 'human_intervene') return `⏸ HITL:${data.type || ''} — 等待人工`
    return JSON.stringify(data).substring(0, 80)
  }

  // ── Controls ──────────────────────────────────────────────────────────────────
  function stopRun() { abortLiveRun() }
  function viewReport() { phase.value = 'report' }

  function exportReport() {
    const html = renderedReport.value
    if (!html) return
    const title = (query.value || '研究报告').trim().slice(0, 80)
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${title.replace(/[\\/:*?"<>|]+/g, '_').slice(0, 60) || 'report'}.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  // ── HITL ──────────────────────────────────────────────────────────────────────
  async function answerHITL(value) {
    hitlPending.value = false
    if (!runId.value) return
    try {
      await fetch(`/api/research/${runId.value}/hitl/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      })
    } catch {}
  }

  async function abortLiveRun() {
    hitlPending.value = false
    runDone.value = true
    machinePhase.value = 'STOPPED'
    _closeSSE()
    if (!runId.value) return
    try {
      await fetch(`/api/research/${runId.value}/hitl/abort`, { method: 'POST' })
    } catch {}
  }

  // ── Stats + History ───────────────────────────────────────────────────────────
  async function _loadStats(id) {
    try {
      const r = await fetch(`/api/research/${id}/stats`)
      if (r.ok) statsData.value = await r.json()
    } catch {}
  }

  async function loadHistory() {
    try {
      const r = await fetch('/api/research/history')
      if (r.ok) { const d = await r.json(); history.value = d.runs || [] }
    } catch {}
  }

  async function loadHistoryRun(hRun) {
    runId.value = hRun.run_id
    liveReport.value = ''
    statsData.value  = null
    showHistory.value = false
    phase.value = 'report'
    try {
      const [statsRes, reportRes] = await Promise.all([
        fetch(`/api/research/${hRun.run_id}/stats`),
        fetch(`/api/research/${hRun.run_id}/report`),
      ])
      if (statsRes.ok)  statsData.value  = await statsRes.json()
      if (reportRes.ok) { const d = await reportRes.json(); liveReport.value = d.content || '' }
    } catch {}
  }

  // ── Computed ──────────────────────────────────────────────────────────────────
  const exampleList = EXAMPLES

  const presetCards = computed(() =>
    ['fast', 'standard', 'deep'].map(id => ({
      id, ...PRESET_META[id], selected: preset.value === id,
    }))
  )

  const clarifyView = computed(() =>
    clarifyQuestions.value.map(q => ({
      ...q,
      options: q.options.map(o => ({
        ...o,
        on: q.multi
          ? (clarify[q.id] || []).includes(o.id)
          : clarify[q.id] === o.id,
      })),
    }))
  )

  const planSummary = computed(() => {
    const pm = PRESET_META[preset.value]
    const answered = clarifyQuestions.value.filter(q =>
      q.id !== 'depth' && q.id !== 'time' &&
      (Array.isArray(clarify[q.id]) ? clarify[q.id].length : clarify[q.id])
    ).length
    return `将派发 ${pm.breadth} 个并行子 Agent · 已明确 ${answered} 项研究偏好 · ${pm.meta}`
  })

  const phaseSteps = computed(() => {
    const order  = ['input', 'clarify', 'running', 'report']
    const labels = { input:'提问', clarify:'澄清意图', running:'并行研究', report:'报告' }
    const curIdx = order.indexOf(phase.value)
    return order.map((p, i) => ({ p, label: labels[p], active: i === curIdx, done: i < curIdx }))
  })

  const workersView = computed(() =>
    workers.value.map(w => {
      const sm = WORKER_STATUS[w.status] || WORKER_STATUS.queued
      return { ...w, sm, animating: w.status === 'searching' || w.status === 'reading' }
    })
  )

  const leadView  = computed(() => leadLog.value.map(e => ({ ...e, color: KIND_COLORS[e.kind] || '#475569' })))
  const traceView = computed(() => trace.value.map(t => ({ ...t, tagColor: TRACE_TAG_COLORS[t.tag] || '#94A3B8' })))

  const doneCount   = computed(() => workers.value.filter(w => w.status === 'done').length)
  const tokensFmt   = computed(() => (tokens.value / 1000).toFixed(1) + 'K')
  const workerCount = computed(() => workers.value.length || PRESET_META[preset.value].breadth)

  const renderedReport = computed(() => {
    const c = liveReport.value
    if (!c) return ''
    const t = c.trimStart()
    // 新版：后端渲染的可视化 HTML 研报，直接用
    if (t.startsWith('<!DOCTYPE') || t.startsWith('<html')) return c
    // 旧版：Markdown 报告，包成简单 HTML 文档以便 iframe 渲染
    return '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
      + '<style>body{font-family:"PingFang SC",-apple-system,sans-serif;max-width:820px;'
      + 'margin:0 auto;padding:40px 28px;line-height:1.75;color:#28323f}'
      + 'h1{font-size:28px}h2{font-size:21px;margin-top:28px}h3{font-size:17px}'
      + 'a{color:#2e6fb8;word-break:break-all}ul,ol{padding-left:22px}</style>'
      + '</head><body>' + marked.parse(c) + '</body></html>'
  })

  const runStateLabel = computed(() => {
    if (hitlPending.value) return '⏸ HITL 干预点 — 等待人工确认'
    const map = {
      PLAN:'规划中…', DISPATCH:'派发子 Agent…', COLLECT:'收集摘要…',
      ASSESS:'评估信息充分性…', SYNTHESIZE:'综合报告…', CITE:'引用核对中…',
      HITL:'⏸ 等待人工干预…', DONE:'研究完成', STOPPED:'已叫停',
    }
    return map[machinePhase.value] || '研究中…'
  })

  const statusColor = computed(() =>
    hitlPending.value ? '#D97706'
      : runDone.value ? (machinePhase.value === 'STOPPED' ? '#DC2626' : '#16A34A')
      : '#2563EB'
  )

  return {
    view, phase, query, preset, clarify, clarifyLoading, clarifyQuestions,
    leadLog, workers, trace, tokens, runDone, machinePhase, rightTab,
    runId, liveReport, statsData, history, apiError, showHistory,
    hitlPending, hitlType, hitlPrompt, hitlPlan,
    goApp, goLanding, goClarify, restart,
    pickPreset, pickExample, toggleOpt,
    startRun, stopRun, viewReport, exportReport,
    answerHITL, abortLiveRun, loadHistory, loadHistoryRun,
    exampleList, presetCards, clarifyView, planSummary, phaseSteps,
    workersView, leadView, traceView,
    doneCount, tokensFmt, workerCount, runStateLabel, statusColor, renderedReport,
  }
})

// 让 Pinia store 支持 HMR 热替换：改 store 代码后无需硬刷新即可生效
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useWorkspaceStore, import.meta.hot))
}
