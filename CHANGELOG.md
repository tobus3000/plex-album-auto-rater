# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-01-11

### Added

- **Dry-Run Mode**: Safe-by-default preview mode (enabled by default)
- **Comprehensive Logging**: Structured logging with timestamps and log levels
- **Environment Validation**: Automatic validation of required environment variables at startup
- **Error Handling**: Robust exception handling for network errors, timeouts, and API failures
- **Type Hints**: Full Python type annotations for all functions
- **Documentation**: Google-style docstrings for all functions and module
- **Docker Support**: Fully containerized application with Docker and Docker Compose
- **Docker Image**: Lightweight `python:3.12-slim` base image
- **Cron Integration**: Designed for easy scheduling via system cron jobs
- **Configuration Template**: `.env-example` file for quick setup
- **Comprehensive README**: Detailed setup, usage, and workflow documentation
- **Auto-Unrating Feature**: Optional `UNRATE_EMPTY_ALBUMS` setting to automatically remove ratings from albums when they fall below coverage threshold (e.g., after tracks are manually unrated)
- **Module Documentation**: Comprehensive module docstring with environment variable descriptions and usage

### Features

#### Safety & Control

- Dry-run mode prevents accidental modifications
- Validation of all required configuration at startup
- Detailed logging of all operations
- Graceful error handling with informative messages

#### Deployment

- Docker containerization for consistent environments
- Docker Compose for simplified orchestration
- Cron scheduling support for nightly automation
- Lightweight container image (Python 3.12-slim base)
- No external dependencies beyond Python packages

#### Configuration

- Environment variable-based configuration
- Configurable rating thresholds
- Optional dry-run mode for testing

### Documentation

- [README.md](README.md) - Installation and usage guide
- Module docstrings - Comprehensive function documentation
- `.env-example` - Configuration template with descriptions

### Known Limitations

- None

---

[Unreleased]: https://github.com/tobus3000/plex-album-auto-rater/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/tobus3000/plex-album-auto-rater/releases/tag/v1.0.0
