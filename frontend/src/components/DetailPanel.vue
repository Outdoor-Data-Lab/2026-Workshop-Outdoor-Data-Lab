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
    <header>
      <h2>{{ $t('detail.title') }}</h2>
      <button type="button" :aria-label="$t('detail.close')" @click="layers.select(null)">×</button>
    </header>
    <template v-if="layers.selected">
      <p v-if="layers.selected.layer === TRAFFIC_AREA_LAYER">
        <strong>{{ $t('layers.cellName') }}</strong> {{ layers.selected.id }}
      </p>
      <p v-else>{{ layers.selected.label }}</p>
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
  align-items: center;
  justify-content: space-between;
  margin: 0 0 var(--space);
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
