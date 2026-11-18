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
    sources: [
      {
        code: 'ecocompteur',
        label: 'Eco-Compteur',
        absolute: true,
        count: 1000,
        first_data: '2024-07-01T10:00:00Z',
        latest_data: '2024-07-31T10:00:00Z',
      },
      {
        code: 'strava',
        label: 'Strava',
        absolute: false,
        count: 500,
        first_data: '2021-07-01T10:00:00Z',
        latest_data: '2024-07-01T10:00:00Z',
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

describe('CellDetail', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('summarizes the traffic score and sources, and the outdoor offers of the cell', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        const body = url.startsWith('/api/traffic/areas/7') ? traffic : offers
        return new Response(JSON.stringify(body))
      }),
    )
    const wrapper = mount(CellDetail, { props: { cell }, global: { plugins: [i18n] } })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Traffic42/100')
    expect(text).toContain('Outdoor2 offers')
    expect(text).toContain('Regulatory zoningcoming soon')
    expect(text).toContain('Eco-Compteur : 1,000 passages counted absolute · 2024')
    expect(text).toContain(
      'Strava : 500 trips summed over the segments of the cell relative · 2021–2024',
    )
    expect(text).toContain('Randonnée (2)')
  })
})
