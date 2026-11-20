# Small official Python base image (Debian slim)
FROM python:3.12-slim
# Install the latest Debian security patches for OS packages (glibc, zlib, etc.)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Version label baked into the image; GitHub Actions overrides this with the commit SHA
ARG APP_VERSION=local
ENV APP_VERSION=${APP_VERSION} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so Docker can cache this layer between builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the app code (changes often, so it goes last)
COPY app.py .

# Don't run as root inside the container
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# gunicorn is a production web server; Flask's built-in server is for development only
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app:app"]
