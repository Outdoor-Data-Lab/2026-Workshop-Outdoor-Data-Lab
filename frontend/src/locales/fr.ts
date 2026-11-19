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
    biodiversity: 'Biodiversité',
    outdoor: 'Outdoor',
    external: 'Couches externes',
  },
  countingObjectTypes: {
    counter: 'Compteur',
    segment: 'Segments et traces',
  },
  layers: {
    loading: '(chargement)',
    failed: '(échec)',
    trafficAreas: 'Fréquentation par maille',
    fromZoom: 'Visible à partir du zoom {zoom} : zoomez sur la carte.',
    cellName: 'Maille',
    outdoorOffers: 'Offres outdoor',
    biodivAreas: 'Taxons protégés ou menacés par maille',
    biodivArea: 'Maille {name} : {count} taxons protégés ou menacés',
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
    scoreRange: '(entre 0 et 100)',
    soon: 'à venir',
    taxa: 'aucun taxon protégé ou menacé | {n} taxon protégé ou menacé | {n} taxons protégés ou menacés',
    taxaList: 'Liste des taxons',
    protected: 'protégé',
    threatened: 'menacé ({code})',
    observations: '{n} observation | {n} observations',
    taxaNote:
      'Protégé : protection nationale. Menacé : liste rouge nationale (RE, CR, EN, VU, EX). Observations GBIF et SINP.',
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
    score: {
      title: 'Comment le score est calculé',
      reference:
        "Source de référence : elle sert à pondérer les autres, elle n'entre pas dans le score.",
      weight: 'Poids dans le score : {weight} %',
      intro:
        "Le score (0 à 100) combine les sources de fréquentation, chacune comptant d'autant plus qu'elle reproduit fidèlement les éco-compteurs (méthode BiodivTourAlps, V. Cazalis).",
      step1:
        'Poids : pour chaque source, on corrèle (Pearson) ses comptages autour des éco-compteurs avec la moyenne journalière de ces derniers en été (juin à septembre, depuis 2021, quinzaines de plus de 10 jours de données).',
      step2:
        'Une source dont la corrélation r ne dépasse pas 0,25 a un poids nul ; sinon son poids brut vaut 1 / (1 − r). Les poids bruts sont ramenés à un total de 100.',
      step3:
        "Chaque source est standardisée : pour chaque maille, on retire la moyenne de toutes les mailles et on divise par l'écart-type (z-score ; une maille sans donnée de la source compte pour 0 passage).",
      step4:
        'Les z-scores sont additionnés avec leur poids, les valeurs au-dessus du 98e centile sont plafonnées, puis le tout est ramené entre 0 et 100.',
      equation: 'score = normalisation 0-100( Σ poids(source) × z-score(source, maille) )',
      counters: 'Poids estimés sur {n} éco-compteurs.',
    },
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
