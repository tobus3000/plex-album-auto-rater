"""Tests for album rating calculations and Plex operations."""

import runpy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import plex_album_auto_rater as rater
from requests.exceptions import ReadTimeout


class Album:
    """Provide a minimal Plex album for rating tests."""

    def __init__(self, ratings_and_durations, current_rating=None):
        """Create an album with track ratings and durations.

        Args:
            ratings_and_durations: Pairs of Plex ratings and durations in milliseconds.
            current_rating: Current Plex album rating, or None if unrated.
        """
        self.userRating = current_rating
        self._tracks = [
            SimpleNamespace(userRating=rating, duration=duration)
            for rating, duration in ratings_and_durations
        ]

    def tracks(self):
        """Return the album's simulated track objects."""
        return self._tracks


class AlbumRatingScaleTests(unittest.TestCase):
    """Test conversion between Plex ratings and star ratings."""

    def setUp(self):
        """Use deterministic settings for rating calculations."""
        settings = patch.multiple(
            rater,
            NEUTRAL_RATING=2.5,
            CONFIDENCE_WEIGHT=4,
            MIN_COVERAGE=0.2,
            MIN_TRACK_DURATION=60,
            ROUNDING_BIAS_BAD_ALBUM=0.65,
            ROUNDING_BIAS_GOOD_ALBUM=0.45,
            UNRATE_EMPTY_ALBUMS=False,
        )
        settings.start()
        self.addCleanup(settings.stop)

    def test_mixed_ratings_are_converted_before_calculation(self):
        """Convert mixed track ratings and skip an already matching album."""
        album = Album([(6, 180000), (8, 180000)])
        self.assertEqual(rater.process_single_album(album), (True, 6, 2, 2))
        album.userRating = 6
        self.assertEqual(rater.process_single_album(album), (False, None, 2, 2))

    def test_coverage_and_short_track_filtering_are_preserved(self):
        """Apply coverage weighting while excluding short tracks."""
        album = Album([(6, 180000), (8, 180000), (10, 30000), (None, 180000)])
        self.assertEqual(rater.process_single_album(album), (True, 5, 2, 4))

    def test_hard_overrides_still_use_all_raw_track_ratings(self):
        """Use all raw track ratings, including short tracks, for overrides."""
        for rating in (2, 10):
            with self.subTest(rating=rating):
                album = Album([(rating, 180000), (rating, 30000)])
                self.assertEqual(rater.process_single_album(album), (True, rating, 1, 2))

        mixed = Album([(2, 180000), (10, 30000)])
        self.assertEqual(rater.process_single_album(mixed), (True, 5, 1, 2))


class PlexReadTimeoutTests(unittest.TestCase):
    """Test that Plex read timeouts are logged without stopping later albums."""

    def setUp(self):
        """Use consistent coverage and duration thresholds."""
        settings = patch.multiple(rater, MIN_COVERAGE=0.2, MIN_TRACK_DURATION=60)
        settings.start()
        self.addCleanup(settings.stop)

    def test_track_timeout_skips_album_and_continues(self):
        """Skip an album when reading a track rating times out."""
        class TimedOutTrack:
            """Simulate a track whose rating cannot be loaded."""

            @property
            def userRating(self):
                """Raise a read timeout when the rating is requested.

                Raises:
                    ReadTimeout: Always, to simulate a failed Plex request.
                """
                raise ReadTimeout("track read timed out")

        failed = Mock(title="Failed", parentTitle="Artist", userRating=None)
        failed.tracks.return_value = [TimedOutTrack()]
        successful = Mock(title="Next", parentTitle="Artist", userRating=None)
        successful.tracks.return_value = [SimpleNamespace(userRating=10, duration=180000)]
        music = Mock()
        music.albums.return_value = [failed, successful]

        with (
            patch.object(rater, "connect_to_plex", return_value=(object(), music)),
            patch.object(rater, "DRY_RUN", False),
            patch.object(rater, "UNRATE_EMPTY_ALBUMS", True),
            self.assertLogs(rater.logger, level="WARNING") as logs,
        ):
            rater.main()

        self.assertIn("album Failed; skipping: track read timed out", "\n".join(logs.output))
        failed.rate.assert_not_called()
        successful.rate.assert_called_once_with(10)

    def test_timeout_during_repeated_track_fetch_skips_album(self):
        """Skip an album if a later request for its tracks times out."""
        failed = Mock(title="Failed", parentTitle="Artist", userRating=None)
        failed.tracks.side_effect = [
            [SimpleNamespace(userRating=10, duration=180000)],
            ReadTimeout("tracks read timed out"),
        ]
        successful = Mock(title="Next", parentTitle="Artist", userRating=None)
        successful.tracks.return_value = [SimpleNamespace(userRating=10, duration=180000)]
        music = Mock()
        music.albums.return_value = [failed, successful]

        with (
            patch.object(rater, "connect_to_plex", return_value=(object(), music)),
            patch.object(rater, "DRY_RUN", False),
            self.assertLogs(rater.logger, level="WARNING") as logs,
        ):
            rater.main()

        self.assertIn("tracks read timed out", "\n".join(logs.output))
        failed.rate.assert_not_called()
        successful.rate.assert_called_once_with(10)

    def test_rating_write_timeout_is_logged_and_continues(self):
        """Log a rating request timeout and continue with the next album."""
        failed = Mock(title="Failed", parentTitle="Artist", userRating=None)
        failed.tracks.return_value = [SimpleNamespace(userRating=10, duration=180000)]
        failed.rate.side_effect = ReadTimeout("rating read timed out")
        successful = Mock(title="Next", parentTitle="Artist", userRating=None)
        successful.tracks.return_value = [SimpleNamespace(userRating=10, duration=180000)]
        music = Mock()
        music.albums.return_value = [failed, successful]

        with (
            patch.object(rater, "connect_to_plex", return_value=(object(), music)),
            patch.object(rater, "DRY_RUN", False),
            self.assertLogs(rater.logger, level="ERROR") as logs,
        ):
            rater.main()

        self.assertIn("rating read timed out", "\n".join(logs.output))
        successful.rate.assert_called_once_with(10)


class AlbumProcessingTests(unittest.TestCase):
    """Test album selection, track handling, and calculation edge cases."""

    def setUp(self):
        """Use deterministic settings for album processing."""
        settings = patch.multiple(
            rater,
            NEUTRAL_RATING=2.5,
            CONFIDENCE_WEIGHT=4,
            MIN_COVERAGE=0.2,
            MIN_TRACK_DURATION=60,
            ROUNDING_BIAS_BAD_ALBUM=0.65,
            ROUNDING_BIAS_GOOD_ALBUM=0.45,
            UNRATE_EMPTY_ALBUMS=False,
        )
        settings.start()
        self.addCleanup(settings.stop)

    def test_rounding_and_empty_calculation(self):
        """Check rating bounds, rounding, and albums with no rated tracks."""
        self.assertEqual(rater.asymmetric_rounding(0.5), 2)
        self.assertEqual(rater.asymmetric_rounding(2.0), 4)
        self.assertEqual(rater.asymmetric_rounding(3.0), 6)
        self.assertIsNone(rater.calculate_album_rating([], 0, 0))
        with patch.object(rater, "CONFIDENCE_WEIGHT", 0):
            self.assertEqual(rater.calculate_album_rating([5], 1, 1), 10)

    def test_invalid_tracks_are_logged_and_missing_duration_is_included(self):
        """Log invalid track data while including tracks without a duration."""
        album = Mock()
        album.tracks.return_value = [
            SimpleNamespace(userRating=6, duration=None),
            SimpleNamespace(userRating=8, duration="invalid", title="Bad duration"),
            SimpleNamespace(title="Missing rating"),
        ]
        with self.assertLogs(rater.logger, level="DEBUG") as logs:
            self.assertEqual(rater.process_album_tracks(album), [6])
        self.assertIn("Bad duration", "\n".join(logs.output))
        self.assertIn("Missing rating", "\n".join(logs.output))

    def test_empty_and_low_coverage_albums(self):
        """Skip or unrate albums that do not meet the coverage threshold."""
        empty = Album([], current_rating=6)
        low_coverage = Album([(6, 180000)] + [(None, 180000)] * 5, current_rating=6)
        self.assertEqual(rater.process_single_album(empty), (False, None, 0, 0))
        self.assertEqual(rater.process_single_album(low_coverage), (False, None, 1, 6))
        with patch.object(rater, "UNRATE_EMPTY_ALBUMS", True):
            self.assertEqual(rater.process_single_album(empty), (True, None, 0, 0))
            self.assertEqual(rater.process_single_album(low_coverage), (True, None, 1, 6))
            empty.userRating = None
            self.assertEqual(rater.process_single_album(empty), (False, None, 0, 0))

    def test_track_fetch_failure_is_logged(self):
        """Log and skip an album when its tracks cannot be retrieved."""
        album = Mock(title="Unavailable")
        album.tracks.side_effect = OSError("track fetch failed")
        with self.assertLogs(rater.logger, level="WARNING") as logs:
            self.assertEqual(rater.process_single_album(album), (False, None, 0, 0))
        self.assertIn("track fetch failed", "\n".join(logs.output))

    def test_unchanged_overrides_and_missing_calculation(self):
        """Skip unchanged overrides and an unavailable calculated rating."""
        for rating in (2, 10):
            with self.subTest(rating=rating):
                album = Album([(rating, 180000)], current_rating=rating)
                self.assertEqual(rater.process_single_album(album), (False, None, 1, 1))
        album = Album([(6, 180000), (8, 180000)])
        with patch.object(rater, "calculate_album_rating", return_value=None):
            self.assertEqual(rater.process_single_album(album), (False, None, 2, 2))


class PlexOperationTests(unittest.TestCase):
    """Test Plex connection, rating operations, and main-loop behavior."""

    def setUp(self):
        """Use consistent coverage and duration thresholds."""
        settings = patch.multiple(rater, MIN_COVERAGE=0.2, MIN_TRACK_DURATION=60)
        settings.start()
        self.addCleanup(settings.stop)

    def test_connect_success_and_failure(self):
        """Return the library on success and log connection failures."""
        server = Mock()
        music = server.library.section.return_value
        with patch.object(rater, "PlexServer", return_value=server) as connect:
            self.assertEqual(rater.connect_to_plex(), (server, music))
        connect.assert_called_once_with(rater.PLEX_URL, rater.PLEX_TOKEN)
        server.library.section.assert_called_once_with(rater.LIBRARY_NAME)

        with (
            patch.object(rater, "PlexServer", side_effect=OSError("offline")),
            self.assertLogs(rater.logger, level="ERROR") as logs,
        ):
            self.assertEqual(rater.connect_to_plex(), (None, None))
        self.assertIn("offline", "\n".join(logs.output))

    def test_rate_and_unrate_failures_are_reported(self):
        """Report failed rating changes and avoid applying a missing rating."""
        album = Mock(title="Album")
        self.assertFalse(rater.apply_album_rating(album, None))
        album.rate.assert_not_called()
        self.assertTrue(rater.unrate_album(album))
        album.rate.assert_called_once_with(None)
        album.rate.side_effect = ValueError("update failed")
        with self.assertLogs(rater.logger, level="ERROR") as logs:
            self.assertFalse(rater.apply_album_rating(album, 6))
            self.assertFalse(rater.unrate_album(album))
        self.assertEqual(len(logs.output), 2)
        self.assertTrue(all("update failed" in message for message in logs.output))

    def test_main_handles_connection_and_library_failures(self):
        """Stop processing when the server or library is unavailable."""
        with patch.object(rater, "connect_to_plex", return_value=(None, None)):
            rater.main()
        with patch.object(rater, "connect_to_plex", return_value=(object(), None)):
            rater.main()
        music = Mock()
        music.albums.side_effect = OSError("library unavailable")
        with (
            patch.object(rater, "connect_to_plex", return_value=(object(), music)),
            self.assertLogs(rater.logger, level="ERROR") as logs,
        ):
            rater.main()
        self.assertIn("library unavailable", "\n".join(logs.output))

    def test_dry_run_does_not_rate_or_unrate(self):
        """Log proposed rating changes without sending them to Plex."""
        rated = Mock(title="Rated", parentTitle="Artist", userRating=4)
        rated.tracks.return_value = [SimpleNamespace(userRating=10, duration=180000)]
        empty = Mock(title="Empty", parentTitle="Artist", userRating=6)
        empty.tracks.return_value = []
        unchanged = Mock(title="Unchanged", parentTitle="Artist", userRating=10)
        unchanged.tracks.return_value = [SimpleNamespace(userRating=10, duration=180000)]
        music = Mock()
        music.albums.return_value = [rated, empty, unchanged]
        with (
            patch.object(rater, "connect_to_plex", return_value=(object(), music)),
            patch.object(rater, "DRY_RUN", True),
            patch.object(rater, "UNRATE_EMPTY_ALBUMS", True),
            self.assertLogs(rater.logger, level="INFO") as logs,
        ):
            rater.main()
        rated.rate.assert_not_called()
        empty.rate.assert_not_called()
        unchanged.rate.assert_not_called()
        output = "\n".join(logs.output)
        self.assertIn("[DRY RUN] Album rating not updated", output)
        self.assertIn("[DRY RUN] Album rating not removed", output)
        self.assertIn("Albums skipped   : 1", output)

    def test_main_unrates_and_continues_after_unrate_failure(self):
        """Continue unrated album processing after a failed removal."""
        failed = Mock(title="Failed", parentTitle="Artist", userRating=6)
        failed.tracks.return_value = []
        failed.rate.side_effect = OSError("unrate failed")
        successful = Mock(title="Success", parentTitle="Artist", userRating=6)
        successful.tracks.return_value = []
        music = Mock()
        music.albums.return_value = [failed, successful]
        with (
            patch.object(rater, "connect_to_plex", return_value=(object(), music)),
            patch.object(rater, "DRY_RUN", False),
            patch.object(rater, "UNRATE_EMPTY_ALBUMS", True),
            self.assertLogs(rater.logger, level="INFO") as logs,
        ):
            rater.main()
        failed.rate.assert_called_once_with(None)
        successful.rate.assert_called_once_with(None)
        output = "\n".join(logs.output)
        self.assertIn("unrate failed", output)
        self.assertIn("Albums updated   : 1", output)

    def test_main_ignores_non_update_result(self):
        """Leave the skip count unchanged for a non-update with a rating."""
        music = Mock()
        music.albums.return_value = [Mock(title="Album")]
        with (
            patch.object(rater, "connect_to_plex", return_value=(object(), music)),
            patch.object(rater, "process_single_album", return_value=(False, 6, 1, 1)),
            self.assertLogs(rater.logger, level="INFO") as logs,
        ):
            rater.main()
        self.assertIn("Albums skipped   : 0", "\n".join(logs.output))

    def test_script_entry_point_runs_main(self):
        """Run the main loop when the module is executed as a script."""
        server = Mock()
        server.library.section.return_value.albums.return_value = []
        with patch("plexapi.server.PlexServer", return_value=server) as connect:
            runpy.run_module("plex_album_auto_rater", run_name="__main__")
        connect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
