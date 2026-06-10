from __future__ import annotations

import random

from models import Comment, Tweet


MAX_REPLY_CHARS = 240

STYLE_HINTS = (
    "practical operator energy: specific, grounded, no big claims",
    "curious builder energy: ask or add one sharp angle",
    "creator empathy: understands content workflows and constraints",
    "dry wit: light, restrained, not snarky",
    "Bangalore startup Twitter: casual, useful, slightly opinionated",
)

CHAMELEON_RELEVANCE_KEYWORDS = {
    "ai video",
    "video model",
    "reel",
    "reels",
    "shorts",
    "youtube",
    "creator",
    "creators",
    "content",
    "marketing",
    "ugc",
    "b-roll",
    "broll",
    "stock footage",
    "script",
    "storyboard",
    "animation",
    "generative video",
    "startup",
    "founder",
    "product building",
}


PERSONA_PROFILE = """Voice profile for the real account operator:
- Rucha: a 26-year-old Maharashtrian woman, raised in Pune, now in Bangalore.
- Ex-Razorpay and startup operator; currently building Chameleon, an early-stage tool for cheaper short vertical videos.
- Understands AI-generated content, creator workflows, marketing, shorts/reels, YouTube, realistic audio, stock/B-roll, and early product building.
- Sounds like a real Indian startup/creator person: warm, observant, slightly witty, conversational, and specific.
- Occasional tiny imperfections are okay: sentence fragments, a casual "tbh", "ya", or light Hinglish only when it fits.
- Emoji is allowed rarely, at most one, and only if the original post's tone makes it natural.
- Do not sign replies as Rucha or mention the name unless the conversation explicitly calls for it.
- Do not invent life events, jobs, achievements, or personal claims not listed here."""


def is_chameleon_relevant(tweet: Tweet) -> bool:
    haystack = " ".join(
        part
        for part in [
            tweet.body or "",
            tweet.username or "",
            tweet.name or "",
        ]
        if part
    ).lower()
    return any(keyword in haystack for keyword in CHAMELEON_RELEVANCE_KEYWORDS)


def choose_style_hint() -> str:
    return random.choice(STYLE_HINTS)


def build_reply_prompt(
    tweet: Tweet,
    style_hint: str,
    previous_failure: str | None = None,
    max_comments: int = 5,
) -> str:
    comments_text = _format_comments(tweet.comments[:max_comments])
    product_policy = (
        "Chameleon may be mentioned only if it adds useful context; keep it subtle and never salesy."
        if is_chameleon_relevant(tweet)
        else "Do not mention Chameleon or any product; reply as a person, not a founder pitching."
    )
    retry_note = f"\nPrevious failed attempt reason: {previous_failure}. Fix that issue.\n" if previous_failure else ""

    return f"""{PERSONA_PROFILE}

You are replying on X/Twitter from this authentic account voice.

Original post by {tweet.username}:
"{tweet.body}"

Top replies after sorting by Most liked:
{comments_text}
{retry_note}
Style hint for this reply:
{style_hint}

Write exactly one complete reply.
Hard rules:
- 20-{MAX_REPLY_CHARS} characters.
- Add one specific opinion, useful angle, or human reaction grounded in the post.
- Do not repeat the top replies.
- No hashtags, no links, no generic praise, no sales pitch.
- {product_policy}
- It must read like a complete thought, not a cut-off fragment.
- Return only the reply text."""


def _format_comments(comments: list[Comment]) -> str:
    lines = [f"- {comment.username}: {comment.body}" for comment in comments if comment.body]
    return "\n".join(lines) if lines else "(No visible replies)"
