# Kinbox-Server als Container (z. B. für NAS mit Portainer). Siehe docker-compose.yml.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno
RUN pip install --no-cache-dir "yt-dlp[default]" gallery-dl flask waitress certifi
COPY server/server.py /app/server.py
COPY server/static /app/static
ENV KINBOX_DOCKER=1 KINBOX_DATA=/data KINBOX_DOWNLOADS=/downloads \
    PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
VOLUME ["/data", "/downloads"]
EXPOSE 8765
WORKDIR /app
CMD ["python", "server.py"]
