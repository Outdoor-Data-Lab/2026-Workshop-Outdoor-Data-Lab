/** Saisons météorologiques, toutes années confondues : des mois de l'année (hiver : décembre à février). */
export type Season = 'winter' | 'spring' | 'summer' | 'autumn'

export const SEASON_MONTHS: Record<Season, number[]> = {
  winter: [12, 1, 2],
  spring: [3, 4, 5],
  summer: [6, 7, 8],
  autumn: [9, 10, 11],
}
