# plex-album-auto-rater

Automatically rate Plex albums based on individual track ratings using a fair, confidence-aware algorithm.

## Features

- Fully **Dockerized** for Linux hosts.
- Safe-by-default **dry-run mode** before making changes.
- Can be scheduled nightly via **cron** for automated management.

## Requirements

- Plex Media Server (Plex Pass recommended)
- Docker & Docker Compose
- Linux host (cron recommended for scheduling)
- Python 3.12+ (used inside container)

## Installation

1. Clone the repository:

### **Option A**: Latest development version (main branch)

```bash
git clone https://github.com/tobus3000/plex-album-auto-rater.git
cd plex-album-auto-rater
```

### **Option B**: Specific release version (stable)

```bash
git clone --branch v1.0.0 https://github.com/tobus3000/plex-album-auto-rater.git
cd plex-album-auto-rater
```

> Replace `v1.0.0` with your desired release tag. See [releases](https://github.com/tobus3000/plex-album-auto-rater/releases) for available versions.

1. Create a `.env` file based on the provided template:

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
```

> Tip: Keep `DRY_RUN=true` for your first run to preview actions without modifying Plex ratings.

1. Build the Docker container:

```bash
docker-compose build
```

## Usage

### Manual run

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

### Nightly automation with cron

1. Open root crontab:

```bash
sudo crontab -e
```

1. Add a nightly job (runs at 3:00 AM):

```cron
0 3 * * * cd /path-to-plex-album-auto-rater/plex-album-auto-rater && docker-compose up plex-album-auto-rater >> /var/log/plex-album-auto-rater.log 2>&1
```

- Update the path `/path-to-plex-album-auto-rater/plex-album-auto-rater` to your repository location.
- Logs are saved to /var/log/plex-album-auto-rater.log.

## Updating

To update to a new version:

### **Option A**: Update to latest development version (main branch)

```bash
git pull origin main
```

### **Option B**: Update to specific release version (stable)

```bash
git fetch --tags
git checkout v1.0.0
```

> Replace `v1.0.0` with your desired release tag. See [releases](https://github.com/tobus3000/plex-album-auto-rater/releases) for available versions.

1. Rebuild the Docker image:

```bash
docker-compose build --no-cache
```

1. Test with dry-run mode first:

```bash
DRY_RUN=true docker-compose up plex-album-auto-rater
```

1. Once verified, run with your configured settings:

```bash
docker-compose up plex-album-auto-rater
```

Check [CHANGELOG.md](CHANGELOG.md) for version-specific changes.

## ⚠️ Important Plex Notes

- Plex album ratings use 1–5 stars
- `track.userRating` and `album.userRating` both follow this scale
- Ratings are user-specific
- This script should run under the same Plex user that rates tracks

## Logging

The application uses Python's standard logging module with INFO level by default. All operations are logged with timestamps and severity levels:

- **INFO**: Configuration summary, album updates, completion statistics
- **WARNING**: Album/track retrieval failures (albums are skipped)
- **ERROR**: Critical failures (connection errors, calculation failures)
- **DEBUG**: Detailed operational information (track processing, skipped albums)

Logs can be captured and redirected as needed (e.g., to a file via cron or Docker logging drivers).

## Rating Algorithm

The rating algorithm is based on a Bayesian Shrinkage Rating system.

> Start with a neutral prior and let real ratings pull the album toward its true value as confidence increases.

### Features of this algorithm

- Assume unrated tracks are neutral (not bad, not amazing)
- Never rate an album if zero tracks are rated
- Avoid inflation from a single 5⭐ track
- Reward albums with consistently high ratings
- Penalize albums with many unrated tracks
- Converge naturally as more tracks are rated
- Stay in Plex’s 1–5 star model

### 🧮 Formula

Let:

- R̄ = average rating of rated tracks
- n = number of rated tracks
- N = total tracks on album
- C = neutral rating (recommend 3.0)
- k = confidence constant (recommend 3–5)

#### Bayesian album rating

```python
album_rating =
  ((n * R̄) + (k * C)) / (n + k)
```

Then apply coverage penalty:

```python
coverage = n / N
final_rating = album_rating * coverage + C * (1 - coverage)
```

Final rating is rounded up to nearest whole star for Plex:

```python
plex_rating = ceil(final_rating)
```

## Contributing

1. Fork the repo
1. Create a feature branch (`git checkout -b feature-name`)
1. Commit changes (`git commit -m 'Add feature'`)
1. Push branch (`git push origin feature-name`)
1. Open a Pull Request
