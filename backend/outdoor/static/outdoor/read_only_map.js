// Loaded after Django's OLMapWidget.js: a map whose options have read_only
// (outdoor.admin.ReadOnlyMapWidget) gets no draw nor modify interaction, so its
// geometry can be viewed but not edited.
const createInteractions = MapWidget.prototype.createInteractions;
MapWidget.prototype.createInteractions = function () {
    if (!this.options.read_only) {
        createInteractions.call(this);
    }
};
