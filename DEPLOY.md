# Container deployment

This project is published as a Docker image to GitHub Container Registry:

```text
ghcr.io/lildengzi/resumemaker:latest
```

## Server setup

Create a deployment directory on the server:

```bash
mkdir -p /opt/resumemaker/data
cd /opt/resumemaker
```

You can configure the model in the app sidebar after the container starts. The saved model settings are written to:

```text
/opt/resumemaker/data/config.json
```

Optionally create `.env` if you prefer environment variables:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.2
LLM_TIMEOUT=60
LLM_MAX_RETRIES=1
```

Create `compose.yaml`:

```yaml
services:
  resumemaker:
    image: ghcr.io/lildengzi/resumemaker:latest
    container_name: resumemaker
    restart: unless-stopped
    ports:
      - "8501:8501"
    environment:
      RESUMEMAKER_CONFIG_PATH: /app/ResumeMaker/data/config.json
    env_file:
      - path: .env
        required: false
    volumes:
      - ./data:/app/ResumeMaker/data
```

Start it:

```bash
docker compose up -d
```

Open:

```text
http://SERVER_IP:8501
```

## Update

After pushing to `main`, GitHub Actions publishes a new image. Update the server:

```bash
cd /opt/resumemaker
docker compose pull
docker compose up -d
```

## Data and secrets

The image does not include local data, uploaded materials, logs, `.env`, or `config.json`.

Runtime data and sidebar-saved model settings are stored in:

```text
/opt/resumemaker/data
```

Keep `.env` only on the server if you use one.
