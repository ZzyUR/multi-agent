<template>
  <div>
    <!-- ── LANDING ── -->
    <template v-if="ws.view === 'landing'">
      <NavBar @scroll-to-workbench="ws.goApp()" />
      <main>
        <HeroSection @scroll-to-workbench="ws.goApp()" />
        <FeaturesSection />
        <WorkflowSection />
        <ArchSection />
        <CompareSection />
        <TechStackSection />
        <CTASection @scroll-to-workbench="ws.goApp()" />
      </main>
      <footer class="site-footer">
        <div class="footer-inner">
          <div class="footer-brand">DeepResearch Agent</div>
          <div class="footer-text">Multi-Agent 深度研究 · 引用溯源 · 防幻觉</div>
        </div>
      </footer>
    </template>

    <!-- ── APP WORKSPACE ── -->
    <AppWorkspace v-else />
  </div>
</template>

<script setup>
import { useWorkspaceStore } from './stores/workspace.js'
import NavBar from './components/NavBar.vue'
import HeroSection from './components/HeroSection.vue'
import FeaturesSection from './components/FeaturesSection.vue'
import WorkflowSection from './components/WorkflowSection.vue'
import ArchSection from './components/ArchSection.vue'
import CompareSection from './components/CompareSection.vue'
import TechStackSection from './components/TechStackSection.vue'
import CTASection from './components/CTASection.vue'
import AppWorkspace from './components/AppWorkspace.vue'

const ws = useWorkspaceStore()
</script>

<style>
.site-footer {
  background: var(--c-dark);
  border-top: 1px solid var(--c-dark-border);
  padding: 36px 40px;
}
.footer-inner {
  max-width: 1200px; margin: 0 auto;
  display: flex; flex-direction: column; align-items: center; gap: 8px;
}
.footer-brand { font-weight: 800; font-size: 17px; color: #fff; }
.footer-text  { font-size: 13px; color: rgb(100, 116, 139); }
</style>
