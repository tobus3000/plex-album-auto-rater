# Plex Album Auto-Rater

Automatically rate your Plex music albums based on track ratings and configurable scoring rules.

This image is published on Docker Hub:

```plaintext
tobotec/plex-album-auto-rater:latest
```

## Setup options

* [Option 1 – Standalone Docker (Docker Hub Image)](#-option-1--standalone-docker-docker-hub-image)
* [Option 2 – Docker Swarm Mode (Cluster / Scheduled Job)](#-option-2--docker-swarm-mode-cluster--scheduled-job)

## ⚙️ Configuration

All setup options read the configuration from a `.env` file.  
Create a `.env` file in your working directory:

```env
# Required
PLEX_URL=http://your-plex-server:32400
PLEX_TOKEN=your_token_here
PLEX_MUSIC_LIBRARY=Music

# Safety
DRY_RUN=false

# Algorithm tuning
NEUTRAL_RATING=2.0
CONFIDENCE_WEIGHT=3
MIN_COVERAGE=0.4
MIN_TRACK_DURATION=60
ROUNDING_BIAS_BAD_ALBUM=0.65
ROUNDING_BIAS_GOOD_ALBUM=0.45

# Feature
UNRATE_EMPTY_ALBUMS=true
```

---

# 🐳 Option 1 – Standalone Docker (Docker Hub Image)

The simplest way to run the container using Docker directly.

---

## 📦 Installation

Pull the latest image:

```bash
docker pull tobotec/plex-album-auto-rater:latest
```

---

## ▶️ Manual Run

```bash
docker run --rm \
  --env-file .env \
  tobotec/plex-album-auto-rater:latest
```

The container will execute once and exit.

---

## ⏰ Nightly Automation with Cron

Edit root crontab:

```bash
sudo crontab -e
```

Add a nightly job (runs at 3:00 AM):

```bash
0 3 * * * cd /path-to-plex-album-auto-rater && docker run --rm --env-file .env tobotec/plex-album-auto-rater:latest
```

Update `/path-to-plex-album-auto-rater` to your actual directory.

---

## 📜 Viewing Logs

Since the container runs with `--rm`, logs are visible only during execution.

To persist logs for scheduled runs:

```bash
0 3 * * * cd /path-to-plex-album-auto-rater && docker run --rm --env-file .env tobotec/plex-album-auto-rater:latest >> plex-auto-rater.log 2>&1
```

---

## 🔄 Updating

Pull the latest version:

```bash
docker pull tobotec/plex-album-auto-rater:latest
```

---

# 🐳 Option 2 – Docker Swarm Mode (Cluster / Scheduled Job)

Deploy Plex Album Auto-Rater as a scheduled cron job in Docker Swarm.

---

## 📋 Prerequisites

* Docker Swarm initialized
* `swarm-cronjob` service deployed

---

## 🧱 Initialize Swarm (if needed)

```bash
docker swarm init
```

---

## ⏱ Deploy swarm-cronjob Service

```bash
docker service create \
  --name swarm-cronjob \
  --constraint "node.role==manager" \
  --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock \
  crazymax/swarm-cronjob:latest
```

---

## 📝 Create `docker-swarm-compose.yml`

```yaml
version: "3.8"

services:
  plex-album-auto-rater:
    image: tobotec/plex-album-auto-rater:latest
    environment:
      PLEX_URL: ${PLEX_URL}
      PLEX_TOKEN: ${PLEX_TOKEN}
      PLEX_MUSIC_LIBRARY: ${PLEX_MUSIC_LIBRARY}
      DRY_RUN: ${DRY_RUN}
      NEUTRAL_RATING: ${NEUTRAL_RATING}
      CONFIDENCE_WEIGHT: ${CONFIDENCE_WEIGHT}
      MIN_COVERAGE: ${MIN_COVERAGE}
      MIN_TRACK_DURATION: ${MIN_TRACK_DURATION}
      ROUNDING_BIAS_BAD_ALBUM: ${ROUNDING_BIAS_BAD_ALBUM}
      ROUNDING_BIAS_GOOD_ALBUM: ${ROUNDING_BIAS_GOOD_ALBUM}
      UNRATE_EMPTY_ALBUMS: ${UNRATE_EMPTY_ALBUMS}
      PYTHONUNBUFFERED: "1"

    deploy:
      mode: replicated
      replicas: 0
      placement:
        constraints:
          - node.role == worker
      restart_policy:
        condition: none
      labels:
        - "swarm.cronjob.enable=true"
        - "swarm.cronjob.schedule=0 3 * * *"
        - "swarm.cronjob.skip-running=false"
```

---

## 🚀 Deploy the Stack

Load your `.env` into the shell:

```bash
export $(grep -v '^#' .env | xargs)
```

Deploy:

```bash
docker stack deploy -c docker-swarm-compose.yml plex-album-auto-rater
```

Verify:

```bash
docker stack services plex-album-auto-rater
```

---

## 🕒 Cron Schedule Examples

Edit the schedule under:

```
swarm.cronjob.schedule=
```

Common patterns:

```
* * * * *    # Every minute
0 * * * *    # Every hour
0 3 * * *    # Daily at 3:00 AM
0 2 * * 0    # Weekly (Sunday 2 AM)
0 0 1 * *    # Monthly (1st at midnight)
```

---

## 📜 Swarm Logs

View service logs:

```bash
docker service logs plex-album-auto-rater
```

Stream logs:

```bash
docker service logs -f plex-album-auto-rater_plex-album-auto-rater
```

Inspect tasks:

```bash
docker stack ps plex-album-auto-rater
```

---

## 🔄 Updating in Swarm

Pull the latest image:

```bash
docker pull tobotec/plex-album-auto-rater:latest
```

Force service update:

```bash
docker service update --force plex-album-auto-rater_plex-album-auto-rater
```

Or redeploy:

```bash
docker stack rm plex-album-auto-rater
docker stack deploy -c docker-swarm-compose.yml plex-album-auto-rater
```

---

## 🛠 Troubleshooting

**Service not running**

```bash
docker service ls | grep swarm-cronjob
docker stack ps plex-album-auto-rater
docker service logs plex-album-auto-rater
```

**Cronjob not firing**

```bash
docker service logs swarm-cronjob
```

Ensure:

* Valid cron syntax
* At least one worker node available
* `replicas: 0` is set
* `restart_policy.condition: none` is set

---

# Summary

| Mode              | Best For                                       |
| ----------------- | ---------------------------------------------- |
| Standalone Docker | Single host, simple cron usage                 |
| Docker Swarm      | Clustered environments, centralized scheduling |

Both modes pull the image directly from Docker Hub and do not require building locally.
