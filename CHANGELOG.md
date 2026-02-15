# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Nothing yet

### Changed

- Changed to using Docker Swarm configs instead of NFS-mounted .env file for configuration management in Swarm mode.

## [1.0.2] - 2026-02-14

### Added

- **Docker Swarm Mode Support**: New `docker-swarm-compose.yml` configuration for deploying as a cronjob service in Docker Swarm clusters.

### Changed

- **Documentation Reorganization**: Moved all Docker-specific installation, usage, and deployment instructions from README.md to dedicated DOCKER.md file for better organization and maintainability.

---

## [1.0.1] - 2026-01-16

### Added

- **Minimum 1★ Rating Enforcement**:  
  - Albums where all rated tracks are 1★ are now always rated 1★ in Plex (internal scale = 2).  
  - Ensures consistently disliked albums are never artificially inflated by Bayesian shrinkage or coverage weighting.

- **Maximum 5★ Rating Enforcement**:  
  - Albums where all rated tracks are 5★ are now always rated 5★ in Plex (internal scale = 10).  
  - Guarantees that superb albums receive the highest possible rating.

### Changed

- **`calculate_album_rating` & `asymmetric_rounding` Rewrite**:  
  - Refactored to correctly handle edge cases for very low-rated albums.  
  - Preserves Bayesian shrinkage and coverage weighting for all other albums.  
  - Ensures asymmetric rounding still applies to mid- and high-rated albums while enforcing a 1★ floor.
  - Ignore track duration when rating falls into very low or very high (all tracks 1★ or all 5★) categories.

### Fixed

- **1★ Album Ratings Previously Inflated**:  
  - Corrected behavior where albums with all 1★ tracks were being rounded up to 2★ or higher.  
  - Now honors hard 1★ override consistently across Plex library updates.

---

## [1.0.0] - 2026-01-15

### Added

- **Dry-Run Mode**: Safe-by-default preview mode (enabled by default).  
- **Comprehensive Logging**: Structured logging with timestamps and log levels.  
- **Environment Validation**: Automatic validation of required environment variables at startup.  
- **Error Handling**: Robust exception handling for network errors, timeouts, and API failures.  
- **Type Hints**: Full Python type annotations for all functions.  
- **Documentation**: Google-style docstrings for all functions and the module.  
- **Docker Support**: Fully containerized application with Docker and Docker Compose.  
- **Docker Image**: Lightweight `python:3.12-slim` base image.  
- **Cron Integration**: Designed for easy scheduling via system cron jobs.  
- **Configuration Template**: `.env-example` file for quick setup.  
- **Comprehensive README**: Detailed setup, usage, and workflow documentation.  
- **Auto-Unrating Feature**: Optional `UNRATE_EMPTY_ALBUMS` setting to automatically remove ratings from albums when they fall below coverage threshold.  
- **Module Documentation**: Comprehensive module docstring with environment variable descriptions and usage.  
- **Docker Logging Integration**: Logging now outputs to STDOUT and is captured by Docker's logging system.  
- **Update Options**: Support for updating to either the latest development version or specific release tags.  
- **Hard 1-Star Album Override**:  
  - Albums where all rated tracks are 1★ are forcibly rated 1★, bypassing Bayesian shrinkage and neutral prior effects.  
  - Prevents consistently disliked albums from being artificially inflated.  
- **Asymmetric Rounding Strategy**:  
  - Introduced asymmetric rounding when converting calculated album ratings (1–5★) to Plex’s internal 1–10 scale.  
  - Lower-rated albums are rounded more harshly, requiring stronger evidence to move up a star.  
  - Higher-rated albums use neutral or slightly generous rounding to preserve strong positive signals.  
- **Configurable Rounding Bias (ENV)**:  
  - Added environment variables to tune rounding behavior:  
    - `ROUNDING_BIAS_BAD_ALBUM` (default: `0.65`) — harsher rounding for albums below neutral rating.  
    - `ROUNDING_BIAS_GOOD_ALBUM` (default: `0.45`) — gentler rounding for albums at or above neutral rating.  

### Changed

- **Album Rating Quantization**:  
  - Replaced unconditional `ceil()` rounding with asymmetric, bias-controlled rounding.  
  - Removes systematic upward bias in automatic ratings and produces more realistic score distributions.  
- **Rating Behavior Near Boundaries**:  
  - Albums near star thresholds now behave more intuitively:  
    - Weak albums are less likely to cross into higher star tiers.  
    - Strong albums are no longer penalized by overly conservative rounding.  

### Fixed

- **Low-Quality Album Inflation**:  
  - Prevented low-rated albums (especially with sparse ratings) from being artificially boosted above 1–2 stars due to Bayesian priors and rounding behavior.  

### Known Limitations

- None

---

[Unreleased]: https://github.com/tobus3000/plex-album-auto-rater/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/tobus3000/plex-album-auto-rater/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/tobus3000/plex-album-auto-rater/releases/tag/v1.0.1
[1.0.0]: https://github.com/tobus3000/plex-album-auto-rater/releases/tag/v1.0.0
