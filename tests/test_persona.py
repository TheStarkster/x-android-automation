import unittest

from models import Comment, Tweet
from persona import build_reply_prompt, is_chameleon_relevant


class PersonaPromptTest(unittest.TestCase):
    def test_prompt_includes_persona_and_product_policy_when_relevant(self):
        tweet = Tweet(
            username="@creator",
            body="Need a cheaper way to make YouTube shorts from rough ideas",
            comments=[Comment(username="@a", body="CapCut templates work sometimes")],
        )

        prompt = build_reply_prompt(tweet, style_hint="creator empathy")

        self.assertIn("Rucha", prompt)
        self.assertIn("Pune", prompt)
        self.assertIn("Bangalore", prompt)
        self.assertIn("Do not sign replies as Rucha", prompt)
        self.assertIn("Chameleon may be mentioned only if it adds useful context", prompt)
        self.assertIn("No hashtags, no links, no generic praise, no sales pitch", prompt)
        self.assertIn("It must read like a complete thought", prompt)

    def test_prompt_blocks_product_mention_when_not_relevant(self):
        tweet = Tweet(username="@dev", body="Which programming language do you hate the most?")

        prompt = build_reply_prompt(tweet, style_hint="dry wit")

        self.assertFalse(is_chameleon_relevant(tweet))
        self.assertIn("Do not mention Chameleon", prompt)


if __name__ == "__main__":
    unittest.main()
