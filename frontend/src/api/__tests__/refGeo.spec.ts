import { afterEach, describe, expect, it, vi } from 'vitest'

import { searchAreas } from '@/api/refGeo'

function area(id_area: number, area_name: string, type_code: string) {
  return { id_area, area_name, area_code: String(id_area), type_code }
}

describe('searchAreas', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('puts the exact name first, then prefixes, and leaves grid cells out', async () => {
    // Ordre de l'API : alphabétique.
    const results = [
      area(1, 'Châteauneuf-sur-Isère', 'COM'),
      area(2, 'Isère', 'M0.5'),
      area(3, 'Isère', 'DEP'),
      area(4, 'Isère-Nord', 'MAS'),
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ count: 4, results }))),
    )

    const found = await searchAreas('isère')

    expect(found.map((a) => a.id_area)).toEqual([3, 4, 1])
  })
})
