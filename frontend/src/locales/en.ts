/** Textes de référence : `fr.ts` doit avoir les mêmes clés (vérifié par le typage). */
export default {
  loading: 'Loading',
  concepts: {
    label: 'Concept',
    global: 'Global',
    traffic: 'Traffic',
    biodiversity: 'Biodiversity',
  },
  layerGroups: {
    traffic: 'Traffic',
    biodiversity: 'Biodiversity',
    outdoor: 'Outdoor',
    external: 'External layers',
  },
  /** Valeurs de référence de l'API, par code (repli : le libellé de l'API). */
  countingObjectTypes: {
    counter: 'Counters',
    segment: 'Segments and tracks',
  },
  layers: {
    title: 'Layers',
    failed: '(failed)',
    trafficAreas: 'Traffic per grid cell',
    fromZoom: 'Visible from zoom {zoom}: zoom in on the map.',
    cellName: 'Cell',
    counterName: 'Counter {id}',
    outdoorOffers: 'Outdoor offers',
    biodivAreas: 'Threatened taxa per grid cell',
    loadError: 'Could not load {label}',
  },
  season: {
    label: 'Season',
    all: 'All year',
    winter: 'Winter (Dec–Feb)',
    spring: 'Spring (Mar–May)',
    summer: 'Summer (Jun–Aug)',
    autumn: 'Autumn (Sep–Nov)',
  },
  areaFilter: {
    label: 'Area',
    placeholder: 'Search a municipality, a department…',
    noResults: 'No area found.',
    clear: 'Remove the area filter',
  },
  /** Types de zones `ref_geo`, par code (repli : le code). */
  areaTypes: {
    COM: 'Municipality',
    DEP: 'Department',
  },
  legend: {
    title: 'Legend',
    counters: 'Counters',
    trafficAreas: 'Traffic per grid cell (score)',
  },
  offer: {
    practice: 'Practice',
  },
  detail: {
    close: 'Close',
  },
  items: {
    counter: 'Counter',
    offer: 'Outdoor offer',
    cell: 'Grid cell',
    cellOfSize: '{size} grid cell',
  },
  cell: {
    noTraffic: 'No traffic data in this cell.',
    traffic: 'Traffic',
    biodiversity: 'Biodiversity',
    outdoor: 'Outdoor',
    zonings: 'Regulatory zoning',
    scoreRange: '(between 0 and 100)',
    soon: 'coming soon',
    taxa: 'no protected or threatened taxon | {n} protected or threatened taxon | {n} protected or threatened taxa',
    taxaList: 'List of taxa',
    protected: 'protected',
    threatened: 'threatened ({code})',
    observations: '{n} observation | {n} observations',
    taxaNote:
      'Protected: national protection. Threatened: national red list (RE, CR, EN, VU, EX). GBIF and SINP observations.',
    offers: 'no offer | {n} offer | {n} offers',
    absolute: 'absolute',
    relative: 'relative',
    km: '{km} km of tracks in the cell · {personKm} person·km',
    kmHelp:
      'Person·km = passages × km of track in the cell. Example: 100 passages on a 2 km track = 200 person·km; on a track that only grazes the cell (0.1 km) = 10. This lets cells be compared without short bits of track weighing as much as long ones.',
    /** What each source counts, by code. */
    units: {
      ecocompteur: '{n} passage counted | {n} passages counted',
      strava:
        '{n} trip on the segments of the cell | {n} trips summed over the segments of the cell',
      outdoorvision: '{n} GPS outing crossing the cell | {n} GPS outings crossing the cell',
      inaturalist: '{n} observer-day | {n} observer-days',
      other: '{n} measure | {n} measures',
    },
    countsNote:
      'Absolute: every passage is counted. Relative: only app users, to compare cells with each other. Person·km: passages × km of track in the cell.',
    score: {
      title: 'How the score is computed',
      reference: 'Reference source: it is used to weight the others and is not part of the score.',
      weight: 'Weight in the score: {weight}%',
      intro:
        'The score (0 to 100) compares cells with each other by combining the sources, each weighted by how reliable it is (BiodivTourAlps method).',
      counts: {
        title: "A source's frequentation",
        eq: 'passages × km of track in the cell',
        text: 'A track that only grazes the cell counts for little.',
      },
      weights: {
        title: "A source's weight",
        eq: 'weight = 1 / (1 − r)',
        text: 'r (0 to 1) is how closely the source follows the eco-counters. Below 0.25 it is ignored. Weights are scaled to a total of 100.',
      },
      final: {
        title: "The cell's score",
        eq: 'score = Σ weight × (frequentation − mean) ÷ standard deviation',
        text: 'Each source is compared to the mean of the cells, then the total is rescaled to 0–100 (extreme values are capped).',
      },
      counters: 'Weights estimated on {n} eco-counters.',
    },
  },
  notifications: {
    close: 'Close',
    withContext: '{context}: {message}',
  },
  errors: {
    network: 'Cannot reach the server. Check your connection.',
    server: 'The server is unavailable at the moment. Try again later.',
    notFound: 'Not found.',
    forbidden: 'You do not have access to this resource.',
    badRequest: 'Invalid request.',
    unexpectedStatus: 'Unexpected server response ({status}).',
    unexpected: 'An unexpected error occurred.',
    field: '{field}: {message}',
  },
}
