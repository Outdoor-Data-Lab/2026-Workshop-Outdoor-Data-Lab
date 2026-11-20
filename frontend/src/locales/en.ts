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
    grid: 'Summary per grid cell',
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
    trafficAreas: 'Traffic',
    fromZoom: 'Visible from zoom {zoom}: zoom in on the map.',
    cellName: 'Cell',
    counterName: 'Counter {id}',
    outdoorOffers: 'Outdoor offers',
    biodivAreas: 'Threatened taxa',
    none: 'None',
    synthesisAreas: 'Traffic x Biodiversity crossing',
    synthesisDescription:
      'Grid cells with a traffic score above 40 and at least one threatened species (national red list).',
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
    trafficAreas: 'Traffic per grid cell (score)',
    otherValues: 'Other',
    synthesisAreas: 'Traffic x Biodiversity crossing: high traffic and threatened species',
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
    taxa: 'no protected or threatened species (observed) | {n} protected or threatened species (observed) | {n} protected or threatened species (observed)',
    taxaList: 'List of taxa',
    habitats: 'Habitat',
    protected: 'protected',
    threatened: 'threatened ({code})',
    observations: '{n} observation | {n} observations',
    taxaNote:
      'Protected: national protection. Threatened: national red list (RE, CR, EN, VU, EX). GBIF and SINP observations.',
    offers: 'no offer | {n} offer | {n} offers',
    absolute: 'absolute',
    lengthLabel: 'Tracks in the cell:',
    lengthValue: '{km} km',
    personKmLabel: 'Person·km:',
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
    score: {
      title: 'How the score is computed',
      referenceLabel: 'Reference source:',
      reference: 'it is used to weight the others and is not part of the score.',
      weightLabel: 'Weight in the score:',
      weightValue: '{weight}%',
      intro:
        'The score (0 to 100) compares cells with each other by combining the sources, each weighted by how reliable it is (BiodivTourAlps method).',
      counts: {
        title: "A source's frequentation",
        eq: 'cumulative km of tracks in the cell',
        text: 'A track that only grazes the cell counts for little.',
      },
      weights: {
        title: "A source's weight",
        eq: 'weight = 1 / (1 − r)',
        text: "The weight shows how closely the source's data agree with those of the eco-counters: r (0 to 1) measures that agreement. Below 0.25 the source is ignored. The weights add up to 100.",
      },
      final: {
        title: "The cell's score",
        eq: 'score = Σ weight × (frequentation − mean) ÷ standard deviation',
        text: 'The values of each source are normalised with a standardised variable (the mean of the cells is subtracted, then the result is divided by the standard deviation). The total is then rescaled to 0–100 (extreme values are capped).',
      },
      credit:
        'Method of the BiodivTourAlps frequentation analysis, developed by Victor Cazalis (Conservara): {link}.',
      creditLink: 'scripts and reports on GitHub',
      counters: 'Weights estimated on {n} eco-counters.',
    },
  },
  notifications: {
    close: 'Close',
    withContext: '{context}: {message}',
  },
  about: {
    open: 'About',
    title: 'About',
    intro: [
      'The controlled development of outdoor activities is a major issue for territories, their stakeholders and the managers of natural areas. It also raises growing questions about biodiversity conservation, visitor flow management and the reconciliation of uses.',
      'This digital tool was designed with this in mind. It was built from open source components by the partners of the Outdoor Data Lab collective, during the Workshop held from 16 to 19 November 2026 in Vallon Pont-d’Arc.',
      'It aims to make it easier to cross and analyse data on outdoor practices and ecological issues, so as to better take into account the interactions between visitor numbers and biodiversity. It thus seeks to support decision-making by protected area managers, local authorities and outdoor providers, to inform their choices in the planning, organisation and management of activities.',
    ],
    schemaAlt:
      'Diagram of the tool: visitor numbers, biodiversity, outdoor offer and zoning data, and their sources, feed ODL.',
    outlook:
      'Designed as an evolving tool, this first development is a working basis meant to be tested, enriched and taken over by its future users, in a project that is yet to be structured and funded.',
    repository: 'See the GitHub repository of this open source tool:',
    credits: 'Version 0.1 made in November 2026 by:',
    funding:
      "This development is part of the European ALCOTRA BiodivTourAlps project (project no. 20140), which supported the preliminary hackathon held in 2025, and of the LIFE Biodiv'France – Sports & Biodiversity programme, co-funded by the European Union and the French Biodiversity Agency (OFB).",
    close: 'Close',
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
