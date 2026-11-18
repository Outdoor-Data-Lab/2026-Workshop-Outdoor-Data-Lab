// Loaded after Django's OLMapWidget.js: a map whose options have read_only
// (outdoor.admin.ReadOnlyMapWidget) gets no draw nor modify interaction, so its
// geometry can be viewed but not edited. Its features are drawn bolder, and the
// initial zoom, fitted on the geometry, is capped: a point is shown in context.
const MAX_INITIAL_ZOOM = 15;
const createInteractions = MapWidget.prototype.createInteractions;
MapWidget.prototype.createInteractions = function () {
    if (!this.options.read_only) {
        createInteractions.call(this);
        return;
    }
    // Called by the constructor right after the view is fitted on the geometry.
    const view = this.map.getView();
    if (view.getZoom() > MAX_INITIAL_ZOOM) {
        view.setZoom(MAX_INITIAL_ZOOM);
    }
    const stroke = new ol.style.Stroke({ color: "#3399CC", width: 3 });
    this.featureOverlay.setStyle(
        new ol.style.Style({
            stroke: stroke,
            fill: new ol.style.Fill({ color: "rgba(51, 153, 204, 0.2)" }),
            image: new ol.style.Circle({
                radius: 8,
                stroke: stroke,
                fill: new ol.style.Fill({ color: "rgba(51, 153, 204, 0.5)" }),
            }),
        }),
    );
};
