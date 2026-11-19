import type en from './en'

export default {
  loading: 'Chargement',
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
    counter: 'Compteurs',
    segment: 'Segments et traces',
  },
  layers: {
    title: 'Couches',
    failed: '(échec)',
    trafficAreas: 'Fréquentation par maille',
    fromZoom: 'Visible à partir du zoom {zoom} : zoomez sur la carte.',
    cellName: 'Maille',
    counterName: 'Compteur {id}',
    outdoorOffers: 'Offres outdoor',
    biodivAreas: 'Taxons menacés par maille',
    loadError: 'Impossible de charger {label}',
  },
  season: {
    label: 'Saison',
    all: "Toute l'année",
    winter: 'Hiver (déc.–févr.)',
    spring: 'Printemps (mars–mai)',
    summer: 'Été (juin–août)',
    autumn: 'Automne (sept.–nov.)',
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
    close: 'Fermer',
  },
  items: {
    counter: 'Compteur',
    offer: 'Offre outdoor',
    cell: 'Maille',
    cellOfSize: 'Maille de {size}',
  },
  cell: {
    noTraffic: 'Pas de données de fréquentation sur cette maille.',
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
    km: '{km} km de tracés dans la maille · {personKm} personnes·km',
    kmHelp:
      'Personnes·km = passages × km de tracé dans la maille. Exemple : 100 passages sur un tracé de 2 km = 200 personnes·km ; sur un tracé qui ne fait que frôler la maille (0,1 km) = 10. Cela permet de comparer les mailles sans que les petits bouts de tracé pèsent autant que les longs.',
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
      "Absolu : tous les passages sont comptés. Relatif : seuls les usagers d'une application, pour comparer les mailles entre elles. Personnes·km : passages × km de tracé dans la maille.",
    score: {
      title: 'Comment le score est calculé',
      reference:
        "Source de référence : elle sert à pondérer les autres, elle n'entre pas dans le score.",
      weight: 'Poids dans le score : {weight} %',
      intro:
        'Le score (0 à 100) compare les mailles entre elles en combinant les sources, chacune pesée selon sa fiabilité (méthode BiodivTourAlps).',
      counts: {
        title: "Fréquentation d'une source",
        eq: 'passages × km de tracé dans la maille',
        text: 'Un tracé qui ne fait que frôler la maille compte peu.',
      },
      weights: {
        title: "Poids d'une source",
        eq: 'poids = 1 / (1 − r)',
        text: 'r (de 0 à 1) mesure à quel point la source suit les éco-compteurs. Sous 0,25, elle est ignorée. Les poids sont ramenés à un total de 100.',
      },
      final: {
        title: 'Score de la maille',
        eq: 'score = Σ poids × (fréquentation − moyenne) ÷ écart-type',
        text: 'Chaque source est comparée à la moyenne des mailles, puis le total est ramené entre 0 et 100 (les valeurs extrêmes sont plafonnées).',
      },
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
