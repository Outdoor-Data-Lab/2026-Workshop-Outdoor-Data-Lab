class DynamicFieldsMixin:
    fields_query_param = "fields"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")
        if request is None or request.method not in ("GET", "HEAD", "OPTIONS"):
            return

        raw = request.query_params.get(self.fields_query_param)
        if not raw:
            return

        requested = {f.strip() for f in raw.split(",") if f.strip()}
        always_keep = {getattr(self.Meta, "geo_field", None)} - {None}

        for name in set(self.fields) - requested - always_keep:
            self.fields.pop(name)