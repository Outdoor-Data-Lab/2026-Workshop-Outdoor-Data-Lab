
# syntax=docker/dockerfile:1

# ---------- Base / build stage ----------
FROM python:3.14-alpine AS builder

# Prevent Python from writing .pyc files to disk.
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout/stderr so logs appear immediately.
ENV PYTHONUNBUFFERED=1

# No musl wheels exist for pyogrio (and possibly others) on Alpine, so they are
# compiled from source: this needs a toolchain plus the GDAL/GEOS/PROJ headers
# (gdal-config must be on PATH).
RUN apk add --no-cache build-base gdal-dev geos-dev proj-dev

RUN pip install --quiet --root-user-action=ignore uv
# Use copy mode since the cache and build filesystem are on different volumes.
ENV UV_LINK_MODE=copy

WORKDIR /app

# GDAL before uv sync: pyogrio is compiled on Alpine and needs it.
RUN apk add --no-cache build-base gdal-dev geos-dev proj-dev

# Install dependencies into a virtual environment using cache and bind mounts
# so neither uv nor the lock files need to be copied into the image.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

# ---------- Development stage ----------
# Inherits the builder (with uv available). Django's dev server reloads
# when Compose Watch syncs files.
FROM builder AS development

ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so \
    GEOS_LIBRARY_PATH=/usr/lib/libgeos_c.so

ENV PATH="/app/.venv/bin:$PATH"

COPY . .
EXPOSE 8000
CMD ["python", "backend/manage.py", "runserver", "0.0.0.0:8000"]

# ---------- Production stage ----------
# Must stay LAST: it is the default target when no --target is given.
FROM python:3.14-alpine AS production

ENV PYTHONUNBUFFERED=1
# Activate the virtual environment copied from the build stage.
ENV PATH="/app/.venv/bin:$PATH"

# GeoDjango libraries (-dev provides the unversioned .so symlinks Django needs).
RUN apk add --no-cache gdal-dev geos-dev proj
ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so \
    GEOS_LIBRARY_PATH=/usr/lib/libgeos_c.so

WORKDIR /app

# Run as a non-root user.
RUN addgroup -S app && adduser -S app -G app

# Copy only the pre-built virtual environment and application source code.
COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app . .

USER app
EXPOSE 8000

# Run Gunicorn as the production WSGI server.
CMD ["gunicorn", "myapp.wsgi:application", "--bind", "0.0.0.0:8000"]