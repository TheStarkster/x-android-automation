from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Comment, Tweet


BANNED_TOPICS = {
    "kill",
    "suicide",
    "terror",
    "bomb",
    "porn",
    "nude",
    "hate",
    "slur",
}


GENERIC_REPLIES = {
    "this is such a great point",
    "really appreciate you sharing this perspective",
    "couldn't agree more",
    "100% this",
}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    text: str | None = None
    reason: str | None = None


def normalize_reply(text: str | None) -> str:
    if not text:
        return ""
    cleaned = text.replace('"', "").replace("\\n", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def validate_tweet(tweet: Tweet) -> ValidationResult:
    body = (tweet.body or "").strip()
    if len(body) < 8:
        return ValidationResult(False, reason="tweet body too short")
    if body.startswith("Replying to"):
        return ValidationResult(False, reason="tweet is already a reply")
    lowered = body.lower()
    if any(word in lowered for word in BANNED_TOPICS):
        return ValidationResult(False, reason="tweet contains banned topic")
    return ValidationResult(True)


def validate_reply(text: str, tweet: Tweet, comments: list[Comment]) -> ValidationResult:
    cleaned = normalize_reply(text)
    if len(cleaned) < 20:
        return ValidationResult(False, reason="reply too short")
    if len(cleaned) > 280:
        return ValidationResult(False, reason="reply too long")
    if cleaned.endswith(("...", " is", " are", " was", " were", " can", " will")):
        return ValidationResult(False, reason="reply appears incomplete")

    lowered = cleaned.lower()
    if any(word in lowered for word in BANNED_TOPICS):
        return ValidationResult(False, reason="reply contains banned topic")
    if any(generic in lowered for generic in GENERIC_REPLIES):
        return ValidationResult(False, reason="reply is too generic")
    if (tweet.body or "").lower().strip(".!? ") == lowered.strip(".!? "):
        return ValidationResult(False, reason="reply duplicates tweet")

    comment_bodies = {(comment.body or "").lower().strip(".!? ") for comment in comments}
    if lowered.strip(".!? ") in comment_bodies:
        return ValidationResult(False, reason="reply duplicates an existing comment")

    return ValidationResult(True, text=cleaned)
