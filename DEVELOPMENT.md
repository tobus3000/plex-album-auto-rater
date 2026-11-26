# Development Notes

## Tests and coverage

Install the application requirements and the `coverage` package in your Python
environment. The tests mock Plex, so a running Plex server is not required.

```bash
python -m coverage run --branch --source=plex_album_auto_rater -m unittest -v test_plex_album_auto_rater
python -m coverage report -m --fail-under=100
```

## Docker Image Publishing

These steps build and publish the standalone image; Docker Swarm is not needed.

### Prerequisites

- Install Docker Desktop (or Docker Engine and the Docker CLI) and start the
  Linux container engine. On Windows, ensure Docker Desktop is using Linux
  containers. Check that the engine is ready with `docker version`.
- Run the commands below from the repository root, where the `Dockerfile` is
  located. The `.dockerignore` file limits the build context to the files
  needed by the image; update it if the `Dockerfile` gains new inputs.
- Have a Docker Hub account with push access to
  `tobotec/plex-album-auto-rater`.
- Choose the target platform for the machine that will run the image. The
  commands below use `linux/amd64` (x86-64).

A Plex server and `.env` file are not needed to build the image. For an
optional live dry run, configure `.env` as described in [DOCKER.md](DOCKER.md)
and keep the Plex token private.

### Build and verify

Replace `v1.0.4` with the release tag when publishing another version:

```bash
docker build --platform linux/amd64 -t tobotec/plex-album-auto-rater:v1.0.4 .
docker image inspect tobotec/plex-album-auto-rater:v1.0.4 --format '{{.Os}}/{{.Architecture}}'
docker run --rm --network none --entrypoint python tobotec/plex-album-auto-rater:v1.0.4 -c "import plexapi, requests; import plex_album_auto_rater"
```

The inspect command should print `linux/amd64`. The import check does not
connect to Plex. To run the regression tests inside the image without network
access, pipe the test file into Python (the tests are not included in the
image):

```powershell
Get-Content -Raw -Encoding UTF8 test_plex_album_auto_rater.py | docker run --rm -i --network none --entrypoint python tobotec/plex-album-auto-rater:v1.0.4 -
```

In a Bash shell:

```bash
docker run --rm -i --network none --entrypoint python tobotec/plex-album-auto-rater:v1.0.4 - < test_plex_album_auto_rater.py
```

To additionally test against your own Plex server without changing ratings:

```bash
docker run --rm --env-file .env -e DRY_RUN=true tobotec/plex-album-auto-rater:v1.0.4
```

### Pushing to Docker Hub

Log in interactively in your own terminal. Do not put credentials in the
repository or command history:

```bash
docker login
```

Push the tested release tag:

```bash
docker push tobotec/plex-album-auto-rater:v1.0.4
```

If this release should also become `latest`, tag the same tested image and
push it only after the release tag succeeds:

```bash
docker tag tobotec/plex-album-auto-rater:v1.0.4 tobotec/plex-album-auto-rater:latest
docker push tobotec/plex-album-auto-rater:latest
```

Verify both tags in the Docker Hub repository after pushing, or use Docker
Buildx to check that their remote digests match:

```bash
docker buildx imagetools inspect tobotec/plex-album-auto-rater:v1.0.4
docker buildx imagetools inspect tobotec/plex-album-auto-rater:latest
```
