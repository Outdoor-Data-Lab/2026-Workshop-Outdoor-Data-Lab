<script setup lang="ts">
import { useI18n } from 'vue-i18n'

export interface LegendSwatch {
  label: string
  color: string
  shape: 'point' | 'line' | 'polygon'
}

/** Dégradé de valeurs, de `min` (première couleur) à `max` (dernière). */
export interface LegendGradient {
  label: string
  colors: readonly string[]
  min: number
  max: number
}

export type LegendItem = LegendSwatch | LegendGradient

defineProps<{ items: LegendItem[] }>()

const { locale } = useI18n()
const formatNumber = (n: number) => n.toLocaleString(locale.value, { maximumFractionDigits: 1 })
</script>

<template>
  <section class="legend" aria-labelledby="legend-title">
    <h2 id="legend-title">{{ $t('legend.title') }}</h2>
    <ul>
      <li v-for="item in items" :key="item.label">
        <template v-if="'colors' in item">
          <div class="gradient">
            {{ item.label }}
            <span
              class="bar"
              :style="{ background: `linear-gradient(to right, ${item.colors.join(', ')})` }"
            ></span>
            <span class="bounds">
              <span>{{ formatNumber(item.min) }}</span>
              <span>{{ formatNumber(item.max) }}</span>
            </span>
          </div>
        </template>
        <template v-else>
          <span class="swatch" :class="item.shape" :style="{ '--color': item.color }"></span>
          {{ item.label }}
        </template>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.legend {
  position: absolute;
  z-index: 1;
  left: 0.75rem;
  bottom: 4rem; /* au-dessus de l'attribution MapLibre */
  min-width: 10rem;
  padding: 0.6rem 0.85rem;
  background: #fff;
  color: #1f2933;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgb(0 0 0 / 18%);
}

h2 {
  margin: 0 0 0.4rem;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #52606d;
}

ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  line-height: 1.6;
}

.swatch {
  flex-shrink: 0;
  width: 0.9rem;
  height: 0.9rem;
  background: var(--color);
}

.swatch.point {
  border: 2px solid #fff;
  border-radius: 50%;
  box-shadow: 0 0 0 1px var(--color);
}

.swatch.line {
  height: 3px;
}

.gradient {
  display: flex;
  flex-direction: column;
  width: 100%;
  margin-top: 0.25rem;
}

.bar {
  height: 0.6rem;
  margin-top: 0.2rem;
  border-radius: 2px;
}

.bounds {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #52606d;
}

.swatch.polygon {
  opacity: 0.6;
  outline: 1.5px solid var(--color);
}
</style>
