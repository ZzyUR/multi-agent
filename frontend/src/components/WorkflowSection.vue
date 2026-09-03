<template>
  <section id="flow" class="workflow-section">
    <div class="section-inner">
      <div class="section-hd">
        <div class="section-tag">WORKFLOW</div>
        <h2 class="section-h2">5 步研究流程，全自动推进</h2>
        <p class="section-sub">从问题输入到报告产出，每一步都由 Agent 自主决策执行。</p>
      </div>
      <div class="flow-steps">
        <div v-for="(step, i) in steps" :key="i" class="flow-step">
          <div class="step-connector" v-if="i < steps.length - 1"></div>
          <div class="step-num">{{ String(i + 1).padStart(2, '0') }}</div>
          <div class="step-icon" :style="{ background: step.iconBg }">
            <span v-html="step.icon"></span>
          </div>
          <div class="step-name">{{ step.name }}</div>
          <p class="step-desc">{{ step.desc }}</p>
          <div class="step-tags">
            <span v-for="t in step.tags" :key="t" class="step-tag mono">{{ t }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
const steps = [
  {
    name: '问题分析 & 规划',
    desc: 'Lead Agent 理解用户问题，生成研究计划，拆分为多个子课题，确定工具调用顺序和 Worker 数量。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M9 12h6M9 16h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
    iconBg: 'linear-gradient(135deg,#EEF3FF,#DBE9FE)',
    tags: ['Plan', 'Lead Agent'],
  },
  {
    name: '并行任务派发',
    desc: '将子课题批量派发给多个 Worker，每个 Worker 独立执行 ReAct 推理循环，N 路并行大幅缩短等待时间。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="6" cy="12" r="2" fill="currentColor"/><circle cx="18" cy="6" r="2" fill="currentColor"/><circle cx="18" cy="18" r="2" fill="currentColor"/><path d="M8 12h4M12 12l4-4M12 12l4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
    iconBg: 'linear-gradient(135deg,#E0F2FE,#BAE6FD)',
    tags: ['Dispatch', 'N Workers'],
  },
  {
    name: '工具调用 & 检索',
    desc: 'Worker 通过 MCP 调用 web_search 获取实时资讯、web_fetch 抓取全文、retrieve 从向量库检索历史知识。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/><path d="M16.5 16.5L21 21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
    iconBg: 'linear-gradient(135deg,#F0FDF4,#BBF7D0)',
    tags: ['MCP Tools', 'RAG'],
  },
  {
    name: '引用核对 & 综合',
    desc: 'CitationAgent 对每个事实逐一核对来源，清除幻觉，Lead Agent 再聚合所有 Worker 结果，起草研究报告。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" stroke-width="2"/></svg>`,
    iconBg: 'linear-gradient(135deg,#FFF7ED,#FED7AA)',
    tags: ['CitationAgent', 'Merge'],
  },
  {
    name: '报告输出 & 存档',
    desc: '完整研究报告 Markdown 实时流式输出，带引用标注。全程 Trace、Token 统计、引用支持率一并存档可查。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="currentColor" stroke-width="2"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
    iconBg: 'linear-gradient(135deg,#F5F3FF,#DDD6FE)',
    tags: ['Report', 'Archive'],
  },
]
</script>

<style scoped>
.workflow-section {
  background: var(--c-bg);
  padding: 80px 40px;
  border-top: 1px solid var(--c-divider);
}
.section-inner { max-width: 1200px; margin: 0 auto; }
.section-hd { text-align: center; margin-bottom: 50px; }

.flow-steps {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0;
  position: relative;
}
.flow-step {
  position: relative;
  padding: 0 16px;
  text-align: center;
}
.step-connector {
  position: absolute;
  top: 44px; right: -8px;
  width: 16px; height: 2px;
  background: var(--c-blue-border);
  z-index: 1;
}
.step-num {
  font-size: 11px; font-weight: 800; color: var(--c-text-4);
  font-family: 'SF Mono', 'JetBrains Mono', monospace;
  margin-bottom: 10px;
}
.step-icon {
  width: 52px; height: 52px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 14px; color: rgb(37, 99, 235);
  border: 1.5px solid var(--c-blue-border);
}
.step-name { font-weight: 800; font-size: 15px; margin-bottom: 10px; }
.step-desc { font-size: 13px; line-height: 1.6; color: var(--c-text-2); margin-bottom: 12px; }
.step-tags { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
.step-tag {
  font-size: 11px; color: var(--c-blue);
  background: var(--c-blue-light); padding: 2px 8px;
  border-radius: 99px; font-weight: 600;
}

@media (max-width: 900px) {
  .workflow-section { padding: 56px 20px; }
  .flow-steps { grid-template-columns: 1fr 1fr; gap: 24px; }
  .step-connector { display: none; }
}
@media (max-width: 500px) {
  .flow-steps { grid-template-columns: 1fr; }
}
</style>
