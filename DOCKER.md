# Docker Setup Guide

This document covers standalone Docker setup and Docker Swarm Mode deployment for Plex Album Auto-Rater.

## Prerequisites

- Plex Media Server (Plex Pass recommended)
- Docker & Docker Compose
- Linux host (for cron/swarm scheduling)
- Python 3.12+ (used inside container)

## Configuration

Create a `.env` file in the repository root with your settings:

```bash
# Required
PLEX_URL=http://plex:32400
PLEX_TOKEN=YOUR_PLEX_TOKEN
PLEX_MUSIC_LIBRARY=Music

# Safety
DRY_RUN=true

# Algorithm tuning
NEUTRAL_RATING=3.0
CONFIDENCE_WEIGHT=4
MIN_COVERAGE=0.2
MIN_TRACK_DURATION=60
ROUNDING_BIAS_BAD_ALBUM=0.65
ROUNDING_BIAS_GOOD_ALBUM=0.45

# Features
UNRATE_EMPTY_ALBUMS=false
```

> Tip: Keep `DRY_RUN=true` for your first run to preview actions without modifying Plex ratings.

## Option 1: Standalone local Docker Compose

### Installation

1. Clone the repository:

#### Latest development version (main branch)

```bash
git clone https://github.com/tobus3000/plex-album-auto-rater.git
cd plex-album-auto-rater
```

#### Specific release version (stable)

```bash
git clone --branch v1.0.1 https://github.com/tobus3000/plex-album-auto-rater.git
cd plex-album-auto-rater
```

> Replace `v1.0.1` with your desired release tag. See [releases](https://github.com/tobus3000/plex-album-auto-rater/releases) for available versions.

1. Build the Docker image:

```bash
docker-compose build
```

### Usage

#### Manual run

```bash
docker-compose up plex-album-auto-rater
```

You should see log output listing albums that would be rated in Plex. The application logs all operations with timestamps and severity levels.

Once verified, disable dry-run mode:

```bash
# Disable dry-run
sed -i 's/DRY_RUN=true/DRY_RUN=false/' .env
docker-compose up plex-album-auto-rater
```

#### Nightly automation with cron

1. Open root crontab:

```bash
sudo crontab -e
```

1. Add a nightly job (runs at 3:00 AM):

```cron
0 3 * * * cd /path-to-plex-album-auto-rater && docker-compose up plex-album-auto-rater
```

- Update the path `/path-to-plex-album-auto-rater` to your repository location.
- Logs are automatically managed by Docker.

### Viewing Logs

The application outputs logs to the Docker container's STDOUT, which Docker automatically captures and rotates.

**View logs in real-time:**

```bash
docker-compose logs -f plex-album-auto-rater
```

**View last 50 log lines:**

```bash
docker-compose logs --tail=50 plex-album-auto-rater
```

**Log rotation details:**

- Individual log files are limited to **10 MB**
- Docker keeps the **latest 3 rotated files** (~30 MB total)
- Logs are stored in Docker's data directory and automatically rotated

### Updating

#### Update to latest development version (main branch)

```bash
git pull origin main
```

#### Update to specific release version (stable)

```bash
git fetch --tags
git checkout v1.0.1
```

> Replace `v1.0.1` with your desired release tag.

Rebuild the Docker image:

```bash
docker-compose build --no-cache
```

Run with your configured settings:

```bash
docker-compose up plex-album-auto-rater
```

---

## Option 2: Standalone Docker from Docker Hub

### Installation

1. Pull the latest image from Docker Hub:

```bash
docker pull tobotec/plex-album-auto-rater:latest
```

### Usage

#### Manual run

```bash
docker run --rm \
  --env-file .env \
  tobotec/plex-album-auto-rater:latest
```

#### Nightly automation with cron

1. Open root crontab:

```bash
sudo crontab -e
```

1. Add a nightly job (runs at 3:00 AM):

```cron
0 3 * * * cd /path-to-plex-album-auto-rater && docker run --rm --env-file .env tobotec/plex-album-auto-rater:latest
```

- Update the path `/path-to-plex-album-auto-rater` to your repository location.

### Viewing Logs

Since the container is run with `--rm`, logs are only available during execution. For scheduled runs, consider redirecting output to a file:

```cron
0 3 * * * cd /path-to-plex-album-auto-rater && docker run --rm --env-file .env tobotec/plex-album-auto-rater:latest >> plex-auto-rater.log 2>&1
```

### Updating

Pull the latest image:

```bash
docker pull tobotec/plex-album-auto-rater:latest
```

---

## Option 3: Docker Swarm Mode

Docker Swarm Mode allows you to deploy and manage containers across a cluster of machines, with automatic scheduling, service management, and orchestration. This guide covers deploying Plex Album Auto-Rater as a scheduled cronjob in Swarm Mode.

### Swarm Prerequisites

- Docker Swarm initialized (`docker swarm init` on the manager node)
- `swarm-cronjob` service deployed on the swarm (see [swarm-cronjob](https://github.com/crazy-max/swarm-cronjob))

### Swarm Setup

1. **Initialize Docker Swarm** (if not already done):

```bash
docker swarm init
```

1. **Deploy swarm-cronjob service** (on the manager node):

```bash
docker service create \
  --name swarm-cronjob \
  --constraint "node.role==manager" \
  --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock \
  crazymax/swarm-cronjob:latest
```

1. **Create the stack configuration** using `docker-swarm-compose.yml`:

The compose file pulls the image from Docker Hub and uses Docker Swarm config. Key features:

- **Image**: `tobotec/plex-album-auto-rater:latest` (pulled from Docker Hub)
- **Replicas**: Set to 0 (swarm-cronjob controls execution)
- **Placement**: Constrained to worker nodes
- **Restart Policy**: `none` (required for cronjob mode)
- **Cronjob Schedule**: `* * * * *` (customize as needed)

1. **Create Swarm config for .env file**:

```bash
docker config create plex-album-auto-rater-env .env
```

1. **Deploy the stack**:

```bash
docker stack deploy -c docker-swarm-compose.yml plex-album-auto-rater
```

1. **Verify deployment**:

```bash
docker stack services plex-album-auto-rater
```

### Swarm Configuration

The `.env` file is mounted from the Docker Swarm config: `plex-album-auto-rater-env`

Update this config to change configuration:

```bash
docker config rm plex-album-auto-rater-env
docker config create plex-album-auto-rater-env .env
```

Changes are automatically picked up on the next scheduled run.

### Cronjob Scheduling

Edit the cronjob schedule in `docker-swarm-compose.yml` under the `swarm.cronjob.schedule` label:

```yaml
labels:
  - "swarm.cronjob.schedule=0 3 * * *"  # Runs at 3:00 AM daily
```

Common schedules:

- `* * * * *` - Every minute
- `0 * * * *` - Every hour
- `0 3 * * *` - Daily at 3:00 AM
- `0 2 * * 0` - Weekly on Sunday at 2:00 AM
- `0 0 1 * *` - Monthly on the 1st at midnight

### Swarm Logs

**View logs from completed tasks:**

```bash
docker service logs plex-album-auto-rater
```

**View logs from a specific task:**

```bash
docker task ps --filter "service=plex-album-auto-rater"
docker logs <task-id>
```

**Stream logs in real-time:**

```bash
docker service logs -f plex-album-auto-rater
```

### Swarm Updating

1. **Pull the latest image**:

```bash
docker pull tobotec/plex-album-auto-rater:latest
```

1. **Force service update**:

```bash
docker service update --force plex-album-auto-rater_plex-album-auto-rater
```

1. **Or redeploy the entire stack**:

```bash
docker stack rm plex-album-auto-rater
docker stack deploy -c docker-swarm-compose.yml plex-album-auto-rater
```

### Troubleshooting Swarm Deployment

#### Service not running

- Verify swarm-cronjob is running: `docker service ls | grep swarm-cronjob`
- Check service status: `docker stack ps plex-album-auto-rater`
- Review logs: `docker service logs plex-album-auto-rater`
- Check `.env` config exists and is readable: `docker config inspect plex-album-auto-rater-env`
- Verify all worker nodes have access to the config and can pull the image

#### Cronjob not firing

- Verify schedule syntax: `docker service ls --filter "name=plex-album-auto-rater" -q | xargs docker service inspect`
- Check swarm-cronjob logs: `docker service logs swarm-cronjob`
- Ensure at least one worker node is available
