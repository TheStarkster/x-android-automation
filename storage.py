from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from models import RunEvent, Tweet


class RunStore:
    def __init__(self, runs_dir: Path):
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = self.runs_dir / "history.jsonl"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.run_path = self.runs_dir / f"{timestamp}.jsonl"

    def append(self, event: RunEvent) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)
        with self.run_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def processed_fingerprints(self) -> set[str]:
        processed: set[str] = set()
        for item in self._read_history():
            if item.get("status") != "posted":
                continue
            fingerprint = item.get("tweet_fingerprint")
            if fingerprint:
                processed.add(fingerprint)
            stable = self._stable_fingerprint_from_history(item)
            if stable:
                processed.add(stable)
        return processed

    def posted_count_since(self, since: datetime) -> int:
        count = 0
        for item in self._read_history():
            if item.get("status") != "posted":
                continue
            created_at = item.get("created_at")
            if not created_at:
                continue
            try:
                timestamp = datetime.fromisoformat(created_at)
            except ValueError:
                continue
            if timestamp >= since:
                count += 1
        return count

    def posted_count_last_hour(self) -> int:
        return self.posted_count_since(datetime.now(timezone.utc) - timedelta(hours=1))

    def _read_history(self) -> Iterable[dict]:
        if not self.history_path.exists():
            return []
        items: list[dict] = []
        with self.history_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return items

    def _stable_fingerprint_from_history(self, item: dict) -> str | None:
        tweet = item.get("tweet")
        if not isinstance(tweet, dict):
            return None
        username = tweet.get("username")
        body = tweet.get("body") or tweet.get("tweet_body")
        if not username or not body:
            return None
        return Tweet(username=username, body=body).fingerprint
