<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import DetailPanel from '@/components/DetailPanel.vue'
import LayerSwitcher from '@/components/LayerSwitcher.vue'
import MapLegend, { type LegendItem } from '@/components/MapLegend.vue'
import MapView from '@/components/MapView.vue'
import { TRAFFIC_AREA_LAYER } from '@/api/traffic'
import { externalLayers, outdoorLayers, trafficLayers } from '@/catalog'
import { useLayersStore } from '@/stores/layers'
import { DOMAIN_COLORS, VALUE_COLORS, valueMax, type LayerId } from '@/types/mapObject'

const layers = useLayersStore()
const { t } = useI18n()

// Un échec est notifié par le gestionnaire global des promesses rejetées (main.ts).
trafficLayers().then(layers.addDefinitions)
outdoorLayers().then(layers.addDefinitions)
externalLayers().then(layers.addDefinitions)

/** Entrées des couches trafic visibles : compteurs, puis dégradé des mailles. */
const legend = computed<LegendItem[]>(() => {
  const visible = (Object.keys(layers.visible) as LayerId[]).filter((id) => layers.visible[id])
  const items: LegendItem[] = []
  if (visible.some((id) => id.startsWith('traffic/') && id !== TRAFFIC_AREA_LAYER)) {
    items.push({ label: t('legend.counters'), color: DOMAIN_COLORS.traffic, shape: 'point' })
  }
  if (visible.includes(TRAFFIC_AREA_LAYER)) {
    items.push({
      label: t('legend.trafficAreas'),
      colors: VALUE_COLORS,
      min: 0,
      max: valueMax((layers.objectsByLayer[TRAFFIC_AREA_LAYER] ?? []).map((o) => o.value)),
    })
  }
  return items
})
</script>

<template>
  <main class="home">
    <div class="map">
      <MapView />
      <LayerSwitcher class="layer-switcher" />
      <MapLegend v-if="legend.length" :items="legend" />
    </div>
    <aside class="panel right">
      <DetailPanel />
    </aside>
  </main>
</template>

<style scoped>
.home {
  flex: 1; /* hauteur restante sous la barre de navigation */
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr var(--panel-width);
}

.panel {
  overflow-y: auto;
  padding: var(--space);
  background: var(--color-panel);
}

.right {
  border-left: 1px solid var(--color-border);
}

.map {
  position: relative;
  min-width: 0;
}

/* Sous les boutons de zoom de MapLibre, en haut à droite. */
.layer-switcher {
  position: absolute;
  top: 100px;
  right: 10px;
}
</style>
