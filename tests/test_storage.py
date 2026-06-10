import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from x_automation.models import RunEvent, Tweet
from x_automation.storage import RunStore


class RunStoreTest(unittest.TestCase):
    def test_run_store_tracks_posted_fingerprints_and_hourly_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(Path(tmp))
            store.append(RunEvent(event="tweet_processed", tweet_fingerprint="abc", status="posted"))
            store.append(RunEvent(event="tweet_processed", tweet_fingerprint="def", status="skipped"))

            self.assertEqual(store.processed_fingerprints(), {"abc"})
            self.assertEqual(store.posted_count_since(datetime(2000, 1, 1, tzinfo=timezone.utc)), 1)

    def test_processed_fingerprints_include_stable_identity_from_old_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(Path(tmp))
            tweet = Tweet(username="@nalinrajput23", body="is coding still worth learning in the AI era??")
            store.append(
                RunEvent(
                    event="tweet_processed",
                    tweet_fingerprint="old_metric_based_fingerprint",
                    tweet={
                        "username": tweet.username,
                        "body": tweet.body,
                        "replies": 10,
                        "likes": 50,
                        "views": 1000,
                    },
                    status="posted",
                )
            )

            self.assertIn(tweet.fingerprint, store.processed_fingerprints())
