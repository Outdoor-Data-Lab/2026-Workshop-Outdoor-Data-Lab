import { afterEach, describe, expect, it, vi } from 'vitest'

import { getSynthesisAreasForMap, getTrafficAreasForMap } from '@/api/traffic'

function cell(id: number, cazalis: number | { score: number; source_weights: object }) {
  return {
    type: 'Feature',
    id,
    geometry: { type: 'MultiPolygon', coordinates: [] },
    properties: { counts: 1, count_segment: 0, count_presence: 1, score: { cazalis } },
  }
}

const first = '/api/traffic/areas?scores=cazalis&limit=1000'
const second = 'http://localhost:5173/api/traffic/areas?scores=cazalis&limit=1000&offset=1000'
const responses: Record<string, unknown> = {
  [first]: { type: 'FeatureCollection', count: 2, features: [cell(1, 12.4)], next: second },
  // Score avec ses détails : un objet.
  [second]: {
    type: 'FeatureCollection',
    count: 2,
    features: [cell(2, { score: 30, source_weights: { 1: 0.5 } })],
    next: null,
  },
}

describe('getTrafficAreasForMap', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads every page and colors by the cazalis score', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => new Response(JSON.stringify(responses[url]))),
    )
    const objects = await getTrafficAreasForMap()

    expect(objects.map((o) => [o.id, o.value])).toEqual([
      [1, 12.4],
      [2, 30],
    ])
    expect(objects[0]!.label).toBe('Cell 1')
  })

  it('sends the months of a season, repeated', async () => {
    const fetch = vi.fn(
      async (_url: string) =>
        new Response(JSON.stringify({ type: 'FeatureCollection', features: [] })),
    )
    vi.stubGlobal('fetch', fetch)
    await getTrafficAreasForMap({ months: [12, 1, 2] })

    expect(fetch.mock.calls[0]![0]).toContain('months=12&months=1&months=2')
  })
})

describe('getSynthesisAreasForMap', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('asks for the synthesis score and keeps only the cells at 1', async () => {
    const fetch = vi.fn(
      async (_url: string) =>
        new Response(
          JSON.stringify({
            type: 'FeatureCollection',
            features: [1, 0, 1].map((synthesis, i) => ({
              type: 'Feature',
              id: i + 1,
              geometry: { type: 'MultiPolygon', coordinates: [] },
              properties: { counts: 1, count_segment: 0, count_presence: 1, score: { synthesis } },
            })),
            next: null,
          }),
        ),
    )
    vi.stubGlobal('fetch', fetch)
    const objects = await getSynthesisAreasForMap({ areaId: 650252 })

    expect(fetch.mock.calls[0]![0]).toBe(
      '/api/traffic/areas?scores=synthesis&area_id=650252&limit=1000',
    )
    expect(objects.map((o) => [o.id, o.layer, o.value])).toEqual([
      [1, 'traffic/synthesis', undefined],
      [3, 'traffic/synthesis', undefined],
    ])
  })
})
