from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from models import GeneratedReply, Tweet
from persona import build_reply_prompt, choose_style_hint
from validation import normalize_reply

logger = logging.getLogger(__name__)


@dataclass
class GeminiClient:
    api_key: str
    model: str
    timeout: int = 30

    @property
    def url(self) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def test(self) -> bool:
        response = requests.post(
            self.url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": "Say OK if you can read this."}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 16},
            },
            timeout=10,
        )
        if response.status_code != 200:
            logger.error("Gemini API test failed: status=%s body=%s", response.status_code, response.text[:500])
            return False
        payload = response.json()
        return bool(payload.get("candidates"))

    def generate_reply(
        self,
        tweet: Tweet,
        attempt: int = 1,
        previous_failure: str | None = None,
    ) -> GeneratedReply:
        style_hint = choose_style_hint()
        prompt = build_reply_prompt(tweet, style_hint=style_hint, previous_failure=previous_failure)
        logger.info("Generating reply with Gemini model=%s prompt_chars=%s", self.model, len(prompt))
        response = requests.post(
            self.url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.75,
                    "maxOutputTokens": 320,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        candidate = payload["candidates"][0]
        finish_reason = candidate.get("finishReason")
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        return GeneratedReply(
            text=normalize_reply(text),
            model=self.model,
            attempt=attempt,
            style_hint=style_hint,
            finish_reason=finish_reason,
        )
