from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    package_name: str
    gemini_api_key: str
    gemini_model: str
    max_tweets_to_comment: int
    max_comments_per_hour: int
    max_scrolls: int
    top_comments: int
    reply_sort: str
    posting_mode: str
    debug_artifacts: bool
    artifacts_dir: Path
    runs_dir: Path
    launch_wait_min: float
    launch_wait_max: float
    post_wait_min: float
    post_wait_max: float
    media_capture_mode: str
    media_capture_retries: int
    media_image_max_edge: int
    media_image_jpeg_quality: int

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv()
        return cls(
            package_name=os.environ.get("X_PACKAGE_NAME", "com.twitter.android"),
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
            max_tweets_to_comment=_env_int("MAX_TWEETS_TO_COMMENT", 30),
            max_comments_per_hour=_env_int("MAX_COMMENTS_PER_HOUR", 20),
            max_scrolls=_env_int("MAX_SCROLLS", 30),
            top_comments=_env_int("TOP_COMMENTS", 5),
            reply_sort=os.environ.get("REPLY_SORT", "most_liked"),
            posting_mode=os.environ.get("POSTING_MODE", "auto_guarded"),
            debug_artifacts=_env_bool("DEBUG_ARTIFACTS", False),
            artifacts_dir=Path(os.environ.get("ARTIFACTS_DIR", "artifacts")),
            runs_dir=Path(os.environ.get("RUNS_DIR", "runs")),
            launch_wait_min=float(os.environ.get("LAUNCH_WAIT_MIN", "5")),
            launch_wait_max=float(os.environ.get("LAUNCH_WAIT_MAX", "7")),
            post_wait_min=float(os.environ.get("POST_WAIT_MIN", "12")),
            post_wait_max=float(os.environ.get("POST_WAIT_MAX", "20")),
            media_capture_mode=os.environ.get("MEDIA_CAPTURE_MODE", "gallery"),
            media_capture_retries=_env_int("MEDIA_CAPTURE_RETRIES", 1),
            media_image_max_edge=_env_int("MEDIA_IMAGE_MAX_EDGE", 1280),
            media_image_jpeg_quality=_env_int("MEDIA_IMAGE_JPEG_QUALITY", 85),
        )

    def validate(self) -> None:
        if self.posting_mode != "auto_guarded":
            raise ValueError("Only POSTING_MODE=auto_guarded is implemented.")
        if self.reply_sort != "most_liked":
            raise ValueError("Only REPLY_SORT=most_liked is implemented.")
        if self.media_capture_mode != "gallery":
            raise ValueError("Only MEDIA_CAPTURE_MODE=gallery is implemented.")
        if self.max_tweets_to_comment < 1:
            raise ValueError("MAX_TWEETS_TO_COMMENT must be at least 1.")
        if self.max_comments_per_hour < 1:
            raise ValueError("MAX_COMMENTS_PER_HOUR must be at least 1.")
        if self.media_capture_retries < 0:
            raise ValueError("MEDIA_CAPTURE_RETRIES must be at least 0.")
        if self.media_image_max_edge < 1:
            raise ValueError("MEDIA_IMAGE_MAX_EDGE must be at least 1.")
        if not 1 <= self.media_image_jpeg_quality <= 95:
            raise ValueError("MEDIA_IMAGE_JPEG_QUALITY must be between 1 and 95.")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required.")
