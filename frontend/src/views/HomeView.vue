<script setup lang="ts">
import { computed } from 'vue'

import AreaFilter from '@/components/AreaFilter.vue'
import DetailPanel from '@/components/DetailPanel.vue'
import SeasonFilter from '@/components/SeasonFilter.vue'
import LayerSwitcher from '@/components/LayerSwitcher.vue'
import MapLegend from '@/components/MapLegend.vue'
import MapView from '@/components/MapView.vue'
import { biodiversityLayers, externalLayers, outdoorLayers, trafficLayers } from '@/catalog'
import { useLayersStore } from '@/stores/layers'

const layers = useLayersStore()

// Un échec est notifié par le gestionnaire global des promesses rejetées (main.ts).
trafficLayers().then(layers.addDefinitions)
outdoorLayers().then(layers.addDefinitions)
biodiversityLayers().then(layers.addDefinitions)
externalLayers().then(layers.addDefinitions)

/** Entrées des couches visibles, dans l'ordre des couches. */
const legend = computed(() =>
  layers.definitions
    .filter((d) => layers.visible[d.id])
    .flatMap((d) => d.legend?.(layers.objectsByLayer[d.id] ?? []) ?? []),
)
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
  /* Recherche et couches à la même largeur : celle du plus long libellé de couche stable,
     « Protected or threatened taxa per grid cell » (353 px). Les couches externes passent à la ligne. */
  width: min(24rem, calc(100% - 20px));
  gap: calc(var(--space) / 1.5);
  /* Au-dessus de la légende et de l'échelle, en bas à gauche ; la liste défile au-delà. */
  max-height: calc(100% - 200px);
  overflow-y: auto;
}

.detail-card {
  position: absolute;
  z-index: 1;
  top: 10px;
  right: 10px;
  /* Large, donc moins haute : elle s'arrête au-dessus du zoom et de l'attribution. */
  width: min(26rem, calc(100% - 20px));
  max-height: calc(100% - 170px);
  overflow-y: auto;
  padding: var(--space);
  background: var(--color-background);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
</style>
