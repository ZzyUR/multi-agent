<template>
  <div class="diagram-card">
    <div class="diagram-head">
      <span class="diagram-label">ORCHESTRATOR · WORKER</span>
      <span class="mono diagram-meta">live graph</span>
    </div>
    <div class="diagram-body">
      <!-- Animated SVG connections -->
      <svg width="100%" height="100%" viewBox="0 0 380 300" class="diagram-svg">
        <g stroke="#93B4F5" stroke-width="2" fill="none"
           stroke-dasharray="6 6" class="flow-paths">
          <path d="M190 66 C 120 96, 86 110, 70 150"/>
          <path d="M190 66 C 190 110, 190 110, 190 150"/>
          <path d="M190 66 C 260 96, 294 110, 310 150"/>
          <path d="M70 196 C 120 240, 160 250, 190 256"/>
          <path d="M190 196 L 190 250"/>
          <path d="M310 196 C 260 240, 220 250, 190 256"/>
        </g>
      </svg>

      <!-- Lead Agent -->
      <div class="node-lead">
        <div class="node-lead-inner">
          <span class="node-ring"></span>
          <div class="node-lead-name">Lead Agent</div>
          <div class="node-lead-sub">ReAct 编排循环</div>
        </div>
      </div>

      <!-- Workers -->
      <div class="node-worker node-w1">
        <div class="node-worker-inner">
          <div class="node-worker-name">Worker 1</div>
          <div class="node-worker-tool mono">web_search</div>
        </div>
      </div>
      <div class="node-worker node-w2">
        <div class="node-worker-inner">
          <div class="node-worker-name">Worker 2</div>
          <div class="node-worker-tool mono">web_fetch</div>
        </div>
      </div>
      <div class="node-worker node-w3">
        <div class="node-worker-inner">
          <div class="node-worker-name">Worker 3</div>
          <div class="node-worker-tool mono">retrieve</div>
        </div>
      </div>

      <!-- CitationAgent -->
      <div class="node-cite">
        <div class="node-cite-inner">
          <div class="node-cite-name">CitationAgent</div>
          <div class="node-cite-sub">逐条核对 · 防幻觉</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diagram-card {
  position: relative; background: #fff;
  border: 1px solid var(--c-nav-border); border-radius: 22px; padding: 30px;
  box-shadow: rgba(15, 23, 42, 0.28) 0 30px 70px -30px;
}
.diagram-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 18px;
}
.diagram-label { font-size: 13px; font-weight: 700; color: var(--c-text-2); letter-spacing: 0.04em; }
.diagram-meta  { font-size: 11.5px; color: var(--c-text-4); }

.diagram-body  { position: relative; height: 300px; }
.diagram-svg   { position: absolute; inset: 0; }

.flow-paths { animation: ds-flow 1s linear infinite; }

/* Lead Agent */
.node-lead {
  position: absolute; left: 50%; top: 18px;
  transform: translateX(-50%); width: 150px; text-align: center;
}
.node-lead-inner {
  position: relative;
  background: linear-gradient(135deg, var(--c-blue), var(--c-blue-d));
  color: #fff; border-radius: 13px; padding: 12px 10px;
  box-shadow: rgba(37, 99, 235, 0.7) 0 12px 24px -10px;
}
.node-ring {
  position: absolute; inset: 0; border-radius: 13px;
  border: 2px solid var(--c-blue);
  animation: ds-ring 2s ease infinite;
}
.node-lead-name { font-weight: 800; font-size: 14.5px; }
.node-lead-sub  { font-size: 11px; opacity: 0.85; margin-top: 1px; }

/* Workers */
.node-worker { position: absolute; width: 118px; text-align: center; }
.node-worker-inner {
  background: #fff; border: 1.5px solid var(--c-blue-border);
  border-radius: 11px; padding: 9px 6px;
  box-shadow: rgba(37, 99, 235, 0.5) 0 8px 18px -12px;
}
.node-worker-name { font-weight: 700; font-size: 12.5px; color: rgb(30, 58, 138); }
.node-worker-tool { font-size: 9.5px; color: var(--c-blue); }
.node-w1 { left: 6px;  top: 150px; animation: ds-float 3s ease-in-out infinite; }
.node-w2 {
  left: 50%; top: 150px; transform: translateX(-50%);
  animation: ds-float 3s ease-in-out 0.5s infinite;
}
.node-w3 { right: 6px; top: 150px; animation: ds-float 3s ease-in-out 1s infinite; }

/* CitationAgent */
.node-cite {
  position: absolute; left: 50%; bottom: 0;
  transform: translateX(-50%); width: 174px; text-align: center;
}
.node-cite-inner {
  background: rgb(240, 253, 244); border: 1.5px solid rgb(134, 239, 172);
  border-radius: 11px; padding: 9px 10px;
  box-shadow: rgba(16, 185, 129, 0.3) 0 8px 18px -12px;
}
.node-cite-name { font-weight: 700; font-size: 12.5px; color: rgb(6, 95, 70); }
.node-cite-sub  { font-size: 9.5px; color: rgb(16, 185, 129); }
</style>
