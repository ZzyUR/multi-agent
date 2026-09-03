<template>
  <nav class="navbar">
    <a class="nav-brand ds-link" href="#">
      <div class="nav-icon">
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="5" r="2.6" fill="#fff"/>
          <circle cx="5" cy="18" r="2.6" fill="#fff"/>
          <circle cx="19" cy="18" r="2.6" fill="#fff"/>
          <path d="M12 7.6V13M12 13L6.5 16.2M12 13l5.5 3.2"
                stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>
        </svg>
      </div>
      <span class="nav-name">DeepResearch</span>
      <span class="nav-badge">Agent</span>
    </a>

    <div class="nav-links">
      <a class="ds-link" href="#hot">核心能力</a>
      <a class="ds-link" href="#flow">工作流程</a>
      <a class="ds-link" href="#arch">系统架构</a>
      <a class="ds-link" href="#stack">技术栈</a>
    </div>

    <button class="nav-cta ds-btn" @click="$emit('scrollToWorkbench')">
      进入研究工作台 →
    </button>
  </nav>
</template>

<script setup>
defineEmits(['scrollToWorkbench'])
</script>

<style scoped>
.navbar {
  position: sticky; top: 0; z-index: 50;
  height: 68px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 40px;
  background: rgba(246, 248, 252, 0.82);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--c-nav-border);
}

.nav-brand {
  display: flex; align-items: center; gap: 11px;
  text-decoration: none; color: var(--c-text);
}
.nav-icon {
  width: 34px; height: 34px; border-radius: 9px;
  background: linear-gradient(135deg, var(--c-blue), var(--c-blue-sky));
  display: flex; align-items: center; justify-content: center;
  box-shadow: rgba(37, 99, 235, 0.6) 0 6px 16px -6px;
  flex-shrink: 0;
}
.nav-name {
  font-weight: 800; font-size: 19px; letter-spacing: -0.02em;
}
.nav-badge {
  font-size: 12px; font-weight: 600; color: var(--c-blue);
  background: var(--c-blue-light); padding: 3px 9px;
  border-radius: 99px; margin-left: 2px;
}

.nav-links {
  display: flex; align-items: center; gap: 34px;
}
.nav-links a {
  font-size: 15px; font-weight: 600; color: var(--c-text-2);
}

.nav-cta {
  border: none; background: var(--c-blue); color: #fff;
  font-weight: 700; font-size: 14.5px;
  padding: 10px 20px; border-radius: 10px;
  box-shadow: rgba(37, 99, 235, 0.55) 0 8px 22px -8px;
}

@media (max-width: 900px) {
  .navbar { padding: 0 20px; }
  .nav-links { display: none; }
}
</style>
