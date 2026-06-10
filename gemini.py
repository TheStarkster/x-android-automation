from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from models import GeneratedReply, Tweet
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

    def generate_reply(self, tweet: Tweet) -> GeneratedReply:
        comments_text = "\n".join(
            f"- {comment.username}: {comment.body}" for comment in tweet.comments[:5] if comment.body
        )
        prompt = f"""You are replying on X/Twitter as a thoughtful real person.

Original post by {tweet.username}:
"{tweet.body}"

Top replies after sorting by Most liked:
{comments_text if comments_text else "(No visible replies)"}

Write one concise reply, 20-240 characters.
Rules:
- Add a specific opinion or useful angle.
- Do not repeat the existing top replies.
- No hashtags, no sales pitch, no generic praise.
- Sound natural and conversational.
- Return only the reply text.
"""
        logger.info("Generating reply with Gemini model=%s prompt_chars=%s", self.model, len(prompt))
        response = requests.post(
            self.url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.75,
                    "maxOutputTokens": 160,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        return GeneratedReply(text=normalize_reply(text), model=self.model)
