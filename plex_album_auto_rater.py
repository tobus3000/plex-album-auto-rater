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
    ROUNDING_BIAS_BAD_ALBUM (str): Rounding bias for albums below neutral rating.
        Defaults to "0.65" (harsher rounding).
    ROUNDING_BIAS_GOOD_ALBUM (str): Rounding bias for albums at or above neutral rating.
        Defaults to "0.45" (gentler rounding).
"""

import os
import logging
from typing import Optional
from plexapi.server import PlexServer
from plexapi.library import LibrarySection

# Configure logging to output to console (STDOUT)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load configuration from environment variables
PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
LIBRARY_NAME = os.getenv("PLEX_MUSIC_LIBRARY", "Music")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
UNRATE_EMPTY_ALBUMS = os.getenv("UNRATE_EMPTY_ALBUMS", "false").lower() == "true"

# Rating algorithm tuning
NEUTRAL_RATING = float(os.getenv("NEUTRAL_RATING", "2.5"))
CONFIDENCE_WEIGHT = int(os.getenv("CONFIDENCE_WEIGHT", "4"))
MIN_COVERAGE = float(os.getenv("MIN_COVERAGE", "0.2"))
MIN_TRACK_DURATION = int(os.getenv("MIN_TRACK_DURATION", "60"))
ROUNDING_BIAS_BAD_ALBUM = float(os.getenv("ROUNDING_BIAS_BAD_ALBUM", "0.65"))
ROUNDING_BIAS_GOOD_ALBUM = float(os.getenv("ROUNDING_BIAS_GOOD_ALBUM", "0.45"))


def asymmetric_rounding(final_rating: float) -> int:
    """
    Convert 1-5 star rating to Plex internal 1-10 scale with asymmetric rounding.
    Albums below NEUTRAL_RATING are rounded more harshly; above or at NEUTRAL_RATING
    are rounded more gently. Minimum rating is 1★ (Plex = 2).
    
    Args:
        final_rating: Album rating in 1-5 star scale.
    
    Returns:
        int: Album rating in Plex internal 1-10 scale.
    """
    plex_float = final_rating * 2
    if plex_float < 2:
        return 2
    if final_rating < NEUTRAL_RATING:
        return int(plex_float + ROUNDING_BIAS_BAD_ALBUM)
    return int(plex_float + ROUNDING_BIAS_GOOD_ALBUM)


def calculate_album_rating(
    rated_track_ratings: list[float], rated_track_count: int, total_tracks: int
) -> Optional[int]:
    """
    Calculate album rating using Bayesian shrinkage with coverage weighting.

    Args:
        rated_track_ratings: List of track ratings (1-5 scale).
        rated_track_count: Number of rated tracks included in calculation.
        total_tracks: Total number of tracks in album.

    Returns:
        Plex album rating (1-10 scale) or None if no rated tracks.
    """
    if rated_track_count == 0:
        return None

    coverage = rated_track_count / total_tracks
    avg_rating = sum(rated_track_ratings) / rated_track_count

    # Bayesian shrinkage formula
    bayesian_rating = (
        (rated_track_count * avg_rating) + (CONFIDENCE_WEIGHT * NEUTRAL_RATING)
    ) / (rated_track_count + CONFIDENCE_WEIGHT)

    # Weight by coverage
    final_rating = bayesian_rating * coverage + NEUTRAL_RATING * (1 - coverage)

    # Convert to Plex internal scale
    return min(asymmetric_rounding(final_rating), 10)


def process_album_tracks(album, include_all_for_override: bool = False) -> list[float]:
    """
    Extract rated tracks from an album, optionally including all tracks for hard overrides.

    Args:
        album: Plex album object.
        include_all_for_override: If True, include all rated tracks regardless of duration.

    Returns:
        List of track ratings (1-5).
    """
    ratings = []
    for track in album.tracks():
        try:
            if track.userRating is None:
                continue
            if not include_all_for_override and track.duration is not None:
                if (track.duration / 1000) < MIN_TRACK_DURATION:
                    continue
            ratings.append(track.userRating)
        except (AttributeError, TypeError) as e:
            logger.debug("Error processing track %s: %s", getattr(track, "title", None), e)
    return ratings


def process_single_album(album) -> tuple[bool, Optional[int], int, int]:
    """
    Determine if an album requires rating update and calculate new rating.

    Args:
        album: Plex album object.

    Returns:
        Tuple of:
        - needs_update (bool)
        - new_rating (int or None)
        - rated_count (int)
        - total_tracks (int)
    """
    try:
        tracks = album.tracks()
    except (OSError, ValueError) as e:
        logger.warning("Failed to retrieve tracks for album %s: %s", album.title, e)
        return False, None, 0, 0

    total_tracks = len(tracks)
    rated_track_ratings = process_album_tracks(album)
    override_track_ratings = process_album_tracks(album, include_all_for_override=True)
    rated_count = len(rated_track_ratings)
    current_rating = getattr(album, "userRating", None)

    # Skip if no rated tracks or coverage too low
    coverage = rated_count / total_tracks if total_tracks > 0 else 0
    if rated_count == 0 or coverage < MIN_COVERAGE:
        if UNRATE_EMPTY_ALBUMS and current_rating is not None:
            return True, None, rated_count, total_tracks
        return False, None, rated_count, total_tracks

    # Hard overrides
    PLEX_1_STAR = 2
    PLEX_5_STAR = 10
    if override_track_ratings and all(r == PLEX_1_STAR for r in override_track_ratings):
        if current_rating != PLEX_1_STAR:
            return True, PLEX_1_STAR, rated_count, total_tracks
        return False, None, rated_count, total_tracks
    if override_track_ratings and all(r == PLEX_5_STAR for r in override_track_ratings):
        if current_rating != PLEX_5_STAR:
            return True, PLEX_5_STAR, rated_count, total_tracks
        return False, None, rated_count, total_tracks

    # Bayesian rating
    new_rating = calculate_album_rating(rated_track_ratings, rated_count, total_tracks)
    if new_rating is None or new_rating == current_rating:
        return False, None, rated_count, total_tracks

    return True, new_rating, rated_count, total_tracks


def log_album_update(album, rated_count: int, total_tracks: int,
                     current_rating: Optional[int], new_rating: Optional[int]) -> None:
    """
    Log album rating updates.

    Args:
        album: Plex album object.
        rated_count: Number of rated tracks included.
        total_tracks: Total tracks in album.
        current_rating: Current album rating (Plex scale).
        new_rating: New album rating (Plex scale).
    """
    display_current = current_rating / 2 if current_rating else None
    display_new = new_rating / 2 if new_rating else None
    old_rating_str = f"{display_current} stars" if display_current else "None"
    logger.info(
        "%s - %s\n  Rated tracks : %d/%d\n  New rating   : %s stars\n  Old rating   : %s\n",
        album.parentTitle, album.title, rated_count, total_tracks, display_new, old_rating_str
    )
    logger.info(
        "Album update needed: %s - %s (rating: %s → %s)",
        album.parentTitle, album.title, display_current or "None", display_new
    )


def apply_album_rating(album, new_rating: Optional[int]) -> bool:
    """
    Apply a rating to a Plex album.

    Args:
        album: Plex album object.
        new_rating: Rating to apply (Plex 1-10 scale).

    Returns:
        True if applied successfully, False otherwise.
    """
    if new_rating is None:
        return False
    try:
        album.rate(new_rating)
        logger.info("Successfully rated album %s as %s in Plex (1-10 scale)", album.title, new_rating)
        return True
    except (OSError, ValueError) as e:
        logger.error("Failed to rate album %s: %s", album.title, e)
        return False


def unrate_album(album) -> bool:
    """
    Remove rating from a Plex album.

    Args:
        album: Plex album object.

    Returns:
        True if unrated successfully, False otherwise.
    """
    try:
        album.rate(None)
        logger.info("Successfully unrated album %s", album.title)
        return True
    except (OSError, ValueError) as e:
        logger.error("Failed to unrate album %s: %s", album.title, e)
        return False


def connect_to_plex() -> tuple[Optional[PlexServer], Optional[LibrarySection]]:
    """
    Connect to Plex server and retrieve music library.

    Returns:
        Tuple of (plex_server, music_library) or (None, None) if connection fails.
    """
    try:
        logger.info("Initializing Plex Album Auto-Rater")
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        music = plex.library.section(LIBRARY_NAME)
        return plex, music
    except (ConnectionError, OSError, KeyError) as e:
        logger.error("Failed to connect to Plex: %s", e)
        return None, None


def log_configuration() -> None:
    """Log startup configuration of the auto-rater."""
    logger.info("Starting Plex Album Auto-Rater")
    logger.info("Library              : %s", LIBRARY_NAME)
    logger.info("Dry run              : %s", DRY_RUN)
    logger.info("Min coverage         : %.0f%%", MIN_COVERAGE * 100)
    logger.info("Min track duration   : %ds", MIN_TRACK_DURATION)
    logger.info("Unrate empty albums  : %s", UNRATE_EMPTY_ALBUMS)


def log_summary(albums_processed: int, albums_updated: int, albums_skipped: int) -> None:
    """
    Log final statistics after processing all albums.

    Args:
        albums_processed: Number of albums that required update.
        albums_updated: Number of albums successfully updated.
        albums_skipped: Number of albums skipped.
    """
    logger.info("-" * 60)
    logger.info("Albums evaluated : %d", albums_processed)
    logger.info("Albums updated   : %d", albums_updated)
    logger.info("Albums skipped   : %d", albums_skipped)
    logger.info("Album auto-rating complete.")


def main() -> None:
    """Main entry point for Plex Album Auto-Rater."""
    plex, music = connect_to_plex()
    if plex is None or music is None:
        return

    log_configuration()
    albums_processed = 0
    albums_updated = 0
    albums_skipped = 0

    try:
        albums = music.albums()
    except (OSError, ValueError) as e:
        logger.error("Failed to retrieve albums from library: %s", e)
        return

    for album in albums:
        needs_update, new_rating, rated_count, total_tracks = process_single_album(album)

        if not needs_update:
            if new_rating is None:
                albums_skipped += 1
            continue

        albums_processed += 1

        if new_rating is None:
            logger.info("Album %s no longer meets coverage threshold", album.title)
            if DRY_RUN:
                logger.info("[DRY RUN] Album rating not removed")
                continue
            if unrate_album(album):
                albums_updated += 1
            continue

        current_rating = album.userRating
        log_album_update(album, rated_count, total_tracks, current_rating, new_rating)

        if DRY_RUN:
            logger.info("[DRY RUN] Album rating not updated")
            continue

        if apply_album_rating(album, new_rating):
            albums_updated += 1

    log_summary(albums_processed, albums_updated, albums_skipped)


if __name__ == "__main__":
    main()
