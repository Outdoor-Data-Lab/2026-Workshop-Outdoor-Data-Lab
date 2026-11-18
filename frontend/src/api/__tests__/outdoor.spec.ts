import { describe, expect, it } from 'vitest'

import { offerToMapObject, type OfferFeature } from '@/api/outdoor'

function offer(name: string): OfferFeature {
  return {
    type: 'Feature',
    id: 279,
    geometry: { type: 'Point', coordinates: [6.2, 44.9] },
    properties: { name, external_id: '903297', practice_label: 'Hiking' },
  } as OfferFeature
}

describe('offerToMapObject', () => {
  it('labels the offer by its name and shows its practice', () => {
    const object = offerToMapObject(offer('Le lac de la Douche'))

    expect(object.label).toBe('Le lac de la Douche')
    expect(object.attributes).toEqual({ Practice: 'Hiking' })
  })

  it('falls back to the id of the source without a name', () => {
    expect(offerToMapObject(offer('')).label).toBe('903297')
  })
})
