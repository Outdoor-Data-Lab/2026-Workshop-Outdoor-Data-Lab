# Format code -> parser class of the traffic imports (registered in commons by
# TrafficConfig.ready()). Paths, not classes: the parsers import commons models.
PARSERS = {
    "outdoorvision": "traffic.parsers.outdoorvision.OutdoorVisionParser",
    "strava": "traffic.parsers.strava.StravaParser",
    "counter": "traffic.parsers.compteur.CompteurParser",
    "inaturalist": "traffic.parsers.inaturalist.INaturalistParser",
}
