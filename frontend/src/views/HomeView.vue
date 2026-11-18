<script setup lang="ts">
import L from 'leaflet'
import type { Feature, FeatureCollection, Geometry, GeoJsonObject } from 'geojson'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

type ScoreSource = { id: number; code: string; label: string }
type ScoreProperties = {
  counts: number
  count_segment: number
  count_presence: number
  score: Partial<Record<'basic' | 'cazalis', number>>
}
type ScoreCollection = FeatureCollection<Geometry, ScoreProperties> & {
  source_weights?: Record<number, number>
}
type PaginatedScoreCollection = ScoreCollection & { next?: string | null; count?: number }
type SelectedArea = Feature<Geometry, ScoreProperties> & { id: number }
type SourcesResponse = ScoreSource[] | { results?: ScoreSource[] }

const palette = ['#e9efdc', '#c4d7a4', '#91b77f', '#e3b45e', '#c9694d']
const indicator = ref<'basic' | 'cazalis'>('basic')
const sources = ref<ScoreSource[]>([])
const selectedSourceIds = ref<number[]>([])
const selectedYear = ref('')
const selectedMonth = ref('')
const scoreData = ref<ScoreCollection | null>(null)
const selectedArea = ref<SelectedArea | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const mapElement = ref<HTMLDivElement | null>(null)

let map: L.Map | null = null
let scoreLayer: L.GeoJSON | null = null
let mapMoveTimer: number | undefined

const isCazalis = computed(() => indicator.value === 'cazalis')
const indicatorTitle = computed(() =>
  isCazalis.value ? 'Indice Cazalis pondéré' : 'Fréquentation cumulée',
)
const scoreUnit = computed(() => (isCazalis.value ? 'points pondérés' : 'passages'))
const scoreFeatures = computed(() => scoreData.value?.features ?? [])
const cazalisSources = computed(() =>
  sources.value.filter((source) => ['strava', 'inaturalist', 'outdoorvision'].includes(source.code)),
)
const hasPositiveCazalisWeight = computed(() =>
  cazalisSources.value.some((source) => Number(scoreData.value?.source_weights?.[source.id] ?? 0) > 0),
)
const sourceFilterLabel = computed(() =>
  selectedSourceIds.value.length
    ? `${selectedSourceIds.value.length} sélectionnée${selectedSourceIds.value.length > 1 ? 's' : ''}`
    : 'Toutes les sources',
)
const monthOptions = Array.from({ length: 12 }, (_, index) => ({
  value: String(index + 1),
  label: new Intl.DateTimeFormat('fr-FR', { month: 'long' }).format(new Date(2024, index, 1)),
}))
const hasNonZeroScores = computed(() =>
  scoreFeatures.value.some((feature) => getScore(feature.properties) > 0),
)
const maxScore = computed(() =>
  Math.max(0, ...scoreFeatures.value.map((feature) => getScore(feature.properties))),
)
const averageScore = computed(() => {
  if (!scoreFeatures.value.length) return 0
  return (
    scoreFeatures.value.reduce((sum, feature) => sum + getScore(feature.properties), 0) /
    scoreFeatures.value.length
  )
})
const scoreBreaks = computed(() => {
  const values = scoreFeatures.value
    .map((feature) => getScore(feature.properties))
    .filter((score) => score > 0)
    .sort((left, right) => left - right)
  return [0.2, 0.4, 0.6, 0.8].map((quantile) => {
    if (!values.length) return 0
    return values[Math.min(values.length - 1, Math.floor(quantile * values.length))] ?? 0
  })
})

function formatScore(value: number) {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(value)
}

function getScore(properties: ScoreProperties) {
  return Number(properties.score[indicator.value] ?? 0)
}

function getColor(score: number) {
  const colorIndex = scoreBreaks.value.findIndex((limit) => score <= limit)
  return palette[colorIndex < 0 ? palette.length - 1 : colorIndex]
}

async function loadAllScorePages(url: string): Promise<ScoreCollection> {
  const features: ScoreCollection['features'] = []
  let nextUrl: string | null = url
  let sourceWeights: Record<number, number> | undefined

  while (nextUrl) {
    const response = await fetch(nextUrl)
    const payload = await response.json().catch(() => ({})) as PaginatedScoreCollection & {
      detail?: string
    }
    if (!response.ok) {
      throw new Error(payload.detail ?? 'Impossible de charger les cartes de score.')
    }
    features.push(...(payload.features ?? []))
    sourceWeights = payload.source_weights ?? sourceWeights
    nextUrl = payload.next ?? null
  }

  return { type: 'FeatureCollection', features, source_weights: sourceWeights }
}

async function loadSources() {
  const response = await fetch('/api/commons/data-source')
  if (!response.ok) throw new Error('Impossible de charger les sources de données.')
  const payload = await response.json() as SourcesResponse
  sources.value = Array.isArray(payload) ? payload : payload.results ?? []
}

async function loadScoreMap() {
  if (!map) return
  const bounds = map.getBounds()
  if (bounds.getEast() - bounds.getWest() > 2.5 || bounds.getNorth() - bounds.getSouth() > 2.5) {
    errorMessage.value = 'Zoomez sur un territoire plus restreint pour afficher les mailles.'
    scoreLayer?.remove()
    scoreLayer = null
    scoreData.value = null
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    const params = new URLSearchParams()
    params.set(
      'bbox',
      [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()]
        .map((coordinate) => coordinate.toFixed(5))
        .join(','),
    )
    params.append('scores', indicator.value)
    if (selectedYear.value) params.set('year', selectedYear.value)
    if (selectedMonth.value) params.set('month', selectedMonth.value)
    for (const sourceId of selectedSourceIds.value) {
      params.append('source', String(sourceId))
    }
    scoreData.value = await loadAllScorePages(`/api/traffic/areas?${params}`)
    selectedArea.value = null
    scoreLayer?.remove()
    if (!scoreFeatures.value.length) {
      scoreLayer = null
      return
    }
    scoreLayer = L.geoJSON(scoreData.value as GeoJsonObject, {
      style: (feature) => ({
        color: '#526b58',
        weight: 0.7,
        opacity: 0.85,
        fillColor: getColor(Number(feature?.properties?.score?.[indicator.value] ?? 0)),
        fillOpacity: 0.78,
      }),
      onEachFeature: (feature: Feature<Geometry, ScoreProperties>, layer) => {
        const areaId = Number(feature.id)
        layer.bindTooltip(
          `Maille ${areaId}<br>${formatScore(getScore(feature.properties))} ${scoreUnit.value}`,
          { sticky: true, className: 'score-tooltip' },
        )
        layer.on('click', () => {
          selectedArea.value = { ...feature, id: areaId }
          if (layer instanceof L.Path) {
            layer.setStyle({ color: '#263b32', weight: 2, fillOpacity: 0.95 })
          }
        })
      },
    }).addTo(map)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Une erreur est survenue.'
  } finally {
    loading.value = false
  }
}

function fitToScores() {
  if (scoreLayer?.getBounds().isValid()) {
    map?.fitBounds(scoreLayer.getBounds(), { padding: [28, 28], maxZoom: 12 })
  }
}

function scheduleViewportRefresh() {
  window.clearTimeout(mapMoveTimer)
  mapMoveTimer = window.setTimeout(() => loadScoreMap(), 350)
}

function toggleSource(sourceId: number, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  selectedSourceIds.value = checked
    ? [...selectedSourceIds.value, sourceId]
    : selectedSourceIds.value.filter((id) => id !== sourceId)
}

function clearFilters() {
  selectedYear.value = ''
  selectedMonth.value = ''
  selectedSourceIds.value = []
  loadScoreMap()
}

async function chooseIndicator(value: 'basic' | 'cazalis') {
  indicator.value = value
  if (value === 'cazalis' && !sources.value.length) {
    try {
      await loadSources()
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : 'Sources indisponibles.'
      return
    }
  }
  await loadScoreMap()
}

onMounted(async () => {
  await nextTick()
  if (!mapElement.value) return
  map = L.map(mapElement.value, { zoomControl: false, preferCanvas: true }).setView([45.02, 6.25], 10)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map)
  L.control.zoom({ position: 'bottomright' }).addTo(map)
  L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(map)
  map.on('moveend', scheduleViewportRefresh)

  try {
    await loadSources()
  } catch {
    // Source weights are only needed for the Cazalis indicator.
  }
  await loadScoreMap()
  window.setTimeout(() => map?.invalidateSize(), 200)
})

onBeforeUnmount(() => {
  window.clearTimeout(mapMoveTimer)
  scoreLayer?.remove()
  map?.remove()
  map = null
})
</script>

<template>
  <div class="score-app">
    <header class="topbar">
      <a class="brand" href="/" aria-label="Outdoor Data Lab, accueil">
        <span class="brand-mark">ODL</span>
        <span class="brand-copy">
          <strong>Outdoor Data Lab</strong>
          <small>Observatoire des pratiques</small>
        </span>
      </a>
      <div class="topbar-context">
        <span class="status-dot"></span>
        <span>{{ scoreFeatures.length }} mailles chargées</span>
      </div>
      <button class="refresh-button" type="button" :disabled="loading" @click="loadScoreMap">
        <span class="refresh-glyph" aria-hidden="true">↻</span>
        Actualiser
      </button>
    </header>

    <main class="page-content">
      <section class="page-heading">
        <div>
          <p class="eyebrow"><span>Exploration territoriale</span><i></i><span>Mailles M1</span></p>
          <h1>Cartes de score<span class="title-period">.</span></h1>
          <p class="intro-copy">Comparez la fréquentation et explorez son poids selon les sources de données.</p>
        </div>
        <div class="headline-stats" aria-label="Résumé des scores">
          <div>
            <span>Score moyen</span>
            <strong>{{ formatScore(averageScore) }}</strong>
          </div>
          <div>
            <span>Maximum observé</span>
            <strong>{{ formatScore(maxScore) }}</strong>
          </div>
          <div>
            <span>Sources</span>
            <strong>{{ sources.length.toString().padStart(2, '0') }}</strong>
          </div>
        </div>
      </section>

      <section class="workspace" aria-label="Exploration des cartes de score">
        <aside class="control-panel">
          <div class="panel-section indicator-section">
            <p class="section-index">01 <span>/</span> INDICATEUR</p>
            <h2>Choisir un score</h2>
            <div class="indicator-switch" role="group" aria-label="Indicateur">
              <button
                type="button"
                :aria-pressed="indicator === 'basic'"
                :class="{ active: indicator === 'basic' }"
                @click="chooseIndicator('basic')"
              >
                Fréquentation
              </button>
              <button
                type="button"
                :aria-pressed="indicator === 'cazalis'"
                :class="{ active: indicator === 'cazalis' }"
                @click="chooseIndicator('cazalis')"
              >
                Cazalis
              </button>
            </div>
            <p class="section-note">
              {{ isCazalis ? 'Ajustez la contribution de chaque source.' : 'Somme des comptages, toutes sources confondues.' }}
            </p>
          </div>

          <div class="panel-section filters-section">
            <p class="section-index">02 <span>/</span> PÉRIODE & SOURCES</p>
            <div class="filter-grid">
              <label class="filter-field">
                <span>Année</span>
                <input v-model="selectedYear" type="number" min="2000" max="2100" placeholder="Toutes" />
              </label>
              <label class="filter-field">
                <span>Mois</span>
                <select v-model="selectedMonth">
                  <option value="">Tous</option>
                  <option v-for="month in monthOptions" :key="month.value" :value="month.value">
                    {{ month.label }}
                  </option>
                </select>
              </label>
            </div>
            <details v-if="sources.length" class="source-filters">
              <summary><span>Sources</span><span>{{ sourceFilterLabel }}</span></summary>
              <div class="source-filter-list">
                <label v-for="source in sources" :key="source.id">
                  <input
                    type="checkbox"
                    :checked="selectedSourceIds.includes(source.id)"
                    @change="toggleSource(source.id, $event)"
                  />
                  {{ source.label }}
                </label>
              </div>
            </details>
            <div class="filter-actions">
              <button class="filter-apply" type="button" :disabled="loading" @click="loadScoreMap">
                Appliquer les filtres
              </button>
              <button class="filter-reset" type="button" @click="clearFilters">Réinitialiser</button>
            </div>
          </div>

          <div v-if="isCazalis" class="panel-section weights-section">
            <div class="weights-heading">
              <div>
                <p class="section-index">03 <span>/</span> PONDÉRATION</p>
                <h2>Poids des sources</h2>
              </div>
              <span class="weight-range">Part / 100 %</span>
            </div>
            <p class="weight-method">Corrélation estivale avec les éco-compteurs; seuil r &gt; 0,25.</p>
            <div v-if="cazalisSources.length" class="source-list">
              <div v-for="source in cazalisSources" :key="source.id" class="source-weight">
                <span class="source-name">
                  <span>{{ source.label }}</span>
                  <output>{{ Number(scoreData?.source_weights?.[source.id] ?? 0) }}%</output>
                </span>
                <span class="weight-track" aria-hidden="true">
                  <span :style="{ width: `${scoreData?.source_weights?.[source.id] ?? 0}%` }"></span>
                </span>
              </div>
            </div>
            <p v-if="scoreData && !hasPositiveCazalisWeight" class="empty-sources">
              Aucune source ne dépasse le seuil BTA dans les références estivales disponibles.
            </p>
            <p v-else-if="!cazalisSources.length" class="empty-sources">Sources BTA indisponibles.</p>
          </div>

          <div class="panel-section selected-section">
            <p class="section-index">{{ isCazalis ? '04' : '03' }} <span>/</span> MAILLE SÉLECTIONNÉE</p>
            <template v-if="selectedArea">
              <h2 class="selected-name">Maille {{ selectedArea.id }}</h2>
              <div class="selected-value">
                <strong>{{ formatScore(getScore(selectedArea.properties)) }}</strong>
                <span>{{ scoreUnit }}</span>
              </div>
              <p class="selected-code">{{ formatScore(selectedArea.properties.counts) }} passages mesurés</p>
              <p class="selected-code">
                {{ formatScore(selectedArea.properties.count_segment) }} segment ·
                {{ formatScore(selectedArea.properties.count_presence) }} présence
              </p>
            </template>
            <p v-else class="section-note">Cliquez sur une maille pour consulter son score.</p>
          </div>

          <div class="panel-footer">
            <span class="data-mark"></span>
            <span>Données territoriales · Référentiel M1</span>
          </div>
        </aside>

        <section class="map-panel" aria-label="Carte des scores">
          <div class="map-header">
            <div class="map-title-wrap">
              <span class="map-overline">CARTE INTERACTIVE</span>
              <h2>{{ indicatorTitle }}</h2>
            </div>
            <div class="map-actions">
              <span class="projection-tag">WGS 84</span>
              <button class="fit-button" type="button" @click="fitToScores">Recentrer</button>
            </div>
          </div>

          <div ref="mapElement" class="map-canvas">
            <div v-if="loading" class="map-loading"><span class="loading-ring"></span>Chargement des mailles</div>
            <div v-if="errorMessage" class="map-error" role="alert">
              <strong>Carte indisponible</strong>
              <span>{{ errorMessage }}</span>
              <button type="button" @click="loadScoreMap">Réessayer</button>
            </div>
            <div v-if="scoreData && scoreFeatures.length && !hasNonZeroScores" class="zero-score-state">
              <span>0</span>
              <div><strong>Aucun passage compté</strong><small>Dans l’emprise visible</small></div>
            </div>
            <div v-if="scoreData && !scoreFeatures.length" class="zero-score-state">
              <span>—</span>
              <div><strong>Aucune donnée</strong><small>Modifiez la période ou les sources</small></div>
            </div>
            <div v-if="scoreFeatures.length" class="map-legend">
              <div class="legend-heading"><span>INTENSITÉ DU SCORE</span><span>{{ scoreUnit }}</span></div>
              <div class="legend-swatches">
                <i v-for="color in palette" :key="color" :style="{ backgroundColor: color }"></i>
              </div>
              <div class="legend-labels"><span>Faible</span><span>{{ formatScore(maxScore) }} max.</span></div>
            </div>
            <div v-if="selectedArea" class="map-selection-chip">
              <span class="selection-dot"></span>
              Maille {{ selectedArea.id }} <b>{{ formatScore(getScore(selectedArea.properties)) }}</b>
            </div>
          </div>
        </section>
      </section>
    </main>
  </div>
</template>

<style scoped>
.score-app { min-height: 100vh; color: #23372f; }
.topbar { height: 72px; display: flex; align-items: center; padding: 0 4.2vw; border-bottom: 1px solid #dfe4d9; background: rgba(253, 254, 250, .96); }
.brand { display: inline-flex; align-items: center; gap: 12px; color: inherit; text-decoration: none; }
.brand-mark { width: 40px; height: 40px; display: grid; place-items: center; background: #29473a; color: #f2d778; font: 700 12px/1 'Trebuchet MS', sans-serif; letter-spacing: 0; }
.brand-copy { display: grid; gap: 2px; }
.brand-copy strong { font: 700 14px/1.1 'Trebuchet MS', sans-serif; }
.brand-copy small { color: #77877e; font: 11px/1.2 'Trebuchet MS', sans-serif; }
.topbar-context { margin-left: auto; margin-right: 22px; display: flex; align-items: center; gap: 8px; color: #64746b; font-size: 12px; }
.status-dot, .data-mark { width: 8px; height: 8px; border-radius: 50%; background: #7aa76d; box-shadow: 0 0 0 3px #e4efdf; }
.refresh-button, .fit-button { display: inline-flex; align-items: center; gap: 8px; border: 1px solid #d7dfd4; background: #fff; color: #32473c; cursor: pointer; font: 600 12px 'Trebuchet MS', sans-serif; transition: background .2s, border-color .2s; }
.refresh-button { min-height: 36px; padding: 0 13px; }
.refresh-button:hover, .fit-button:hover { border-color: #9baa8f; background: #f5f8f0; }
.refresh-button:disabled { opacity: .55; cursor: wait; }
.refresh-glyph { color: #bd684d; font-size: 18px; line-height: 0; }
.page-content { max-width: 1680px; margin: 0 auto; padding: 30px 4.2vw 36px; }
.page-heading { min-height: 124px; display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; padding-bottom: 22px; }
.eyebrow, .section-index, .map-overline { color: #75867b; font: 700 9px/1.2 'Trebuchet MS', sans-serif; letter-spacing: 0; text-transform: uppercase; }
.eyebrow { display: flex; align-items: center; gap: 9px; margin-bottom: 10px; }
.eyebrow i { width: 18px; height: 1px; background: #cf7954; }
h1 { color: #263b32; font: 500 36px/.98 Georgia, 'Times New Roman', serif; letter-spacing: 0; }
.title-period { color: #d1734f; }
.intro-copy { margin-top: 10px; color: #758179; font-size: 13px; }
.headline-stats { display: flex; gap: 28px; padding-bottom: 3px; }
.headline-stats div { min-width: 90px; display: grid; gap: 5px; }
.headline-stats span { color: #7b8880; font-size: 10px; }
.headline-stats strong { color: #2f4439; font: 600 20px/1 Georgia, serif; }
.workspace { min-height: min(690px, calc(100vh - 260px)); display: grid; grid-template-columns: 284px minmax(0, 1fr); background: #fff; border: 1px solid #dfe5dc; box-shadow: 0 14px 40px rgba(37, 58, 46, .06); }
.control-panel { display: flex; flex-direction: column; border-right: 1px solid #e1e6de; background: #fbfcf8; }
.panel-section { padding: 24px 22px; border-bottom: 1px solid #e4e9e1; }
.section-index { margin-bottom: 12px; color: #9a6d55; }
.section-index span { padding: 0 4px; color: #c5cfc4; }
.panel-section h2 { margin-bottom: 13px; color: #283d33; font: 500 19px/1.1 Georgia, serif; letter-spacing: 0; }
.indicator-switch { display: grid; grid-template-columns: 1fr 1fr; gap: 3px; padding: 3px; background: #edf1e9; }
.indicator-switch button { min-height: 35px; border: 0; background: transparent; color: #718078; cursor: pointer; font: 600 11px 'Trebuchet MS', sans-serif; }
.indicator-switch button.active { background: #29473a; color: #f6f7ed; box-shadow: 0 2px 6px rgba(28, 52, 40, .12); }
.section-note { color: #7b8980; font-size: 11px; line-height: 1.55; }
.indicator-section .section-note { margin-top: 11px; }
.filters-section { padding-top: 20px; padding-bottom: 18px; }
.filter-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
.filter-field { display: grid; gap: 5px; color: #738178; font-size: 10px; }
.filter-field input, .filter-field select { width: 100%; min-width: 0; height: 32px; padding: 0 8px; border: 1px solid #dce3d8; border-radius: 0; background: #fff; color: #354a3e; font-size: 11px; }
.filter-field input::placeholder { color: #97a198; }
.source-filters { margin-top: 13px; border-top: 1px solid #e3e8e0; }
.source-filters summary { display: flex; justify-content: space-between; gap: 8px; padding: 10px 0; color: #52665a; cursor: pointer; font-size: 10px; list-style: none; }
.source-filters summary::-webkit-details-marker { display: none; }
.source-filters summary span:last-child { color: #8a968e; }
.source-filter-list { display: grid; gap: 8px; max-height: 150px; overflow-y: auto; padding: 0 2px 8px; }
.source-filter-list label { display: flex; align-items: center; gap: 7px; color: #617267; font-size: 10px; }
.source-filter-list input { accent-color: #578160; }
.filter-actions { display: flex; align-items: center; gap: 10px; margin-top: 14px; }
.filter-apply { min-height: 32px; padding: 0 10px; border: 0; background: #29473a; color: #f6f7ed; cursor: pointer; font: 600 10px 'Trebuchet MS', sans-serif; }
.filter-apply:disabled { opacity: .55; cursor: wait; }
.filter-reset { padding: 5px 0; border: 0; background: none; color: #8a7060; cursor: pointer; font-size: 10px; }
.weights-section { padding-top: 20px; padding-bottom: 18px; }
.weights-heading { display: flex; align-items: flex-end; justify-content: space-between; }
.weights-heading .section-index { margin-bottom: 8px; }
.weights-heading h2 { margin-bottom: 0; font-size: 17px; }
.weight-range { padding-bottom: 2px; color: #859087; font-size: 9px; }
.weight-method { margin-top: 9px; color: #879188; font-size: 9px; line-height: 1.45; }
.source-list { display: grid; gap: 13px; max-height: 204px; overflow-y: auto; margin: 19px -2px 17px 0; padding-right: 7px; }
.source-weight { display: grid; gap: 6px; }
.source-name { display: flex; justify-content: space-between; align-items: center; color: #56685d; font-size: 10px; }
.source-name output { color: #bd694e; font: 700 10px 'Trebuchet MS', sans-serif; font-variant-numeric: tabular-nums; }
.weight-track { height: 4px; overflow: hidden; background: #e6ebe2; }
.weight-track span { display: block; height: 100%; background: #6b9470; transition: width .25s ease; }
.empty-sources { margin: 16px 0; color: #9a614c; font-size: 11px; }
.selected-section { min-height: 130px; }
.selected-section .section-note { margin-top: 8px; }
.selected-name { margin: 0 0 12px !important; font-size: 18px !important; }
.selected-value { display: flex; align-items: baseline; gap: 7px; }
.selected-value strong { color: #29473a; font: 500 28px/1 Georgia, serif; }
.selected-value span, .selected-code { color: #7c8981; font-size: 10px; }
.selected-code { margin-top: 7px; }
.panel-footer { display: flex; align-items: center; gap: 9px; margin-top: auto; padding: 17px 22px; color: #839087; font-size: 9px; }
.panel-footer .data-mark { width: 6px; height: 6px; box-shadow: none; }
.map-panel { min-width: 0; display: flex; flex-direction: column; }
.map-header { min-height: 65px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 0 20px; border-bottom: 1px solid #e3e8e0; }
.map-title-wrap { display: grid; gap: 5px; }
.map-overline { color: #9a705b; font-size: 8px; }
.map-header h2 { color: #33483d; font: 500 16px/1 Georgia, serif; letter-spacing: 0; }
.map-actions { display: flex; align-items: center; gap: 9px; }
.projection-tag { padding: 5px 7px; background: #f1f4ec; color: #78877c; font: 700 8px 'Trebuchet MS', sans-serif; }
.fit-button { min-height: 30px; padding: 0 10px; font-size: 10px; }
.map-canvas { position: relative; flex: 1; min-height: 520px; background: #e9eee5; isolation: isolate; }
.map-loading { position: absolute; z-index: 500; top: 16px; left: 50%; display: flex; align-items: center; gap: 9px; transform: translateX(-50%); padding: 9px 13px; background: rgba(255,255,255,.95); color: #46594d; box-shadow: 0 3px 14px rgba(30,48,38,.12); font-size: 11px; }
.loading-ring { width: 12px; height: 12px; border: 2px solid #dce5d8; border-top-color: #d97854; border-radius: 50%; animation: spin .8s linear infinite; }
.map-error { position: absolute; z-index: 600; top: 18px; left: 50%; width: min(350px, calc(100% - 32px)); display: grid; gap: 8px; transform: translateX(-50%); padding: 14px 16px; background: #fffaf6; border-left: 3px solid #d97854; box-shadow: 0 4px 18px rgba(42,54,43,.12); color: #80513f; font-size: 11px; }
.map-error strong { color: #4a3e34; font: 600 15px Georgia, serif; }
.map-error button { justify-self: start; padding: 5px 0; border: 0; background: none; color: #b95d3d; cursor: pointer; font: 700 10px 'Trebuchet MS', sans-serif; }
.zero-score-state { position: absolute; z-index: 500; top: 14px; left: 14px; display: flex; align-items: center; gap: 9px; padding: 9px 12px; background: rgba(255,255,252,.96); border-left: 2px solid #d97854; box-shadow: 0 3px 12px rgba(34,54,40,.1); }
.zero-score-state > span { color: #bd694e; font: 500 21px/1 Georgia, serif; }
.zero-score-state div { display: grid; gap: 2px; }
.zero-score-state strong { color: #46594d; font: 600 10px 'Trebuchet MS', sans-serif; }
.zero-score-state small { color: #89938b; font-size: 9px; }
.map-legend { position: absolute; z-index: 500; right: 16px; bottom: 24px; width: 188px; padding: 12px 13px; background: rgba(255,255,252,.96); border: 1px solid rgba(215,224,210,.9); box-shadow: 0 4px 15px rgba(34,54,40,.11); }
.legend-heading { display: flex; justify-content: space-between; gap: 6px; color: #79867c; font: 700 8px 'Trebuchet MS', sans-serif; }
.legend-heading span:last-child { color: #ac7158; font-weight: 500; text-transform: none; }
.legend-swatches { display: grid; grid-template-columns: repeat(5, 1fr); gap: 2px; margin-top: 10px; }
.legend-swatches i { height: 9px; }
.legend-labels { display: flex; justify-content: space-between; margin-top: 5px; color: #7e8b81; font-size: 9px; }
.map-selection-chip { position: absolute; z-index: 500; top: 14px; left: 14px; display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: rgba(255,255,252,.96); box-shadow: 0 3px 12px rgba(34,54,40,.1); color: #56695c; font-size: 10px; }
.map-selection-chip b { color: #bd694e; font-variant-numeric: tabular-nums; }
.selection-dot { width: 7px; height: 7px; border-radius: 50%; background: #d97854; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (min-width: 1500px) { .map-canvas { min-height: 650px; } }
@media (max-width: 900px) {
  .page-content { padding: 24px 20px 28px; }
  .workspace { grid-template-columns: 250px minmax(0, 1fr); }
  .panel-section { padding-right: 17px; padding-left: 17px; }
  .headline-stats { gap: 16px; }
}
@media (max-width: 680px) {
  .topbar { height: 62px; padding: 0 16px; }
  .brand-mark { width: 35px; height: 35px; }
  .brand-copy small { display: none; }
  .topbar-context { margin-right: 11px; font-size: 9px; }
  .refresh-button { width: 36px; min-height: 36px; justify-content: center; padding: 0; overflow: hidden; font-size: 0; }
  .refresh-glyph { font-size: 20px; }
  .page-content { padding: 22px 12px; }
  .page-heading { min-height: auto; display: block; padding: 0 4px 17px; }
  h1 { font-size: 32px; }
  .intro-copy { max-width: 350px; font-size: 11px; }
  .headline-stats { justify-content: flex-start; gap: 25px; margin-top: 19px; }
  .headline-stats div { min-width: 75px; }
  .headline-stats strong { font-size: 17px; }
  .workspace { display: flex; flex-direction: column; }
  .control-panel { order: 2; border-top: 1px solid #e1e6de; border-right: 0; }
  .map-panel { order: 1; }
  .map-header { min-height: 58px; padding: 0 12px; }
  .map-header h2 { font-size: 14px; }
  .map-canvas { min-height: 58vh; }
  .projection-tag { display: none; }
  .map-legend { right: 9px; bottom: 17px; width: 158px; padding: 10px; }
  .panel-section { padding: 20px 18px; }
  .panel-footer { padding: 14px 18px; }
  .source-list { max-height: 180px; }
}
</style>
