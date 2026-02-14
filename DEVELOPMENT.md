# Development Notes

## Docker Image Publishing

### Building

To build the image locally:

```bash
docker build -t tobotec/plex-album-auto-rater:tagname .
```

Replace `tagname` with your desired tag (e.g., `latest`, `v1.0.2`, etc.)

### Pushing to Docker Hub

1. **Log in to Docker Hub**:

```bash
docker login
```

1. **Tag the image** (if not already tagged):

```bash
docker tag plex-album-auto-rater:tagname tobotec/plex-album-auto-rater:tagname
```

1. **Push to Docker Hub**:

```bash
docker push tobotec/plex-album-auto-rater:tagname
```

To push multiple tags at once:

```bash
docker build -t tobotec/plex-album-auto-rater:tagname -t tobotec/plex-album-auto-rater:latest .
docker push tobotec/plex-album-auto-rater:tagname
docker push tobotec/plex-album-auto-rater:latest
```
