from pathlib import Path
import unittest

from parser import (
    extract_number,
    parse_comment_from_content_desc,
    parse_top_comments,
    parse_tweet_from_content_desc,
    parse_visible_tweets,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class ParserTest(unittest.TestCase):
    def test_extract_number_variants(self):
        self.assertEqual(extract_number("215"), 215)
        self.assertEqual(extract_number("3.6K"), 3600)
        self.assertEqual(extract_number("1.2M"), 1_200_000)
        self.assertEqual(extract_number("bad"), 0)

    def test_parse_tweet_from_content_desc(self):
        desc = (
            "Mari @Tech_girlll Verified.    Do you think learning software engineering "
            "is worth it in the era of artificial intelligence?.            "
            "2 hours ago.  33 replies.  2 reposts.  26 likes.  4228 verified views. "
        )
        tweet = parse_tweet_from_content_desc(desc)
        self.assertIsNotNone(tweet)
        self.assertEqual(tweet.username, "@Tech_girlll")
        self.assertEqual(
            tweet.body,
            "Do you think learning software engineering is worth it in the era of artificial intelligence?",
        )
        self.assertEqual(tweet.replies, 33)
        self.assertEqual(tweet.views, 4228)

    def test_parse_visible_tweets_from_snapshot(self):
        tweets = parse_visible_tweets((FIXTURES / "current_feed_ui.xml").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(tweets), 2)
        self.assertEqual(tweets[0].username, "@Manixh02")
        self.assertEqual(tweets[0].feed_text_index, 0)
        self.assertTrue(tweets[0].has_media)
        self.assertEqual(tweets[0].media_bounds, "[117,252][697,578]")
        self.assertNotEqual(tweets[0].fingerprint, tweets[1].fingerprint)

    def test_parse_quote_prefers_added_text(self):
        desc = (
            "Arthur MacWaters @ArthurMacwaters Verified Legion Health.    Quoted. "
            "Claude @claudeai Verified Anthropic.  Introducing Claude Fable 5. "
            "Arthur MacWaters @ArthurMacwaters Verified Legion Health.  "
            "Added this is freaking insane.          9 hours ago.  71 replies. "
            "40 reposts.  643 likes.  123674 verified views. "
        )
        tweet = parse_tweet_from_content_desc(desc)
        self.assertIsNotNone(tweet)
        self.assertTrue(tweet.is_quote)
        self.assertEqual(tweet.body, "this is freaking insane")

    def test_fingerprint_ignores_volatile_metrics_after_reply(self):
        before = parse_tweet_from_content_desc(
            "Nalin @nalinrajput23 Verified.    is coding still worth learning in the AI era??. "
            "2 hours ago.  10 replies.  2 reposts.  50 likes.  1000 verified views. "
        )
        after = parse_tweet_from_content_desc(
            "Nalin @nalinrajput23 Verified.    is coding still worth learning in the AI era??. "
            "2 hours ago.  11 replies.  2 reposts.  51 likes.  1020 verified views. "
        )
        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertEqual(before.fingerprint, after.fingerprint)

    def test_parse_comment_from_content_desc(self):
        desc = (
            "Guillermo Rauch @rauchg Verified Vercel.   Replying to @Bhavani_00007.  "
            "Vercel.            2 hours ago.  9 replies.  1 repost.  96 likes. "
            "3764 verified views. "
        )
        comment = parse_comment_from_content_desc(desc)
        self.assertIsNotNone(comment)
        self.assertEqual(comment.username, "@rauchg")
        self.assertEqual(comment.body, "Vercel")
        self.assertEqual(comment.likes, 96)

    def test_parse_top_comments_from_snapshot(self):
        comments = parse_top_comments((FIXTURES / "click_tweet_ui.xml").read_text(encoding="utf-8"), max_comments=5)
        self.assertTrue(comments)
        self.assertEqual(comments[0].body, "Vercel")
