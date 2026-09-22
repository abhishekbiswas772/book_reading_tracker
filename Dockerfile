# Reading List Tracker — single-container image for Render.com (Web Service).
# Build: docker build -t reading-list-tracker .
# Run locally: docker run -p 8000:8000 reading-list-tracker

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so this layer is cached across source-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + static frontend. .env and other local-only files are excluded
# via .dockerignore — configuration must come from the platform's env vars
# (e.g. Render's dashboard), never baked into the image.
COPY . .

# Render assigns the external port at runtime via $PORT and routes traffic
# to it; 8000 is just the documented/local-default fallback for `docker run`
# without -e PORT=..., since Render itself ignores EXPOSE.
EXPOSE 8000

# Shell form (not exec-form JSON array) so $PORT is expanded at container
# start; ${PORT:-8000} falls back to 8000 when run outside Render.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
