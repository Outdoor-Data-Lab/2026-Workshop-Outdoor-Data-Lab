# OutdoorDataLab

OutdoorDataLab is a web application for publishing and displaying visitor traffic
data, either combined with or shown alongside biodiversity data.

The application provides:

- data models based on exchange standards for biodiversity and visitor traffic
  data, backed by PostgreSQL and PostGIS;
- a Django REST API for accessing and visualizing the data;
- a Vue.js web interface with an interactive map.

## Getting started

Start with the [installation guide](install.md) to run OutdoorDataLab locally or
deploy it to a production server.

The data administration guides explain how to:

- [import data](imports.md);
- [configure external GeoJSON layers](external-layers.md);
- [control the order of layers on the map](layer-order.md).
