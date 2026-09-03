<template>
  <section id="hot" class="features-section">
    <div class="section-inner">
      <div class="section-hd">
        <div class="section-tag">CORE CAPABILITIES</div>
        <h2 class="section-h2">9 大研究能力，深度覆盖研究场景</h2>
        <p class="section-sub">每一项都是真正用于生产的 Agentic 系统能力，不是 demo。</p>
      </div>
      <div class="features-grid">
        <div
          v-for="f in features" :key="f.title"
          class="feature-card ds-hover-lift"
        >
          <div class="feature-icon" :style="{ background: f.iconBg }">
            <span v-html="f.icon"></span>
          </div>
          <div class="feature-title">{{ f.title }}</div>
          <p class="feature-desc">{{ f.desc }}</p>
          <div class="feature-tags">
            <span v-for="t in f.tags" :key="t" class="feature-tag mono">{{ t }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
const features = [
  {
    title: 'Multi-Agent 编排',
    desc: 'Lead Agent 拆解问题，动态派发 N 路 Worker，各自并行检索与推理，结果汇聚综合，真正模拟研究团队协作模式。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="5" r="2.5" fill="currentColor"/><circle cx="5" cy="18" r="2.5" fill="currentColor"/><circle cx="19" cy="18" r="2.5" fill="currentColor"/><path d="M12 7.5V13M12 13L6.5 16.2M12 13l5.5 3.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`,
    iconBg: 'linear-gradient(135deg,#EEF3FF,#DBE9FE)',
    tags: ['ReAct Loop', 'Parallel Dispatch'],
  },
  {
    title: 'MCP 工具调用',
    desc: 'Worker 通过标准 Model Context Protocol 调用 web_search、web_fetch、retrieve 等工具，协议统一，工具可插拔。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="11" width="18" height="2" rx="1" fill="currentColor"/><rect x="8" y="6" width="2" height="12" rx="1" fill="currentColor"/><rect x="14" y="6" width="2" height="12" rx="1" fill="currentColor"/></svg>`,
    iconBg: 'linear-gradient(135deg,#E0F2FE,#BAE6FD)',
    tags: ['MCP Protocol', 'Pluggable Tools'],
  },
  {
    title: 'RAG 检索增强',
    desc: '双路检索（向量 + BM25），Chroma 向量库持久化，Self-Query 过滤，保证检索结果准确、有上下文。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/><path d="M16.5 16.5L21 21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
    iconBg: 'linear-gradient(135deg,#F0FDF4,#BBF7D0)',
    tags: ['Chroma', 'BM25 Hybrid'],
  },
  {
    title: '引用溯源防幻觉',
    desc: 'CitationAgent 逐条比对报告中每个事实与原始检索结果，自动标注引用，幻觉率大幅降低。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" stroke-width="2"/></svg>`,
    iconBg: 'linear-gradient(135deg,#FFF7ED,#FED7AA)',
    tags: ['CitationAgent', 'Cross-Check'],
  },
  {
    title: '断点续跑',
    desc: '研究过程全程 Checkpoint，网络波动或意外中断后可从上次进度恢复，不浪费已完成的子任务结果。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M3 12a9 9 0 1018 0 9 9 0 00-18 0z" stroke="currentColor" stroke-width="2"/><path d="M12 8v4l3 3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
    iconBg: 'linear-gradient(135deg,#F5F3FF,#DDD6FE)',
    tags: ['Checkpoint', 'Resume'],
  },
  {
    title: '多模型 / 分级调用',
    desc: '按任务复杂度自动选择 DeepSeek-R1 / GPT-4o / Gemini，推理任务走大模型，摘要走小模型，兼顾质量与成本。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="7" rx="2" fill="currentColor" opacity=".4"/><rect x="14" y="3" width="7" height="7" rx="2" fill="currentColor"/><rect x="3" y="14" width="7" height="7" rx="2" fill="currentColor"/><rect x="14" y="14" width="7" height="7" rx="2" fill="currentColor" opacity=".4"/></svg>`,
    iconBg: 'linear-gradient(135deg,#FFF1F2,#FFD1DC)',
    tags: ['Multi-LLM', 'Cost Control'],
  },
  {
    title: 'SSE 实时流式输出',
    desc: '研究过程 Trace 事件和最终报告通过 SSE 实时推送前端，用户全程可见每个子任务的进展，无需刷新。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="currentColor" opacity=".3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
    iconBg: 'linear-gradient(135deg,#ECFDF5,#A7F3D0)',
    tags: ['SSE Stream', 'Real-time'],
  },
  {
    title: '虚拟文件系统',
    desc: 'Agent 可在沙盒虚拟文件系统中读写中间结果、缓存页面内容，隔离副作用，支持多轮迭代修改。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" stroke="currentColor" stroke-width="2"/></svg>`,
    iconBg: 'linear-gradient(135deg,#E0E7FF,#C7D2FE)',
    tags: ['VirtualFS', 'Isolation'],
  },
  {
    title: '研究档案管理',
    desc: '每次研究自动保存完整 Trace、报告、统计。支持历史查看、对比分析，数据完整可追溯。',
    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="4" y="4" width="16" height="16" rx="2" stroke="currentColor" stroke-width="2"/><path d="M8 10h8M8 14h5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
    iconBg: 'linear-gradient(135deg,#FDF4FF,#E9D5FF)',
    tags: ['Archive', 'Trace History'],
  },
]
</script>

<style scoped>
.features-section {
  background: #fff;
  padding: 80px 40px;
  border-top: 1px solid var(--c-divider);
}
.section-inner { max-width: 1200px; margin: 0 auto; }
.section-hd { text-align: center; margin-bottom: 50px; }

.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 22px;
}
.feature-card {
  background: var(--c-card-bg);
  border: 1px solid var(--c-card-border);
  border-radius: 16px;
  padding: 26px;
}
.feature-icon {
  width: 44px; height: 44px; border-radius: 11px;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 14px; color: rgb(37, 99, 235);
}
.feature-title {
  font-weight: 800; font-size: 16.5px; margin-bottom: 9px;
}
.feature-desc {
  font-size: 14px; line-height: 1.65; color: var(--c-text-2);
  margin-bottom: 14px;
}
.feature-tags { display: flex; flex-wrap: wrap; gap: 7px; }
.feature-tag {
  font-size: 11.5px; color: var(--c-blue);
  background: var(--c-blue-light); padding: 3px 9px;
  border-radius: 99px; font-weight: 600;
}

@media (max-width: 900px) {
  .features-section { padding: 56px 20px; }
  .features-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 600px) {
  .features-grid { grid-template-columns: 1fr; }
}
</style>
