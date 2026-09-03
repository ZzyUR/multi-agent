<template>
  <section class="cta-section">
    <div class="section-inner">
      <div class="cta-tag">GET STARTED</div>
      <h2 class="cta-h2">准备好开始你的第一次深度研究了吗？</h2>
      <p class="cta-sub">
        输入任意研究问题——市场调研、技术分析、竞品对比——Agent 团队立刻上阵。
      </p>
      <div class="cta-btns">
        <button class="cta-btn-primary ds-btn" @click="$emit('scrollToWorkbench')">
          ▶ 立即体验
        </button>
        <a class="cta-btn-outline ds-btn" href="#arch">了解系统架构</a>
      </div>
    </div>
  </section>
</template>

<script setup>
defineEmits(['scrollToWorkbench'])
</script>

<style scoped>
.cta-section {
  background: linear-gradient(135deg, rgb(29,55,160), rgb(37,99,235), rgb(14,165,233));
  padding: 80px 40px;
  text-align: center;
}
.section-inner { max-width: 700px; margin: 0 auto; }
.cta-tag {
  font-size: 13px; font-weight: 700; color: rgba(255,255,255,.7);
  letter-spacing: 0.1em; margin-bottom: 18px;
}
.cta-h2 {
  font-size: 40px; font-weight: 800; color: #fff;
  line-height: 1.1; letter-spacing: -0.02em; margin-bottom: 16px;
}
.cta-sub {
  font-size: 17px; color: rgba(255,255,255,.8); line-height: 1.6; margin-bottom: 36px;
}
.cta-btns {
  display: flex; gap: 14px; justify-content: center; flex-wrap: wrap;
}
.cta-btn-primary {
  border: none; background: #fff; color: var(--c-blue);
  font-weight: 700; font-size: 16px; padding: 14px 28px;
  border-radius: 12px;
  box-shadow: rgba(0,0,0,.2) 0 12px 30px -10px;
}
.cta-btn-outline {
  border: 2px solid rgba(255,255,255,.45); background: rgba(255,255,255,.1);
  color: #fff; font-weight: 700; font-size: 16px;
  padding: 14px 28px; border-radius: 12px;
  display: inline-flex; align-items: center;
  backdrop-filter: blur(8px);
}
</style>
