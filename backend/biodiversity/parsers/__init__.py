# Format code -> parser class of the biodiversity imports (registered in commons
# by BiodiversityConfig.ready()). Paths, not classes: the parsers import commons models.
PARSERS = {
    "sinp": "biodiversity.parsers.sinp.SINPParser",
    "gbif": "biodiversity.parsers.gbif.GBIFParser",
}
