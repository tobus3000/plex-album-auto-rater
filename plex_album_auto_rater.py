import os
import math
import logging
from typing import List, Optional
from plexapi.server import PlexServer

# =========================
# Environment Configuration
# =========================

PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
LIBRARY_NAME = os.getenv("PLEX_MUSIC_LIBRARY", "Music")

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# Rating algorithm tuning
NEUTRAL_RATING = float(os.getenv("NEUTRAL_RATING", 3.0))
CONFIDENCE_WEIGHT = int(os.getenv("CONFIDENCE_WEIGHT", 4))
MIN_COVERAGE = float(os.getenv("MIN_COVERAGE", 0.2))  # 20% rated tracks minimum
MIN_TRACK_DURATION = int(os.getenv("MIN_TRACK_DURATION", 60))  # seconds (exclude intros/skits)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def calculate_album_rating(
    rated_track_ratings: List[float],
    rated_track_count: int,
    total_tracks: int
) -> Optional[int]:
    """Calculate album rating using Bayesian shrinkage with coverage weighting.
    
    Combines individual track ratings with a Bayesian approach to generate a
    reliable album rating. Albums with insufficient track coverage are excluded.
    
    Args:
        rated_track_ratings: List of user ratings for individual tracks (1-10 scale).
        rated_track_count: Number of rated tracks in the album.
        total_tracks: Total number of tracks in the album.
    
    Returns:
        Album rating (1-10 scale) or None if coverage threshold not met or no rated tracks.
    """

    if rated_track_count == 0:
        return None

    coverage = rated_track_count / total_tracks
    if coverage < MIN_COVERAGE:
        return None

    avg_rating = sum(rated_track_ratings) / rated_track_count

    bayesian_rating = (
        (rated_track_count * avg_rating) +
        (CONFIDENCE_WEIGHT * NEUTRAL_RATING)
    ) / (rated_track_count + CONFIDENCE_WEIGHT)

    final_rating = (
        bayesian_rating * coverage +
        NEUTRAL_RATING * (1 - coverage)
    )

    return math.ceil(final_rating)

def main() -> None:
    """Main entry point for Plex Album Auto-Rater.
    
    Connects to Plex server, retrieves music library, and auto-rates albums
    based on individual track ratings using Bayesian methodology.
    """
    try:
        logger.info("Initializing Plex Album Auto-Rater")
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        music = plex.library.section(LIBRARY_NAME)
    except ConnectionError as e:
        logger.error("Failed to connect to Plex server: %s", e)
        return
    except (OSError, KeyError) as e:
        logger.error("Unexpected error initializing Plex: %s", e)
        return

    logger.info("Starting Plex Album Auto-Rater")
    logger.info("Library              : %s", LIBRARY_NAME)
    logger.info("Dry run              : %s", DRY_RUN)
    logger.info("Min coverage         : %.0f%%", MIN_COVERAGE * 100)
    logger.info("Min track duration   : %ds", MIN_TRACK_DURATION)

    albums_processed = 0
    albums_updated = 0
    albums_skipped = 0

    try:
        albums = music.albums()
    except (OSError, ValueError) as e:
        logger.error("Failed to retrieve albums from library: %s", e)
        return

    for album in albums:
        try:
            tracks = album.tracks()
        except (OSError, ValueError) as e:
            logger.warning("Failed to retrieve tracks for album %s: %s", album.title, e)
            albums_skipped += 1
            continue

        total_tracks = len(tracks)
        rated_track_ratings = []

        for track in tracks:
            try:
                # Exclude intros/skits based on duration
                if track.duration is not None and (track.duration / 1000) < MIN_TRACK_DURATION:
                    continue

                if track.userRating is not None:
                    rated_track_ratings.append(track.userRating)
            except (AttributeError, TypeError) as e:
                logger.debug("Error processing track %s: %s", track.title, e)
                continue

        rated_count = len(rated_track_ratings)

        try:
            new_rating = calculate_album_rating(
                rated_track_ratings,
                rated_count,
                total_tracks
            )
        except (ValueError, TypeError) as e:
            logger.error("Failed to calculate rating for album %s: %s", album.title, e)
            continue

        if new_rating is None:
            albums_skipped += 1
            continue

        current_rating = album.userRating

        if current_rating == new_rating:
            logger.debug("Album %s already has rating %s, skipping", album.title, new_rating)
            continue

        albums_processed += 1

        status_msg = (
            f"{album.parentTitle} – {album.title}\n"
            f"  Rated tracks : {rated_count}/{total_tracks}\n"
            f"  New rating   : {new_rating} stars\n"
            f"  Old rating   : {current_rating or 'None'}\n"
        )
        logger.info("%s", status_msg)
        logger.info("Album update needed: %s – %s (rating: %s → %s)",
                   album.parentTitle, album.title, current_rating or 'None', new_rating)

        if DRY_RUN:
            logger.info("[DRY RUN] Album rating not updated")
            logger.info("[DRY RUN] Would rate %s as %s", album.title, new_rating)
            continue

        try:
            album.rate(new_rating)
            albums_updated += 1
            logger.info("Successfully rated album %s as %s", album.title, new_rating)
        except (OSError, ValueError) as e:
            logger.error("Failed to rate album %s: %s", album.title, e)
            continue

    logger.info("-" * 60)
    logger.info("Albums evaluated : %s", albums_processed)
    logger.info("Albums updated   : %s", albums_updated)
    logger.info("Albums skipped   : %s", albums_skipped)
    logger.info("Album auto-rating complete.")

# =========================
# Entrypoint
# =========================

if __name__ == "__main__":
    main()
