import unittest
from pathlib import Path

from config import Config
from models import Tweet
from ui import TwitterUI


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
        media_capture_mode="gallery",
        media_capture_retries=1,
        media_image_max_edge=1280,
        media_image_jpeg_quality=85,
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
        self.swipes = []
        self.swipe_xmls = []
        self.presses = []
        self.gallery_xml = None
        self.detail_xml = None
        self.xml = """<?xml version='1.0' encoding='UTF-8'?><hierarchy>
          <node text="Show 12 new posts" content-desc="" bounds="[250,120][470,180]" resource-id="" package="com.twitter.android" />
        </hierarchy>"""

    def __call__(self, **kwargs):
        if "resourceId" in kwargs:
            exists = f'resource-id="{kwargs["resourceId"]}"' in self.xml
            return FakeSelector(exists=exists)
        if "text" in kwargs:
            exists = f'text="{kwargs["text"]}"' in self.xml
            return FakeSelector(exists=exists)
        if kwargs.get("textContains") in {"Show", "new posts", "New posts", "posts"}:
            return self.selector
        return FakeSelector()

    def dump_hierarchy(self):
        return self.xml

    def click(self, x, y):
        self.clicked = (x, y)
        self.selector.clicked = True
        if self.gallery_xml:
            self.detail_xml = self.xml
            self.xml = self.gallery_xml

    def swipe(self, x1, y1, x2, y2, duration=0):
        self.swipes.append((x1, y1, x2, y2, duration))
        if self.swipe_xmls:
            self.xml = self.swipe_xmls.pop(0)

    def press(self, key):
        self.presses.append(key)
        if key == "back" and self.detail_xml:
            self.xml = self.detail_xml
            self.detail_xml = None

    def screenshot(self, format=None):
        from PIL import Image

        return Image.new("RGB", (320, 240), "white")

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

    def test_verify_detail_does_not_scroll_when_reply_sorting_is_below_large_media(self):
        selector = FakeSelector()
        ui = RefreshingUI(selector, [])
        ui.d.xml = """<?xml version='1.0' encoding='UTF-8'?><hierarchy>
          <node resource-id="com.twitter.android:id/toolbar" text="" bounds="[0,59][720,164]" />
          <node resource-id="com.twitter.android:id/row" content-desc="Author @author Big image post. 1 hour ago." bounds="[0,164][720,1416]" />
          <node resource-id="com.twitter.android:id/card_media_tweet_container" bounds="[23,533][698,1390]" />
          <node resource-id="com.twitter.android:id/byline_combined" text="1:00 pm · 10 Jun 26 · 1K Views" bounds="[23,1401][698,1416]" />
          <node resource-id="com.twitter.android:id/persistent_reply" bounds="[0,1416][720,1510]" />
        </hierarchy>"""
        ui.d.swipe_xmls = [
            """<?xml version='1.0' encoding='UTF-8'?><hierarchy>
              <node resource-id="com.twitter.android:id/toolbar" text="" bounds="[0,59][720,164]" />
              <node resource-id="com.twitter.android:id/row" content-desc="Author @author Big image post. 1 hour ago." bounds="[0,164][720,943]" />
              <node resource-id="com.twitter.android:id/reply_sorting" text="Most relevant replies" bounds="[0,943][342,1033]" />
              <node resource-id="com.twitter.android:id/persistent_reply" bounds="[0,1416][720,1510]" />
            </hierarchy>"""
        ]

        self.assertTrue(ui.verify_tweet_detail_opened())
        self.assertEqual(ui.d.swipes, [])
        self.assertNotIn("com.twitter.android:id/reply_sorting", ui.d.xml)

        self.assertTrue(ui._ensure_reply_sorting_visible())
        self.assertEqual(len(ui.d.swipes), 1)
        self.assertIn("com.twitter.android:id/reply_sorting", ui.d.xml)

    def test_verify_detail_does_not_scroll_feed_without_reply_sorting(self):
        selector = FakeSelector()
        ui = RefreshingUI(selector, [])
        ui.d.xml = """<?xml version='1.0' encoding='UTF-8'?><hierarchy>
          <node content-desc="Home timeline list" bounds="[0,164][720,1510]" />
          <node resource-id="com.twitter.android:id/row" content-desc="Author @author Feed post. 1 hour ago." bounds="[0,300][720,700]" />
        </hierarchy>"""

        self.assertFalse(ui.verify_tweet_detail_opened())
        self.assertEqual(ui.d.swipes, [])

    def test_capture_primary_media_opens_gallery_encodes_and_returns_to_detail(self):
        selector = FakeSelector()
        ui = RefreshingUI(selector, [])
        detail_xml = """<?xml version='1.0' encoding='UTF-8'?><hierarchy>
          <node resource-id="com.twitter.android:id/toolbar" text="" bounds="[0,59][720,164]" />
          <node resource-id="com.twitter.android:id/row" content-desc="Author @author Big image post. 1 hour ago." bounds="[0,164][720,943]" />
          <node resource-id="com.twitter.android:id/card_media_tweet_container" bounds="[117,252][697,578]" />
          <node resource-id="com.twitter.android:id/persistent_reply" bounds="[0,1416][720,1510]" />
        </hierarchy>"""
        ui.d.xml = detail_xml
        ui.d.gallery_xml = """<?xml version='1.0' encoding='UTF-8'?><hierarchy>
          <node resource-id="com.twitter.android:id/gallery_chrome_root" bounds="[0,0][720,1600]" />
        </hierarchy>"""

        image = ui.capture_primary_media_from_gallery(retries=0)

        self.assertEqual(image.status, "captured")
        self.assertEqual(image.mime_type, "image/jpeg")
        self.assertTrue(image.data_base64)
        self.assertEqual(ui.d.clicked, (407, 415))
        self.assertEqual(ui.d.presses, ["back"])
        self.assertEqual(ui.d.xml, detail_xml)

    def test_capture_primary_media_retries_once_after_failed_gallery_open(self):
        selector = FakeSelector()
        ui = RefreshingUI(selector, [])
        ui.d.xml = """<?xml version='1.0' encoding='UTF-8'?><hierarchy>
          <node resource-id="com.twitter.android:id/card_media_tweet_container" bounds="[117,252][697,578]" />
        </hierarchy>"""

        image = ui.capture_primary_media_from_gallery(retries=1)

        self.assertEqual(image.status, "failed")
        self.assertEqual(image.reason, "media gallery did not open")


if __name__ == "__main__":
    unittest.main()
