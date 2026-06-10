import tempfile
import unittest
from pathlib import Path

from models import Tweet
from runner import _probe_skip_reason, _probe_summary_row, _write_probe_summary


class ProbeSummaryTest(unittest.TestCase):
    def test_probe_summary_marks_usable_click_target(self):
        tweet = Tweet(
            name="Dev",
            username="@dev",
            body="Which stack are you using today?",
            bounds="[0,300][720,600]",
            text_bounds="[117,380][697,430]",
            header_bounds="[117,330][588,360]",
        )
        candidates = [("text", 407, 405)]

        self.assertIsNone(_probe_skip_reason(tweet, candidates))
        row = _probe_summary_row(2, 1, tweet, candidates, None)

        self.assertTrue(row["usable"])
        self.assertEqual(row["screen"], 2)
        self.assertEqual(row["click_target"], "text")
        self.assertEqual(row["click_x"], 407)
        self.assertEqual(row["fingerprint"], tweet.fingerprint)

    def test_probe_summary_writes_json_and_csv(self):
        row = {
            "screen": 0,
            "row_index": 1,
            "username": "@dev",
            "name": "Dev",
            "body_preview": "hello",
            "fingerprint": "abc",
            "row_bounds": "[0,0][1,1]",
            "text_bounds": "[0,0][1,1]",
            "header_bounds": None,
            "has_media": False,
            "is_promoted": False,
            "is_quote": False,
            "usable": True,
            "skip_reason": None,
            "click_target": "text",
            "click_x": 1,
            "click_y": 1,
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            _write_probe_summary(path, [row])

            self.assertIn('"username": "@dev"', (path / "feed_summary.json").read_text(encoding="utf-8"))
            self.assertIn("@dev", (path / "feed_summary.csv").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
