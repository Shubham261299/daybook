FROM python:3.13-slim

WORKDIR /app

# GitPython imports the `git` binary at module load time (even though this
# image only reads repos through the bind mounts set up in
# docker-compose.yml), so it must be present or the app fails to start.
# tzdata is needed for the TZ env var (set in docker-compose.yml) to
# actually resolve a named zone instead of silently
# falling back to UTC — matters for the EOD_HOUR job.
RUN apt-get update && apt-get install -y --no-install-recommends git tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY collector/ collector/
COPY summarizer/ summarizer/
COPY db/ db/
COPY dashboard/ dashboard/
COPY config/ config/

CMD ["python", "-m", "dashboard.backend.main"]
