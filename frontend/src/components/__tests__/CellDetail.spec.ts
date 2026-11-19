import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import CellDetail from '@/components/CellDetail.vue'
import { i18n } from '@/i18n'
import type { MapObject } from '@/types/mapObject'

const cell: MapObject = {
  key: 'traffic/area:7',
  id: 7,
  domain: 'traffic',
  layer: 'traffic/area',
  label: 'Cell 7',
  value: 42.4,
  geometry: { type: 'MultiPolygon', coordinates: [] },
}

const traffic = {
  type: 'Feature',
  id: 7,
  properties: {
    counts: 1500,
    // Le score cazalis est un objet : sa valeur et ses détails (poids par id de source).
    score: { cazalis: { score: 42.4, source_weights: { 3: 100 }, reference_counters: 12 } },
    sources: [
      {
        id: 2,
        code: 'ecocompteur',
        label: 'Eco-Compteur',
        absolute: true,
        count: 1000,
        first_data: '2024-07-01T10:00:00Z',
        latest_data: '2024-07-31T10:00:00Z',
        length_km: null,
        person_km: null,
      },
      {
        id: 3,
        code: 'strava',
        label: 'Strava',
        absolute: false,
        count: 500,
        first_data: '2021-07-01T10:00:00Z',
        latest_data: '2024-07-01T10:00:00Z',
        length_km: 12.44,
        person_km: 1340.52,
      },
    ],
  },
}
const offers = {
  count: 2,
  results: [
    { id: 1, name: 'Tour du lac', practice_label: 'Randonnée', source_label: 'Geotrek' },
    { id: 2, name: 'Col', practice_label: 'Randonnée', source_label: 'Geotrek' },
  ],
}
const taxa = {
  type: 'Feature',
  id: 7,
  properties: {
    taxa: [
      {
        cd_ref: 92,
        lb_nom: 'Salamandra salamandra',
        nom_vern: 'Salamandre tachetée',
        protection: [
          { lb_type_statut: 'Protection nationale', code_statut: 'FRAR3', label_statut: '' },
        ],
        threatened: [
          { lb_type_statut: 'Liste rouge nationale', code_statut: 'VU', label_statut: '' },
        ],
        count: 4,
        date_min: '2017-04-07',
        date_max: '2024-03-13',
      },
    ],
  },
}

describe('CellDetail', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('summarizes the traffic score and sources, the protected or threatened taxa and the outdoor offers of the cell', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        const body = url.startsWith('/api/traffic/areas/7')
          ? traffic
          : url.startsWith('/api/biodiversity/list_taxa/7')
            ? taxa
            : offers
        return new Response(JSON.stringify(body))
      }),
    )
    const wrapper = mount(CellDetail, { props: { cell }, global: { plugins: [i18n] } })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Traffic42 (between 0 and 100)')
    expect(text).toContain('Outdoor2 offers')
    expect(text).toContain('Regulatory zoningcoming soon')
    expect(text).toContain('Eco-Compteur : 1,000 passages counted absolute · 2024')
    expect(text).toContain(
      'Strava : 500 trips summed over the segments of the cell relative · 2021–2024',
    )
    expect(text).toContain('Reference source: it is used to weight the others')
    expect(text).toContain('Weight in the score: 100%')
    expect(text).toContain('Weights estimated on 12 eco-counters.')
    expect(text).toContain('12.4 km of tracks in the cell · 1,340.5 person·km')
    expect(text).not.toContain('null km')
    expect(text).toContain('Biodiversity1 protected or threatened taxon')
    expect(text).toContain(
      'Salamandre tachetée Salamandra salamandraprotected · threatened (VU) · 4 observations · 2017–2024',
    )
    expect(text).toContain('Randonnée (2)')
  })
})
