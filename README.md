# Workshop 2026

This repository contains a web application for publishing and displaying visitor frequentation data, either combined with or side by side with biodiversity data.


The data served are :
- **Frequentation data.** From outdoor traces, hike trails to _eco-compteur_ data
- **Naturalist data** Observation of species, natural habitats


To do this, we propose a stack composed of :
- A database models based on exchange standards for naturalist and frequentation data (PostgreSQL database + PostGIS)
- An API allowing any data-visualisation library or app to easily retrieved data (Django + Django-RestFramework)
- A integrated visual interface (VueJS)


## Requirements

- **Docker** This app was envisioned to be used with Docker. Follow the [official documentation](https://docs.docker.com/get-started/get-docker/) if Docker is not setup on your machine.


### Development requirements

- **Python** To setup the virtual environnement for Python, we recommend that you use `uv` ([Installation instructions](https://docs.astral.sh/uv/getting-started/installation/))
- **Node.js** If not installed, you can setup the recommended version of node using NVM and the `.nvmrc` file.
   ```sh
   cd frontend
   nvm install
   nvm use 
   ```
   If nvm is not installed on your computer, follow the [official documentation](https://nodejs.org/en/download) provided by Node.js


## Get started

To run the dev stack, 

```sh
docker compose -f docker-compose-dev.yaml up -d
```

> [!NOTE]
> An easy way of listening to changes in requirements and DockerFile is to use the `watch` target
> ```sh
> docker compose -f docker-compose-dev.yaml watch
> ```

To stop the stack,

```sh
docker compose -f docker-compose-dev.yaml down
```

To stop the stack and erase the database

```sh
docker compose -f docker-compose-dev.yaml down -v 
```

## Load demonstration traffic data

Start the development stack, then load the sample traffic data with the Django management command:

```sh
docker compose -f docker-compose-dev.yaml exec web python backend/manage.py load_traffic_demo
```

The command runs `backend/workshop2026/processing/insert_traffic_data.sql`. The script creates five synthetic counters or segments in the first three 1 km grid cells of ref_geo, with counts on the 5th, 15th and 25th of January–March 2023 (and 2024 for one counter). It is safe to rerun: only rows with the script's `demo_m1_*` external IDs are replaced. These records are sample data, not real observations.

Counts and scores per 1 km grid cell are computed on the fly from the measures. The cells of each counting object are kept in `traffic.counting_object_areas` by a database trigger. If ref_geo was loaded or reloaded after the counting objects, rebuild that table:

```sh
docker compose -f docker-compose-dev.yaml exec web python backend/manage.py sync_counting_object_areas
```
