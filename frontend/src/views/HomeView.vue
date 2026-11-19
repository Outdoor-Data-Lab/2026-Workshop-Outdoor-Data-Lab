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
    <MapView />
    <div class="controls">
      <AreaFilter />
      <SeasonFilter />
      <LayerSwitcher />
    </div>
    <MapLegend v-if="legend.length" :items="legend" />
    <!-- Par-dessus la carte, à la taille de son contenu : la carte ne bouge pas. -->
    <aside v-if="layers.selected" class="detail-card">
      <DetailPanel />
    </aside>
  </main>
</template>

<style scoped>
.home {
  flex: 1; /* hauteur restante sous la barre de navigation */
  min-height: 0;
  position: relative;
}

/* Recherche de zone, saison puis couches, en haut à gauche ; le zoom est en bas à droite. */
.controls {
  position: absolute;
  z-index: 1;
  top: 10px;
  left: 10px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: calc(var(--space) / 1.5);
  max-height: calc(100% - 20px);
  overflow-y: auto;
}

.detail-card {
  position: absolute;
  z-index: 1;
  top: 10px;
  right: 10px;
  width: var(--panel-width);
  /* Au-dessus du zoom et de l'attribution, en bas à droite. */
  max-height: calc(100% - 150px);
  overflow-y: auto;
  padding: var(--space);
  background: var(--color-background);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
</style>
