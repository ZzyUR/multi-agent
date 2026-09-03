<template>
  <div class="workspace">

    <!-- ── HITL MODAL OVERLAY ──────────────────────────────────────── -->
    <HITLModal
      v-if="s.hitlPending"
      :type="s.hitlType"
      :prompt="s.hitlPrompt"
      :plan="s.hitlPlan"
      @confirm="s.answerHITL"
      @abort="s.abortLiveRun"
    />

    <!-- ── HISTORY SLIDE PANEL ─────────────────────────────────────── -->
    <div v-if="s.showHistory" class="history-overlay" @click.self="s.showHistory = false">
      <div class="history-panel">
        <div class="history-head">
          <span class="history-title">历史研究</span>
          <button class="history-close ds-btn" @click="s.showHistory = false">✕</button>
        </div>
        <div v-if="s.history.length === 0" class="history-empty">暂无历史记录</div>
        <div v-else class="history-list">
          <div
            v-for="r in s.history" :key="r.run_id"
            class="history-item ds-btn"
            @click="s.loadHistoryRun(r)"
          >
            <div class="history-q">{{ r.question || r.run_id }}</div>
            <div class="history-meta mono">
              {{ r.profile || '—' }} · {{ r.tokens?.toLocaleString() || '—' }} tokens · ${{ (r.estimated_cost_usd || 0).toFixed(4) }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- TOP BAR -->
    <div class="topbar">
      <div class="topbar-left">
        <button class="back-btn ds-btn" @click="s.goLanding()">← 首页</button>
        <div class="topbar-brand">
          <div class="topbar-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="5" r="2.6" fill="#fff"/>
              <circle cx="5" cy="18" r="2.6" fill="#fff"/>
              <circle cx="19" cy="18" r="2.6" fill="#fff"/>
              <path d="M12 7.6V13M12 13L6.5 16.2M12 13l5.5 3.2" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
          </div>
          <span class="topbar-name">DeepResearch</span>
        </div>
      </div>

      <!-- phase stepper -->
      <div class="phase-steps">
        <template v-for="(ps, i) in s.phaseSteps" :key="ps.p">
          <div class="step-dot" :class="{ active: ps.active, done: ps.done }">
            {{ ps.done ? '✓' : i + 1 }}
          </div>
          <span class="step-label" :class="{ active: ps.active }">{{ ps.label }}</span>
          <span class="step-sep" v-if="i < s.phaseSteps.length - 1">›</span>
        </template>
      </div>

      <div class="topbar-right">
        <button class="hist-btn ds-btn" @click="openHistory">历史 ⊞</button>
      </div>
    </div>

    <!-- ─── PHASE: INPUT ────────────────────────────────────────────── -->
    <div v-if="s.phase === 'input'" class="phase-input ds-anim-up">
      <div class="input-wrap">
        <div class="input-hd">
          <h1 class="input-title">你想研究什么？</h1>
          <p class="input-sub">
            提出一个研究问题，Agent 会先和你澄清范围与深度，再开始工作。
          </p>
        </div>
        <div class="query-card">
          <textarea
            v-model="s.query"
            placeholder="例如：分析 2026 新能源汽车行业竞争格局"
            class="query-ta"
          />
          <div class="query-footer">
            <div class="example-chips">
              <button
                v-for="ex in s.exampleList" :key="ex.q"
                class="chip ds-btn"
                @click="s.pickExample(ex.q)"
              >{{ ex.label }}</button>
            </div>
            <button
              class="next-btn ds-btn"
              :disabled="!s.query.trim()"
              @click="s.goClarify()"
            >下一步：澄清意图 →</button>
          </div>
        </div>
        <!-- Preset cards -->
        <div class="preset-section">
          <div class="preset-label">研究档位 · Depth × Breadth 成本旋钮</div>
          <div class="preset-grid">
            <div
              v-for="pc in s.presetCards" :key="pc.id"
              class="preset-card ds-btn"
              :class="{ selected: pc.selected }"
              @click="s.pickPreset(pc.id)"
            >
              <div class="preset-row">
                <span class="preset-name" :class="{ 'preset-name--sel': pc.selected }">{{ pc.name }}</span>
                <span class="preset-check" v-if="pc.selected">✓</span>
              </div>
              <div class="preset-desc">{{ pc.desc }}</div>
              <div class="preset-meta mono">{{ pc.meta }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ─── PHASE: CLARIFY ──────────────────────────────────────────── -->
    <div v-else-if="s.phase === 'clarify'" class="phase-clarify ds-anim-up">
      <div class="clarify-wrap">
        <div class="clarify-ai-head">
          <div class="ai-avatar">AI</div>
          <div>
            <div class="ai-title">在开始前，我想先确认一下研究意图</div>
            <div class="ai-query">你的问题：<span class="ai-q-text">{{ s.query }}</span></div>
          </div>
        </div>

        <!-- Loading skeleton while AI generates questions -->
        <div v-if="s.clarifyLoading" class="clarify-thinking">
          <div class="thinking-row">
            <div class="thinking-dots">
              <span></span><span></span><span></span>
            </div>
            <span class="thinking-text">AI 正在分析研究意图，生成定制问题…</span>
          </div>
          <div class="skel-card"></div>
          <div class="skel-card skel-card--wide"></div>
          <div class="skel-card skel-card--sm"></div>
        </div>

        <!-- Actual AI-generated questions -->
        <div v-else class="clarify-questions">
          <div v-for="q in s.clarifyView" :key="q.id" class="clarify-card">
            <div class="clarify-q-title">
              {{ q.title }}
              <span class="multi-hint" v-if="q.multi"> · 可多选</span>
              <span class="ai-gen-tag" v-if="!q.fixed">⚡ AI 按主题生成</span>
            </div>
            <div class="clarify-reason" v-if="q.reason">💡 {{ q.reason }}</div>
            <div class="clarify-opts">
              <button
                v-for="o in q.options" :key="o.id"
                class="opt-btn ds-btn"
                :class="{ 'opt-btn--on': o.on }"
                @click="s.toggleOpt(q.id, o.id, q.multi)"
              >{{ o.label }}</button>
            </div>
          </div>
        </div>

        <div class="clarify-footer" v-if="!s.clarifyLoading">
          <div class="plan-summary">{{ s.planSummary }}</div>
          <div class="clarify-actions">
            <button class="skip-btn ds-btn" @click="s.startRun()">跳过，直接开始</button>
            <button class="start-btn ds-btn" @click="s.startRun()">✓ 确认意图，开始研究</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ─── PHASE: RUNNING ──────────────────────────────────────────── -->
    <div v-else-if="s.phase === 'running'" class="phase-running">
      <!-- error banner -->
      <div v-if="s.apiError" class="error-strip">
        ⚠ 连接错误：{{ s.apiError }}
        <button class="ds-btn err-close" @click="s.apiError = ''">✕</button>
      </div>

      <!-- run control strip -->
      <div class="run-strip">
        <div class="run-strip-left">
          <div class="run-status">
            <span class="run-dot" :style="{
              background: s.statusColor,
              animation: !s.runDone ? 'ds-blink 1s infinite' : 'none'
            }"></span>
            <span class="run-state-label">{{ s.runStateLabel }}</span>
          </div>
          <div class="run-query">{{ s.query }}</div>
        </div>
        <div class="run-strip-right">
          <div class="run-stats">
            <div class="run-stat">
              <div class="run-stat-val mono">{{ s.tokensFmt }}</div>
              <div class="run-stat-key">tokens</div>
            </div>
            <div class="run-stat">
              <div class="run-stat-val mono" style="color:#16A34A">{{ s.doneCount }}</div>
              <div class="run-stat-key">workers done</div>
            </div>
          </div>
          <div class="run-divider"></div>
          <button class="ctrl-btn ds-btn stop-btn" @click="s.stopRun()">■ 叫停</button>
          <button v-if="s.runDone" class="report-btn ds-btn" @click="s.viewReport()">查看报告 →</button>
        </div>
      </div>

      <!-- 3-col layout -->
      <div class="run-cols">
        <!-- LEFT: Lead Agent -->
        <div class="col-lead">
          <div class="col-head">
            <span class="col-title">Lead Agent · ReAct 循环</span>
            <span class="phase-chip mono">{{ s.machinePhase }}</span>
          </div>
          <div class="col-body">
            <div v-for="(e, i) in s.leadView" :key="i" class="lead-entry ds-anim-up">
              <div class="lead-entry-left">
                <span class="lead-dot" :style="{ background: e.color }"></span>
                <span class="lead-line"></span>
              </div>
              <div class="lead-content">
                <div class="lead-kind" :style="{ color: e.color }">{{ e.kind }}</div>
                <div class="lead-text">{{ e.text }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- CENTER: Workers -->
        <div class="col-workers">
          <div class="col-head col-head--workers">
            <span class="col-title">并行研究子 Agent · A2A 隔离上下文</span>
            <span class="mono" style="font-size:12px;color:#64748B">
              breadth = {{ s.workerCount }} · 互不通信
            </span>
          </div>
          <div class="col-body col-body--workers">
            <div v-for="(w, i) in s.workersView" :key="i" class="worker-card ds-anim-up">
              <div class="worker-card-top">
                <div class="worker-id-row">
                  <span class="worker-id-chip mono" :style="{ background: w.sm.bg, color: w.sm.color }">W{{ w.id }}</span>
                  <span class="worker-title">{{ w.title }}</span>
                </div>
                <span class="worker-badge" :style="{
                  background: w.sm.bg, color: w.sm.color, border: '1px solid ' + w.sm.border
                }">{{ w.sm.label }}</span>
              </div>
              <div class="worker-sub">{{ w.sub }}</div>
              <div class="worker-bar">
                <div class="worker-fill" :style="{ width: w.progress + '%' }"></div>
              </div>
              <div class="worker-tool">
                <span class="worker-tool-dot" :style="{
                  background: w.sm.color,
                  animation: w.animating ? 'ds-blink 1s infinite' : 'none'
                }"></span>
                <span class="mono" style="font-size:12px;color:#475569">{{ w.currentTool }}</span>
              </div>
              <div v-if="w.summary" class="worker-summary">
                <div class="worker-summary-label">↩ 回传摘要（原文已写入 findings/）</div>
                <div class="worker-summary-text">{{ w.summary }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- RIGHT: Trace -->
        <div class="col-right">
          <div class="right-head">
            <span class="col-title" style="color:#94A3B8">⊹ Trace 可观测</span>
          </div>
          <div class="right-body" ref="traceEl">
            <div v-for="(t, i) in s.traceView" :key="i" class="trace-row ds-anim-up mono">
              <span class="trace-ts">{{ t.ts }}</span>
              <span class="trace-tag" :style="{ color: t.tagColor }">{{ t.tag }}</span>
              <span class="trace-text">{{ t.text }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ─── PHASE: REPORT ───────────────────────────────────────────── -->
    <div v-else-if="s.phase === 'report'" class="phase-report ds-anim-up">
      <div class="report-wrap">

        <!-- report header -->
        <div class="report-header">
          <div class="report-header-left">
            <div class="report-badge">研究报告</div>
            <div class="report-meta-text">
              <span v-if="s.statsData">
                {{ s.statsData.profile || '' }} · {{ (s.statsData.tokens || 0).toLocaleString() }} tokens
                · ${{ (s.statsData.estimated_cost_usd || 0).toFixed(4) }}
              </span>
              <span v-else>{{ s.query }}</span>
            </div>
          </div>
          <button v-if="s.renderedReport" class="export-btn ds-btn" @click="s.exportReport()">⬇ 导出 HTML</button>
          <button class="restart-btn ds-btn" @click="s.restart()">↺ 新研究</button>
        </div>

        <!-- rendered report -->
        <iframe
          v-if="s.renderedReport"
          :srcdoc="s.renderedReport"
          class="report-frame"
          @load="onFrameLoad"
        ></iframe>

        <!-- loading state -->
        <div v-else class="report-card report-loading">
          <div class="loading-spinner"></div>
          <div class="loading-text">报告生成中，请稍候…</div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useWorkspaceStore } from '../stores/workspace.js'
import HITLModal  from './HITLModal.vue'

const s = useWorkspaceStore()
const traceEl = ref(null)

watch(() => s.trace.length, async () => {
  await nextTick()
  if (traceEl.value) traceEl.value.scrollTop = traceEl.value.scrollHeight
})

async function openHistory() {
  await s.loadHistory()
  s.showHistory = true
}

// iframe 研报：加载后按内容高度自适应（ECharts 异步渲染，多量几次）
function onFrameLoad(e) {
  const f = e.target
  const setH = () => {
    try { f.style.height = f.contentWindow.document.body.scrollHeight + 'px' } catch (_) {}
  }
  setH()
  setTimeout(setH, 600)
  setTimeout(setH, 1600)
}
</script>

<style scoped>
.workspace {
  min-height: 100vh; display: flex; flex-direction: column;
  background: var(--c-bg);
}

/* ── TOPBAR ──────────────────────────────────────────────────────── */
.topbar {
  height: 60px; flex: none;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px;
  background: #fff; border-bottom: 1px solid var(--c-nav-border);
  position: sticky; top: 0; z-index: 30;
}
.topbar-left  { display: flex; align-items: center; gap: 14px; }
.topbar-right { display: flex; align-items: center; gap: 10px; }
.back-btn {
  border: 1px solid var(--c-divider-2); background: #fff; color: var(--c-text-2);
  font-weight: 600; font-size: 13.5px; padding: 7px 13px; border-radius: 9px;
}
.topbar-brand { display: flex; align-items: center; gap: 9px; }
.topbar-icon {
  width: 28px; height: 28px; border-radius: 8px;
  background: linear-gradient(135deg, var(--c-blue), var(--c-blue-sky));
  display: flex; align-items: center; justify-content: center;
}
.topbar-name { font-weight: 800; font-size: 16px; }
.phase-steps { display: flex; align-items: center; gap: 6px; }
.step-dot {
  width: 22px; height: 22px; border-radius: 50%;
  background: var(--c-divider-2); color: var(--c-text-4);
  font-size: 11px; font-weight: 800;
  display: flex; align-items: center; justify-content: center; flex: none;
}
.step-dot.active { background: var(--c-blue); color: #fff; }
.step-dot.done   { background: var(--c-green); color: #fff; }
.step-label { font-size: 12.5px; font-weight: 700; color: var(--c-text-4); }
.step-label.active { color: var(--c-text); }
.step-sep { color: var(--c-text-4); margin: 0 8px; font-size: 14px; }

.hist-btn {
  border: 1px solid var(--c-divider-2); background: #fff; color: var(--c-text-2);
  font-weight: 600; font-size: 13px; padding: 7px 13px; border-radius: 9px;
}

/* ── INPUT PHASE ─────────────────────────────────────────────────── */
.phase-input {
  flex: 1; display: flex; align-items: center; justify-content: center; padding: 48px 24px;
}
.input-wrap { width: 100%; max-width: 760px; }
.input-hd { text-align: center; margin-bottom: 30px; }
.input-title { font-size: 36px; font-weight: 800; letter-spacing: -0.02em; }
.input-sub { font-size: 17px; color: var(--c-text-3); margin: 12px 0 0; }

.query-card {
  background: #fff; border: 1px solid var(--c-divider-2);
  border-radius: 18px; padding: 8px;
  box-shadow: rgba(15,23,42,.3) 0 24px 60px -30px;
}
.query-ta {
  width: 100%; border: none; outline: none; resize: none;
  font-family: inherit; font-size: 18px; line-height: 1.5;
  padding: 18px 18px 8px; background: transparent; color: var(--c-text); height: 96px;
}
.query-footer {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px 10px; flex-wrap: wrap; gap: 10px;
}
.example-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
  border: 1px solid var(--c-divider-2); background: var(--c-card-bg);
  color: var(--c-text-2); font-size: 13px; font-weight: 600;
  padding: 6px 11px; border-radius: 99px;
}
.next-btn {
  border: none; background: var(--c-blue); color: #fff;
  font-weight: 700; font-size: 15px; padding: 11px 22px;
  border-radius: 11px; box-shadow: rgba(37,99,235,.7) 0 10px 22px -10px;
}
.next-btn:disabled { opacity: 0.45; cursor: not-allowed; transform: none !important; }

.preset-section { margin-top: 28px; }
.preset-label { font-size: 13.5px; font-weight: 700; color: var(--c-text-2); margin-bottom: 12px; }
.preset-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.preset-card {
  text-align: left; border: 1.5px solid var(--c-divider-2); background: #fff;
  border-radius: 14px; padding: 16px 18px; cursor: pointer;
}
.preset-card.selected {
  border-color: var(--c-blue); background: #F5F9FF;
  box-shadow: rgba(37,99,235,.6) 0 12px 26px -16px;
}
.preset-row { display: flex; justify-content: space-between; align-items: center; }
.preset-name { font-weight: 800; font-size: 16px; color: var(--c-text); }
.preset-name--sel { color: var(--c-blue); }
.preset-check {
  width: 20px; height: 20px; border-radius: 50%;
  background: var(--c-blue); color: #fff; font-size: 11px; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
}
.preset-desc { font-size: 13px; color: var(--c-text-3); margin-top: 6px; }
.preset-meta { font-size: 11.5px; color: var(--c-blue); margin-top: 10px; }

/* ── CLARIFY PHASE ───────────────────────────────────────────────── */
.phase-clarify { flex: 1; display: flex; justify-content: center; padding: 42px 24px 60px; overflow: auto; }
.clarify-wrap  { width: 100%; max-width: 760px; }
.clarify-ai-head { display: flex; align-items: flex-start; gap: 13px; margin-bottom: 26px; }
.ai-avatar {
  width: 38px; height: 38px; flex: none; border-radius: 11px;
  background: linear-gradient(135deg, var(--c-blue), var(--c-blue-sky));
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 800; font-size: 13px;
}
.ai-title { font-weight: 700; font-size: 17px; margin-bottom: 3px; }
.ai-query { font-size: 14.5px; color: var(--c-text-3); }
.ai-q-text { color: var(--c-blue); font-weight: 600; }

/* thinking skeleton */
.clarify-thinking { display: flex; flex-direction: column; gap: 16px; }
.thinking-row { display: flex; align-items: center; gap: 12px; padding: 4px 0 6px; }
.thinking-dots { display: flex; gap: 6px; }
.thinking-dots span {
  width: 8px; height: 8px; border-radius: 50%; background: var(--c-blue);
  animation: ds-blink 1.2s infinite;
}
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
.thinking-text { font-size: 14px; color: var(--c-text-3); font-weight: 600; }

@keyframes skel-shimmer {
  0%   { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}
.skel-card {
  height: 90px; border-radius: 15px;
  background: linear-gradient(90deg, #f0f4f8 25%, #e4eaf2 50%, #f0f4f8 75%);
  background-size: 800px 100%;
  animation: skel-shimmer 1.4s infinite linear;
}
.skel-card--wide { height: 130px; }
.skel-card--sm   { height: 70px; }

.clarify-questions { display: flex; flex-direction: column; gap: 18px; }
.clarify-card {
  background: #fff; border: 1px solid var(--c-nav-border);
  border-radius: 15px; padding: 20px 22px;
}
.clarify-q-title { font-weight: 700; font-size: 15.5px; margin-bottom: 6px; }
.multi-hint { color: var(--c-text-4); font-weight: 600; font-size: 13px; }
.ai-gen-tag {
  margin-left: 8px; font-size: 11px; font-weight: 700; color: var(--c-blue);
  background: var(--c-blue-light); padding: 2px 8px; border-radius: 99px;
}
.clarify-reason { font-size: 13px; color: var(--c-text-3); margin-bottom: 13px; }
.clarify-opts { display: flex; flex-wrap: wrap; gap: 10px; }
.opt-btn {
  border: 1.5px solid var(--c-divider-2); background: #fff; color: var(--c-text-2);
  font-weight: 600; font-size: 13.5px; padding: 9px 15px; border-radius: 10px;
}
.opt-btn--on { border-color: var(--c-blue); background: var(--c-blue); color: #fff; }

.clarify-footer {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 26px; background: var(--c-blue-light); border: 1px solid var(--c-blue-border);
  border-radius: 14px; padding: 16px 20px; gap: 14px; flex-wrap: wrap;
}
.plan-summary { font-size: 14px; color: rgb(30,58,138); font-weight: 600; }
.clarify-actions { display: flex; gap: 10px; align-items: center; flex-shrink: 0; }
.skip-btn {
  border: 1px solid var(--c-divider-2); background: #fff; color: var(--c-text-3);
  font-weight: 600; font-size: 13.5px; padding: 12px 18px; border-radius: 11px;
}
.start-btn {
  border: none; background: var(--c-blue); color: #fff;
  font-weight: 700; font-size: 15.5px; padding: 13px 26px;
  border-radius: 11px; box-shadow: rgba(37,99,235,.7) 0 12px 26px -10px;
  flex-shrink: 0;
}

/* ── RUNNING PHASE ───────────────────────────────────────────────── */
.phase-running { flex: 1; display: flex; flex-direction: column; min-height: 0; }

.error-strip {
  background: rgb(254,242,242); border-bottom: 1px solid rgb(252,165,165);
  color: rgb(185,28,28); padding: 10px 24px; font-size: 13.5px; font-weight: 600;
  display: flex; align-items: center; gap: 12px;
}
.err-close {
  margin-left: auto; border: none; background: transparent; color: rgb(185,28,28);
  font-size: 16px; padding: 0 4px;
}

.run-strip {
  flex: none; display: flex; align-items: center; justify-content: space-between;
  padding: 12px 24px; background: #fff; border-bottom: 1px solid var(--c-nav-border);
  gap: 16px; flex-wrap: wrap;
}
.run-strip-left { display: flex; align-items: center; gap: 16px; }
.run-status { display: flex; align-items: center; gap: 8px; }
.run-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.run-state-label { font-weight: 700; font-size: 14.5px; }
.run-query { font-size: 13.5px; color: var(--c-text-3); max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.run-strip-right { display: flex; align-items: center; gap: 14px; }
.run-stats { display: flex; gap: 18px; }
.run-stat { text-align: right; }
.run-stat-val { font-size: 16px; font-weight: 700; color: var(--c-blue); }
.run-stat-key { font-size: 11px; color: var(--c-text-4); font-weight: 600; }
.run-divider { width: 1px; height: 30px; background: var(--c-divider-2); }
.ctrl-btn {
  border: 1px solid var(--c-divider-2); background: #fff; color: var(--c-text);
  font-weight: 600; font-size: 13px; padding: 8px 13px; border-radius: 9px;
}
.stop-btn { border-color: rgb(253,200,200); background: rgb(254,242,242); color: rgb(220,38,38); }
.report-btn {
  border: none; background: var(--c-green); color: #fff;
  font-weight: 700; font-size: 13.5px; padding: 9px 16px; border-radius: 9px;
  box-shadow: rgba(22,163,74,.7) 0 10px 20px -10px;
}

.run-cols { flex: 1; display: grid; grid-template-columns: 320px 1fr 340px; min-height: 0; overflow: hidden; }

/* Lead column */
.col-lead {
  border-right: 1px solid var(--c-nav-border); background: #fff;
  display: flex; flex-direction: column; min-height: 0;
}
.col-head {
  flex: none; padding: 14px 18px; border-bottom: 1px solid var(--c-divider);
  display: flex; align-items: center; justify-content: space-between;
}
.col-title { font-weight: 700; font-size: 14px; }
.phase-chip {
  font-size: 11px; font-weight: 800; color: var(--c-blue);
  background: var(--c-blue-light); padding: 3px 9px; border-radius: 99px;
}
.col-body { flex: 1; overflow: auto; padding: 16px 18px; }

.lead-entry { display: flex; gap: 11px; margin-bottom: 16px; }
.lead-entry-left { display: flex; flex-direction: column; align-items: center; flex: none; }
.lead-dot { width: 11px; height: 11px; border-radius: 50%; flex: none; margin-top: 3px; }
.lead-line { width: 2px; flex: 1; background: var(--c-divider); margin-top: 4px; }
.lead-kind { font-size: 11.5px; font-weight: 800; letter-spacing: 0.04em; }
.lead-text { font-size: 13.5px; color: rgb(51,65,85); line-height: 1.5; margin-top: 2px; }

/* Workers column */
.col-workers { background: var(--c-bg); display: flex; flex-direction: column; min-height: 0; }
.col-head--workers { background: #fff; border-bottom: 1px solid var(--c-nav-border); }
.col-body--workers { flex: 1; overflow: auto; padding: 22px; display: flex; flex-direction: column; gap: 16px; }

.worker-card {
  background: #fff; border: 1px solid var(--c-nav-border);
  border-radius: 15px; padding: 18px 20px;
  box-shadow: rgba(15,23,42,.4) 0 8px 24px -18px;
}
.worker-card-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.worker-id-row { display: flex; align-items: center; gap: 10px; }
.worker-id-chip {
  width: 30px; height: 24px; border-radius: 7px; font-size: 11px; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
}
.worker-title { font-weight: 700; font-size: 15.5px; }
.worker-badge { font-size: 11.5px; font-weight: 700; padding: 4px 11px; border-radius: 99px; }
.worker-sub { font-size: 13px; color: var(--c-text-3); margin: 2px 0 12px; padding-left: 40px; }
.worker-bar { height: 7px; border-radius: 99px; background: var(--c-divider); overflow: hidden; margin-bottom: 10px; }
.worker-fill { height: 100%; border-radius: 99px; background: linear-gradient(90deg, var(--c-blue), var(--c-blue-sky)); transition: width 0.6s ease; }
.worker-tool { display: flex; align-items: center; gap: 8px; }
.worker-tool-dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.worker-summary {
  margin-top: 12px; background: rgb(243,251,245);
  border: 1px solid rgb(201,235,211); border-radius: 10px; padding: 11px 13px;
}
.worker-summary-label { font-size: 11px; font-weight: 800; color: rgb(21,128,61); letter-spacing: 0.04em; margin-bottom: 3px; }
.worker-summary-text  { font-size: 13px; color: rgb(50,102,71); line-height: 1.5; }

/* Right column (trace) */
.col-right { border-left: 1px solid var(--c-nav-border); background: var(--c-dark); display: flex; flex-direction: column; min-height: 0; }
.right-head { flex: none; padding: 14px 18px; border-bottom: 1px solid rgb(30,41,59); }
.right-body { flex: 1; overflow: auto; padding: 14px 16px; display: flex; flex-direction: column; gap: 9px; }

.trace-row { display: flex; gap: 9px; font-size: 11.5px; align-items: baseline; }
.trace-ts  { color: rgb(71,85,105); flex: none; min-width: 60px; }
.trace-tag { flex: none; font-weight: 700; min-width: 100px; font-size: 11px; }
.trace-text { color: rgb(203,213,225); line-height: 1.45; }

/* ── REPORT PHASE ────────────────────────────────────────────────── */
.phase-report { flex: 1; overflow: auto; background: var(--c-bg); }
.report-wrap { max-width: 880px; margin: 0 auto; padding: 40px 24px 80px; }

.report-header {
  display: flex; align-items: center; gap: 14px; margin-bottom: 24px; flex-wrap: wrap;
}
.report-header-left { display: flex; align-items: center; gap: 12px; flex: 1; }
.report-badge {
  background: var(--c-blue-light); border: 1px solid var(--c-blue-border);
  color: var(--c-blue); font-size: 13px; font-weight: 800;
  padding: 6px 14px; border-radius: 99px;
}
.report-meta-text { font-size: 14px; color: var(--c-text-3); }
.export-btn {
  border: none; background: var(--c-blue); color: #fff;
  font-weight: 700; font-size: 13.5px; padding: 8px 16px; border-radius: 9px; flex-shrink: 0;
  box-shadow: rgba(37,99,235,.6) 0 8px 18px -10px;
}
.restart-btn {
  border: 1px solid var(--c-divider-2); background: #fff; color: var(--c-text-2);
  font-weight: 600; font-size: 13.5px; padding: 8px 14px; border-radius: 9px; flex-shrink: 0;
}

.report-card {
  background: #fff; border: 1px solid var(--c-nav-border);
  border-radius: 18px; padding: 40px 48px;
  box-shadow: rgba(15,23,42,.3) 0 24px 60px -36px;
}
.report-frame {
  width: 100%; min-height: 600px; border: 1px solid var(--c-nav-border);
  border-radius: 14px; background: #fff; display: block;
  box-shadow: rgba(15,23,42,.3) 0 24px 60px -40px;
}
.report-loading {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 240px; gap: 16px;
}
.loading-spinner {
  width: 40px; height: 40px; border-radius: 50%;
  border: 3px solid var(--c-divider-2);
  border-top-color: var(--c-blue);
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { font-size: 15px; color: var(--c-text-3); font-weight: 600; }

/* Real markdown report styles (applied via v-html) */
.report-md :deep(h1) { font-size: 28px; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 16px; line-height: 1.2; }
.report-md :deep(h2) { font-size: 20px; font-weight: 800; margin: 28px 0 12px; }
.report-md :deep(h3) { font-size: 16px; font-weight: 700; margin: 20px 0 8px; }
.report-md :deep(p)  { font-size: 15.5px; line-height: 1.75; color: rgb(51,65,85); margin-bottom: 14px; }
.report-md :deep(ul), .report-md :deep(ol) { padding-left: 22px; margin-bottom: 14px; }
.report-md :deep(li) { font-size: 15px; line-height: 1.7; color: rgb(51,65,85); margin-bottom: 6px; }
.report-md :deep(blockquote) {
  border-left: 3px solid var(--c-blue); margin: 16px 0;
  padding: 10px 16px; background: var(--c-card-bg); border-radius: 0 8px 8px 0;
  color: rgb(30,58,138);
}
.report-md :deep(code) {
  background: var(--c-card-bg); border: 1px solid var(--c-card-border);
  padding: 2px 6px; border-radius: 5px; font-size: 13.5px;
}
.report-md :deep(pre code) {
  background: transparent; border: none; padding: 0; display: block;
}
.report-md :deep(pre) {
  background: var(--c-dark); color: #E2E8F0;
  padding: 18px 22px; border-radius: 12px; overflow-x: auto; margin-bottom: 16px;
}
.report-md :deep(sup) { color: var(--c-blue); font-weight: 700; font-size: 0.8em; }
.report-md :deep(a) { color: var(--c-blue); text-decoration: underline; }
.report-md :deep(hr) { border: none; border-top: 1px solid var(--c-divider); margin: 24px 0; }

/* ── HISTORY PANEL ───────────────────────────────────────────────── */
.history-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(11,18,32,0.5);
  display: flex; justify-content: flex-end;
  animation: ds-up 0.15s ease both;
}
.history-panel {
  width: min(420px, 92vw); height: 100vh; background: #fff;
  display: flex; flex-direction: column;
  box-shadow: rgba(11,18,32,.4) -20px 0 50px -10px;
  animation: slide-in 0.2s ease both;
}
@keyframes slide-in {
  from { transform: translateX(40px); opacity: 0; }
  to   { transform: translateX(0);    opacity: 1; }
}
.history-head {
  padding: 20px 22px; border-bottom: 1px solid var(--c-nav-border);
  display: flex; align-items: center; justify-content: space-between;
}
.history-title { font-weight: 800; font-size: 17px; }
.history-close {
  border: none; background: transparent; font-size: 18px; color: var(--c-text-3);
  padding: 4px 8px; border-radius: 7px;
}
.history-empty { padding: 40px; text-align: center; color: var(--c-text-4); font-size: 15px; }
.history-list { flex: 1; overflow: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.history-item {
  background: var(--c-card-bg); border: 1px solid var(--c-card-border);
  border-radius: 12px; padding: 14px 16px; text-align: left; cursor: pointer;
}
.history-item:hover { border-color: var(--c-blue); background: #F5F9FF; }
.history-q { font-weight: 700; font-size: 14.5px; margin-bottom: 4px; color: var(--c-text); }
.history-meta { font-size: 12px; color: var(--c-text-4); }
</style>
