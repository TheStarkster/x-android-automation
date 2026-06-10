from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Comment:
    username: str | None = None
    body: str | None = None
    likes: int = 0
    raw_content_desc: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TweetImage:
    mime_type: str
    data_base64: str | None = None
    source: str = "gallery"
    width: int | None = None
    height: int | None = None
    bytes_size: int | None = None
    status: str = "captured"
    reason: str | None = None

    def to_dict(self, include_data: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_data:
            data.pop("data_base64", None)
        return data


@dataclass
class Tweet:
    name: str | None = None
    username: str | None = None
    verified: bool = False
    body: str | None = None
    posted_time: str | None = None
    replies: int = 0
    reposts: int = 0
    likes: int = 0
    views: int = 0
    bounds: str | None = None
    text_bounds: str | None = None
    header_bounds: str | None = None
    media_bounds: str | None = None
    feed_text_index: int | None = None
    has_media: bool = False
    is_promoted: bool = False
    is_quote: bool = False
    comments: list[Comment] = field(default_factory=list)
    image_context: TweetImage | None = None
    raw_content_desc: str | None = None

    @property
    def fingerprint(self) -> str:
        normalized_body = re.sub(r"\s+", " ", self.body or "").strip().lower()
        seed = "|".join(
            [
                (self.username or "").lower(),
                normalized_body,
            ]
        )
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fingerprint"] = self.fingerprint
        data["comments"] = [comment.to_dict() for comment in self.comments]
        data["image_context"] = self.image_context.to_dict() if self.image_context else None
        return data


@dataclass
class GeneratedReply:
    text: str
    provider: str = "gemini"
    model: str | None = None
    attempt: int | None = None
    style_hint: str | None = None
    finish_reason: str | None = None
    validation_reason: str | None = None
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunEvent:
    event: str
    tweet_fingerprint: str | None = None
    tweet: dict[str, Any] | None = None
    reply: dict[str, Any] | None = None
    status: str | None = None
    reason: str | None = None
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
