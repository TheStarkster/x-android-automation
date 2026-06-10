from __future__ import annotations

import logging
import random
import re
import time

from .config import Config
from .models import Tweet
from .parser import parse_top_comments, parse_visible_tweets

logger = logging.getLogger(__name__)


class TwitterUI:
    def __init__(self, device, config: Config):
        self.d = device
        self.config = config

    def wait_random(self, min_sec: float, max_sec: float, action: str) -> None:
        wait_time = random.uniform(min_sec, max_sec)
        logger.info("Waiting %.1fs after %s", wait_time, action)
        time.sleep(wait_time)

    def launch(self) -> None:
        logger.info("Launching X app package=%s", self.config.package_name)
        self.d.app_start(self.config.package_name)
        self.wait_random(self.config.launch_wait_min, self.config.launch_wait_max, "app launch")
        self.ensure_home_feed()

    def restart(self) -> None:
        logger.info("Restarting X app")
        try:
            self.d.app_stop(self.config.package_name)
            time.sleep(2)
        except Exception:
            logger.exception("App stop failed; continuing with app_start")
        self.launch()

    def visible_tweets(self) -> list[Tweet]:
        self.ensure_home_feed()
        xml_str = self.d.dump_hierarchy()
        self.save_artifact("feed.xml", xml_str)
        return parse_visible_tweets(xml_str)

    def open_tweet(self, tweet: Tweet, max_retries: int = 2) -> bool:
        for attempt in range(max_retries + 1):
            current = self._refresh_tweet_from_feed(tweet)
            if not current:
                logger.warning("Tweet is no longer visible before open: %s", tweet.fingerprint)
                return False

            candidates = self._open_candidates(current)
            if not candidates:
                logger.warning("Tweet has no usable open coordinates: %s", tweet.fingerprint)
                return False

            for name, x, y in candidates:
                logger.info("Opening tweet %s attempt=%s target=%s point=(%s,%s)", tweet.fingerprint, attempt + 1, name, x, y)
                self.d.click(x, y)
                if self.verify_tweet_detail_opened():
                    return True

                if not self.is_feed_screen():
                    self.d.press("back")
                    self.wait_random(1, 2, "failed open retry")

        return False

    def _refresh_tweet_from_feed(self, tweet: Tweet) -> Tweet | None:
        tweets = self.visible_tweets()
        for current in tweets:
            if current.fingerprint == tweet.fingerprint:
                return current
        return None

    def can_open_tweet(self, tweet: Tweet) -> bool:
        return bool(self._open_candidates(tweet))

    def verify_tweet_detail_opened(self) -> bool:
        self.wait_random(1, 2, "tweet detail load")
        xml_str = self.d.dump_hierarchy()
        if "com.twitter.android:id/gallery_chrome_root" in xml_str or "com.twitter.android:id/gallery_chrome_control_root" in xml_str:
            logger.warning("Opened media gallery instead of tweet detail")
            self.save_artifact("open_gallery.xml", xml_str)
            return False
        if self.d(resourceId="com.twitter.android:id/tweet_button").exists:
            logger.warning("Opened composer instead of tweet detail")
            self.save_artifact("open_composer.xml", xml_str)
            return False
        if self.d(resourceId="com.twitter.android:id/reply_sorting").exists:
            return True

        self.save_artifact("open_failed.xml", xml_str)
        return False

    def sort_replies_most_liked(self) -> bool:
        logger.info("Sorting replies by Most liked")
        if not self.d(resourceId="com.twitter.android:id/reply_sorting").exists:
            logger.warning("Reply sorting control not found")
            return False

        self.d(resourceId="com.twitter.android:id/reply_sorting").click()
        self.wait_random(1, 2, "sorting sheet open")
        if self.d(text="Most liked").exists:
            self.d(text="Most liked").click()
            self.wait_random(2, 3, "reply reorder")
            return True

        logger.warning("Most liked option not found")
        self.d.press("back")
        return False

    def top_comments(self, max_comments: int) -> list:
        self.wait_random(2, 3, "comments load")
        xml_str = self.d.dump_hierarchy()
        self.save_artifact("comments.xml", xml_str)
        return parse_top_comments(xml_str, max_comments=max_comments)

    def post_reply(self, reply_text: str) -> bool:
        logger.info("Posting validated reply chars=%s", len(reply_text))
        if not self._open_reply_box():
            self.save_artifact("post_comment_failed.xml", self.d.dump_hierarchy())
            return False

        self.wait_random(1, 2, "reply box open")
        self.d.send_keys(reply_text, clear=True)
        self.wait_random(1, 2, "typing")

        if not self.d(resourceId="com.twitter.android:id/tweet_button").exists:
            logger.warning("Tweet button not found")
            return False

        self.d(resourceId="com.twitter.android:id/tweet_button").click()
        self.wait_random(self.config.post_wait_min, self.config.post_wait_max, "comment posting")
        return True

    def _open_reply_box(self) -> bool:
        selectors = [
            {"resourceId": "com.twitter.android:id/tweet_box"},
            {"text": "Reply"},
            {"resourceId": "com.twitter.android:id/inline_reply"},
        ]
        for kwargs in selectors:
            selector = self.d(**kwargs)
            if selector.exists:
                selector.click()
                return True

        width, height = self.d.window_size()
        self.d.swipe(width // 2, int(height * 0.5), width // 2, int(height * 0.3), duration=0.3)
        self.wait_random(1, 2, "reply box scroll")

        for kwargs in selectors:
            selector = self.d(**kwargs)
            if selector.exists:
                selector.click()
                return True
        return False

    def back_to_feed(self) -> None:
        for attempt in range(4):
            if self.is_feed_screen():
                return
            self.d.press("back")
            self.wait_random(1.5, 2.5, f"back to feed attempt {attempt + 1}")
        if not self.is_feed_screen():
            logger.warning("Could not verify feed after back navigation; relaunching app")
            self.launch()

    def scroll_feed(self) -> None:
        self.ensure_home_feed()
        width, height = self.d.window_size()
        self.d.swipe(width // 2, int(height * 0.8), width // 2, int(height * 0.3), duration=0.5)
        self.wait_random(2, 3, "feed scroll")

    def refresh_at_dead_end(self, previous_fingerprints: set[str]) -> bool:
        logger.info("Refreshing feed at dead end")
        if self.click_new_posts_pill():
            self.wait_random(2, 4, "new posts pill")
            if self._feed_changed(previous_fingerprints):
                return True

        self.restart()
        self.wait_random(3, 5, "restart refresh")
        return self._feed_changed(previous_fingerprints)

    def click_new_posts_pill(self) -> bool:
        xml_str = self.d.dump_hierarchy()
        for text, bounds in self._text_nodes(xml_str):
            lowered = text.lower()
            if "new" in lowered and "post" in lowered and bounds:
                x, y = self._center(bounds)
                logger.info("Clicking new-posts pill text=%r point=(%s,%s)", text, x, y)
                self.d.click(x, y)
                return True
        return False

    def _feed_changed(self, previous_fingerprints: set[str]) -> bool:
        tweets = self.visible_tweets()
        current = {tweet.fingerprint for tweet in tweets}
        return bool(current and not current.issubset(previous_fingerprints))

    def is_feed_screen(self) -> bool:
        try:
            xml_str = self.d.dump_hierarchy()
        except Exception:
            return False
        return "Home timeline list" in xml_str

    def ensure_home_feed(self) -> bool:
        if self.is_feed_screen():
            return True

        if self._click_home_tab():
            self.wait_random(2, 3, "home tab")
            if self.is_feed_screen():
                return True

        for attempt in range(3):
            if self.is_feed_screen():
                return True
            self.d.press("back")
            self.wait_random(1, 2, f"home recovery back {attempt + 1}")

        if self.is_feed_screen():
            return True

        logger.warning("Home feed recovery failed; restarting X")
        self.restart_without_recovery()
        return self.is_feed_screen()

    def restart_without_recovery(self) -> None:
        logger.info("Restarting X app")
        try:
            self.d.app_stop(self.config.package_name)
            time.sleep(2)
        except Exception:
            logger.exception("App stop failed; continuing with app_start")
        self.d.app_start(self.config.package_name)
        self.wait_random(self.config.launch_wait_min, self.config.launch_wait_max, "app restart")

    def _click_home_tab(self) -> bool:
        try:
            xml_str = self.d.dump_hierarchy()
            import xml.etree.ElementTree as ET

            root = ET.fromstring(xml_str)
            _, height = self.d.window_size()
            for node in root.iter("node"):
                if node.get("package") != self.config.package_name:
                    continue
                text = node.get("content-desc") or node.get("text") or ""
                bounds = node.get("bounds")
                lowered = text.lower()
                if not text or not bounds:
                    continue
                x1, y1, x2, y2 = self._parse_bounds(bounds)
                if lowered.startswith("home") and y1 >= int(height * 0.80) and y2 <= int(height * 0.96):
                    x, y = self._center(bounds)
                    logger.info("Clicking bottom Home tab point=(%s,%s) desc=%r", x, y, text)
                    self.d.click(x, y)
                    return True
        except Exception:
            logger.exception("Failed while looking for Home tab")
        return False

    def _open_candidates(self, tweet: Tweet) -> list[tuple[str, int, int]]:
        if tweet.is_promoted or not (tweet.body or "").strip():
            return []

        candidates: list[tuple[str, int, int]] = []
        for name, bounds in [
            ("text", tweet.text_bounds),
            ("header", tweet.header_bounds),
        ]:
            if bounds:
                x, y = self._center(bounds)
                if self._is_safe_open_target(name, bounds, x, y):
                    candidates.append((name, x, y))

        deduped: list[tuple[str, int, int]] = []
        seen: set[tuple[int, int]] = set()
        for item in candidates:
            point = (item[1], item[2])
            if point not in seen:
                deduped.append(item)
                seen.add(point)
        return deduped

    def _is_safe_open_target(self, name: str, bounds: str, x: int, y: int) -> bool:
        width, height = self.d.window_size()
        x1, y1, x2, y2 = self._parse_bounds(bounds)
        min_y = max(170, int(height * 0.11))
        max_y = int(height * 0.80)
        min_x = int(width * 0.12)
        max_x = int(width * 0.84)

        if not (min_x <= x <= max_x and min_y <= y <= max_y):
            logger.info(
                "Skipping unsafe open target=%s point=(%s,%s) bounds=%s safe_x=%s-%s safe_y=%s-%s",
                name,
                x,
                y,
                bounds,
                min_x,
                max_x,
                min_y,
                max_y,
            )
            return False
        if y2 > int(height * 0.92) or y1 < min_y:
            logger.info("Skipping clipped open target=%s bounds=%s", name, bounds)
            return False
        return True

    def _text_nodes(self, xml_str: str) -> list[tuple[str, str | None]]:
        import xml.etree.ElementTree as ET

        nodes: list[tuple[str, str | None]] = []
        root = ET.fromstring(xml_str)
        for node in root.iter("node"):
            text = node.get("text") or node.get("content-desc") or ""
            if text:
                nodes.append((text, node.get("bounds")))
        return nodes

    def _parse_bounds(self, bounds: str) -> tuple[int, int, int, int]:
        nums = list(map(int, re.findall(r"\d+", bounds)))
        if len(nums) != 4:
            raise ValueError(f"Invalid bounds: {bounds}")
        return nums[0], nums[1], nums[2], nums[3]

    def _center(self, bounds: str) -> tuple[int, int]:
        x1, y1, x2, y2 = self._parse_bounds(bounds)
        return (x1 + x2) // 2, (y1 + y2) // 2

    def save_artifact(self, name: str, content: str) -> None:
        if not self.config.debug_artifacts:
            return
        self.config.artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = self.config.artifacts_dir / name
        if path.exists():
            path = self.config.artifacts_dir / f"{int(time.time())}-{name}"
        path.write_text(content, encoding="utf-8")
