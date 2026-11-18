import { describe, expect, it } from 'vitest'

import { referenceLabel } from '@/i18n'

describe('referenceLabel', () => {
  it('translates a known code and falls back to the API label otherwise', () => {
    expect(referenceLabel('countingObjectTypes', 'counter', 'Compteur')).toBe('Counter')
    expect(referenceLabel('countingObjectTypes', 'unknown', 'Inconnu')).toBe('Inconnu')
  })
})
