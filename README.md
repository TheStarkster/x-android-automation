# X Android Automation

Guarded X/Twitter Android automation via `uiautomator2`.

## Setup

```bash
pip install -r requirements.txt
```

Use an Android device or emulator with USB debugging enabled. Create a local `.env`
or export environment variables:

```bash
GEMINI_API_KEY=...
MAX_TWEETS_TO_COMMENT=30
MAX_COMMENTS_PER_HOUR=20
REPLY_SORT=most_liked
POSTING_MODE=auto_guarded
DEBUG_ARTIFACTS=false
MEDIA_CAPTURE_MODE=gallery
MEDIA_CAPTURE_RETRIES=1
MEDIA_IMAGE_MAX_EDGE=1280
MEDIA_IMAGE_JPEG_QUALITY=85
```

## Run

```bash
python3 main.py run
```

Before posting from a new app/device state, run a safe selector probe:

```bash
python3 main.py probe
python3 main.py probe --scrolls 5
```

`probe` opens X, captures the initial feed plus the requested number of scrolls,
and writes raw XML plus `feed_summary.json`/`feed_summary.csv` under
`artifacts/feed_probe/<timestamp>/`. It then opens one safe readable tweet,
writes `detail.xml`, selects `Most liked`, reads visible comments, and returns
to the feed. It does not call Gemini and does not post.

The production flow opens each visible post, captures the primary tweet image
from the media gallery when media is present, sorts replies by `Most liked`,
reads up to five comments, generates a contextual reply, validates it, posts it,
and records the result in `runs/`. Image bytes are sent to Gemini for generation
but are not stored in run history. At feed dead ends it tries the new-posts pill
first, then restarts the app as a fallback.

Debug XML snapshots are written only when `DEBUG_ARTIFACTS=true`.

## Tests

```bash
python3 -m unittest discover -s tests
```

