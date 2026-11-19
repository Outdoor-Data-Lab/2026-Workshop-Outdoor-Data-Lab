<script setup lang="ts">
/** Détail de l'objet sélectionné sur la carte : titré par son nom, sous le nom de sa couche. */
import { computed } from 'vue'

import { TRAFFIC_AREA_LAYER } from '@/api/traffic'
import CellDetail from '@/components/CellDetail.vue'
import { useLayersStore } from '@/stores/layers'

const layers = useLayersStore()

const layerLabel = computed(
  () => layers.definitions.find((d) => d.id === layers.selected?.layer)?.label,
)

/** Valeur en texte : sans balises HTML, listes séparées par des virgules. */
function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(text).join(', ')
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return new DOMParser().parseFromString(String(value), 'text/html').body.textContent ?? ''
}
</script>

<template>
  <section class="detail">
    <template v-if="layers.selected">
      <header>
        <div>
          <p class="layer">{{ layerLabel }}</p>
          <h2>{{ layers.selected.label }}</h2>
        </div>
        <button type="button" :aria-label="$t('detail.close')" @click="layers.select(null)">
          ×
        </button>
      </header>
      <CellDetail
        v-if="layers.selected.layer === TRAFFIC_AREA_LAYER"
        :key="layers.selected.key"
        :cell="layers.selected"
      />
      <dl v-else-if="layers.selected.attributes">
        <template v-for="(value, name) in layers.selected.attributes" :key="name">
          <dt>{{ name }}</dt>
          <dd>{{ text(value) }}</dd>
        </template>
      </dl>
    </template>
  </section>
</template>

<style scoped>
header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space);
  margin: 0 0 var(--space);
}

.layer {
  color: var(--color-muted);
  font-size: 0.85rem;
}

h2 {
  margin: 0;
  font-size: 1.4rem;
}

header button {
  border: 0;
  background: none;
  color: inherit;
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
}

p {
  margin: 0;
}

dl {
  margin: var(--space) 0 0;
}

dt {
  font-weight: bold;
}

dd {
  margin: 0 0 calc(var(--space) / 2);
  overflow-wrap: anywhere;
}
</style>
