import uiautomator2 as u2
import logging
import time
import sys
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import random
import os

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitter_commenter.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyDl9NU2dDm2CIfj7S0plFylwA7rW95eVco')
GEMINI_MODEL = 'gemini-2.5-flash' # model dekh lena apne hisaab se
MAX_TWEETS_TO_COMMENT = int(os.environ.get('MAX_TWEETS_TO_COMMENT', '30'))

def wait_random(min_sec, max_sec, action):
    """Wait random time to appear more human-like"""
    wait_time = random.uniform(min_sec, max_sec)
    logger.info(f"Waiting {wait_time:.1f}s after {action}...")
    time.sleep(wait_time)

def extract_number(text):
    """Extract number from text like '3.6K' or '127K' or '215'"""
    if not text:
        return 0
    
    text = str(text).strip().replace(',', '')
    
    try:
        if 'K' in text:
            num = float(text.replace('K', ''))
            return int(num * 1000)
        if 'M' in text:
            num = float(text.replace('M', ''))
            return int(num * 1000000)
        return int(float(text))
    except:
        return 0

def parse_tweet_from_content_desc(content_desc):
    """Parse tweet data from content-desc attribute"""
    try:
        content_desc = content_desc.replace('&#10;', '\n')
        content_desc = content_desc.replace('&quot;', '"')
        content_desc = content_desc.replace('&amp;', '&')
        
        tweet_data = {
            'name': None,
            'username': None,
            'verified': False,
            'tweet_body': None,
            'posted_time': None,
            'replies': 0,
            'reposts': 0,
            'likes': 0,
            'views': 0,
            'comments': []
        }
        
        name_username_pattern = r'^(.+?)\s@(\w+)'
        name_match = re.search(name_username_pattern, content_desc)
        if name_match:
            tweet_data['name'] = name_match.group(1).strip()
            tweet_data['username'] = '@' + name_match.group(2)
        else:
            return None
        
        if 'Verified' in content_desc:
            tweet_data['verified'] = True
        
        time_match = re.search(r'(\d+\s+(?:hour|minute|day|second)s?\s+ago)', content_desc)
        if time_match:
            tweet_data['posted_time'] = time_match.group(1)
        
        replies_match = re.search(r'(\d+)\s+repl(?:y|ies)', content_desc)
        if replies_match:
            tweet_data['replies'] = extract_number(replies_match.group(1))
        
        reposts_match = re.search(r'(\d+)\s+repost', content_desc)
        if reposts_match:
            tweet_data['reposts'] = extract_number(reposts_match.group(1))
        
        likes_match = re.search(r'(\d+)\s+like', content_desc)
        if likes_match:
            tweet_data['likes'] = extract_number(likes_match.group(1))
        
        views_match = re.search(r'(\d+)\s+(?:verified\s+)?views', content_desc)
        if views_match:
            tweet_data['views'] = extract_number(views_match.group(1))
        
        body_pattern = r'Verified\.?\s+(.*?)\s+\d+\s+(?:hour|minute|day|second)s?\s+ago'
        body_match = re.search(body_pattern, content_desc, re.DOTALL)
        if body_match:
            body = body_match.group(1).strip()
            body = re.sub(r'\s+', ' ', body)
            tweet_data['tweet_body'] = body[:500]
        
        return tweet_data
        
    except Exception as e:
        logger.error(f"Error parsing tweet: {str(e)}")
        return None

def parse_comment_from_content_desc(content_desc):
    """Parse comment/reply data from content-desc"""
    try:
        content_desc = content_desc.replace('&#10;', '\n')
        content_desc = content_desc.replace('&quot;', '"')
        content_desc = content_desc.replace('&amp;', '&')
        
        comment_data = {
            'username': None,
            'comment_body': None,
            'likes': 0
        }
        
        username_match = re.search(r'@(\w+)', content_desc)
        if username_match:
            comment_data['username'] = '@' + username_match.group(1)
        
        likes_match = re.search(r'(\d+)\s+like', content_desc)
        if likes_match:
            comment_data['likes'] = extract_number(likes_match.group(1))
        
        body_pattern = r'Replying to.*?\.  (.*?)\s+\d+\s+(?:hour|minute|day|second)s?\s+ago'
        body_match = re.search(body_pattern, content_desc, re.DOTALL)
        if body_match:
            body = body_match.group(1).strip()
            body = re.sub(r'\s+', ' ', body)
            comment_data['comment_body'] = body[:300]
        
        return comment_data
        
    except Exception as e:
        logger.error(f"Error parsing comment: {str(e)}")
        return None

def get_visible_tweets(d):
    """Get all tweet elements visible on current screen.
    Uses current_feed_ui.xml structure: each tweet is a row; we always use the
    tweet_content_text bounds for clicking so we open the tweet (not profile image
    or media). tweet_auto_playable_content_parent can contain text_content_container
    (tweet_content_text) and/or media; clicking text opens tweet detail.
    """
    try:
        xml_str = d.dump_hierarchy()
        
        with open('current_feed_ui.xml', 'w', encoding='utf-8') as f:
            f.write(xml_str)
        
        root = ET.fromstring(xml_str)
        
        tweets = []
        for node in root.iter('node'):
            resource_id = node.get('resource-id', '')
            if resource_id == 'com.twitter.android:id/row':
                content_desc = node.get('content-desc', '')
                if content_desc and '@' in content_desc:
                    tweet_data = parse_tweet_from_content_desc(content_desc)
                    if tweet_data and tweet_data['username'] and tweet_data.get('tweet_body'):
                        bounds = node.get('bounds', '')
                        tweet_data['bounds'] = bounds
                        # Prefer text area bounds so we never click profile image or media
                        text_bounds = None
                        for desc in node.iter('node'):
                            if desc.get('resource-id') == 'com.twitter.android:id/tweet_content_text':
                                text_bounds = desc.get('bounds', '')
                                break
                        tweet_data['text_bounds'] = text_bounds
                        tweets.append(tweet_data)
        
        return tweets
        
    except Exception as e:
        logger.error(f"Error getting visible tweets: {str(e)}")
        return []

def verify_tweet_detail_opened(d):
    """Verify that we opened the tweet detail page (not image viewer)"""
    try:
        wait_random(1, 2, "page load verification")
        
        if d(resourceId="com.twitter.android:id/reply_sorting").exists:
            logger.info("✓ Tweet detail page verified (found reply_sorting)")
            return True
        
        if d(resourceId="com.twitter.android:id/tweet_box").exists:
            logger.info("✓ Tweet detail page verified (found tweet_box)")
            return True
        
        if d(resourceId="com.twitter.android:id/inline_reply").exists:
            logger.info("✓ Tweet detail page verified (found inline_reply)")
            return True
        
        xml_str = d.dump_hierarchy()
        if 'image_view' in xml_str or 'photo_viewer' in xml_str or 'media_viewer' in xml_str:
            logger.warning("✗ Opened image viewer instead of tweet detail")
            return False
        
        logger.warning("✗ Could not verify tweet detail page opened")
        return False
        
    except Exception as e:
        logger.error(f"Error verifying tweet detail: {str(e)}")
        return False

def click_on_tweet(d, tweet_data, tweet_index=None, retry_count=0, max_retries=2):
    """Click on the text part of the tweet to open it (never on image/profile).
    Uses resource-id tweet_content_text at tweet_index so the actual view receives the tap."""
    try:
        if tweet_index is None:
            logger.warning("click_on_tweet requires tweet_index when clicking from feed")
            return False

        logger.info(f"Clicking on tweet from {tweet_data['username']} at index {tweet_index} (attempt {retry_count + 1}/{max_retries + 1})...")

        sel = d(resourceId="com.twitter.android:id/tweet_content_text")
        count = sel.count
        if count < tweet_index + 1:
            logger.warning(f"tweet_content_text count {count} < index {tweet_index + 1}, out of range")
            return False

        logger.info(f"Clicking tweet at index {tweet_index} (resource-id tweet_content_text)")
        sel[tweet_index].click()

        if verify_tweet_detail_opened(d):
            logger.info("✓ Successfully opened tweet detail page")
            return True

        logger.warning("✗ Did not open tweet detail page correctly")
        if retry_count < max_retries:
            logger.info("Going back to retry...")
            d.press("back")
            wait_random(1, 2, "back to feed")
            return click_on_tweet(d, tweet_data, tweet_index=tweet_index, retry_count=retry_count + 1, max_retries=max_retries)

        logger.error("Max retries reached, could not open tweet detail page")
        d.press("back")
        wait_random(1, 2, "back to feed")
        return False

    except Exception as e:
        logger.error(f"Error clicking tweet: {str(e)}")
        return False

def sort_replies_by_most_liked(d):
    """Click to sort replies by 'Most liked'"""
    try:
        logger.info("Sorting replies by 'Most liked'...")
        
        if d(resourceId="com.twitter.android:id/reply_sorting").exists:
            d(resourceId="com.twitter.android:id/reply_sorting").click()
            logger.info("✓ Clicked reply sorting")
            wait_random(1, 2, "sorting menu open")

            if d(text="Most liked").exists:
                d(text="Most liked").click()
                logger.info("✓ Clicked 'Most liked'")
                wait_random(2, 3, "replies reorder")
                return True
            logger.warning("Could not find 'Most liked' option")
            return False
        else:
            logger.warning("Reply sorting button not found")
            return False
            
    except Exception as e:
        logger.error(f"Error sorting replies: {str(e)}")
        return False

def scrape_top_comments(d, max_comments=5):
    """Scrape top comments from the tweet view"""
    try:
        logger.info(f"Scraping top {max_comments} comments...")
        
        comments = []
        
        wait_random(2, 3, "comments load")
        
        xml_str = d.dump_hierarchy()
        
        with open('comments_ui.xml', 'w', encoding='utf-8') as f:
            f.write(xml_str)
        
        root = ET.fromstring(xml_str)
        
        comment_count = 0
        for node in root.iter('node'):
            if comment_count >= max_comments:
                break
                
            content_desc = node.get('content-desc', '')
            
            if 'Replying to' in content_desc and '@' in content_desc:
                comment_data = parse_comment_from_content_desc(content_desc)
                
                if comment_data and comment_data['comment_body']:
                    comments.append(comment_data)
                    comment_count += 1
                    logger.info(f"  Comment {comment_count}: {comment_data['username']} - {comment_data['comment_body'][:50]}...")
        
        logger.info(f"✓ Scraped {len(comments)} comments")
        return comments
        
    except Exception as e:
        logger.error(f"Error scraping comments: {str(e)}")
        return []

def test_gemini_api():
    """Test if Gemini API key and model work"""
    try:
        logger.info("Testing Gemini API connection...")
        
        if not GEMINI_API_KEY:
            logger.error("❌ GEMINI_API_KEY is not set!")
            return False
        
        import requests
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        data = {
            "contents": [{
                "parts": [{
                    "text": "Say 'OK' if you can read this."
                }]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1000
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                logger.info(f"✓ Gemini API is working! Model: {GEMINI_MODEL}")
                return True
            else:
                logger.error(f"❌ Unexpected API response: {result}")
                return False
        elif response.status_code == 400:
            logger.error(f"❌ Bad request - Model '{GEMINI_MODEL}' may not exist or API key is invalid")
            logger.error(f"Response: {response.text}")
            return False
        elif response.status_code == 403:
            logger.error("❌ API key is invalid or doesn't have permission")
            logger.error(f"Response: {response.text}")
            return False
        else:
            logger.error(f"❌ API request failed with status {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("❌ Gemini API request timed out")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error testing Gemini API: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing Gemini API: {str(e)}")
        return False

def generate_reply_with_gemini(tweet_data):
    """Use Gemini API to generate a smart reply"""
    try:
        logger.info("Generating reply with Gemini...")
        
        tweet_text = tweet_data['tweet_body']
        comments_text = "\n".join([
            f"- {c['username']}: {c['comment_body']}" 
            for c in tweet_data['comments'][:5]
        ])
        
        prompt = f"""You are a helpful Twitter user who provides thoughtful, engaging replies.

Original Tweet by {tweet_data['username']}:
"{tweet_text}"

Top Comments:
{comments_text if comments_text else "(No comments yet)"}

Generate ONE complete, engaging reply (20-280 characters) that:
- Is relevant to the tweet content
- Adds value to the conversation
- Doesn't repeat what others have said
- Can include emojis if appropriate
- MOST IMPORTANTLY HAVE A SENSE OF HUMOR AND BE CONCISE

IMPORTANT: Reply with ONLY the complete comment text. Make sure it's a proper, finished sentence. NO EXTRA TEXT.

Your reply:"""
        logger.info(f"="*100)
        logger.info(f"Prompt: {prompt}")
        logger.info(f"="*100)

        import requests
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        data = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.8,
                "maxOutputTokens": 4500,
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        generated_reply = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        generated_reply = generated_reply.replace('"', '').strip()
        generated_reply = generated_reply.replace('\n', ' ').strip()
        
        if len(generated_reply) < 10:
            logger.warning(f"Reply too short ({len(generated_reply)} chars), using fallback")
            raise ValueError("Reply too short")
        
        incomplete_patterns = ['...', ' is', ' are', ' was', ' were', ' can', ' will', ' really']
        if any(generated_reply.endswith(pattern) for pattern in incomplete_patterns):
            logger.warning(f"Reply seems incomplete: '{generated_reply}', regenerating...")
            if not generated_reply[-1] in ['.', '!', '?', ')', '🔥', '💯', '😊', '👍', '🙌']:
                generated_reply += '!'
        
        if len(generated_reply) > 280:
            generated_reply = generated_reply[:277] + "..."
        
        logger.info(f"✓ Generated reply: {generated_reply}")
        return generated_reply
        
    except Exception as e:
        logger.error(f"Error generating reply with Gemini: {str(e)}")
        fallback_replies = [
            "This is such a great point! 👍",
            "Really appreciate you sharing this perspective!",
            "This resonates so much with me!",
            "Couldn't agree more with this take! 🔥",
            "Thanks for bringing this up, needed to hear this!",
            "100% this! So well said! 💯",
            "This is exactly what I've been thinking about lately!",
            "Love this energy! Keep sharing these thoughts! 🙌"
        ]
        return random.choice(fallback_replies)

def post_comment(d, comment_text):
    """Post a comment on the current tweet"""
    try:
        logger.info(f"Posting comment: {comment_text}")
        
        reply_clicked = False
        
        if d(resourceId="com.twitter.android:id/tweet_box").exists:
            d(resourceId="com.twitter.android:id/tweet_box").click()
            logger.info("✓ Clicked tweet box (method 1)")
            reply_clicked = True
        elif d(text="Reply").exists:
            d(text="Reply").click()
            logger.info("✓ Clicked Reply button (method 2)")
            reply_clicked = True
        elif d(resourceId="com.twitter.android:id/inline_reply").exists:
            d(resourceId="com.twitter.android:id/inline_reply").click()
            logger.info("✓ Clicked inline_reply (method 3)")
            reply_clicked = True
        else:
            logger.info("Reply box not visible, scrolling down...")
            width, height = d.window_size()
            d.swipe(width // 2, int(height * 0.5), width // 2, int(height * 0.3), duration=0.3)
            wait_random(1, 2, "scroll to reply box")
            
            if d(resourceId="com.twitter.android:id/tweet_box").exists:
                d(resourceId="com.twitter.android:id/tweet_box").click()
                logger.info("✓ Clicked tweet box after scroll")
                reply_clicked = True
            elif d(resourceId="com.twitter.android:id/inline_reply").exists:
                d(resourceId="com.twitter.android:id/inline_reply").click()
                logger.info("✓ Clicked inline_reply after scroll")
                reply_clicked = True
        
        if not reply_clicked:
            logger.warning("Could not find any reply box element")
            xml_str = d.dump_hierarchy()
            with open('post_comment_ui.xml', 'w', encoding='utf-8') as f:
                f.write(xml_str)
            return False
        
        wait_random(1, 2, "reply box open")
        
        d.send_keys(comment_text, clear=True)
        logger.info("✓ Comment typed")
        wait_random(1, 2, "typing")
        
        if d(resourceId="com.twitter.android:id/tweet_button").exists:
            d(resourceId="com.twitter.android:id/tweet_button").click()
            logger.info("✓ Clicked tweet button")
            wait_random(15, 25, "comment posting")
            return True
        else:
            logger.warning("Tweet button not found")
            return False
            
    except Exception as e:
        logger.error(f"Error posting comment: {str(e)}")
        return False

def go_back(d):
    """Press back button to return to feed"""
    try:
        logger.info("Going back to feed...")
        d.press("back")
        wait_random(2, 3, "back navigation")
        return True
    except Exception as e:
        logger.error(f"Error going back: {str(e)}")
        return False

def scroll_feed(d):
    """Scroll the feed down"""
    try:
        width, height = d.window_size()
        start_y = int(height * 0.8)
        end_y = int(height * 0.3)
        x = int(width / 2)
        
        d.swipe(x, start_y, x, end_y, duration=0.5)
        return True
    except Exception as e:
        logger.error(f"Scroll error: {str(e)}")
        return False

def scroll_feed_to_load_more(d, num_scrolls=4, at_end=False):
    """Scroll down num_scrolls times to load more posts. If at_end, wait 5s before each scroll."""
    for i in range(num_scrolls):
        if at_end:
            logger.info("Reached end of feed, waiting 5s before scroll...")
            time.sleep(5)
        scroll_feed(d)
        logger.info(f"Scroll down to load more {i + 1}/{num_scrolls}")
        wait_time = 2.0 if at_end else random.uniform(1.0, 1.8)
        time.sleep(wait_time)
    wait_random(2, 3, "feed load settle")

def save_tweets_with_comments(tweets, filename='tweets_with_comments.json'):
    """Save all tweets with their comments to JSON"""
    try:
        output = {
            'timestamp': datetime.now().isoformat(),
            'total_tweets': len(tweets),
            'tweets': tweets
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Saved {len(tweets)} tweets to {filename}")
        
    except Exception as e:
        logger.error(f"Error saving tweets: {str(e)}")

def main():
    try:
        logger.info("=" * 70)
        logger.info("TWITTER AUTO-COMMENTER")
        logger.info("=" * 70)
        
        logger.info("Step 1: Testing Gemini API...")
        if not test_gemini_api():
            logger.error("=" * 70)
            logger.error("GEMINI API TEST FAILED!")
            logger.error("=" * 70)
            logger.error("Please check:")
            logger.error("1. GEMINI_API_KEY is set correctly in environment or .env file")
            logger.error("2. The API key has proper permissions")
            logger.error(f"3. The model '{GEMINI_MODEL}' is accessible")
            logger.error("")
            logger.error("Script will EXIT. Please fix the API configuration and try again.")
            logger.error("=" * 70)
            sys.exit(1)
        
        logger.info("✓ Gemini API test passed!")
        logger.info("")
        
        logger.info("Connecting to device...")
        d = u2.connect()
        logger.info("✓ Connected")
        
        logger.info("Launching Twitter...")
        d.app_start("com.twitter.android")
        wait_random(5, 7, "app launch")
        
        max_tweets_to_comment = MAX_TWEETS_TO_COMMENT
        commented_tweets = []
        processed_usernames = set()
        scroll_attempts = 0
        max_scrolls = 20
        at_end_of_feed = False
        
        while len(commented_tweets) < max_tweets_to_comment and scroll_attempts < max_scrolls:
            logger.info("=" * 70)
            logger.info(f"PROGRESS: {len(commented_tweets)}/{max_tweets_to_comment} tweets commented")
            logger.info("=" * 70)
            
            tweets = get_visible_tweets(d)
            logger.info(f"Found {len(tweets)} tweets on screen")
            
            new_tweets_this_round = [t for t in tweets if t['username'] not in processed_usernames]
            did_scroll_at_end = False
            if (tweets and not new_tweets_this_round) or (not tweets and scroll_attempts > 0):
                at_end_of_feed = True
                logger.info("End of feed (no new tweets). Scrolling down with 5s wait before each try...")
                scroll_feed_to_load_more(d, num_scrolls=4, at_end=True)
                did_scroll_at_end = True
            
            for idx, tweet in enumerate(tweets):
                if len(commented_tweets) >= max_tweets_to_comment:
                    break
                
                if tweet['username'] in processed_usernames:
                    logger.debug(f"Skipping already processed: {tweet['username']}")
                    continue
                
                processed_usernames.add(tweet['username'])
                
                logger.info("-" * 70)
                logger.info(f"Processing tweet from {tweet['username']}")
                logger.info(f"Tweet: {(tweet.get('tweet_body') or '')[:100]}...")
                logger.info("-" * 70)
                
                if not click_on_tweet(d, tweet, tweet_index=idx):
                    logger.warning("Failed to open tweet detail page after retries, skipping...")
                    continue
                
                wait_random(1, 2, "tweet stabilize")
                
                sort_replies_by_most_liked(d)
                
                comments = scrape_top_comments(d, max_comments=5)
                tweet['comments'] = comments
                
                reply = generate_reply_with_gemini(tweet)
                tweet['our_comment'] = reply
                
                if post_comment(d, reply):
                    logger.info(f"✓ Successfully commented on tweet from {tweet['username']}")
                    commented_tweets.append(tweet)
                else:
                    logger.warning("Failed to post comment")
                
                go_back(d)
                wait_random(2, 3, "back to feed")
            
            if did_scroll_at_end:
                logger.info("Skipping scroll after load-more; next iteration will show updated feed.")
            else:
                logger.info("Scrolling to see more tweets...")
                scroll_feed(d)
                wait_random(2, 3, "scroll")
                scroll_attempts += 1
        
        logger.info("=" * 70)
        logger.info("SAVING RESULTS")
        logger.info("=" * 70)
        save_tweets_with_comments(commented_tweets)
        
        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total tweets commented: {len(commented_tweets)}")
        logger.info(f"Scrolls performed: {scroll_attempts}")
        
        for i, tweet in enumerate(commented_tweets, 1):
            logger.info(f"{i}. {tweet['username']}: {tweet['our_comment']}")
        
        logger.info("=" * 70)
        logger.info("✓ AUTO-COMMENTING COMPLETED")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error("=" * 70)
        logger.error("COMMENTER FAILED")
        logger.error("=" * 70)
        logger.error(str(e), exc_info=True)
        try:
            d.screenshot("error_commenter.png")
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()