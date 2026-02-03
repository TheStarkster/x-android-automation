import uiautomator2 as u2
import logging
import time
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitter_automation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def wait_and_log(seconds, action):
    """Helper function to wait and log"""
    logger.info(f"Waiting {seconds}s after {action}...")
    time.sleep(seconds)

def check_element_exists(d, selector, element_name):
    """Check if element exists and log result"""
    logger.debug(f"Checking for element: {element_name}")
    exists = selector.exists
    if exists:
        logger.info(f"✓ {element_name} found")
        return True
    else:
        logger.error(f"✗ {element_name} NOT found")
        return False

def main():
    try:
        logger.info("=" * 60)
        logger.info("Starting Twitter Automation Script")
        logger.info("=" * 60)
        
        logger.info("Connecting to device...")
        d = u2.connect()
        logger.info(f"✓ Connected to device: {d.info}")
        
        device_info = d.device_info
        logger.debug(f"Device info: {device_info}")
        
        logger.info("-" * 60)
        logger.info("Step 1: Launching Twitter app")
        logger.info("-" * 60)
        
        package_name = "com.twitter.android"
        logger.debug(f"Package name: {package_name}")
        
        d.app_start(package_name)
        logger.info(f"✓ Twitter app started")
        wait_and_log(4, "app launch")
        
        screenshot_path = "01_after_launch.png"
        d.screenshot(screenshot_path)
        logger.debug(f"Screenshot saved: {screenshot_path}")
        
        logger.info("-" * 60)
        logger.info("Step 2: Clicking first composer_write button")
        logger.info("-" * 60)
        
        composer_write = d(resourceId="com.twitter.android:id/composer_write")
        if check_element_exists(d, composer_write, "composer_write button"):
            composer_write.click()
            logger.info("✓ First composer_write button clicked")
            wait_and_log(2, "first composer_write click")
            d.screenshot("02_after_first_compose_click.png")
        else:
            raise Exception("composer_write button not found")
        
        logger.info("-" * 60)
        logger.info("Step 3: Clicking second composer_write button")
        logger.info("-" * 60)
        
        composer_write_2 = d(resourceId="com.twitter.android:id/composer_write")
        if check_element_exists(d, composer_write_2, "composer_write button (2nd)"):
            composer_write_2.click()
            logger.info("✓ Second composer_write button clicked")
            wait_and_log(2, "second composer_write click")
            d.screenshot("03_after_second_compose_click.png")
        else:
            logger.warning("⚠ Second composer_write button not found, continuing...")
        
        logger.info("-" * 60)
        logger.info("Step 4: Clicking tweet text field")
        logger.info("-" * 60)
        
        tweet_text = d(resourceId="com.twitter.android:id/tweet_text")
        if check_element_exists(d, tweet_text, "tweet_text field"):
            tweet_text.click()
            logger.info("✓ Tweet text field clicked")
            wait_and_log(1, "tweet text field click")
            d.screenshot("04_after_text_field_click.png")
        else:
            raise Exception("tweet_text field not found")
        
        logger.info("-" * 60)
        logger.info("Step 5: Typing tweet content")
        logger.info("-" * 60)
        
        tweet_content = "this is test"
        logger.debug(f"Tweet content: '{tweet_content}'")
        logger.info("Sending keys to text field...")
        
        d.send_keys(tweet_content, clear=True)
        logger.info(f"✓ Text entered: '{tweet_content}'")
        wait_and_log(1, "text input")
        d.screenshot("05_after_text_input.png")
        
        logger.info("-" * 60)
        logger.info("Step 7: Clicking post button via xpath")
        logger.info("-" * 60)
        
        xpath_selector = '//*[@resource-id="com.twitter.android:id/composer_toolbar"]/android.widget.LinearLayout[1]'
        logger.debug(f"XPath: {xpath_selector}")
        
        post_button = d.xpath(xpath_selector)
        if post_button.exists:
            logger.info("✓ Post button found via xpath")
            post_button.click()
            logger.info("✓ Post button clicked")
            wait_and_log(2, "post button click")
            d.screenshot("08_after_post_click.png")
        else:
            logger.error("✗ Post button NOT found via xpath")
            raise Exception("Post button not found")
        
        logger.info("-" * 60)
        logger.info("Step 8: Verification")
        logger.info("-" * 60)
        
        wait_and_log(3, "post submission")
        d.screenshot("09_final_state.png")
        
        logger.info("=" * 60)
        logger.info("✓ Twitter automation completed successfully!")
        logger.info("=" * 60)
        logger.info(f"Check screenshots 01-09 and twitter_automation.log for details")
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error("✗ AUTOMATION FAILED")
        logger.error("=" * 60)
        logger.error(f"Error: {str(e)}", exc_info=True)
        
        try:
            error_screenshot = "error_screenshot.png"
            d.screenshot(error_screenshot)
            logger.info(f"Error screenshot saved: {error_screenshot}")
        except:
            logger.error("Could not save error screenshot")
        
        try:
            logger.info("Dumping UI hierarchy for debugging...")
            xml = d.dump_hierarchy()
            with open('ui_hierarchy_error.xml', 'w', encoding='utf-8') as f:
                f.write(xml)
            logger.info("UI hierarchy saved: ui_hierarchy_error.xml")
        except:
            logger.error("Could not dump UI hierarchy")
        
        sys.exit(1)
    
    finally:
        logger.info("Script execution finished")

if __name__ == "__main__":
    main()