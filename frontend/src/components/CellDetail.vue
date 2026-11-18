<script setup lang="ts">
/** Synthèse d'une maille : fréquentation, biodiversité, offres outdoor, zonages réglementaires. */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { describeError } from '@/api/errors'
import { getAreaOffers } from '@/api/outdoor'
import { getTrafficArea, type SourceCount } from '@/api/traffic'
import { useAsync } from '@/composables/useAsync'
import type { MapObject } from '@/types/mapObject'

// Le parent recrée le composant à chaque maille (`:key`) : un seul chargement.
const props = defineProps<{ cell: MapObject }>()

const { t, te, n } = useI18n()

const { data, error, loading } = useAsync(async () => {
  const id = Number(props.cell.id)
  const [traffic, offers] = await Promise.all([getTrafficArea(id), getAreaOffers(id)])
  return { traffic: traffic.properties, offers }
})

/** Score de la carte (0 à 100). */
const score = computed(() => (props.cell.value === undefined ? '–' : Math.round(props.cell.value)))

const practices = computed(() => {
  const groups = new Map<string, NonNullable<typeof data.value>['offers']['results']>()
  for (const offer of data.value?.offers.results ?? []) {
    groups.set(offer.practice_label, [...(groups.get(offer.practice_label) ?? []), offer])
  }
  return groups
})

/** Ce que compte la source, ex. « 250 trajets cumulés sur les tronçons de la maille ». */
function countText(source: SourceCount) {
  const key = te(`cell.units.${source.code}`) ? `cell.units.${source.code}` : 'cell.units.other'
  return t(key, { n: n(source.count) }, source.count)
}

/** Années couvertes par les mesures, ex. « 2021–2024 ». */
function years(source: SourceCount) {
  const [first, last] = [source.first_data, source.latest_data].map((d) =>
    new Date(d).getFullYear(),
  )
  return first === last ? String(first) : `${first}–${last}`
}
</script>

<template>
  <p v-if="loading" class="hint">{{ $t('cell.loading') }}</p>
  <p v-else-if="error" class="hint">{{ describeError(error) }}</p>
  <div v-else-if="data" class="cell">
    <dl>
      <dt>{{ $t('cell.traffic') }}</dt>
      <dd>{{ score }}/100</dd>
      <dt>{{ $t('cell.biodiversity') }}</dt>
      <dd class="hint">{{ $t('cell.soon') }}</dd>
      <dt>{{ $t('cell.outdoor') }}</dt>
      <dd>{{ $t('cell.offers', data.offers.count) }}</dd>
      <dt>{{ $t('cell.zonings') }}</dt>
      <dd class="hint">{{ $t('cell.soon') }}</dd>
    </dl>

    <h3>{{ $t('cell.traffic') }}</h3>
    <ul class="sources">
      <li v-for="source in data.traffic.sources" :key="source.code">
        <strong>{{ source.label }}</strong> : {{ countText(source) }}
        <div class="hint">
          {{ source.absolute ? $t('cell.absolute') : $t('cell.relative') }} · {{ years(source) }}
        </div>
      </li>
    </ul>
    <p class="hint note">{{ $t('cell.countsNote') }}</p>

    <h3>{{ $t('cell.outdoor') }}</h3>
    <p>{{ $t('cell.offers', data.offers.count) }}</p>
    <details v-for="[practice, offers] in practices" :key="practice">
      <summary>{{ practice }} ({{ offers.length }})</summary>
      <ul>
        <li v-for="offer in offers" :key="offer.id">
          {{ offer.name }} <span class="hint">· {{ offer.source_label }}</span>
        </li>
      </ul>
    </details>
  </div>
</template>

<style scoped>
.cell {
  margin-top: var(--space);
}

dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: calc(var(--space) / 3) var(--space);
  margin: 0;
}

dt {
  font-weight: bold;
}

dd {
  margin: 0;
}

h3 {
  margin: var(--space) 0 calc(var(--space) / 2);
  padding-top: calc(var(--space) / 2);
  border-top: 1px solid var(--color-border);
  font-size: 1rem;
}

p {
  margin: 0;
}

.sources {
  padding: 0;
  list-style: none;
}

.sources li + li {
  margin-top: calc(var(--space) / 2);
}

.note {
  margin-top: calc(var(--space) / 2);
  font-size: 0.85rem;
}

ul {
  margin: 0;
  padding-left: 1.2rem;
}

summary {
  cursor: pointer;
}

.hint {
  color: var(--color-muted);
}
</style>
