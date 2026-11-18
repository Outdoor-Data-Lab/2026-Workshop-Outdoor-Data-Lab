import type { Domain } from './mapObject'

/** Angle de lecture choisi dans le panneau gauche ; il décide des couches affichées. */
export type Concept = 'global' | 'traffic' | 'biodiversity'

export const CONCEPTS: { id: Concept; label: string; domains: Domain[] }[] = [
  { id: 'global', label: 'Global', domains: ['traffic', 'biodiversity'] },
  { id: 'traffic', label: 'Traffic', domains: ['traffic'] },
  { id: 'biodiversity', label: 'Biodiversity', domains: ['biodiversity'] },
]
