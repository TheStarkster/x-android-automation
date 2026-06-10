import unittest

from models import Comment, Tweet, TweetImage
from persona import build_reply_prompt, build_reply_system_instruction, is_chameleon_relevant


class PersonaPromptTest(unittest.TestCase):
    def test_prompt_includes_persona_and_product_policy_when_relevant(self):
        tweet = Tweet(
            username="@creator",
            body="Need a cheaper way to make YouTube shorts from rough ideas",
            comments=[Comment(username="@a", body="CapCut templates work sometimes")],
        )

        prompt = build_reply_prompt(tweet, style_hint="creator empathy")

        self.assertIn("Chameleon may be mentioned only if it adds useful context", prompt)
        system_instruction = build_reply_system_instruction()
        self.assertIn("Rucha", system_instruction)
        self.assertIn("Pune", system_instruction)
        self.assertIn("Bangalore", system_instruction)
        self.assertIn("Do not sign replies as Rucha", system_instruction)
        self.assertIn("No hashtags, no links, no generic praise, no sales pitch", system_instruction)
        self.assertIn("Usually 8-120 characters", system_instruction)
        self.assertIn("no need for perfect grammar", system_instruction)
        self.assertIn("do not try to be witty every time", system_instruction)
        self.assertIn("only when it lands naturally", system_instruction)

    def test_prompt_blocks_product_mention_when_not_relevant(self):
        tweet = Tweet(username="@dev", body="Which programming language do you hate the most?")

        prompt = build_reply_prompt(tweet, style_hint="dry wit")

        self.assertFalse(is_chameleon_relevant(tweet))
        self.assertIn("Do not mention Chameleon", prompt)

    def test_prompt_mentions_attached_image_when_captured(self):
        tweet = Tweet(
            username="@visual",
            body="this chart is doing numbers",
            has_media=True,
            image_context=TweetImage(mime_type="image/jpeg", data_base64="abc"),
        )

        prompt = build_reply_prompt(tweet, style_hint="dry wit")

        self.assertIn("Attached image from the tweet is available", prompt)
        self.assertIn("Use the attached image only if it changes the meaning", prompt)

    def test_prompt_defines_when_long_replies_are_allowed(self):
        tweet = Tweet(username="@dev", body="thoughts on this architecture?")

        prompt = build_reply_prompt(tweet, style_hint="practical operator energy")

        system_instruction = build_reply_system_instruction()
        self.assertIn("Use 120-240 only when the post genuinely needs nuance", system_instruction)
        self.assertIn("Never pad the reply", system_instruction)


if __name__ == "__main__":
    unittest.main()
