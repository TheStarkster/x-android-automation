import unittest
from pathlib import Path

from config import Config
from models import GeneratedReply, Tweet
from runner import CommentRunner


def config() -> Config:
    return Config(
        package_name="com.twitter.android",
        gemini_api_key="test",
        gemini_model="test-model",
        max_tweets_to_comment=1,
        max_comments_per_hour=1,
        max_scrolls=2,
        top_comments=5,
        reply_sort="most_liked",
        posting_mode="auto_guarded",
        debug_artifacts=False,
        artifacts_dir=Path("artifacts"),
        runs_dir=Path("runs"),
        launch_wait_min=0,
        launch_wait_max=0,
        post_wait_min=0,
        post_wait_max=0,
        media_capture_mode="gallery",
        media_capture_retries=1,
        media_image_max_edge=1280,
        media_image_jpeg_quality=85,
    )


class FakeGenerator:
    def __init__(self, replies=None):
        self.replies = list(replies or [GeneratedReply(text="That distribution changes once the tool solves a real painful workflow.")])
        self.calls = []

    def test(self):
        return True

    def generate_reply(self, tweet, attempt=1, previous_failure=None):
        self.calls.append({"attempt": attempt, "previous_failure": previous_failure})
        generated = self.replies.pop(0)
        generated.attempt = attempt
        return generated


class FakeStore:
    def __init__(self):
        self.events = []

    def processed_fingerprints(self):
        return set()

    def posted_count_last_hour(self):
        return 0

    def append(self, event):
        self.events.append(event)


class FakeUI:
    def __init__(self, visible_sequences):
        self.visible_sequences = list(visible_sequences)
        self.scrolled = 0
        self.opened = []
        self.posted_replies = []
        self.capture_calls = 0

    def launch(self):
        return None

    def visible_tweets(self):
        if self.visible_sequences:
            return self.visible_sequences.pop(0)
        return []

    def can_open_tweet(self, tweet):
        return bool(tweet.text_bounds)

    def scroll_feed(self):
        self.scrolled += 1

    def refresh_at_dead_end(self, previous_fingerprints):
        return False

    def open_tweet(self, tweet):
        self.opened.append(tweet)
        return True

    def sort_replies_most_liked(self):
        return True

    def capture_primary_media_from_gallery(self, retries=None):
        self.capture_calls += 1
        from models import TweetImage

        return TweetImage(mime_type="image/jpeg", data_base64="abc", width=10, height=10, bytes_size=3)

    def top_comments(self, max_comments):
        return []

    def post_reply(self, reply_text):
        self.posted_replies.append(reply_text)
        return True

    def back_to_feed(self):
        return None


class RunnerTest(unittest.TestCase):
    def test_clipped_tweet_is_deferred_not_marked_seen(self):
        clipped = Tweet(username="@dev", body="Which model are you using most right now?")
        visible = Tweet(
            username="@dev",
            body="Which model are you using most right now?",
            text_bounds="[117,466][697,614]",
            header_bounds="[117,433][588,461]",
        )
        store = FakeStore()
        ui = FakeUI([[clipped], [visible]])
        runner = CommentRunner(config(), ui, FakeGenerator(), store)

        self.assertEqual(runner.run(), 1)

        self.assertEqual(ui.scrolled, 1)
        self.assertEqual([tweet.fingerprint for tweet in ui.opened], [visible.fingerprint])
        self.assertIn(visible.fingerprint, runner.session_seen)
        self.assertEqual([event.status for event in store.events], ["posted"])

    def test_generation_retries_after_token_limit(self):
        tweet = Tweet(
            username="@creator",
            body="AI video for reels is getting cheaper but still feels hard to control",
            text_bounds="[117,466][697,614]",
            header_bounds="[117,433][588,461]",
        )
        generator = FakeGenerator(
            [
                GeneratedReply(text="Creators need the tool to handle research and visuals because", finish_reason="MAX_TOKENS"),
                GeneratedReply(text="Cost only matters if the output still feels watchable. For reels, clear info beats cinematic flex most days."),
            ]
        )
        store = FakeStore()
        ui = FakeUI([[tweet]])
        runner = CommentRunner(config(), ui, generator, store)

        self.assertEqual(runner.run(), 1)

        self.assertEqual(len(generator.calls), 2)
        self.assertEqual(generator.calls[1]["previous_failure"], "model output hit token limit")
        self.assertEqual(len(ui.posted_replies), 1)
        self.assertEqual(store.events[0].reply["attempt"], 2)

    def test_generation_skips_after_all_attempts_fail_validation(self):
        tweet = Tweet(
            username="@dev",
            body="AI changes software engineering",
            text_bounds="[117,466][697,614]",
            header_bounds="[117,433][588,461]",
        )
        generator = FakeGenerator(
            [
                GeneratedReply(text="This is such a great point!"),
                GeneratedReply(text="This is such a great point!"),
                GeneratedReply(text="This is such a great point!"),
            ]
        )
        store = FakeStore()
        ui = FakeUI([[tweet], [], [], []])
        runner = CommentRunner(config(), ui, generator, store)

        self.assertEqual(runner.run(), 0)

        self.assertEqual(len(generator.calls), 3)
        self.assertEqual(ui.posted_replies, [])
        self.assertEqual(store.events[0].status, "skipped")
        self.assertEqual(store.events[0].reason, "reply is too generic")

    def test_media_capture_happens_before_reply_sorting(self):
        tweet = Tweet(
            username="@visual",
            body="This product screenshot explains the whole launch",
            text_bounds="[117,466][697,614]",
            header_bounds="[117,433][588,461]",
            has_media=True,
        )
        store = FakeStore()

        class OrderedUI(FakeUI):
            def __init__(self, visible_sequences):
                super().__init__(visible_sequences)
                self.actions = []

            def capture_primary_media_from_gallery(self, retries=None):
                self.actions.append("capture")
                return super().capture_primary_media_from_gallery(retries)

            def sort_replies_most_liked(self):
                self.actions.append("sort")
                return True

        ui = OrderedUI([[tweet]])
        runner = CommentRunner(config(), ui, FakeGenerator(), store)

        self.assertEqual(runner.run(), 1)
        self.assertEqual(ui.actions[:2], ["capture", "sort"])
        self.assertEqual(store.events[0].tweet["image_context"]["status"], "captured")
        self.assertNotIn("data_base64", store.events[0].tweet["image_context"])


if __name__ == "__main__":
    unittest.main()
