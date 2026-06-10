import unittest
from pathlib import Path

from x_automation.config import Config
from x_automation.models import Tweet
from x_automation.ui import TwitterUI


def config() -> Config:
    return Config(
        package_name="com.twitter.android",
        gemini_api_key="test",
        gemini_model="test-model",
        max_tweets_to_comment=1,
        max_comments_per_hour=1,
        max_scrolls=1,
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
    )


class FakeSelector:
    def __init__(self, exists=False, info=None):
        self.exists = exists
        self.info = info or {}
        self.clicked = False

    def click(self):
        self.clicked = True


class FakeDevice:
    def __init__(self, selector):
        self.selector = selector
        self.clicked = None
        self.xml = """<?xml version='1.0' encoding='UTF-8'?><hierarchy>
          <node text="Show 12 new posts" content-desc="" bounds="[250,120][470,180]" resource-id="" package="com.twitter.android" />
        </hierarchy>"""

    def __call__(self, **kwargs):
        if kwargs.get("textContains") in {"Show", "new posts", "New posts", "posts"}:
            return self.selector
        return FakeSelector()

    def dump_hierarchy(self):
        return self.xml

    def click(self, x, y):
        self.clicked = (x, y)
        self.selector.clicked = True

    def window_size(self):
        return 720, 1600


class RefreshingUI(TwitterUI):
    def __init__(self, selector, visible_sequences):
        super().__init__(FakeDevice(selector), config())
        self.visible_sequences = list(visible_sequences)
        self.restarted = False

    def wait_random(self, min_sec, max_sec, action):
        return None

    def restart(self):
        self.restarted = True

    def visible_tweets(self):
        if self.visible_sequences:
            return self.visible_sequences.pop(0)
        return []


class UIRefreshTest(unittest.TestCase):
    def test_click_new_posts_pill_when_present(self):
        selector = FakeSelector(exists=True, info={"text": "Show 12 new posts"})
        ui = RefreshingUI(selector, [])

        self.assertTrue(ui.click_new_posts_pill())
        self.assertTrue(selector.clicked)

    def test_refresh_uses_restart_when_pill_does_not_change_feed(self):
        selector = FakeSelector(exists=True, info={"text": "Show 12 new posts"})
        old = Tweet(username="@a", body="old")
        new = Tweet(username="@b", body="new")
        ui = RefreshingUI(selector, [[old], [new]])

        self.assertTrue(ui.refresh_at_dead_end({old.fingerprint}))
        self.assertTrue(ui.restarted)

    def test_open_candidates_reject_partial_bottom_tweet(self):
        selector = FakeSelector()
        ui = RefreshingUI(selector, [])
        tweet = Tweet(
            username="@a",
            body="bottom partial",
            bounds="[0,1360][720,1510]",
            text_bounds="[117,1390][697,1472]",
            header_bounds="[117,1360][588,1400]",
        )

        self.assertEqual(ui._open_candidates(tweet), [])

    def test_open_candidates_prefer_text_then_header(self):
        selector = FakeSelector()
        ui = RefreshingUI(selector, [])
        tweet = Tweet(
            username="@a",
            body="safe visible tweet",
            bounds="[0,300][720,600]",
            text_bounds="[117,380][697,430]",
            header_bounds="[117,330][588,360]",
        )

        self.assertEqual(
            ui._open_candidates(tweet),
            [("text", 407, 405), ("header", 352, 345)],
        )

    def test_open_tweet_refreshes_coordinates_before_click(self):
        selector = FakeSelector()
        stale = Tweet(
            username="@a",
            body="same tweet body",
            bounds="[0,100][720,300]",
            text_bounds="[117,150][697,190]",
            header_bounds="[117,110][588,140]",
        )
        refreshed = Tweet(
            username="@a",
            body="same tweet body",
            bounds="[0,600][720,900]",
            text_bounds="[117,700][697,740]",
            header_bounds="[117,650][588,680]",
        )
        ui = RefreshingUI(selector, [[refreshed]])
        ui.verify_tweet_detail_opened = lambda: True

        self.assertTrue(ui.open_tweet(stale))
        self.assertEqual(ui.d.clicked, (407, 720))

    def test_click_home_tab_ignores_android_system_home(self):
        selector = FakeSelector()
        ui = RefreshingUI(selector, [])
        ui.d.xml = """<?xml version='1.0' encoding='UTF-8'?><hierarchy>
          <node content-desc="Home" bounds="[280,1510][439,1600]" package="com.android.systemui" />
          <node content-desc="Home. New items" bounds="[0,1405][144,1510]" package="com.twitter.android" />
        </hierarchy>"""

        self.assertTrue(ui._click_home_tab())
        self.assertEqual(ui.d.clicked, (72, 1457))


if __name__ == "__main__":
    unittest.main()
