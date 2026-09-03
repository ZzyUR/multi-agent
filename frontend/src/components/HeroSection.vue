<template>
  <section class="hero">
    <div class="blob blob-1"></div>
    <div class="blob blob-2"></div>
    <div class="hero-inner">
      <!-- Left: copy -->
      <div class="ds-anim-up">
        <div class="hero-badge">
          <span class="badge-dot"></span>
          Multi-Agent 深度研究 · 引用溯源防幻觉
        </div>
        <h1 class="hero-h1">
          像研究分析师团队一样工作的<br>
          <span class="grad">Multi-Agent 深度研究智能体</span>
        </h1>
        <p class="hero-desc">
          输入一个研究问题，Agent 自主拆解任务、并行派发子 Agent、通过 MCP 调用工具、RAG 检索增强、交叉验证防幻觉——最终产出一份<strong>带引用溯源的研究报告</strong>。
        </p>
        <p class="hero-tagline">不是套壳调 API 的 Workflow，而是真正的 Agentic 系统。</p>
        <div class="hero-actions">
          <button class="btn-primary ds-btn" @click="$emit('scrollToWorkbench')">
            ▶ 体验深度研究
          </button>
          <a class="btn-outline ds-btn" href="#arch">查看系统架构</a>
        </div>
        <div class="hero-stats">
          <div class="hero-stat">
            <div class="stat-num">9 大</div>
            <div class="stat-lab">核心研究能力</div>
          </div>
          <div class="stat-divider"></div>
          <div class="hero-stat">
            <div class="stat-num">N 路</div>
            <div class="stat-lab">子 Agent 并行检索</div>
          </div>
          <div class="stat-divider"></div>
          <div class="hero-stat">
            <div class="stat-num">逐句</div>
            <div class="stat-lab">引用可溯源防幻觉</div>
          </div>
        </div>
      </div>

      <!-- Right: animated diagram -->
      <ArchDiagram />
    </div>
  </section>
</template>

<script setup>
import ArchDiagram from './ArchDiagram.vue'
defineEmits(['scrollToWorkbench'])
</script>

<style scoped>
.hero {
  position: relative; overflow: hidden;
  padding: 84px 40px 72px;
}
.blob {
  position: absolute; border-radius: 50%; pointer-events: none;
}
.blob-1 {
  top: -180px; right: -140px; width: 560px; height: 560px;
  background: radial-gradient(circle, rgba(37,99,235,.13), transparent 65%);
}
.blob-2 {
  top: 60px; left: -120px; width: 420px; height: 420px;
  background: radial-gradient(circle, rgba(14,165,233,.10), transparent 65%);
}
.hero-inner {
  max-width: 1200px; margin: 0 auto; position: relative;
  display: grid; grid-template-columns: 1.05fr 0.95fr;
  gap: 56px; align-items: center;
}

.hero-badge {
  display: inline-flex; align-items: center; gap: 9px;
  background: #fff; border: 1px solid rgb(224,232,244);
  padding: 7px 14px; border-radius: 99px;
  font-size: 13.5px; font-weight: 600; color: var(--c-blue);
  box-shadow: rgba(37,99,235,.4) 0 4px 14px -8px;
}
.badge-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--c-green); flex-shrink: 0;
  animation: ds-blink 1.6s ease infinite;
}

.hero-h1 {
  font-size: 54px; line-height: 1.08;
  letter-spacing: -0.03em; margin: 22px 0 0;
  font-weight: 800;
}
.grad {
  background: linear-gradient(120deg, var(--c-blue), var(--c-blue-sky));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}

.hero-desc {
  font-size: 19px; line-height: 1.6; color: var(--c-text-2);
  margin: 22px 0 0; max-width: 540px;
}
.hero-desc strong { color: var(--c-text); }

.hero-tagline {
  font-size: 16px; color: var(--c-text-3);
  margin: 14px 0 0; font-weight: 600;
}

.hero-actions {
  display: flex; gap: 14px; margin-top: 32px; flex-wrap: wrap;
}
.btn-primary {
  border: none; background: var(--c-blue); color: #fff;
  font-weight: 700; font-size: 16px; padding: 15px 28px;
  border-radius: 12px;
  box-shadow: rgba(37,99,235,.7) 0 14px 30px -12px;
}
.btn-outline {
  border: 1px solid rgb(212,222,237); background: #fff; color: rgb(30,41,59);
  font-weight: 700; font-size: 16px; padding: 15px 28px;
  border-radius: 12px; display: inline-flex; align-items: center;
}

.hero-stats {
  display: flex; gap: 30px; margin-top: 38px; align-items: center;
}
.hero-stat {}
.stat-num { font-size: 28px; font-weight: 800; color: var(--c-text); }
.stat-lab { font-size: 13.5px; color: var(--c-text-3); font-weight: 600; }
.stat-divider { width: 1px; height: 36px; background: var(--c-divider-2); }

@media (max-width: 900px) {
  .hero { padding: 56px 20px 48px; }
  .hero-inner { grid-template-columns: 1fr; }
  .hero-h1 { font-size: 38px; }
  .hero-desc { font-size: 16px; }
  /* Hide diagram card on mobile */
  .hero-inner > :last-child { display: none; }
}
</style>
