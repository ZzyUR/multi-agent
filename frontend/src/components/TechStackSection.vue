<template>
  <section id="stack" class="stack-section">
    <div class="stack-inner">
      <div class="stack-hd">
        <div class="section-tag">技术栈</div>
        <h2 class="section-h2">完整技术实现</h2>
      </div>
      <div class="stack-grid">
        <div v-for="item in stack" :key="item.label" class="stack-item">
          <div class="stack-label">{{ item.label }}</div>
          <div class="stack-value mono">{{ item.value }}</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
const stack = [
  { label:'前端',  value:'Vue 3 + Vite + Pinia + Element Plus + SSE 流式' },
  { label:'后端',  value:'Python 3.11 + FastAPI + SQLAlchemy' },
  { label:'存储',  value:'MySQL(业务) + Redis(队列/流式/检查点)' },
  { label:'向量库', value:'Chroma (RAG 检索)' },
  { label:'编排',  value:'自研 Harness + LangGraph 对照实现(可切换)' },
  { label:'模型',  value:'OpenAI 兼容 (GPT / DeepSeek / 通义 / vLLM)' },
]
</script>

<style scoped>
.stack-section {
  padding: 74px 40px;
  background: var(--c-bg);
  border-top: 1px solid var(--c-divider);
}
.stack-inner { max-width: 1100px; margin: 0 auto; }
.stack-hd { text-align: center; margin-bottom: 42px; }

.stack-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
}
.stack-item {
  background: #fff;
  border: 1px solid var(--c-card-border);
  border-radius: 14px;
  padding: 20px 22px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.stack-label {
  font-size: 13px; font-weight: 800; color: var(--c-blue);
  background: var(--c-blue-light); border-radius: 8px;
  padding: 8px 12px; white-space: nowrap;
  min-width: 78px; text-align: center; flex-shrink: 0;
}
.stack-value {
  font-size: 15px; color: rgb(51, 65, 85); font-weight: 600;
}

@media (max-width: 700px) {
  .stack-section { padding: 56px 20px; }
  .stack-grid { grid-template-columns: 1fr; }
}
</style>
