<script setup lang="ts">
/** Synthèse d'une maille : fréquentation, biodiversité, offres outdoor, zonages réglementaires. */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { getAreaTaxa, type AreaTaxon } from '@/api/biodiv'
import { describeError } from '@/api/errors'
import { getAreaOffers } from '@/api/outdoor'
import { getTrafficArea, type SourceCount } from '@/api/traffic'
import { useAsync } from '@/composables/useAsync'
import type { MapObject } from '@/types/mapObject'

// Le parent recrée le composant à chaque maille (`:key`) : un seul chargement.
const props = defineProps<{ cell: MapObject }>()

const { t, te, n } = useI18n()

/** Longueur ou personnes·km avec une décimale. */
const oneDecimal = (value: number) => n(value, { maximumFractionDigits: 1 })

const { data, error, loading } = useAsync(async () => {
  const id = Number(props.cell.id)
  const [traffic, offers, taxa] = await Promise.all([
    getTrafficArea(id),
    getAreaOffers(id),
    getAreaTaxa(id),
  ])
  return { traffic: traffic.properties, offers, taxa: taxa.properties.taxa }
})

/** Les trois formules de l'explication du score, dans l'ordre. */
const scoreSteps = ['counts', 'weights', 'final'] as const

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

type Cazalis = {
  source_weights?: Record<string, number>
  reference_counters?: number
}

/** Détail du score cazalis : poids de chaque source (clés = id de source). */
const cazalis = computed<Cazalis>(() => {
  const score = data.value?.traffic.score.cazalis
  return typeof score === 'object' ? (score as Cazalis) : {}
})

/** Poids de la source dans le score, en points sur 100 ; `undefined` si inconnu. */
function weight(source: SourceCount) {
  return cazalis.value.source_weights?.[source.id]
}

/** Années couvertes, ex. « 2021–2024 ». */
function years(from: string, to: string) {
  const [first, last] = [from, to].map((d) => new Date(d).getFullYear())
  return first === last ? String(first) : `${first}–${last}`
}

/** Statuts, observations et années d'un taxon, ex. « protégé · menacé (VU) · 4 observations · 2017–2024 ». */
function taxonText(taxon: AreaTaxon) {
  return [
    taxon.protection.length && t('cell.protected'),
    ...taxon.threatened.map((s) => t('cell.threatened', { code: s.code_statut })),
    t('cell.observations', { n: n(taxon.count) }, taxon.count),
    years(taxon.date_min, taxon.date_max),
  ]
    .filter(Boolean)
    .join(' · ')
}
</script>

<template>
  <p v-if="loading" class="hint">{{ $t('cell.loading') }}</p>
  <p v-else-if="error" class="hint">{{ describeError(error) }}</p>
  <div v-else-if="data" class="cell">
    <dl>
      <dt>{{ $t('cell.traffic') }}</dt>
      <dd>
        {{ score }} <span class="hint">{{ $t('cell.scoreRange') }}</span>
      </dd>
      <dt>{{ $t('cell.biodiversity') }}</dt>
      <dd>{{ $t('cell.taxa', data.taxa.length) }}</dd>
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
          {{ source.absolute ? $t('cell.absolute') : $t('cell.relative') }} ·
          {{ years(source.first_data, source.latest_data) }}
        </div>
        <div v-if="source.length_km != null && source.person_km != null" class="hint">
          {{
            $t('cell.km', {
              km: oneDecimal(source.length_km),
              personKm: oneDecimal(source.person_km),
            })
          }}
        </div>
        <div v-if="source.code === 'ecocompteur'" class="hint">
          {{ $t('cell.score.reference') }}
        </div>
        <div v-else-if="weight(source) !== undefined" class="weight">
          {{ $t('cell.score.weight', { weight: weight(source) }) }}
        </div>
      </li>
    </ul>
    <p class="hint note">{{ $t('cell.countsNote') }}</p>

    <details class="formula">
      <summary>{{ $t('cell.score.title') }}</summary>
      <p>{{ $t('cell.score.intro') }}</p>
      <ol>
        <li v-for="step in scoreSteps" :key="step">
          <strong>{{ $t(`cell.score.${step}.title`) }}</strong>
          <code class="formula-eq">{{ $t(`cell.score.${step}.eq`) }}</code>
          <span class="hint">{{ $t(`cell.score.${step}.text`) }}</span>
        </li>
      </ol>
      <p v-if="cazalis.reference_counters" class="hint">
        {{ $t('cell.score.counters', { n: cazalis.reference_counters }) }}
      </p>
    </details>

    <h3>{{ $t('cell.biodiversity') }}</h3>
    <p>{{ $t('cell.taxa', data.taxa.length) }}</p>
    <details v-if="data.taxa.length">
      <summary>{{ $t('cell.taxaList') }}</summary>
      <ul>
        <li v-for="taxon in data.taxa" :key="taxon.cd_ref">
          {{ taxon.nom_vern ?? taxon.lb_nom }} <em v-if="taxon.nom_vern">{{ taxon.lb_nom }}</em>
          <div class="hint">{{ taxonText(taxon) }}</div>
        </li>
      </ul>
    </details>
    <p class="hint note">{{ $t('cell.taxaNote') }}</p>

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
  font-size: 1.2rem;
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

.weight {
  font-weight: 600;
}

.formula {
  margin-top: calc(var(--space) / 2);
  font-size: 0.85rem;
}

.formula ol {
  margin: calc(var(--space) / 3) 0;
  padding-left: 1.2rem;
}

.formula li + li {
  margin-top: calc(var(--space) / 2);
}

.formula-eq {
  display: block;
  margin: 0.2rem 0;
  padding: 0.25rem 0.5rem;
  border-left: 3px solid var(--color-accent);
  border-radius: var(--radius);
  background: var(--color-panel);
  font-family: monospace;
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
