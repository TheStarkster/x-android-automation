from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET

from models import Comment, Tweet


TIME_PATTERN = r"\d+\s+(?:hour|minute|day|second|week|month|year)s?\s+ago"


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = text.replace("\u200e", "").replace("\ufeff", "")
    text = text.replace("&#10;", "\n")
    return re.sub(r"\s+", " ", text).strip()


def extract_number(text: str | None) -> int:
    if not text:
        return 0

    value = str(text).strip().replace(",", "")
    multiplier = 1
    if value.upper().endswith("K"):
        multiplier = 1_000
        value = value[:-1]
    elif value.upper().endswith("M"):
        multiplier = 1_000_000
        value = value[:-1]

    try:
        return int(float(value) * multiplier)
    except ValueError:
        return 0


def _metric(pattern: str, text: str) -> int:
    match = re.search(pattern, text, re.IGNORECASE)
    return extract_number(match.group(1)) if match else 0


def parse_tweet_from_content_desc(content_desc: str | None) -> Tweet | None:
    text = normalize_text(content_desc)
    if not text or "@" not in text:
        return None

    name_match = re.search(r"^(.+?)\s@([A-Za-z0-9_]+)", text)
    if not name_match:
        return None

    username = "@" + name_match.group(2)
    posted_match = re.search(rf"({TIME_PATTERN})", text, re.IGNORECASE)
    metric_start = posted_match.start() if posted_match else len(text)

    body_start = name_match.end()
    prefix = text[body_start:metric_start]
    prefix = re.sub(r"^\s*Verified(?:\s+[^.]{1,40})?\.\s*", "", prefix).strip()
    prefix = re.sub(r"\s*Reposted by .*$", "", prefix).strip()
    body = prefix.rstrip(". ").strip()
    is_quote = "Quoted." in text
    is_promoted = "Promoted." in text

    # Quote rows put the quoted post first, then the author's added text. When
    # X exposes that shape, prefer the actual visible "Added ..." note.
    added_match = re.search(r"\bAdded\s+(.+)$", body, re.IGNORECASE)
    if added_match:
        body = added_match.group(1).strip()

    if body.startswith("Replying to "):
        return None

    tweet = Tweet(
        name=name_match.group(1).strip(),
        username=username,
        verified="Verified" in text[: max(metric_start, 0)],
        body=body[:500] or None,
        posted_time=posted_match.group(1) if posted_match else None,
        replies=_metric(r"([\d,.]+[KMkm]?)\s+repl(?:y|ies)", text),
        reposts=_metric(r"([\d,.]+[KMkm]?)\s+repost", text),
        likes=_metric(r"([\d,.]+[KMkm]?)\s+like", text),
        views=_metric(r"([\d,.]+[KMkm]?)\s+(?:verified\s+)?views", text),
        is_quote=is_quote,
        is_promoted=is_promoted,
        raw_content_desc=text[:1000],
    )
    return tweet if tweet.username and tweet.body else None


def parse_comment_from_content_desc(content_desc: str | None) -> Comment | None:
    text = normalize_text(content_desc)
    if not text or "Replying to" not in text or "@" not in text:
        return None

    username_match = re.search(r"@([A-Za-z0-9_]+)", text)
    posted_match = re.search(rf"({TIME_PATTERN})", text, re.IGNORECASE)
    if not posted_match:
        return None

    before_time = text[: posted_match.start()].strip()
    body = re.sub(r"^.*?Replying to\s+@?[A-Za-z0-9_]+\.?\s*", "", before_time).strip()
    body = body.rstrip(". ").strip()

    if not body:
        return None

    return Comment(
        username=("@" + username_match.group(1)) if username_match else None,
        body=body[:300],
        likes=_metric(r"([\d,.]+[KMkm]?)\s+like", text),
        raw_content_desc=text[:1000],
    )


def parse_visible_tweets(xml_str: str) -> list[Tweet]:
    root = ET.fromstring(xml_str)
    tweets: list[Tweet] = []
    text_index = 0

    for node in root.iter("node"):
        if node.get("resource-id") == "com.twitter.android:id/row":
            tweet = parse_tweet_from_content_desc(node.get("content-desc"))
            if not tweet:
                continue

            tweet.bounds = node.get("bounds") or None
            for desc in node.iter("node"):
                if desc.get("resource-id") == "com.twitter.android:id/tweet_header":
                    tweet.header_bounds = desc.get("bounds") or None
                if desc.get("resource-id") == "com.twitter.android:id/tweet_content_text":
                    tweet.text_bounds = desc.get("bounds") or None
                    tweet.feed_text_index = text_index
                    text_index += 1
                if desc.get("resource-id") == "com.twitter.android:id/card_media_tweet_container":
                    tweet.has_media = True
                    tweet.media_bounds = desc.get("bounds") or tweet.media_bounds
            tweets.append(tweet)

    return tweets


def parse_top_comments(xml_str: str, max_comments: int = 5) -> list[Comment]:
    root = ET.fromstring(xml_str)
    comments: list[Comment] = []

    for node in root.iter("node"):
        if len(comments) >= max_comments:
            break
        comment = parse_comment_from_content_desc(node.get("content-desc"))
        if comment and comment.body:
            comments.append(comment)

    return comments
