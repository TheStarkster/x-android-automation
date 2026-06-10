from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import datetime, timezone

import uiautomator2 as u2

from .config import Config
from .gemini import GeminiClient
from .models import RunEvent, utc_now_iso
from .parser import parse_visible_tweets
from .storage import RunStore
from .ui import TwitterUI
from .validation import validate_reply, validate_tweet


logger = logging.getLogger(__name__)


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


class CommentRunner:
    def __init__(self, config: Config, ui: TwitterUI, generator: GeminiClient, store: RunStore):
        self.config = config
        self.ui = ui
        self.generator = generator
        self.store = store
        self.processed = store.processed_fingerprints()
        self.session_seen: set[str] = set()
        self.posted = 0

    def run(self) -> int:
        if not self.generator.test():
            raise RuntimeError("Gemini API test failed.")

        self.ui.launch()
        scroll_attempts = 0
        stale_rounds = 0

        while self.posted < self.config.max_tweets_to_comment and scroll_attempts < self.config.max_scrolls:
            if self.store.posted_count_last_hour() >= self.config.max_comments_per_hour:
                logger.warning("Hourly post limit reached; stopping")
                break

            tweets = self.ui.visible_tweets()
            logger.info("Visible tweets=%s posted=%s target=%s", len(tweets), self.posted, self.config.max_tweets_to_comment)
            fresh_tweets = [
                tweet
                for tweet in tweets
                if tweet.fingerprint not in self.processed and tweet.fingerprint not in self.session_seen
            ]

            actionable_tweets = self._actionable_tweets(fresh_tweets)
            if not actionable_tweets:
                previous = {tweet.fingerprint for tweet in tweets}
                stale_rounds += 1
                if stale_rounds >= 3 and self.ui.refresh_at_dead_end(previous):
                    stale_rounds = 0
                else:
                    self.ui.scroll_feed()
                    scroll_attempts += 1
                continue

            stale_rounds = 0
            tweet = actionable_tweets[0]
            self.session_seen.add(tweet.fingerprint)

            if not self.ui.open_tweet(tweet):
                self._record_skip(tweet, "could not open tweet detail")
                continue

            try:
                self.ui.sort_replies_most_liked()
                tweet.comments = self.ui.top_comments(self.config.top_comments)
                generated = self.generator.generate_reply(tweet)
                reply_check = validate_reply(generated.text, tweet, tweet.comments)
                if not reply_check.ok or not reply_check.text:
                    self._record_skip(tweet, reply_check.reason, generated.to_dict())
                    continue

                generated.text = reply_check.text
                if self.ui.post_reply(generated.text):
                    self.posted += 1
                    self.processed.add(tweet.fingerprint)
                    self.store.append(
                        RunEvent(
                            event="tweet_processed",
                            tweet_fingerprint=tweet.fingerprint,
                            tweet=tweet.to_dict(),
                            reply=generated.to_dict(),
                            status="posted",
                        )
                    )
                else:
                    self._record_skip(tweet, "post failed", generated.to_dict())
            finally:
                self.ui.back_to_feed()

            # Re-read the feed after every navigation/post. X often inserts,
            # removes, or repositions rows, so continuing an old row list can tap
            # a partial bottom row or a row control such as Grok.
            continue

        logger.info("Run complete posted=%s scroll_attempts=%s", self.posted, scroll_attempts)
        return self.posted

    def _actionable_tweets(self, tweets):
        actionable = []
        for tweet in tweets:
            tweet_check = validate_tweet(tweet)
            if not tweet_check.ok:
                self.session_seen.add(tweet.fingerprint)
                self._record_skip(tweet, tweet_check.reason)
                continue
            if tweet.is_promoted:
                self.session_seen.add(tweet.fingerprint)
                self._record_skip(tweet, "promoted tweet")
                continue
            if not self.ui.can_open_tweet(tweet):
                logger.info("Deferring tweet until fully visible: %s", tweet.fingerprint)
                continue
            actionable.append(tweet)
        return actionable

    def _refresh_tweet_position(self, tweet):
        current_tweets = self.ui.visible_tweets()
        for current in current_tweets:
            if current.fingerprint == tweet.fingerprint:
                return current
        return None

    def _record_skip(self, tweet, reason: str | None, reply: dict | None = None) -> None:
        logger.info("Skipping tweet=%s reason=%s", tweet.fingerprint, reason)
        self.store.append(
            RunEvent(
                event="tweet_processed",
                tweet_fingerprint=tweet.fingerprint,
                tweet=tweet.to_dict(),
                reply=reply,
                status="skipped",
                reason=reason,
            )
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded X Android commenter")
    parser.add_argument("command", choices=["run", "probe"], nargs="?", default="run")
    parser.add_argument("--debug", action="store_true", help="Enable debug logs and artifacts when DEBUG_ARTIFACTS is set")
    parser.add_argument("--scrolls", type=int, default=5, help="Feed scrolls to capture during probe")
    return parser


def run_probe(config: Config, scrolls: int = 5) -> int:
    device = u2.connect()
    object.__setattr__(config, "debug_artifacts", True)
    probe_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    object.__setattr__(config, "artifacts_dir", config.artifacts_dir / "feed_probe" / probe_id)
    ui = TwitterUI(device, config)
    ui.launch()

    config.artifacts_dir.mkdir(parents=True, exist_ok=True)
    target = None
    summary_rows = []
    snapshots = max(0, scrolls) + 1

    for screen in range(snapshots):
        xml_str = device.dump_hierarchy()
        (config.artifacts_dir / f"feed_{screen:02d}.xml").write_text(xml_str, encoding="utf-8")
        tweets = parse_visible_tweets(xml_str)
        current_screen_target = None
        logger.info("Probe screen=%s/%s feed tweets=%s", screen + 1, snapshots, len(tweets))
        for idx, tweet in enumerate(tweets, 1):
            candidates = ui._open_candidates(tweet)
            skip_reason = _probe_skip_reason(tweet, candidates)
            summary_rows.append(_probe_summary_row(screen, idx, tweet, candidates, skip_reason))
            logger.info(
                "Probe tweet %s user=%s usable=%s reason=%s media=%s quote=%s promoted=%s text_bounds=%s header_bounds=%s body=%r",
                idx,
                tweet.username,
                not skip_reason,
                skip_reason,
                tweet.has_media,
                tweet.is_quote,
                tweet.is_promoted,
                tweet.text_bounds,
                tweet.header_bounds,
                (tweet.body or "")[:120],
            )
            if current_screen_target is None and not skip_reason:
                current_screen_target = tweet

        target = current_screen_target

        if screen < snapshots - 1:
            ui.scroll_feed()

    _write_probe_summary(config.artifacts_dir, summary_rows)

    if not target:
        logger.warning("Probe found no non-promoted tweet with readable text bounds")
        return 1

    if not ui.open_tweet(target):
        logger.warning("Probe could not open a real sortable tweet detail page for %s", target.fingerprint)
        return 1

    (config.artifacts_dir / "detail.xml").write_text(device.dump_hierarchy(), encoding="utf-8")
    ui.sort_replies_most_liked()
    comments = ui.top_comments(config.top_comments)
    logger.info("Probe comments=%s", len(comments))
    for idx, comment in enumerate(comments, 1):
        logger.info("Probe comment %s user=%s likes=%s body=%r", idx, comment.username, comment.likes, (comment.body or "")[:120])
    ui.back_to_feed()
    logger.info("Probe completed at %s; XML is under %s", utc_now_iso(), config.artifacts_dir)
    return 0


def _probe_skip_reason(tweet, candidates: list[tuple[str, int, int]]) -> str | None:
    if tweet.is_promoted:
        return "promoted"
    if not (tweet.body or "").strip():
        return "empty_body"
    if not candidates:
        return "no_safe_click_target"
    return None


def _probe_summary_row(screen: int, row_index: int, tweet, candidates: list[tuple[str, int, int]], skip_reason: str | None) -> dict:
    first_candidate = candidates[0] if candidates else None
    return {
        "screen": screen,
        "row_index": row_index,
        "username": tweet.username,
        "name": tweet.name,
        "body_preview": (tweet.body or "")[:160],
        "fingerprint": tweet.fingerprint,
        "row_bounds": tweet.bounds,
        "text_bounds": tweet.text_bounds,
        "header_bounds": tweet.header_bounds,
        "has_media": tweet.has_media,
        "is_promoted": tweet.is_promoted,
        "is_quote": tweet.is_quote,
        "usable": skip_reason is None,
        "skip_reason": skip_reason,
        "click_target": first_candidate[0] if first_candidate else None,
        "click_x": first_candidate[1] if first_candidate else None,
        "click_y": first_candidate[2] if first_candidate else None,
    }


def _write_probe_summary(artifacts_dir, rows: list[dict]) -> None:
    json_path = artifacts_dir / "feed_summary.json"
    csv_path = artifacts_dir / "feed_summary.csv"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    fields = [
        "screen",
        "row_index",
        "username",
        "name",
        "body_preview",
        "fingerprint",
        "row_bounds",
        "text_bounds",
        "header_bounds",
        "has_media",
        "is_promoted",
        "is_quote",
        "usable",
        "skip_reason",
        "click_target",
        "click_x",
        "click_y",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = Config.from_env()
    configure_logging(debug=args.debug)
    if args.command == "probe":
        return run_probe(config, scrolls=args.scrolls)

    config.validate()

    device = u2.connect()
    ui = TwitterUI(device, config)
    generator = GeminiClient(config.gemini_api_key, config.gemini_model)
    store = RunStore(config.runs_dir)
    runner = CommentRunner(config, ui, generator, store)
    runner.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
