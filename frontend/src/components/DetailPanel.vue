<script setup lang="ts">
/** Détail de l'objet sélectionné sur la carte. */
import { TRAFFIC_AREA_LAYER } from '@/api/traffic'
import CellDetail from '@/components/CellDetail.vue'
import { useLayersStore } from '@/stores/layers'

const layers = useLayersStore()

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
    <h2>{{ $t('detail.title') }}</h2>
    <template v-if="layers.selected">
      <p>{{ layers.selected.label }}</p>
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
    <p v-else class="hint">{{ $t('detail.empty') }}</p>
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

.hint {
  color: var(--color-muted);
}
</style>
