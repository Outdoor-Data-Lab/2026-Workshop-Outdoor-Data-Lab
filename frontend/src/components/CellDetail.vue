<script setup lang="ts">
/**
 * Synthèse d'une maille : fréquentation, biodiversité, offres outdoor, zonages réglementaires.
 * Le domaine de la couche cliquée (`focus`) passe en premier.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { getAreaTaxa, type AreaTaxon } from '@/api/biodiv'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import { ApiError } from '@/api/client'
import { describeError } from '@/api/errors'
import { getAreaOffers } from '@/api/outdoor'
import { getTrafficArea, type SourceCount } from '@/api/traffic'
import { useAsync } from '@/composables/useAsync'
import { useLayersStore } from '@/stores/layers'
import type { MapObject } from '@/types/mapObject'

// Le parent recrée le composant à chaque maille (`:key`) : un seul chargement.
const props = withDefaults(defineProps<{ cell: MapObject; focus?: 'traffic' | 'biodiversity' }>(), {
  focus: 'traffic',
})

/** Sections dans l'ordre d'affichage. */
const sections = computed(() =>
  props.focus === 'biodiversity'
    ? (['biodiversity', 'traffic', 'outdoor'] as const)
    : (['traffic', 'biodiversity', 'outdoor'] as const),
)

const { t, te, n } = useI18n()
// Même saison que la carte.
const layers = useLayersStore()

/** Longueur ou personnes·km avec une décimale. */
const oneDecimal = (value: number) => n(value, { maximumFractionDigits: 1 })

const { data, error, loading } = useAsync(async () => {
  const id = Number(props.cell.id)
  const [traffic, offers, taxa] = await Promise.all([
    // 404 : pas de mesure de fréquentation sur la maille (cliquée depuis la biodiversité).
    getTrafficArea(id, layers.filters.months).catch((e) => {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    }),
    getAreaOffers(id),
    getAreaTaxa(id),
  ])
  return { traffic: traffic?.properties ?? null, offers, taxa: taxa.properties.taxa }
})

/** Dépôt de l'analyse R de Victor Cazalis (Conservara) dont le score est issu. */
const BTA_REPOSITORY = 'https://github.com/PnEcrins/BTA-analyse-frequentation'

/** Les trois formules de l'explication du score, dans l'ordre. */
const scoreSteps = ['counts', 'weights', 'final'] as const

/** Score de fréquentation (0 à 100), lu dans la réponse : la couleur de la maille cliquée peut être celle d'un autre domaine. */
const score = computed(() => {
  const value = data.value?.traffic?.score.cazalis
  const number = typeof value === 'object' ? (value as { score?: number }).score : value
  return number === undefined ? '–' : Math.round(number)
})

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
  const score = data.value?.traffic?.score.cazalis
  return typeof score === 'object' ? (score as Cazalis) : {}
})

/** Poids de la source dans le score, en points sur 100 ; `undefined` si inconnu. */
function weight(source: SourceCount) {
  return cazalis.value.source_weights?.[source.id]
}

/** Vrai si la source a des tracés dans la maille (longueur et personnes·km connues). */
function hasKm(source: SourceCount) {
  return source.length_km != null && source.person_km != null
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
  <LoadingSpinner v-if="loading" />
  <p v-else-if="error" class="hint">{{ describeError(error) }}</p>
  <div v-else-if="data" class="cell">
    <dl>
      <template v-for="section in sections" :key="section">
        <template v-if="section === 'traffic'">
          <dt>{{ $t('cell.traffic') }}</dt>
          <dd v-if="data.traffic">
            {{ score }} <span class="hint">{{ $t('cell.scoreRange') }}</span>
          </dd>
          <dd v-else class="hint">{{ $t('cell.noTraffic') }}</dd>
        </template>
        <template v-else-if="section === 'biodiversity'">
          <dt>{{ $t('cell.biodiversity') }}</dt>
          <dd>{{ $t('cell.taxa', data.taxa.length) }}</dd>
        </template>
        <template v-else>
          <dt>{{ $t('cell.outdoor') }}</dt>
          <dd>{{ $t('cell.offers', data.offers.count) }}</dd>
        </template>
      </template>
      <dt>{{ $t('cell.zonings') }}</dt>
      <dd class="hint">{{ $t('cell.soon') }}</dd>
    </dl>

    <template v-for="section in sections" :key="section">
      <section v-if="section === 'traffic'">
        <h3>{{ $t('cell.traffic') }}</h3>
        <template v-if="data.traffic">
          <ul class="sources">
            <li v-for="source in data.traffic.sources" :key="source.code">
              <strong>{{ source.label }}</strong> : {{ countText(source) }}
              <div class="hint">
                <template v-if="source.absolute">{{ $t('cell.absolute') }} · </template
                >{{ years(source.first_data, source.latest_data) }}
              </div>
              <div
                v-if="hasKm(source) || (source.code !== 'ecocompteur' && weight(source) !== undefined)"
                class="hint chain"
              >
                <template v-if="hasKm(source)">
                  <span class="item">
                    {{ $t('cell.lengthLabel') }}
                    <span class="value">{{
                      $t('cell.lengthValue', { km: oneDecimal(source.length_km!) })
                    }}</span>
                  </span>
                  <span class="item">
                    <span class="has-tip" :title="$t('cell.kmHelp')">{{
                      $t('cell.personKmLabel')
                    }}</span>
                    {{ ' ' }}
                    <span class="value">{{ oneDecimal(source.person_km!) }}</span>
                  </span>
                </template>
                <span v-if="source.code !== 'ecocompteur' && weight(source) !== undefined" class="item">
                  {{ $t('cell.score.weightLabel') }}
                  <span class="value">{{
                    $t('cell.score.weightValue', { weight: weight(source) })
                  }}</span>
                </span>
              </div>
              <div v-if="source.code === 'ecocompteur'" class="hint label">
                {{ $t('cell.score.referenceLabel') }}
                <span class="value">{{ $t('cell.score.reference') }}</span>
              </div>
            </li>
          </ul>

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
          <i18n-t keypath="cell.score.credit" tag="p" class="hint note">
            <template #link>
              <a :href="BTA_REPOSITORY" target="_blank" rel="noopener noreferrer">{{
                $t('cell.score.creditLink')
              }}</a>
            </template>
          </i18n-t>
        </template>
        <p v-else class="hint">{{ $t('cell.noTraffic') }}</p>
      </section>

      <section v-else-if="section === 'biodiversity'">
        <h3>{{ $t('cell.biodiversity') }}</h3>
        <p>{{ $t('cell.taxa', data.taxa.length) }}</p>
        <details v-if="data.taxa.length">
          <summary>{{ $t('cell.taxaList') }}</summary>
          <ul>
            <li v-for="taxon in data.taxa" :key="taxon.cd_ref">
              {{ taxon.nom_vern ?? taxon.lb_nom }}
              <em v-if="taxon.nom_vern">{{ taxon.lb_nom }}</em>
              <div class="hint">{{ taxonText(taxon) }}</div>
            </li>
          </ul>
        </details>
        <p class="hint note">{{ $t('cell.taxaNote') }}</p>
      </section>

      <section v-else>
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
      </section>
    </template>
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

/* Libellés explicatifs d'une source : en gras, à la taille du texte courant, donc plus petits
   que le titre de section (h3). Seules les valeurs restent en normal. Les éléments d'une
   « chaîne » sont séparés par un point médian placé en fin d'élément : une ligne ne commence
   jamais par un point. */
.sources .label,
.sources .chain .item {
  font-size: 1rem;
  font-weight: 600;
}

.sources .label .value,
.sources .chain .value {
  font-weight: normal;
}

.sources .chain .item:not(:last-child)::after {
  content: ' ·';
  margin-right: 0.3em;
  font-weight: normal;
}

.has-tip {
  cursor: help;
  text-decoration: underline dotted;
  text-underline-offset: 2px;
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
