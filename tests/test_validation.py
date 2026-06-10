import unittest

from x_automation.models import Comment, Tweet
from x_automation.validation import normalize_reply, validate_reply, validate_tweet


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

    def test_normalize_reply_removes_quotes_and_newlines(self):
        self.assertEqual(normalize_reply('"hello\\nworld"'), "hello world")
        self.assertEqual(normalize_reply('"hello\nworld"'), "hello world")
