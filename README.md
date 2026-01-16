# Plex Album Rating Engine

Automatically rate Plex albums based on individual track ratings using a fair, confidence-aware algorithm that accounts for unrated tracks and can exclude intros or skits.

## 🧠 Summary (TL;DR)

| Question | Answer |
| --- | --- |
| Does the script re-evaluate album ratings? | ✅ Yes |
| Is re-evaluation done every run? | ✅ Yes |
| Are track changes detected? | ✅ Yes |
| Are ratings updated if result changes? | ✅ Yes |
| Are ratings removed if coverage drops? | ✅ Yes |
| Can intros/skits be ignored? | ✅ Yes |
| Does it handle partially-rated albums? | ✅ Yes |
| Does it modify individual track ratings? | ❌ No (only album ratings) |
| Will it rate albums with zero rated tracks? | ❌ No (requires minimum coverage) |
| Can I test in dry-run mode before making changes? | ✅ Yes |
| Can it run automatically on a schedule? | ✅ Yes |
| Does it require Docker? | ✅ Yes (recommended) |

## Features

- Fully **Dockerized** for Linux hosts.
- Safe-by-default **dry-run mode** before making changes.
- **Automatic album rating** based on track ratings using Bayesian shrinkage algorithm.
- **Coverage-aware** - respects minimum rated track threshold before rating albums.
- **Optional auto-unrating** - removes ratings from albums when tracks are manually unrated below threshold.
- **Track duration filtering** - excludes short tracks (intros/skits) from rating calculations.
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
git clone --branch v1.0.1 https://github.com/tobus3000/plex-album-auto-rater.git
cd plex-album-auto-rater
```

> Replace `v1.0.1` with your desired release tag. See [releases](https://github.com/tobus3000/plex-album-auto-rater/releases) for available versions.

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
ROUNDING_BIAS_BAD_ALBUM=0.65
ROUNDING_BIAS_GOOD_ALBUM=0.45

# Features
UNRATE_EMPTY_ALBUMS=false
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

## Updating

To update to a new version:

### **Option A**: Update to latest development version (main branch)

```bash
git pull origin main
```

### **Option B**: Update to specific release version (stable)

```bash
git fetch --tags
git checkout v1.0.1
```

> Replace `v1.0.1` with your desired release tag. See [releases](https://github.com/tobus3000/plex-album-auto-rater/releases) for available versions.

1. Rebuild the Docker image:

```bash
docker-compose build --no-cache
```

1. Run with your configured settings (maybe in dry-run mode first):

```bash
docker-compose up plex-album-auto-rater
```

Check [CHANGELOG.md](CHANGELOG.md) for version-specific changes.

## ⚠️ Important Plex Notes

- Plex album ratings use 1–5 stars but are stored internally as 1–10 "tenths".
- Ratings are user-specific.
- This script should run under the same Plex user that rates tracks.

## Logging

The application uses Python's standard logging module with INFO level by default. All operations are logged with timestamps and severity levels:

- **INFO**: Configuration summary, album updates, completion statistics
- **WARNING**: Album/track retrieval failures (albums are skipped)
- **ERROR**: Critical failures (connection errors, calculation failures)
- **DEBUG**: Detailed operational information (track processing, skipped albums)

Logs can be captured and redirected as needed (e.g., to a file via cron or Docker logging drivers).

## Configuration Options

### Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `PLEX_URL` | — | Plex server URL (e.g., `http://plex:32400`). **Required**. |
| `PLEX_TOKEN` | — | Plex authentication token. **Required**. |
| `PLEX_MUSIC_LIBRARY` | `Music` | Name of the music library to process. |
| `DRY_RUN` | `true` | Preview mode. Set to `false` to apply ratings to Plex. |
| `NEUTRAL_RATING` | `3.0` | Neutral prior rating for Bayesian calculation (1-10 scale). |
| `CONFIDENCE_WEIGHT` | `4` | Confidence constant for shrinkage (higher = more conservative). |
| `MIN_COVERAGE` | `0.2` | Minimum fraction of rated tracks required to rate album (0.0-1.0). |
| `MIN_TRACK_DURATION` | `60` | Minimum track duration in seconds (excludes short tracks). |
| `UNRATE_EMPTY_ALBUMS` | `false` | Automatically remove ratings from albums that no longer meet coverage threshold. |
| `ROUNDING_BIAS_BAD_ALBUM` | `0.65` | Harsher rounding for albums below neutral rating. |
| `ROUNDING_BIAS_GOOD_ALBUM` | `0.45` | Gentler rounding for albums at or above neutral rating. |

### UNRATE_EMPTY_ALBUMS Feature

When enabled (`true`), this feature automatically removes ratings from albums that have fallen below the `MIN_COVERAGE` threshold. This is useful when you manually unrate tracks in Plex and want albums to be automatically unrated if they no longer have enough rated tracks.

**Example scenario:**

- Album has 10 tracks, 3 are rated (30% coverage) → Album is rated ✓
- You manually unrate 2 tracks in Plex
- Album now has 1 rated track (10% coverage) → Falls below MIN_COVERAGE (20%)
- With `UNRATE_EMPTY_ALBUMS=true`, album rating is automatically removed ✓

**Default is `false`** to prevent accidental removal of ratings. Enable only if this behavior is desired.

## Rating Algorithm

The rating algorithm is based on a Bayesian Shrinkage Rating system with deterministic overrides and asymmetric rounding.

> Start with a neutral prior and let real ratings pull the album toward its true value as confidence increases — while enforcing hard rules for consistently loved or disliked albums.

### Understanding the Rating Scale

The algorithm calculates ratings on a 1–5 star scale (matching Plex’s user-facing display).  
However, Plex stores ratings internally using a 1–10 scale (called “tenths”).  
The conversion is automatic:

- Algorithm calculates: 3.0 stars
- Plex stores internally: 6 (tenths)
- Plex UI displays: 3 stars ✓

The final conversion multiplies the calculated rating by 2 and applies asymmetric rounding to avoid systematic inflation:

- Lower-rated albums are rounded more conservatively, requiring stronger evidence to move up a star
- Higher-rated albums are rounded neutrally or slightly generously to preserve strong positive signals

This replaces unconditional upward rounding and produces a more realistic distribution of album ratings.

### Features of this algorithm

- Uses a Bayesian prior to stabilize ratings with limited data
- Assumes unrated tracks are neutral (not bad, not amazing)
- Never rates an album if zero tracks are rated
- Avoids inflation from a single high-rated track
- Rewards albums with consistently high ratings
- Penalizes albums with low coverage or weak signals
- Hard-enforces 1⭐ albums when all rated tracks are 1⭐
- Applies asymmetric rounding to be harsher on weak albums
- Converges naturally as more tracks are rated
- Stays fully within Plex’s 1–5 star model

### 🧮 Formula

Let:

- R̄ = average rating of rated tracks
- n = number of rated tracks
- N = total tracks on album
- C = neutral rating (recommend 3.0)
- k = confidence constant (recommend 3–5)

```python
album_rating =
  ((n * R̄) + (k * C)) / (n + k)
```

#### Hard 1-Star/5-Star Override

Before applying coverage or Bayesian adjustments, the algorithm now checks if the album is consistently disliked or liked.

Simplified example:

```python
# If all rated tracks are 1 star, force album rating to 1
if override_track_ratings and all(r == PLEX_1_STAR for r in override_track_ratings)
    return PLEX_1_STAR
# If all rated tracks are 5 star, force album rating to 5
if override_track_ratings and all(r == PLEX_5_STAR for r in override_track_ratings):
    return PLEX_5_STAR    
```

This ensures albums where all rated tracks are 1★ are immediately rated 1★, bypassing Bayesian smoothing and neutral priors. Same symetric logic applies to albums with all 5★ tracks.

This is useful because:

- Bayesian shrinkage normally pulls very low ratings toward the neutral rating (e.g., 2.5★)
- The override prevents genuinely good or bad albums from being artificially inflated/deflated.
- Helps keep the library clean and avoids overrating poorly received albums

**Example:** An album with 5/5 rated tracks all at 1★ would normally smooth toward ~2.5★. With this override, it is immediately rated 1★.

#### Bayesian + Coverage Adjustment

After this, coverage weighting and Bayesian averaging are applied for albums that are not all 1★ or all 5★:

```python
coverage = rated_count / total_tracks
bayesian_rating = (rated_count * avg_rating + CONFIDENCE_WEIGHT * NEUTRAL_RATING) / (rated_count + CONFIDENCE_WEIGHT)
final_rating = bayesian_rating * coverage + NEUTRAL_RATING * (1 - coverage)
```

#### Asymmetric Rounding

Finally, the rating is converted to Plex’s 1–10 scale using asymmetric rounding:

```python
plex_rating = min(asymmetric_rounding(final_rating), 10)
```

- Lower-rated albums are rounded more conservatively
- Higher-rated albums are rounded neutrally or slightly generously
- This avoids systematic inflation while keeping ratings intuitive in the Plex UI

## Contributing

1. Fork the repo
1. Create a feature branch (`git checkout -b feature-name`)
1. Commit changes (`git commit -m 'Add feature'`)
1. Push branch (`git push origin feature-name`)
1. Open a Pull Request
