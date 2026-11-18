import { afterEach, describe, expect, it, vi } from 'vitest'

import { getTrafficAreasForMap } from '@/api/traffic'

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
    expect(objects[0]!.label).toBe('Cell 1: score 12')
  })
})
