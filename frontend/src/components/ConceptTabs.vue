<script setup lang="ts">
/** Choix du concept : Global, Traffic ou Biodiversity. */
import { useLayersStore } from '@/stores/layers'
import { CONCEPTS } from '@/types/concept'

const layers = useLayersStore()
</script>

<template>
  <nav class="concepts" aria-label="Concept">
    <button
      v-for="concept in CONCEPTS"
      :key="concept.id"
      type="button"
      :aria-pressed="layers.concept === concept.id"
      @click="layers.setConcept(concept.id)"
    >
      {{ concept.label }}
    </button>
  </nav>
</template>

<style scoped>
.concepts {
  display: flex;
  flex-direction: column;
  gap: calc(var(--space) / 3);
}

button {
  padding: calc(var(--space) / 2) var(--space);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-background);
  color: var(--color-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

button[aria-pressed='true'] {
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: var(--color-background);
}

button:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
</style>
