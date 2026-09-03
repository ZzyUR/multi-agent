<template>
  <section id="arch" class="arch-section">
    <div class="arch-inner">
      <div class="arch-hd">
        <div class="section-tag" style="color:#60A5FA">系统架构</div>
        <h2 class="section-h2" style="color:#fff">Multi-Agent Orchestrator-Worker</h2>
        <p class="section-sub" style="color:#94A3B8">一个 Lead 统一指挥，Worker 之间互不通信 —— 可控、可调试、可控成本</p>
      </div>

      <div class="flow">
        <!-- Lead Agent -->
        <div class="flow-lead">
          <div class="lead-name">Lead Agent · 编排者</div>
          <div class="lead-sub">ReAct 规划 / A2A 派发 / 综合 · 对标 Claude Code 主循环</div>
        </div>

        <!-- connector -->
        <div class="connector"></div>
        <div class="connector-label mono">A2A 任务委派 · 并行扇出 (asyncio)</div>

        <!-- Workers grid -->
        <div class="workers-grid">
          <div v-for="w in workers" :key="w.title" class="worker-card">
            <div class="worker-head">
              <span class="worker-dot"></span>
              <span class="worker-title">{{ w.title }}</span>
            </div>
            <div class="worker-body">{{ w.body }}</div>
            <div class="worker-tools mono">{{ w.tools }}</div>
          </div>
        </div>

        <!-- connector -->
        <div class="connector"></div>
        <div class="connector-label" style="color:#64748B;font-weight:600">只回摘要，原文写入虚拟文件系统（外部记忆）</div>

        <!-- CitationAgent -->
        <div class="flow-cite">
          <div class="cite-name">CitationAgent · 防幻觉验证</div>
          <div class="cite-sub">逐条核对论断 ↔ 来源，无支撑即删除</div>
        </div>

        <!-- connector -->
        <div class="connector" style="background:linear-gradient(#14532D,#334155)"></div>

        <!-- Report output -->
        <div class="flow-report">📄 带引用的研究报告</div>
      </div>

      <!-- Iron rule callout -->
      <div class="iron-rule">
        <div class="iron-icon">⛓️</div>
        <div>
          <div class="iron-title">一条铁律：编排层硬禁递归派生</div>
          <div class="iron-body">子 Agent 不能再派生子 Agent —— 在代码层强制，而非 prompt 里「请求」模型，从根上杜绝 token 爆炸。这是「懂成本的工程师」的关键信号。</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
const workers = [
  { title:'Worker 1', body:'隔离上下文 · 研究一个独立子课题，不知道其他 Agent 存在', tools:'MCP: web_search → web_fetch' },
  { title:'Worker 2', body:'并行执行 · 大块原文写虚拟文件系统，只回摘要给 Lead',   tools:'MCP: web_fetch → retrieve' },
  { title:'Worker 3', body:'Function Calling · 失败重试 / 降级 / 熔断兜底',          tools:'MCP: retrieve (Chroma)' },
]
</script>

<style scoped>
.arch-section {
  padding: 80px 40px;
  background: #0B1220;
}
.arch-inner {
  max-width: 1160px; margin: 0 auto;
}
.arch-hd {
  text-align: center; max-width: 720px; margin: 0 auto 50px;
}

/* ── Flow ── */
.flow {
  display: flex; flex-direction: column; align-items: center; gap: 0;
}

/* Lead */
.flow-lead {
  background: linear-gradient(135deg, #2563EB, #1D4ED8);
  border-radius: 15px; padding: 18px 34px; text-align: center;
  box-shadow: rgba(37,99,235,.8) 0 18px 40px -16px;
  min-width: 300px;
}
.lead-name { font-weight: 800; font-size: 19px; color: #fff; }
.lead-sub  { font-size: 13.5px; color: #BFDBFE; margin-top: 2px; }

/* Connector */
.connector {
  width: 2px; height: 32px;
  background: linear-gradient(#3B82F6, #1E3A8A);
}
.connector-label {
  font-size: 12.5px; color: #60A5FA; font-weight: 700;
  margin-bottom: 18px; text-align: center;
}

/* Workers */
.workers-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 18px; width: 100%; max-width: 880px;
}
.worker-card {
  background: #131C2E; border: 1px solid #243246;
  border-radius: 14px; padding: 18px;
}
.worker-head {
  display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
}
.worker-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #0EA5E9; flex-shrink: 0;
  animation: ds-blink 1.4s ease infinite;
}
.worker-title { font-weight: 700; font-size: 15.5px; color: #E2E8F0; }
.worker-body  { font-size: 13px; color: #94A3B8; line-height: 1.55; }
.worker-tools {
  font-size: 11px; color: #60A5FA; margin-top: 10px;
  background: #0F1827; border: 1px solid #243246;
  border-radius: 7px; padding: 6px 9px;
}

/* CitationAgent */
.flow-cite {
  background: #0E2A1E; border: 1px solid #14532D;
  border-radius: 14px; padding: 16px 30px; text-align: center; min-width: 300px;
}
.cite-name { font-weight: 800; font-size: 17px; color: #34D399; }
.cite-sub  { font-size: 13px; color: #6EE7B7; margin-top: 2px; }

/* Report output */
.flow-report {
  background: #fff; border-radius: 13px; padding: 14px 32px;
  font-weight: 800; font-size: 16px; color: #0F172A;
}

/* Iron rule */
.iron-rule {
  margin-top: 46px; background: #131C2E; border: 1px solid #243246;
  border-radius: 14px; padding: 22px 26px;
  display: flex; gap: 26px; align-items: center;
}
.iron-icon  { font-size: 30px; flex-shrink: 0; }
.iron-title { font-weight: 700; font-size: 16.5px; color: #F1F5F9; }
.iron-body  { font-size: 14px; color: #94A3B8; margin-top: 4px; line-height: 1.6; }

@media (max-width: 700px) {
  .arch-section { padding: 56px 20px; }
  .workers-grid { grid-template-columns: 1fr; }
  .iron-rule { flex-direction: column; }
}
</style>
