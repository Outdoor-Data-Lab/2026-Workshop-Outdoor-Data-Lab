import type { Domain } from './mapObject'

/** Angle de lecture choisi dans le panneau gauche ; il décide des couches affichées. */
export type Concept = 'global' | 'traffic' | 'biodiversity'

/** Libellés : clés `concepts.<id>` des traductions. */
export const CONCEPTS: { id: Concept; domains: Domain[] }[] = [
  { id: 'global', domains: ['traffic', 'biodiversity'] },
  { id: 'traffic', domains: ['traffic'] },
  { id: 'biodiversity', domains: ['biodiversity'] },
]
