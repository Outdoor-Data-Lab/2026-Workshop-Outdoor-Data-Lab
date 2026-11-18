# Workshop 2026

This repository contains a web application for publishing and displaying visitor frequentation data, either combined with or side by side with biodiversity data.


The data served are :
- **Frequentation data.** From outdoor traces, hike trails to automatic counter data
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


## Configuration

Docker Compose files are chained through the `COMPOSE_FILE` variable of the `.env` file:

- `docker-compose.yaml`: base stack (database, TaxHub init job, Django, frontend)
- `docker-compose-dev.yaml`: development overrides (dev servers, exposed ports, watch, debug)
- `docker-compose-prod.yaml`: production overrides (Gunicorn, nginx, Traefik with HTTPS)

Create your `.env` from the sample and fill in the values:

```sh
cp .env.sample .env
```

## Get started

To run the dev stack (`COMPOSE_FILE=docker-compose.yaml:docker-compose-dev.yaml` in `.env`),

```sh
docker compose up -d
```

> [!NOTE]
> An easy way of listening to changes in requirements and DockerFile is to use the `watch` target
> ```sh
> docker compose watch
> ```

To stop the stack,

```sh
docker compose down
```

To stop the stack and erase the database (`db-data` volume)

```sh
docker compose down -v
```

## Deploy to production

On the server, with Docker installed, ports 80 and 443 open and the domain's DNS pointing to it:

```sh
cp .env.sample .env
```

In `.env`, set `COMPOSE_FILE=docker-compose.yaml:docker-compose-prod.yaml`, `DOMAIN`, `ACME_EMAIL` and strong secrets (`POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `TAXHUB_SECRET_KEY`). Then:

```sh
docker compose up -d --build
```

Traefik gets a Let's Encrypt certificate for `DOMAIN` and redirects HTTP to HTTPS. `/api`, `/admin` and `/static` go to Django, everything else to the frontend. Django migrations run when the `web` container starts, after the TaxHub init job has finished.

Create an admin account:

```sh
docker compose exec web python backend/manage.py createsuperuser
```

## Importer des données

Voir [docs/imports.md](docs/imports.md).

## Load demonstration traffic data

Start the development stack, then load the sample traffic data with the Django management command:

```sh
docker compose exec web python backend/manage.py load_traffic_demo
```

The command runs `backend/workshop2026/processing/insert_traffic_data.sql`. The script creates five synthetic counters or segments in the first three 1 km grid cells of ref_geo, with counts on the 5th, 15th and 25th of January–March 2023 (and 2024 for one counter). It is safe to rerun: only rows with the script's `demo_m1_*` external IDs are replaced. These records are sample data, not real observations.

Counts and scores per 1 km grid cell are computed on the fly from the measures. The cells of each counting object are kept in `traffic.counting_object_areas` by a database trigger. If ref_geo was loaded or reloaded after the counting objects, rebuild that table:

```sh
docker compose exec web python backend/manage.py sync_counting_object_areas
```
