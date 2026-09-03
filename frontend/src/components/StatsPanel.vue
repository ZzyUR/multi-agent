<template>
  <div class="stats-panel" v-if="stats">
    <div class="stats-title">📊 执行统计</div>
    <div class="stats-grid">
      <div class="stat-cell">
        <div class="stat-val mono">{{ stats.tokens?.toLocaleString() || '—' }}</div>
        <div class="stat-key">Tokens 消耗</div>
      </div>
      <div class="stat-cell">
        <div class="stat-val mono">{{ durationFmt }}</div>
        <div class="stat-key">总耗时</div>
      </div>
      <div class="stat-cell">
        <div class="stat-val mono" :style="{ color: costColor }">
          ${{ (stats.estimated_cost_usd || 0).toFixed(4) }}
        </div>
        <div class="stat-key">估算成本</div>
      </div>
      <div class="stat-cell">
        <div class="stat-val mono" :style="{ color: cacheColor }">
          {{ ((stats.cache_hit_rate || 0) * 100).toFixed(0) }}%
        </div>
        <div class="stat-key">缓存命中率</div>
      </div>
      <div class="stat-cell">
        <div class="stat-val mono" :style="{ color: citeColor }">
          {{ citeRateFmt }}
        </div>
        <div class="stat-key">引用支撑率</div>
      </div>
      <div class="stat-cell">
        <div class="stat-val mono">{{ stats.profile || '—' }}</div>
        <div class="stat-key">研究档位</div>
      </div>
    </div>

    <div v-if="hasToolStats" class="tool-section">
      <div class="tool-title">工具调用成功率</div>
      <div class="tool-rows">
        <div v-for="(ts, name) in stats.tool_stats" :key="name" class="tool-row">
          <span class="tool-name mono">{{ name }}</span>
          <div class="tool-bar-wrap">
            <div class="tool-bar-bg">
              <div class="tool-bar-fill"
                :style="{ width: (ts.success_rate * 100) + '%', background: ts.success_rate > 0.8 ? 'var(--c-green)' : '#F59E0B' }"
              />
            </div>
            <span class="tool-pct mono" :style="{ color: ts.success_rate > 0.8 ? 'var(--c-green)' : '#F59E0B' }">
              {{ (ts.success_rate * 100).toFixed(0) }}%
            </span>
          </div>
          <span class="tool-calls mono">{{ ts.calls }} 次</span>
          <span class="tool-latency mono">{{ ts.avg_latency_ms?.toFixed(0) || 0 }}ms</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stats: { type: Object, default: null },
})

const durationFmt = computed(() => {
  const s = props.stats?.duration_s || 0
  return s > 60 ? `${(s / 60).toFixed(1)}m` : `${s.toFixed(0)}s`
})

const costColor  = computed(() => (props.stats?.estimated_cost_usd || 0) > 0.1 ? '#D97706' : 'var(--c-text)')
const cacheColor = computed(() => (props.stats?.cache_hit_rate || 0) > 0.3 ? 'var(--c-green)' : '#D97706')
const citeColor  = computed(() => {
  const r = props.stats?.citation_support_rate
  if (r < 0) return 'var(--c-text-3)'
  return r >= 0.8 ? 'var(--c-green)' : '#D97706'
})
const citeRateFmt = computed(() => {
  const r = props.stats?.citation_support_rate
  return (r == null || r < 0) ? '—' : `${(r * 100).toFixed(0)}%`
})
const hasToolStats = computed(() =>
  props.stats?.tool_stats && Object.keys(props.stats.tool_stats).length > 0
)
</script>

<style scoped>
.stats-panel {
  background: #fff; border: 1px solid var(--c-nav-border);
  border-radius: 16px; padding: 24px 28px; margin-top: 28px;
}
.stats-title {
  font-weight: 800; font-size: 15px; margin-bottom: 18px;
  color: var(--c-text-2);
}
.stats-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
  margin-bottom: 6px;
}
.stat-cell {
  background: var(--c-card-bg); border: 1px solid var(--c-card-border);
  border-radius: 12px; padding: 14px 16px; text-align: center;
}
.stat-val { font-size: 20px; font-weight: 800; }
.stat-key { font-size: 12px; color: var(--c-text-4); margin-top: 4px; font-weight: 600; }

.tool-section { margin-top: 22px; border-top: 1px solid var(--c-divider); padding-top: 18px; }
.tool-title { font-weight: 700; font-size: 13.5px; color: var(--c-text-2); margin-bottom: 12px; }
.tool-rows { display: flex; flex-direction: column; gap: 8px; }
.tool-row {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px;
}
.tool-name { min-width: 110px; color: var(--c-text-2); font-size: 12.5px; }
.tool-bar-wrap { flex: 1; display: flex; align-items: center; gap: 6px; }
.tool-bar-bg { flex: 1; height: 6px; border-radius: 99px; background: var(--c-divider); overflow: hidden; }
.tool-bar-fill { height: 100%; border-radius: 99px; transition: width 0.5s ease; }
.tool-pct  { font-size: 12.5px; font-weight: 700; min-width: 32px; text-align: right; }
.tool-calls  { color: var(--c-text-4); min-width: 38px; font-size: 12px; }
.tool-latency { color: var(--c-text-4); font-size: 12px; min-width: 46px; }
</style>
