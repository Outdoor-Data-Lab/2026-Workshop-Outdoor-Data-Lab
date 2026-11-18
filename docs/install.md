# Installation

## Requirements

- Docker Engine with the Docker Compose plugin (`docker compose`).
- For production, a server reachable on ports 80 and 443, and a domain name
  whose DNS records point to that server.

Check that Docker is installed:

```sh
docker --version
docker compose version
```

The stack always uses `docker-compose.yaml` together with the file for the
selected environment:

- `docker-compose-dev.yaml` for development;
- `docker-compose-prod.yaml` for production.

The `COMPOSE_FILE` variable in `.env` selects the environment.

## Development quickstart

1. Create the local configuration:

   ```sh
   cp .env.sample .env
   ```

2. In `.env`, keep the development configuration and replace the example
   secrets:

   ```dotenv
   COMPOSE_FILE=docker-compose.yaml:docker-compose-dev.yaml
   POSTGRES_PASSWORD=a-local-password
   DJANGO_SECRET_KEY=a-local-secret-key
   TAXHUB_SECRET_KEY=another-local-secret-key
   ```

3. Build and start the containers:

   ```sh
   docker compose up -d --build
   ```

   On the first start, the `taxhub` service initializes the TaxHub/ref_geo
   schemas and imports TaxRef. This may take several minutes.

4. Wait for initialization to finish, then apply the Django migrations:

   ```sh
   docker compose wait taxhub
   docker compose exec web python backend/manage.py migrate
   ```

URLs:

* The frontend application is then available at <http://localhost:5173>
* The backend API is at <http://localhost:8000/api/>. There is a Swagger documentation also available at <http://localhost:8000/api/docs/>.
* The backoffice is available at <http://localhost:8000/admin/>

To synchronize source changes and automatically rebuild images when
dependencies change:

```sh
docker compose watch
```

To follow the logs or stop the environment:

```sh
docker compose logs -f
docker compose down
```

## Production quickstart

1. Clone the repository on the server, then create the configuration:

   ```sh
   cp .env.sample .env
   ```

2. In `.env`, enable the production override and set the domain, the Let's
   Encrypt contact address, and strong secrets:

   ```dotenv
   COMPOSE_FILE=docker-compose.yaml:docker-compose-prod.yaml
   POSTGRES_PASSWORD=<strong-password>
   DJANGO_SECRET_KEY=<strong-secret-key>
   TAXHUB_SECRET_KEY=<another-strong-secret-key>
   DOMAIN=myapp.example.org
   ACME_EMAIL=admin@example.org
   ```

   `DOMAIN` must contain only the hostname, without `https://` or a path. The
   `.env` file contains secrets and must not be committed.

   Gunicorn uses three worker processes and two threads per worker by default.
   Adjust its capacity and runtime safeguards in `.env` when needed:

   ```dotenv
   WEB_CONCURRENCY=3
   GUNICORN_CMD_ARGS=--threads 2 --timeout 120 --graceful-timeout 30 --max-requests 1000 --max-requests-jitter 100
   ```

   Approximate request concurrency is `WEB_CONCURRENCY x --threads`. Each
   worker is a separate process and therefore has its own memory footprint.
   Start with one worker per available CPU, measure worker memory under a
   representative load, then increase the worker count only while both CPU and
   RAM have enough headroom. Threads can improve concurrency for I/O-bound
   requests without multiplying process memory. `--max-requests` and its
   jitter periodically recycle workers to limit long-term memory growth.

   Any option accepted by Gunicorn can be added to `GUNICORN_CMD_ARGS`,
   including `--workers`. An explicit `--workers` value takes precedence over
   `WEB_CONCURRENCY`. These settings tune the application processes; Docker
   CPU and memory limits must be configured separately.

3. Build and start the stack:

   ```sh
   docker compose up -d --build
   ```

   Traefik automatically requests a Let's Encrypt certificate and redirects
   HTTP traffic to HTTPS. The Django container waits for TaxHub initialization,
   then automatically applies its migrations before starting Gunicorn.

4. Check the services and create the administrator account:

   ```sh
   docker compose ps
   docker compose logs --tail=100 taxhub web traefik
   docker compose exec web python backend/manage.py createsuperuser
   ```

The application is available at `https://<DOMAIN>`, the API at
`https://<DOMAIN>/api/`, and the Django administration interface at
`https://<DOMAIN>/admin/`.

To deploy a new version after updating the source code:

```sh
docker compose up -d --build
```

To stop the services without deleting data:

```sh
docker compose down
```

> [!CAUTION]
> `docker compose down -v` deletes the PostgreSQL data, uploaded files, and
> Let's Encrypt certificate volumes. Do not run this command in production
> without a backup.
