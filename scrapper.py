import uiautomator2 as u2
import logging
import time
import sys
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitter_scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def wait_and_log(seconds, action):
    """Helper function to wait and log"""
    logger.info(f"Waiting {seconds}s after {action}...")
    time.sleep(seconds)

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
    """
    Parse tweet data from content-desc attribute
    Example: "Dishant Miyani @dishantwt_ Verified.    hear me out&#10;&#10;an IDE...            23 hours ago.  159 replies.  93 reposts.  3661 likes.  163465 verified views. "
    """
    try:
        logger.debug(f"Parsing: {content_desc[:100]}...")
        
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
            'engagement_rate': 0.0,
            'raw_content_desc': content_desc[:200]
        }
        
        name_username_pattern = r'^(.+?)\s@(\w+)'
        name_match = re.search(name_username_pattern, content_desc)
        if name_match:
            tweet_data['name'] = name_match.group(1).strip()
            tweet_data['username'] = '@' + name_match.group(2)
            logger.debug(f"Found: {tweet_data['name']} ({tweet_data['username']})")
        else:
            logger.warning("Could not extract name/username")
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
            logger.debug(f"Tweet body: {tweet_data['tweet_body'][:50]}...")
        else:
            body_pattern2 = r'@\w+\s+(.*?)\s+\d+\s+(?:hour|minute|day|second)s?\s+ago'
            body_match2 = re.search(body_pattern2, content_desc, re.DOTALL)
            if body_match2:
                body = body_match2.group(1).strip()
                body = re.sub(r'\s+', ' ', body)
                tweet_data['tweet_body'] = body[:500]
        
        if tweet_data['views'] > 0:
            total_engagement = tweet_data['replies'] + tweet_data['reposts'] + tweet_data['likes']
            tweet_data['engagement_rate'] = round((total_engagement / tweet_data['views']) * 100, 2)
        
        logger.info(f"✓ Parsed: {tweet_data['username']} | Likes: {tweet_data['likes']} | Views: {tweet_data['views']} | Engagement: {tweet_data['engagement_rate']}%")
        
        return tweet_data
        
    except Exception as e:
        logger.error(f"Error parsing tweet: {str(e)}", exc_info=True)
        return None

def scrape_visible_tweets(d):
    """
    Scrape all visible tweets from current screen by parsing XML
    """
    tweets = []
    
    try:
        logger.info("Dumping current screen XML...")
        xml_str = d.dump_hierarchy()
        
        with open('current_ui.xml', 'w', encoding='utf-8') as f:
            f.write(xml_str)
        
        logger.info("Parsing XML to find tweet elements...")
        root = ET.fromstring(xml_str)
        
        tweet_count = 0
        for node in root.iter('node'):
            resource_id = node.get('resource-id', '')
            if resource_id == 'com.twitter.android:id/row':
                content_desc = node.get('content-desc', '')
                
                if content_desc and '@' in content_desc:
                    logger.debug(f"Found tweet row #{tweet_count + 1}")
                    tweet_data = parse_tweet_from_content_desc(content_desc)
                    
                    if tweet_data and tweet_data['username']:
                        tweets.append(tweet_data)
                        tweet_count += 1
        
        logger.info(f"Extracted {len(tweets)} tweets from current screen")
        return tweets
        
    except Exception as e:
        logger.error(f"Error scraping visible tweets: {str(e)}", exc_info=True)
        return []

def scroll_feed(d):
    """Scroll the Twitter feed down"""
    try:
        width, height = d.window_size()
        logger.debug(f"Screen: {width}x{height}")
        
        start_y = int(height * 0.8)
        end_y = int(height * 0.3)
        x = int(width / 2)
        
        logger.info(f"Scrolling from y={start_y} to y={end_y}")
        d.swipe(x, start_y, x, end_y, duration=0.5)
        
        return True
        
    except Exception as e:
        logger.error(f"Scroll error: {str(e)}")
        return False

def scrape_tweets(d, max_tweets=20, scroll_count=10):
    """
    Main scraping function with scrolling
    """
    all_tweets = []
    seen_tweets = set()
    
    logger.info(f"Target: {max_tweets} tweets, Max scrolls: {scroll_count}")
    
    for scroll_num in range(scroll_count):
        logger.info("=" * 70)
        logger.info(f"SCROLL ITERATION {scroll_num + 1}/{scroll_count}")
        logger.info("=" * 70)
        
        new_tweets = scrape_visible_tweets(d)
        
        added = 0
        for tweet in new_tweets:
            identifier = (tweet['username'], tweet['posted_time'], tweet['likes'])
            
            if identifier not in seen_tweets:
                all_tweets.append(tweet)
                seen_tweets.add(identifier)
                added += 1
        
        logger.info(f"Added {added} new tweets (total: {len(all_tweets)})")
        
        screenshot_file = f"scroll_{scroll_num + 1}.png"
        d.screenshot(screenshot_file)
        logger.debug(f"Screenshot: {screenshot_file}")
        
        if len(all_tweets) >= max_tweets:
            logger.info(f"✓ Reached target of {max_tweets} tweets")
            break
        
        if scroll_num < scroll_count - 1:
            logger.info("Scrolling to load more...")
            if scroll_feed(d):
                wait_and_log(2, "scroll")
            else:
                logger.warning("Scroll failed, stopping")
                break
    
    logger.info(f"Scraping complete: {len(all_tweets)} tweets collected")
    return all_tweets[:max_tweets]

def save_tweets(tweets, json_file='scraped_tweets.json', csv_file='scraped_tweets.csv'):
    """Save tweets to JSON and CSV"""
    try:
        logger.info(f"Saving {len(tweets)} tweets...")
        
        output = {
            'scrape_timestamp': datetime.now().isoformat(),
            'total_tweets': len(tweets),
            'tweets': tweets
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Saved to {json_file}")
        
        if tweets:
            import csv
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                fields = ['name', 'username', 'verified', 'posted_time', 'replies', 'reposts', 'likes', 'views', 'engagement_rate', 'tweet_body']
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for tweet in tweets:
                    writer.writerow({k: tweet.get(k, '') for k in fields})
            logger.info(f"✓ Saved to {csv_file}")
        
    except Exception as e:
        logger.error(f"Save error: {str(e)}", exc_info=True)

def main():
    try:
        logger.info("=" * 70)
        logger.info("TWITTER SCRAPER - FIXED VERSION")
        logger.info("=" * 70)
        
        logger.info("Connecting to device...")
        d = u2.connect()
        logger.info("✓ Connected")
        
        logger.info("Launching Twitter...")
        d.app_start("com.twitter.android")
        wait_and_log(5, "app launch")
        d.screenshot("00_initial.png")
        
        logger.info("Starting scraping process...")
        tweets = scrape_tweets(d, max_tweets=20, scroll_count=10)
        
        logger.info("Saving results...")
        save_tweets(tweets)
        
        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total tweets scraped: {len(tweets)}")
        
        if tweets:
            total_likes = sum(t['likes'] for t in tweets)
            total_views = sum(t['views'] for t in tweets)
            avg_engagement = sum(t['engagement_rate'] for t in tweets) / len(tweets)
            
            logger.info(f"Total likes: {total_likes:,}")
            logger.info(f"Total views: {total_views:,}")
            logger.info(f"Average engagement: {avg_engagement:.2f}%")
            
            logger.info("\nTop 5 tweets by engagement:")
            sorted_tweets = sorted(tweets, key=lambda x: x['engagement_rate'], reverse=True)
            for i, t in enumerate(sorted_tweets[:5], 1):
                logger.info(f"{i}. {t['username']}: {t['engagement_rate']}% ({t['likes']:,} likes, {t['views']:,} views)")
            
            logger.info("\nTop 5 tweets by likes:")
            sorted_by_likes = sorted(tweets, key=lambda x: x['likes'], reverse=True)
            for i, t in enumerate(sorted_by_likes[:5], 1):
                logger.info(f"{i}. {t['username']}: {t['likes']:,} likes ({t['engagement_rate']}% engagement)")
        
        logger.info("=" * 70)
        logger.info("✓ SCRAPING COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info(f"Check: scraped_tweets.json and scraped_tweets.csv")
        
    except Exception as e:
        logger.error("=" * 70)
        logger.error("SCRAPING FAILED")
        logger.error("=" * 70)
        logger.error(str(e), exc_info=True)
        try:
            d.screenshot("error.png")
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()