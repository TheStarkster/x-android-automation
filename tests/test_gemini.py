import unittest
from unittest.mock import patch

from gemini import GeminiClient
from models import Tweet, TweetImage


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class GeminiClientTest(unittest.TestCase):
    @patch("gemini.choose_style_hint", return_value="practical operator energy")
    @patch("gemini.requests.post")
    def test_generate_reply_disables_thinking_and_uses_large_output_budget(self, post, _style):
        post.return_value = FakeResponse(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "This only works if the workflow gets cheaper and less fussy."}]},
                    }
                ]
            }
        )
        client = GeminiClient(api_key="key", model="gemini-2.5-flash")
        tweet = Tweet(username="@a", body="AI video is still too expensive for most reels")

        reply = client.generate_reply(tweet)

        self.assertEqual(reply.finish_reason, "STOP")
        payload = post.call_args.kwargs["json"]
        generation_config = payload["generationConfig"]
        self.assertEqual(generation_config["maxOutputTokens"], 1024)
        self.assertEqual(generation_config["thinkingConfig"], {"thinkingBudget": 0})
        self.assertIn("Usually 8-120 characters", payload["systemInstruction"]["parts"][0]["text"])

    @patch("gemini.requests.post")
    def test_api_test_disables_thinking(self, post):
        post.return_value = FakeResponse({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]})
        client = GeminiClient(api_key="key", model="gemini-2.5-flash")

        self.assertTrue(client.test())

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["generationConfig"]["thinkingConfig"], {"thinkingBudget": 0})

    @patch("gemini.choose_style_hint", return_value="practical operator energy")
    @patch("gemini.requests.post")
    def test_generate_reply_sends_captured_image_inline(self, post, _style):
        post.return_value = FakeResponse(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "The visual makes the launch feel much less abstract."}]},
                    }
                ]
            }
        )
        client = GeminiClient(api_key="key", model="gemini-2.5-flash")
        tweet = Tweet(
            username="@a",
            body="launch day",
            has_media=True,
            image_context=TweetImage(mime_type="image/jpeg", data_base64="abc123", width=10, height=10, bytes_size=5),
        )

        client.generate_reply(tweet)

        parts = post.call_args.kwargs["json"]["contents"][0]["parts"]
        self.assertEqual(parts[1]["inline_data"], {"mime_type": "image/jpeg", "data": "abc123"})


if __name__ == "__main__":
    unittest.main()
