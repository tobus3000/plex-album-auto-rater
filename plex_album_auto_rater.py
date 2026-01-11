"""Plex Album Auto-Rater: Automatically rate albums based on track ratings.

This module implements a Bayesian shrinkage algorithm to automatically rate Plex
albums based on individual track ratings. It processes a music library, calculates
confidence-aware album ratings, and updates them in Plex.

Environment Variables:
    PLEX_URL (str): Plex server URL (e.g., http://plex:32400). Required.
    PLEX_TOKEN (str): Plex authentication token. Required.
    PLEX_MUSIC_LIBRARY (str): Music library name. Defaults to "Music".
    DRY_RUN (str): Preview mode without modifying ratings. Defaults to "true".
        Set to "false" to apply ratings to Plex.
    NEUTRAL_RATING (str): Neutral prior rating for Bayesian calculation.
        Defaults to "2.5" (midpoint of 1-5 star scale; range: 1-5).
    CONFIDENCE_WEIGHT (str): Confidence weight parameter for Bayesian shrinkage.
        Defaults to "4" (higher = more conservative).
    MIN_COVERAGE (str): Minimum fraction of rated tracks required to rate album.
        Defaults to "0.2" (20%, range: 0.0-1.0).
    MIN_TRACK_DURATION (str): Minimum track duration in seconds to include in
        rating calculation. Defaults to "60" (excludes intros/skits).
    UNRATE_EMPTY_ALBUMS (str): Remove ratings from albums that no longer meet
        coverage requirements (e.g., after tracks are manually unrated).
        Defaults to "false".
"""

import os
import math
import logging
from typing import List, Optional
from plexapi.server import PlexServer

# Configure logging to output to console (STDOUT)
# Docker's logging driver automatically captures and manages log rotation
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load configuration from environment variables
PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
LIBRARY_NAME = os.getenv("PLEX_MUSIC_LIBRARY", "Music")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
UNRATE_EMPTY_ALBUMS = os.getenv("UNRATE_EMPTY_ALBUMS", "false").lower() == "true"

# Rating algorithm tuning
NEUTRAL_RATING = float(os.getenv("NEUTRAL_RATING", "2.5"))  # 2.5 = midpoint of 1-5 star scale
CONFIDENCE_WEIGHT = int(os.getenv("CONFIDENCE_WEIGHT", "4"))
MIN_COVERAGE = float(os.getenv("MIN_COVERAGE", "0.2"))  # 20% rated tracks minimum
MIN_TRACK_DURATION = int(os.getenv("MIN_TRACK_DURATION", "60"))  # seconds (exclude intros/skits)

def calculate_album_rating(
    rated_track_ratings: List[float],
    rated_track_count: int,
    total_tracks: int
) -> Optional[int]:
    """Calculate album rating using Bayesian shrinkage with coverage weighting.
    
    Combines individual track ratings with a Bayesian approach to generate a
    reliable album rating. Albums with insufficient track coverage are excluded.
    
    Args:
        rated_track_ratings: List of user ratings for individual tracks (1-5 star scale).
        rated_track_count: Number of rated tracks in the album.
        total_tracks: Total number of tracks in the album.
    
    Returns:
        Album rating for Plex's internal 1-10 scale or None if coverage threshold not met or no rated tracks.
    """

    if rated_track_count == 0:
        return None

    coverage = rated_track_count / total_tracks
    if coverage < MIN_COVERAGE:
        return None

    avg_rating = sum(rated_track_ratings) / rated_track_count

    # Hard floor: bad albums with high coverage get a 1-star rating
    if coverage >= 0.7 and avg_rating <= 1.3:
        return 1

    bayesian_rating = (
        (rated_track_count * avg_rating) +
        (CONFIDENCE_WEIGHT * NEUTRAL_RATING)
    ) / (rated_track_count + CONFIDENCE_WEIGHT)

    final_rating = (
        bayesian_rating * coverage +
        NEUTRAL_RATING * (1 - coverage)
    )

    # Convert from 1-5 star scale to Plex's 1-10 internal scale (multiply by 2)
    # Cap at 10 to ensure valid Plex rating (0-10)
    plex_rating = min(math.ceil(final_rating * 2), 10)
    return plex_rating

def process_album_tracks(album) -> List[float]:
    """Extract user ratings from rated tracks in an album.
    
    Filters out short tracks (intros/skits) and collects ratings from tracks
    that have been explicitly rated by the user.
    
    Args:
        album: Plex album object to process.
    
    Returns:
        List of user ratings from rated tracks.
    """
    rated_track_ratings = []

    for track in album.tracks():
        try:
            # Exclude intros/skits based on duration
            if track.duration is not None and (track.duration / 1000) < MIN_TRACK_DURATION:
                continue

            if track.userRating is not None:
                rated_track_ratings.append(track.userRating)
        except (AttributeError, TypeError) as e:
            logger.debug("Error processing track %s: %s", track.title, e)
            continue

    return rated_track_ratings


def process_single_album(album) -> tuple[bool, Optional[int]]:
    """Process a single album and determine if it needs a rating update.
    
    Collects track ratings, calculates a new album rating, and checks if it
    differs from the current rating. If UNRATE_EMPTY_ALBUMS is enabled, albums
    with no valid rating and an existing rating will be flagged for unrating.

    Args:
        album: Plex album object to process.

    Returns:
        Tuple of (needs_update, new_rating) where needs_update is True if
        the album should be rated/unrated and new_rating is the calculated rating
        or None if album should be unrated.
    """
    try:
        tracks = album.tracks()
    except (OSError, ValueError) as e:
        logger.warning("Failed to retrieve tracks for album %s: %s", album.title, e)
        return False, None

    total_tracks = len(tracks)
    rated_track_ratings = process_album_tracks(album)
    rated_count = len(rated_track_ratings)

    try:
        new_rating = calculate_album_rating(
            rated_track_ratings,
            rated_count,
            total_tracks
        )
    except (ValueError, TypeError) as e:
        logger.error("Failed to calculate rating for album %s: %s", album.title, e)
        return False, None

    current_rating = album.userRating

    if new_rating is None:
        # Check if we should unrate this album
        if UNRATE_EMPTY_ALBUMS and current_rating is not None:
            # Mark for unrating
            return True, None

        return False, None

    if current_rating == new_rating:
        logger.debug("Album %s already has rating %s, skipping", album.title, new_rating)
        return False, None

    return True, new_rating


def log_album_update(album, rated_count: int, total_tracks: int,
                     current_rating: Optional[int], new_rating: Optional[int]) -> None:
    """Log information about an album that needs rating update.
    
    Args:
        album: Plex album object.
        rated_count: Number of rated tracks in the album.
        total_tracks: Total number of tracks in the album.
        current_rating: Current album rating (Plex internal 1-10 scale) or None.
        new_rating: Newly calculated album rating (Plex internal 1-10 scale).
    """
    # Convert from Plex internal scale (1-10) to user-friendly display (1-5)
    display_new_rating = new_rating / 2 if new_rating is not None else None
    display_current_rating = current_rating / 2 if current_rating is not None else None
    
    status_msg = (
        f"{album.parentTitle} – {album.title}\n"
        f"  Rated tracks : {rated_count}/{total_tracks}\n"
        f"  New rating   : {display_new_rating} stars\n"
        f"  Old rating   : {display_current_rating or 'None'}\n"
    )
    logger.info("%s", status_msg)
    logger.info("Album update needed: %s – %s (rating: %s → %s)",
               album.parentTitle, album.title, display_current_rating or 'None', display_new_rating)


def apply_album_rating(album, new_rating: Optional[int]) -> bool:
    """Apply a new rating to an album in Plex.
    
    Args:
        album: Plex album object.
        new_rating: Rating to apply (1-10 scale) or None if no rating.
    
    Returns:
        True if rating was successfully applied, False otherwise.
    """
    if new_rating is None:
        return False

    try:
        album.rate(new_rating)
        logger.info("Successfully rated album %s as %s", album.title, new_rating)
        return True
    except (OSError, ValueError) as e:
        logger.error("Failed to rate album %s: %s", album.title, e)
        return False


def unrate_album(album) -> bool:
    """Remove the rating from an album in Plex.

    Args:
        album: Plex album object to unrate.

    Returns:
        True if album was successfully unrated, False otherwise.
    """
    try:
        album.rate(None)
        logger.info("Successfully unrated album %s", album.title)
        return True
    except (OSError, ValueError) as e:
        logger.error("Failed to unrate album %s: %s", album.title, e)
        return False


def connect_to_plex():
    """Connect to Plex server and retrieve music library.

    Returns:
        Tuple of (plex_server, music_library) or (None, None) if connection fails.
    """
    try:
        logger.info("Initializing Plex Album Auto-Rater")
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        music = plex.library.section(LIBRARY_NAME)
        return plex, music
    except ConnectionError as e:
        logger.error("Failed to connect to Plex server: %s", e)
        return None, None
    except (OSError, KeyError) as e:
        logger.error("Unexpected error initializing Plex: %s", e)
        return None, None


def log_configuration() -> None:
    """Log the current configuration and startup parameters."""
    logger.info("Starting Plex Album Auto-Rater")
    logger.info("Library              : %s", LIBRARY_NAME)
    logger.info("Dry run              : %s", DRY_RUN)
    logger.info("Min coverage         : %.0f%%", MIN_COVERAGE * 100)
    logger.info("Min track duration   : %ds", MIN_TRACK_DURATION)
    logger.info("Unrate empty albums  : %s", UNRATE_EMPTY_ALBUMS)


def log_summary(albums_processed: int, albums_updated: int, albums_skipped: int) -> None:
    """Log final statistics of the run.
    
    Args:
        albums_processed: Number of albums with updates needed.
        albums_updated: Number of albums that were successfully updated.
        albums_skipped: Number of albums that were skipped.
    """
    logger.info("-" * 60)
    logger.info("Albums evaluated : %s", albums_processed)
    logger.info("Albums updated   : %s", albums_updated)
    logger.info("Albums skipped   : %s", albums_skipped)
    logger.info("Album auto-rating complete.")


def main() -> None:
    """Main entry point for Plex Album Auto-Rater.
    
    Orchestrates the album rating process: connects to Plex, logs configuration,
    processes all albums, and logs final statistics.
    """
    # Connect to Plex server
    plex, music = connect_to_plex()
    if plex is None or music is None:
        return

    # Log startup configuration
    log_configuration()

    # Initialize counters
    albums_processed = 0
    albums_updated = 0
    albums_skipped = 0

    # Retrieve albums from library
    try:
        albums = music.albums()
    except (OSError, ValueError) as e:
        logger.error("Failed to retrieve albums from library: %s", e)
        return

    # Process each album
    for album in albums:
        needs_update, new_rating = process_single_album(album)

        if not needs_update:
            if new_rating is None:
                albums_skipped += 1
            continue

        albums_processed += 1

        # Handle unrating case
        if new_rating is None:
            logger.info("Album %s no longer meets coverage threshold", album.title)

            if DRY_RUN:
                logger.info("[DRY RUN] Album rating not removed")
                logger.info("[DRY RUN] Would unrate %s", album.title)
                continue

            if unrate_album(album):
                albums_updated += 1
            continue

        # Get album info for logging
        tracks = album.tracks()
        total_tracks = len(tracks)
        rated_track_ratings = process_album_tracks(album)
        rated_count = len(rated_track_ratings)
        current_rating = album.userRating

        # Log the update
        log_album_update(album, rated_count, total_tracks, current_rating, new_rating)

        # Handle dry-run mode
        if DRY_RUN:
            logger.info("[DRY RUN] Album rating not updated")
            logger.info("[DRY RUN] Would rate %s as %s", album.title, new_rating)
            continue

        # Apply rating to Plex
        if apply_album_rating(album, new_rating):
            albums_updated += 1

    # Log final summary
    log_summary(albums_processed, albums_updated, albums_skipped)

# =========================
# Entrypoint
# =========================

if __name__ == "__main__":
    main()
