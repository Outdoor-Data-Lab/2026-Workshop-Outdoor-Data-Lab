<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import AreaFilter from '@/components/AreaFilter.vue'
import DetailPanel from '@/components/DetailPanel.vue'
import SeasonFilter from '@/components/SeasonFilter.vue'
import LayerSwitcher from '@/components/LayerSwitcher.vue'
import MapLegend, { type LegendItem } from '@/components/MapLegend.vue'
import MapView from '@/components/MapView.vue'
import { TRAFFIC_AREA_LAYER } from '@/api/traffic'
import { biodiversityLayers, externalLayers, outdoorLayers, trafficLayers } from '@/catalog'
import { useLayersStore } from '@/stores/layers'
import { DOMAIN_COLORS, VALUE_COLORS, valueMax, type LayerId } from '@/types/mapObject'

const layers = useLayersStore()
const { t } = useI18n()

// Un échec est notifié par le gestionnaire global des promesses rejetées (main.ts).
trafficLayers().then(layers.addDefinitions)
outdoorLayers().then(layers.addDefinitions)
biodiversityLayers().then(layers.addDefinitions)
externalLayers().then(layers.addDefinitions)

/** Entrées des couches trafic visibles : compteurs, puis dégradé des mailles. */
const legend = computed<LegendItem[]>(() => {
  const visible = (Object.keys(layers.visible) as LayerId[]).filter((id) => layers.visible[id])
  const items: LegendItem[] = []
  // Couches en tuiles : des lignes, sous le nom de la couche ; les autres : des points.
  const tiled = new Set(layers.definitions.filter((d) => d.tiles).map((d) => d.id))
  const traffic = visible.filter((id) => id.startsWith('traffic/') && id !== TRAFFIC_AREA_LAYER)
  if (traffic.some((id) => !tiled.has(id))) {
    items.push({ label: t('legend.counters'), color: DOMAIN_COLORS.traffic, shape: 'point' })
  }
  for (const definition of layers.definitions) {
    if (tiled.has(definition.id) && traffic.includes(definition.id)) {
      items.push({ label: definition.label, color: DOMAIN_COLORS.traffic, shape: 'line' })
    }
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
      <div class="controls">
        <AreaFilter />
        <SeasonFilter />
      </div>
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

/* Filtres en haut à gauche de la carte : zone, puis saison, à la même largeur. */
.controls {
  position: absolute;
  z-index: 1;
  top: 10px;
  left: 10px;
  display: flex;
  flex-direction: column;
  gap: calc(var(--space) / 1.5);
  width: min(18rem, calc(100% - 20px));
}

/* Sous les boutons de zoom de MapLibre, en haut à droite. */
.layer-switcher {
  position: absolute;
  top: 100px;
  right: 10px;
}
</style>
