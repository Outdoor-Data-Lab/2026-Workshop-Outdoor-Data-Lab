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
    grid: 'Synthèse par mailles',
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
    trafficAreas: 'Fréquentation',
    fromZoom: 'Visible à partir du zoom {zoom} : zoomez sur la carte.',
    cellName: 'Maille',
    counterName: 'Compteur {id}',
    outdoorOffers: 'Offres outdoor',
    biodivAreas: 'Taxons menacés',
    none: 'Aucune',
    synthesisAreas: 'Croisement Fréquentation x Biodiversité',
    synthesisDescription:
      'Mailles au score de fréquentation supérieur à 40 avec au moins une espèce menacée (liste rouge nationale).',
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
    trafficAreas: 'Fréquentation par maille (score)',
    otherValues: 'Autre',
    synthesisAreas:
      'Croisement Fréquentation x Biodiversité : forte fréquentation et espèce menacée',
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
    taxa: 'aucune espèce protégée ou menacée (observée) | {n} espèce protégée ou menacée (observée) | {n} espèces protégées ou menacées (observées)',
    taxaList: 'Liste des taxons',
    habitats: 'Habitat',
    protected: 'protégé',
    threatened: 'menacé ({code})',
    observations: '{n} observation | {n} observations',
    taxaNote:
      'Protégé : protection nationale. Menacé : liste rouge nationale (RE, CR, EN, VU, EX). Observations GBIF et SINP.',
    offers: 'aucune offre | {n} offre | {n} offres',
    absolute: 'absolu',
    lengthLabel: 'Tracés dans la maille :',
    lengthValue: '{km} km',
    personKmLabel: 'Personnes·km :',
    kmHelp:
      'Personnes·km = passages × km de tracé dans la maille. Exemple : 100 passages sur un tracé de 2 km = 200 personnes·km ; sur un tracé qui ne fait que frôler la maille (0,1 km) = 10 personnes·km. Cela permet de comparer les mailles sans que les petits bouts de tracé pèsent autant que les longs.',
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
    score: {
      title: 'Comment le score est calculé',
      referenceLabel: 'Source de référence :',
      reference: "elle sert à pondérer les autres, elle n'entre pas dans le score.",
      weightLabel: 'Poids dans le score :',
      weightValue: '{weight} %',
      intro:
        'Le score (0 à 100) compare les mailles entre elles en combinant les sources, chacune pondérée selon sa fiabilité (méthode BiodivTourAlps).',
      counts: {
        title: "Fréquentation d'une source",
        eq: 'km cumulés des tracés dans la maille',
        text: '',
      },
      weights: {
        title: "Poids d'une source",
        eq: 'poids = 1 / (1 − r)',
        text: 'Le poids indique à quel point les données de la source sont en accord avec celles des éco-compteurs : r (de 0 à 1) mesure cet accord. Sous 0,25, la source est ignorée. La somme des poids fait 100.',
      },
      final: {
        title: 'Score de la maille',
        eq: 'score = Σ poids × (fréquentation − moyenne) ÷ écart-type',
        text: 'Les valeurs de chaque source est centrée et réduite (i.e. ce qui permet de mettre sur la même échelle les scores pour chaque source). Le total est ensuite ramené entre 0 et 100 (les valeurs extrêmes sont plafonnées).',
      },
      counters: 'Poids estimés sur {n} éco-compteurs.',
      credit:
        "Méthode de l'analyse de fréquentation BiodivTourAlps, développée par Victor Cazalis (Conservara) : {link}.",
      creditLink: 'scripts et rapports sur GitHub',
    },
  },
  notifications: {
    close: 'Fermer',
    withContext: '{context} : {message}',
  },
  about: {
    open: 'À propos',
    title: 'À propos',
    intro: [
      "Le développement maîtrisé des activités de pleine nature constitue un enjeu important pour les territoires, leurs acteurs et les gestionnaires d'espaces naturels. Il soulève également des questions croissantes en matière de préservation de la biodiversité, de gestion des flux de fréquentation et de conciliation des usages.",
      "C'est dans cette perspective qu'a été imaginé cet outil numérique, développé à partir de briques open source par les partenaires du collectif Outdoor Data Lab, à l'occasion du Workshop qui s'est déroulé du 16 au 19 novembre 2026 à Vallon Pont-d'Arc.",
      "Son ambition est de faciliter le croisement et l'analyse de données relatives aux pratiques outdoor et aux enjeux écologiques, afin de mieux prendre en compte les interactions entre fréquentation et biodiversité. Il vise ainsi à apporter une aide à la décision aux gestionnaires d'espaces protégés, aux collectivités et aux acteurs de l'offre outdoor, pour éclairer leurs choix d'aménagement, d'organisation et de gestion des activités.",
    ],
    schemaAlt:
      "Schéma de l'outil : les données de fréquentation, de biodiversité, d'offre outdoor et de zonages, et leurs sources, alimentent ODL.",
    outlook:
      'Conçu comme un outil évolutif, ce premier développement constitue une base de travail qui a vocation à être expérimentée, enrichie et appropriée par ses futurs utilisateurs dans un projet qui reste à structurer et financer.',
    repository: 'Consulter le dépôt GitHub de cet outil open source :',
    credits: 'Version 0.1 réalisée en novembre 2026 par :',
    funding:
      "Ce développement s'inscrit notamment dans le cadre du projet européen ALCOTRA BiodivTourAlps (projet n° 20140), qui a soutenu le hackathon préalable organisé en 2025, et du programme LIFE Biodiv'France – Sports & biodiversité, cofinancé par l'Union européenne et l'Office français de la biodiversité.",
    close: 'Fermer',
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
