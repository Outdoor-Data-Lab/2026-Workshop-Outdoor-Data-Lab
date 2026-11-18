<script setup lang="ts">
import MapLegend, { type LegendItem } from '@/components/MapLegend.vue'
import MapView from '@/components/MapView.vue'
import {
  COUNTING_OBJECT_LAYER,
  TRAFFIC_AREA_LAYER,
  getCountingObjectsForMap,
  getTrafficAreasForMap,
} from '@/api/traffic'
import { computed } from 'vue'

import { useMapObjectsStore } from '@/stores/mapObjects'
import { DOMAIN_COLORS, VALUE_COLORS, valueMax } from '@/types/mapObject'

const mapObjects = useMapObjectsStore()

// Les erreurs sont notifiées par le store.
mapObjects.loadLayer(COUNTING_OBJECT_LAYER, () => getCountingObjectsForMap(), {
  label: 'les compteurs',
})
mapObjects.loadLayer(TRAFFIC_AREA_LAYER, () => getTrafficAreasForMap(), {
  label: 'la fréquentation par maille',
})

const legend = computed<LegendItem[]>(() => [
  { label: 'Compteurs', color: DOMAIN_COLORS.traffic, shape: 'point' },
  {
    label: 'Fréquentation par maille (score)',
    colors: VALUE_COLORS,
    min: 0,
    max: valueMax((mapObjects.layers[TRAFFIC_AREA_LAYER] ?? []).map((o) => o.value)),
  },
])
</script>

<template>
  <main>
    <MapView />
    <MapLegend :items="legend" />
  </main>
</template>

<style scoped>
main {
  flex: 1; /* hauteur restante sous le header */
  min-height: 0;
  position: relative;
}
</style>
