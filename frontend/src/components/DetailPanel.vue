<script setup lang="ts">
/** Détail de l'objet sélectionné sur la carte. */
import { useLayersStore } from '@/stores/layers'

const layers = useLayersStore()
</script>

<template>
  <section class="detail">
    <h2>Detail</h2>
    <p v-if="layers.selected">{{ layers.selected.label }}</p>
    <p v-else class="hint">Select an object on the map.</p>
  </section>
</template>

<style scoped>
h2 {
  margin: 0 0 var(--space);
  font-size: 1.1rem;
}

p {
  margin: 0;
}

.hint {
  color: var(--color-muted);
}
</style>
