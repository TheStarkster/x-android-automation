import unittest

from models import Comment, Tweet
from validation import normalize_reply, validate_reply, validate_tweet


class ValidationTest(unittest.TestCase):
    def test_validate_tweet_skips_reply_like_tweets(self):
        tweet = Tweet(username="@a", body="Replying to @b. hello")
        result = validate_tweet(tweet)
        self.assertFalse(result.ok)

    def test_validate_reply_normalizes_and_accepts_specific_reply(self):
        tweet = Tweet(username="@a", body="Which hosting platform is best for a tiny side project?")
        comments = [Comment(username="@b", body="Vercel")]
        result = validate_reply("  Railway for quick APIs, Vercel for frontends. Depends where the pain is.  ", tweet, comments)
        self.assertTrue(result.ok)
        self.assertEqual(result.text, "Railway for quick APIs, Vercel for frontends. Depends where the pain is.")

    def test_validate_reply_rejects_generic_and_duplicate(self):
        tweet = Tweet(username="@a", body="AI changes software engineering")
        self.assertFalse(validate_reply("This is such a great point!", tweet, []).ok)
        self.assertFalse(validate_reply("AI changes software engineering", tweet, []).ok)

    def test_validate_reply_allows_short_casual_human_reply(self):
        tweet = Tweet(username="@a", body="This dashboard finally makes sense")
        result = validate_reply("ya this lands", tweet, [])

        self.assertTrue(result.ok)
        self.assertEqual(result.text, "ya this lands")

    def test_normalize_reply_removes_quotes_and_newlines(self):
        self.assertEqual(normalize_reply('"hello\\nworld"'), "hello world")
        self.assertEqual(normalize_reply('"hello\nworld"'), "hello world")

    def test_validate_reply_rejects_incomplete_and_over_limit_text(self):
        tweet = Tweet(username="@a", body="AI video costs are still wild for short clips")

        self.assertFalse(validate_reply("This matters for creators because", tweet, []).ok)
        self.assertFalse(validate_reply("I keep seeing this in creator workflows,", tweet, []).ok)
        self.assertFalse(validate_reply("x" * 241, tweet, []).ok)

    def test_validate_reply_enforces_chameleon_relevance(self):
        unrelated = Tweet(username="@a", body="Which programming language do you hate the most?")
        relevant = Tweet(username="@b", body="Need a cheaper way to make reels from an idea")

        self.assertFalse(
            validate_reply("Chameleon is exactly the kind of tool that would help here.", unrelated, []).ok
        )
        self.assertTrue(
            validate_reply("Chameleon is relevant here only if it keeps the reel useful, not just shiny.", relevant, []).ok
        )
