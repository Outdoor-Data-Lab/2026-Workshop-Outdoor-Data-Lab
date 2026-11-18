import type en from './en'

export default {
  concepts: {
    label: 'Concept',
    global: 'Global',
    traffic: 'Fréquentation',
    biodiversity: 'Biodiversité',
  },
  layerGroups: {
    traffic: 'Fréquentation',
    outdoor: 'Outdoor',
    external: 'Couches externes',
  },
  countingObjectTypes: {
    counter: 'Compteur',
    segment: 'Segment',
  },
  layers: {
    loading: '(chargement)',
    failed: '(échec)',
    trafficAreas: 'Fréquentation par maille',
    trafficArea: 'Maille {id} : score {score}',
    outdoorOffers: 'Offres outdoor',
    loadError: 'Impossible de charger {label}',
  },
  areaFilter: {
    label: 'Zone',
    placeholder: 'Rechercher une commune, un département…',
    noResults: 'Aucune zone trouvée.',
    clear: 'Retirer le filtre de zone',
  },
  areaTypes: {
    COM: 'Commune',
    DEP: 'Département',
  },
  legend: {
    title: 'Légende',
    counters: 'Compteurs',
    trafficAreas: 'Fréquentation par maille (score)',
  },
  offer: {
    practice: 'Pratique',
  },
  detail: {
    title: 'Détail',
    empty: 'Sélectionnez un objet sur la carte.',
  },
  cell: {
    loading: 'Chargement…',
    traffic: 'Fréquentation',
    biodiversity: 'Biodiversité',
    outdoor: 'Outdoor',
    zonings: 'Zonage réglementaire',
    soon: 'à venir',
    offers: 'aucune offre | {n} offre | {n} offres',
    absolute: 'absolu',
    relative: 'relatif',
    /** Ce que compte chaque source, par code. */
    units: {
      ecocompteur: '{n} passage compté | {n} passages comptés',
      strava:
        '{n} trajet sur les tronçons de la maille | {n} trajets cumulés sur les tronçons de la maille',
      outdoorvision:
        '{n} sortie GPS qui traverse la maille | {n} sorties GPS qui traversent la maille',
      inaturalist: '{n} observateur-jour | {n} observateurs-jours',
      other: '{n} mesure | {n} mesures',
    },
    countsNote:
      "Absolu : le compteur compte tous les passages. Relatif : seuls les usagers d'une application sont comptés ; ces chiffres servent à comparer les mailles entre elles. Le score combine les sources, pondérées selon leur concordance avec les éco-compteurs.",
  },
  notifications: {
    close: 'Fermer',
    withContext: '{context} : {message}',
  },
  errors: {
    network: 'Connexion au serveur impossible. Vérifiez votre réseau.',
    server: 'Le serveur est indisponible pour le moment. Réessayez plus tard.',
    notFound: 'Élément introuvable.',
    forbidden: "Vous n'avez pas accès à cette ressource.",
    badRequest: 'Requête invalide.',
    unexpectedStatus: 'Réponse inattendue du serveur ({status}).',
    unexpected: 'Une erreur inattendue est survenue.',
    field: '{field} : {message}',
  },
} satisfies typeof en
