<template>
  <section class="compare-section">
    <div class="compare-inner">
      <div class="compare-hd">
        <div class="section-tag">研究质量</div>
        <h2 class="section-h2">结论可信，每句话都能溯源</h2>
      </div>

      <div class="compare-grid">
        <div class="compare-col col-bad">
          <div class="col-type" style="color:#B45454">普通 AI 问答</div>
          <div class="col-title" style="color:#7F3838">一次调用，自己写，容易出错</div>
          <div class="col-items">
            <div class="col-item" style="color:#7C5454"><span>✕</span>无自主规划，一锤子买卖</div>
            <div class="col-item" style="color:#7C5454"><span>✕</span>不会并行协作</div>
            <div class="col-item" style="color:#7C5454"><span>✕</span>容易一本正经胡编（幻觉）</div>
            <div class="col-item" style="color:#7C5454"><span>✕</span>无记忆、无工具调用兜底</div>
          </div>
        </div>
        <div class="compare-col col-good">
          <div class="col-type" style="color:#15803D">本项目</div>
          <div class="col-title" style="color:#14532D">自主规划 · 并行协作 · 交叉验证</div>
          <div class="col-items">
            <div class="col-item" style="color:#326647"><span>✓</span>ReAct 自主拆解任务树</div>
            <div class="col-item" style="color:#326647"><span>✓</span>A2A 并行子 Agent 协作</div>
            <div class="col-item" style="color:#326647"><span>✓</span>CitationAgent 独立验证防幻觉</div>
            <div class="col-item" style="color:#326647"><span>✓</span>五层上下文压缩 + 长程记忆</div>
          </div>
        </div>
      </div>

      <div class="dark-callout">
        <div class="callout-headline">
          每条结论都有来源支撑<br>
          <span class="callout-grad">不是猜测，不是捏造</span>
        </div>
        <p class="callout-body">独立的 CitationAgent 在报告生成后逐条核对论断与来源——有支撑的标注引用编号，没有支撑的直接删除。你看到的每一句话，都经过独立验证。</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.compare-section {
  padding: 78px 40px;
  background: #fff;
}
.compare-inner { max-width: 1100px; margin: 0 auto; }
.compare-hd { text-align: center; max-width: 680px; margin: 0 auto 46px; }

.compare-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 22px;
  margin-bottom: 24px;
}
.compare-col { border-radius: 16px; padding: 26px; border: 1px solid; }
.col-bad  { border-color: #EAD9D9; background: #FCF6F6; }
.col-good { border-color: #BFD8C4; background: #F3FBF5; }

.col-type  { font-size: 13px; font-weight: 700; letter-spacing: 0.06em; }
.col-title { font-weight: 800; font-size: 22px; margin: 6px 0 16px; }
.col-items { display: flex; flex-direction: column; gap: 11px; }
.col-item  { display: flex; gap: 9px; font-size: 15px; }

.dark-callout {
  background: #0B1220; border-radius: 16px; padding: 34px; text-align: center;
}
.callout-headline {
  font-size: 28px; font-weight: 800; color: #fff;
  letter-spacing: -0.02em; line-height: 1.3;
}
.callout-grad {
  background: linear-gradient(120deg, #60A5FA, #22D3EE);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.callout-body {
  font-size: 15.5px; color: #94A3B8; margin: 14px auto 0;
  max-width: 640px; line-height: 1.7;
}

@media (max-width: 700px) {
  .compare-section { padding: 56px 20px; }
  .compare-grid { grid-template-columns: 1fr; }
}
</style>
