from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
import time
import logging
from datetime import datetime
import re
from retrying import retry
import json
import argparse
import subprocess
import os
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

def retry_on_timeout(retries=3, delay=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except TimeoutException as e:
                    if attempt == retries - 1:
                        raise
                    logging.warning(f"Timeout occurred, retrying in {delay} seconds... (Attempt {attempt + 1}/{retries})")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

def get_waaw_link(driver):
    """Get video link from waaw.to by finding the iframe src attribute."""
    try:
        logging.info("Looking for waaw.to iframe")
        
        # Look for iframe with waaw.to in src
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            src = iframe.get_attribute('src')
            if src and 'waaw.to' in src:
                logging.info(f"Found waaw.to link: {src}")
                return src
        
        logging.warning("No waaw.to iframe found")
        return None
        
    except Exception as e:
        logging.error(f"Error getting waaw.to link: {str(e)}")
        return None

def find_m3u8_links(driver, is_netu=False):
    """Find all .m3u8 links in the page source and network requests."""
    if is_netu:
        waaw_link = get_waaw_link(driver)
        if waaw_link:
            return [waaw_link]
        return []
        
    m3u8_links = set()
    
    # Get initial network requests
    logs = driver.get_log('performance')
    for entry in logs:
        try:
            log = json.loads(entry['message'])['message']
            if 'Network.responseReceived' in log['method']:
                url = log['params']['response']['url']
                if '.m3u8' in url:
                    m3u8_links.add(url)
                    logging.info(f"Found m3u8 link: {url}")
        except:
            continue
    
    # Check for any iframes that might contain video players
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for iframe in iframes:
        try:
            driver.switch_to.frame(iframe)
            time.sleep(2)
            
            # Get network requests from iframe
            iframe_logs = driver.get_log('performance')
            for entry in iframe_logs:
                try:
                    log = json.loads(entry['message'])['message']
                    if 'Network.responseReceived' in log['method']:
                        url = log['params']['response']['url']
                        if '.m3u8' in url:
                            m3u8_links.add(url)
                            logging.info(f"Found m3u8 link in iframe: {url}")
                except:
                    continue
            
            driver.switch_to.default_content()
        except:
            continue
    
    # Additional wait for any delayed requests
    time.sleep(5)
    
    # Get final network requests
    final_logs = driver.get_log('performance')
    for entry in final_logs:
        try:
            log = json.loads(entry['message'])['message']
            if 'Network.responseReceived' in log['method']:
                url = log['params']['response']['url']
                if '.m3u8' in url:
                    m3u8_links.add(url)
                    logging.info(f"Found m3u8 link: {url}")
        except:
            continue
    
    return list(m3u8_links)

def wait_for_element(driver, by, value, timeout=100):
    """Wait for an element to be present and visible."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((by, value))
        )
        return element
    except TimeoutException:
        logging.error(f"Timeout waiting for element: {value}")
        raise

def get_movie_details(driver):
    """Scrape movie details from the page."""
    try:
        logging.info("Scraping movie details...")
        
        # Get title
        title = driver.find_element(By.CSS_SELECTOR, 'h1.Title').text
        logging.info(f"Title: {title}")
        
        # Get image URL
        img_element = driver.find_element(By.CSS_SELECTOR, 'figure img.lazy')
        image_url = img_element.get_attribute('src')
        logging.info(f"Image URL: {image_url}")
        
        # Get description
        description = driver.find_element(By.CSS_SELECTOR, 'div.Description').text
        logging.info(f"Description: {description}")
        
        # Get rating, duration and year
        info = driver.find_element(By.CSS_SELECTOR, 'p.Info').text
        logging.info(f"Info: {info}")
        
        # Get genres
        genres = [a.text for a in driver.find_elements(By.CSS_SELECTOR, 'li.AAIco-adjust:first-child a')]
        logging.info(f"Genres: {', '.join(genres)}")
        
        # Get actors
        actors = [a.text for a in driver.find_elements(By.CSS_SELECTOR, 'li.AAIco-adjust:nth-child(2) a')]
        logging.info(f"Actors: {', '.join(actors)}")
        
        return {
            'title': title,
            'image_url': image_url,
            'description': description,
            'info': info,
            'genres': genres,
            'actors': actors
        }
    except Exception as e:
        logging.error(f"Error scraping movie details: {e}")
        return None

def remove_netu_overlay(driver):
    """Try to remove the netu overlay by clicking random positions."""
    try:
        logging.info("Attempting to remove netu overlay")
        
        # First try to find and remove any overlay elements
        driver.execute_script("""
            document.querySelectorAll('.overlay, .popup, .modal, [class*="overlay"], [class*="popup"], [class*="modal"], img[src^="data:image"]').forEach(function(element) {
                element.remove();
            });
        """)
        
        # Try clicking at more positions where the play button might be
        positions = [
            (400, 300),  # Center
            (400, 250),  # Center top
            (400, 350),  # Center bottom
            (300, 300),  # Left center
            (500, 300),  # Right center
            (350, 250),  # Top left
            (450, 250),  # Top right
            (350, 350),  # Bottom left
            (450, 350)   # Bottom right
        ]
        
        for x, y in positions:
            try:
                # Create action chain to move to position and click
                actions = ActionChains(driver)
                actions.move_by_offset(x, y).click().perform()
                time.sleep(1)
                logging.info(f"Clicked position ({x}, {y})")
                
                # Try to find and click any play button that might be visible
                try:
                    play_buttons = driver.find_elements(By.CSS_SELECTOR, 'button[class*="play"], div[class*="play"], img[class*="play"]')
                    for button in play_buttons:
                        if button.is_displayed():
                            driver.execute_script("arguments[0].click();", button)
                            logging.info("Found and clicked play button")
                            time.sleep(2)
                            return True
                except:
                    continue
                
            except:
                continue
        
        # Additional wait after overlay removal attempts
        time.sleep(2)
        return True
    except Exception as e:
        logging.warning(f"Error removing netu overlay: {str(e)}")
        return False

def find_and_click_video_option(driver, source_flags=None):
    """Find and click video option based on provided source flags."""
    if source_flags is None:
        source_flags = {}
    
    # Define all possible options with their corresponding flags
    hd_options = {
        'vidhide_hd': "//span[contains(text(), 'vidhide - HD')]",
        'filemoon_hd': "//span[contains(text(), 'filemoon - HD')]",
        'voesx_hd': "//span[contains(text(), 'voesx - HD')]"
    }
    
    cam_options = {
        'vidhide_cam': "//span[contains(text(), 'vidhide - CAM')]",
        'filemoon_cam': "//span[contains(text(), 'filemoon - CAM')]",
        'voesx_cam': "//span[contains(text(), 'voesx - CAM')]"
    }
    
    # Check if any flags are set
    has_flags = any(source_flags.values())
    
    if has_flags:
        options_to_try = []
        
        # Add HD options if their flags are set
        for flag, xpath in hd_options.items():
            if source_flags.get(flag):
                options_to_try.append((xpath, 'HD'))
        
        # Add CAM options if their flags are set
        for flag, xpath in cam_options.items():
            if source_flags.get(flag):
                options_to_try.append((xpath, 'CAM'))
        
        # If no specific flags were matched, return False
        if not options_to_try:
            logging.error("No matching video options found for provided flags")
            return False, False
    else:
        # If no flags provided, try all options in order
        options_to_try = [(xpath, 'HD') for xpath in hd_options.values()]
        options_to_try.extend([(xpath, 'CAM') for xpath in cam_options.values()])
    
    # Try each option in order
    for option_xpath, quality in options_to_try:
        try:
            logging.info(f"Looking for {quality} video option: {option_xpath}")
            video_option = wait_for_element(driver, By.XPATH, option_xpath, timeout=20)
            
            # Click the option
            driver.execute_script("arguments[0].click();", video_option)
            time.sleep(8)
            
            logging.info(f"Successfully clicked {quality} option: {option_xpath}")
            return True, False
            
        except Exception as e:
            logging.warning(f"Could not find or click {quality} option {option_xpath}: {str(e)}")
            continue
    
    logging.error("Could not find any suitable video option")
    return False, False

def check_and_handle_iframe(driver):
    """Check for iframes and handle them similar to check_image.py logic."""
    try:
        logging.info("Checking for iframes...")
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        
        # Check each iframe for the player link
        for iframe in iframes:
            src = iframe.get_attribute('src')
            if src:
                # Handle voe.sx iframes
                if 'voe.sx' in src:
                    logging.info(f"Found voe.sx iframe with URL: {src}")
                    # Navigate to the voe.sx URL
                    driver.get(src)
                    time.sleep(3)
                    
                    try:
                        # Wait for and click the voe logo
                        wait = WebDriverWait(driver, 10)
                        voe_logo = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'img.icon[src="/s/images/logos/voe-logo-2.svg"]'))
                        )
                        logging.info("Found voe logo, attempting to click...")
                        driver.execute_script("arguments[0].click();", voe_logo)
                        
                        # Wait for redirect and m3u8 links
                        time.sleep(3)
                        return driver.current_url
                        
                    except Exception as e:
                        logging.error(f"Error handling voe.sx iframe: {e}")
                        continue
                
                # Handle cuevana3 player iframes
                elif 'player.cuevana3.eu/player.php' in src:
                    logging.info(f"Found player iframe with URL: {src}")
                    player_url = src
                    
                    # Navigate to the player URL
                    logging.info("Navigating to player URL...")
                    driver.get(player_url)
                    time.sleep(3)
                    
                    # Find and click the play button
                    logging.info("Looking for play button...")
                    try:
                        # Wait for the play button to be present
                        wait = WebDriverWait(driver, 10)
                        play_button = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'img[src="play.png"][alt="Reproducir"][id="start"]'))
                        )
                        
                        # Try to click using JavaScript
                        logging.info("Found play button, attempting to click...")
                        driver.execute_script("arguments[0].click();", play_button)
                        
                        # Wait for redirect with countdown
                        logging.info("Waiting for redirect...")
                        max_wait = 30  # Maximum wait time in seconds
                        start_time = time.time()
                        
                        while time.time() - start_time < max_wait:
                            current_url = driver.current_url
                            if current_url != player_url:
                                elapsed = int(time.time() - start_time)
                                logging.info(f"Redirected after {elapsed} seconds!")
                                logging.info(f"Final URL: {current_url}")
                                return current_url
                            
                            # Update countdown every second
                            elapsed = int(time.time() - start_time)
                            remaining = max_wait - elapsed
                            logging.info(f"Waiting for redirect... {remaining} seconds remaining")
                            time.sleep(1)
                        
                        logging.warning("No redirect after maximum wait time")
                        return None
                        
                    except Exception as e:
                        logging.error(f"Error finding/clicking play button: {e}")
                        # Try alternative click method
                        try:
                            logging.info("Trying alternative click method...")
                            actions = ActionChains(driver)
                            actions.move_to_element(play_button).click().perform()
                            
                            # Wait for redirect with countdown
                            logging.info("Waiting for redirect...")
                            max_wait = 30
                            start_time = time.time()
                            
                            while time.time() - start_time < max_wait:
                                current_url = driver.current_url
                                if current_url != player_url:
                                    elapsed = int(time.time() - start_time)
                                    logging.info(f"Redirected after {elapsed} seconds!")
                                    logging.info(f"Final URL: {current_url}")
                                    return current_url
                                
                                elapsed = int(time.time() - start_time)
                                remaining = max_wait - elapsed
                                logging.info(f"Waiting for redirect... {remaining} seconds remaining")
                                time.sleep(1)
                            
                            logging.warning("No redirect after maximum wait time")
                            return None
                            
                        except Exception as e2:
                            logging.error(f"Alternative click method also failed: {e2}")
                            return None
        
        logging.info("No player iframes found")
        return None
        
    except Exception as e:
        logging.error(f"Error checking iframes: {e}")
        return None

def check_vlc_playback(process):
    """Check if VLC is actually playing the video."""
    try:
        # Wait longer to see if VLC starts playing properly
        time.sleep(15)  # Increased from 8 to 15 seconds
        
        # Check if process is still running
        if process.poll() is not None:
            logging.warning("VLC process terminated unexpectedly")
            return False
            
        # Additional check after a few more seconds
        time.sleep(10)  # Increased from 3 to 10 seconds
        
        # Check again if process is still running
        if process.poll() is not None:
            logging.warning("VLC process terminated after initial playback")
            return False
            
        # If we get here, VLC is still running after 25 seconds
        # This is a good indication that playback is working
        return True
        
    except Exception as e:
        logging.error(f"Error checking VLC playback: {str(e)}")
        return False

def try_play_in_vlc(video_links, auto_test=False):
    """Try to play each link in VLC until one works."""
    if not video_links:
        logging.error("No video links to try")
        return False
        
    # Filter out swiftplayers.com and jonathansociallike.com links
    filtered_links = [link for link in video_links if 'swiftplayers.com/stream/' not in link and 'jonathansociallike.com' not in link]
    
    if not filtered_links:
        logging.error("No valid video links to try after filtering out excluded domains")
        return False
        
    # Try each link in order
    for link in filtered_links:
        logging.info(f"Attempting to play: {link}")
        
        try:
            # Default VLC path for Windows
            vlc_path = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
            
            # Check if VLC exists at default path
            if not os.path.exists(vlc_path):
                # Try alternative common paths
                alt_paths = [
                    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
                    os.path.expanduser("~\\AppData\\Local\\Programs\\VideoLAN\\VLC\\vlc.exe")
                ]
                for path in alt_paths:
                    if os.path.exists(path):
                        vlc_path = path
                        break
                else:
                    logging.error("VLC not found in common installation paths")
                    return False
            
            # Open VLC with the m3u8 URL
            process = subprocess.Popen([vlc_path, link])
            
            # Wait a bit for VLC to start
            time.sleep(5)
            
            # Check if process is still running
            if process.poll() is not None:
                logging.warning("VLC process terminated unexpectedly")
                continue
            
            # If auto_test is True, just check if VLC is still running after a few seconds
            if auto_test:
                time.sleep(25)  # Increased from 8 to 25 seconds to give more time for verification
                if process.poll() is None:  # If process is still running
                    process.terminate()  # Kill the process since we just wanted to test
                    time.sleep(2)  # Wait for VLC to close
                    return True
                continue
            
            # For manual testing, ask user if video is playing
            while True:
                response = input("\nIs the video playing correctly in VLC? (yes/no): ").lower().strip()
                if response in ['yes', 'no']:
                    break
                print("Please answer 'yes' or 'no'")
            
            if response == 'yes':
                logging.info("User confirmed video is playing correctly")
                return True
            else:
                logging.info("User reported video is not playing correctly, trying next link")
                # Kill the VLC process
                process.terminate()
                time.sleep(2)  # Wait for VLC to close
                continue  # Try next link
                    
        except Exception as e:
            logging.error(f"Error trying to play in VLC: {str(e)}")
            continue  # Try next link
    
    logging.error("Failed to play any of the links in VLC")
    return False

def get_best_m3u8_link(video_links):
    """Get the best m3u8 link by prioritizing index links and avoiding master links."""
    if not video_links:
        return None
        
    # First try to find links with 'index' but not 'master'
    priority_links = [link for link in video_links if 'index' in link.lower() and 'master' not in link.lower()]
    
    if priority_links:
        logging.info("Found priority m3u8 link with index")
        return priority_links[0]
    
    # If no priority links found, return the first non-master link
    non_master_links = [link for link in video_links if 'master' not in link.lower()]
    if non_master_links:
        logging.info("No index link found, using first available non-master link")
        return non_master_links[0]
    
    # If all links are master links, return the first one as last resort
    logging.info("Only master links found, using first available link as last resort")
    return video_links[0]

def search_movie_by_title(search_term):
    """Search for a movie in movie_links.txt by title."""
    try:
        logging.info(f"Searching for movie with term: {search_term}")
        matches = []
        
        # Read movie_links.txt
        with open('movie_links.txt', 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                    
                # Split the line into title and URL
                parts = line.split(' | ')
                if len(parts) != 2:
                    continue
                    
                title, url = parts
                
                # Check if search term is in title (case insensitive)
                if search_term.lower() in title.lower():
                    matches.append((title, url))
        
        if matches:
            logging.info(f"Found {len(matches)} matches")
            return matches
        else:
            logging.info("No matches found")
            return None
            
    except FileNotFoundError:
        logging.error("movie_links.txt file not found")
        return None
    except Exception as e:
        logging.error(f"Error searching for movie: {str(e)}")
        return None

def format_roku_xml(movie_details, video_links):
    """Format movie details in Roku XML format."""
    if not movie_details or not video_links:
        return None
        
    # Extract year and runtime from info
    info_parts = movie_details['info'].split()
    year = info_parts[-1] if len(info_parts) > 0 else ""
    runtime = " ".join(info_parts[1:-1]) if len(info_parts) > 2 else ""
    
    # Get the first working video link
    video_url = ""
    for link in video_links:
        logging.info(f"Testing video link for Roku output: {link}")
        if try_play_in_vlc([link], auto_test=True):
            video_url = link
            logging.info("Found working video link for Roku output")
            break
    
    if not video_url:
        logging.error("No working video links found for Roku output")
        return None
    
    # Format genres as comma-separated string
    genres = ", ".join(movie_details['genres'])
    
    # Clean up title and description - remove empty quotes and strip whitespace
    title = movie_details['title'].strip().replace('""', '').replace('"', '')
    description = movie_details['description'].strip().replace('""', '').replace('"', '')
    
    # Create XML content for just the item
    xml_content = f"""   <item
           title="{title}"
           description="{description}"
           hdposterurl="{movie_details['image_url']}"
           streamformat="hls"
           url="{video_url}">

      <genre>{genres}</genre>
      <year>{year}</year>
      <runtime>{runtime}</runtime>

      <subtitle language="eng" description="English" url=""/>
      <subtitle language="spa" description="Spanish" url=""/>
   </item>"""
    
    return xml_content

def process_all_movies_for_roku(randomize=False):
    """Process all movies from movie_links.txt and create Roku XML output."""
    try:
        # Read existing history if any
        processed_movies = set()
        if os.path.exists('MainHistory.txt'):
            with open('MainHistory.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    if ' | ' in line:
                        title = line.split(' | ')[0].strip()
                        processed_movies.add(title.lower())
            logging.info(f"Found {len(processed_movies)} previously processed movies")

        # Read movie_links.txt
        with open('movie_links.txt', 'r', encoding='utf-8') as f:
            movies = [line.strip() for line in f if line.strip()]

        # Randomize the order if requested
        if randomize:
            random.shuffle(movies)
            logging.info("Randomized movie processing order")

        total_movies = len(movies)
        logging.info(f"Found {total_movies} movies to process")

        # Initialize or read existing Roku XML
        if os.path.exists('RokuChannelList.xml'):
            with open('RokuChannelList.xml', 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace('</Content>', '')
        else:
            content = '<Content>\n'

        # Process each movie
        for i, movie_line in enumerate(movies, 1):
            try:
                title, url = movie_line.split(' | ')
                title = title.strip()
                url = url.strip()

                # Skip if already processed
                if title.lower() in processed_movies:
                    logging.info(f"Skipping already processed movie: {title}")
                    continue

                logging.info(f"Processing movie {i}/{total_movies}: {title}")
                
                # Set up Chrome options for each movie
                chrome_options = Options()
                chrome_options.add_argument('--headless')  # Re-enable headless for AWS
                chrome_options.add_argument('--window-size=1920,1080')
                chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
                chrome_options.add_argument('--start-maximized')
                chrome_options.add_argument('--ignore-certificate-errors')
                chrome_options.add_argument('--ignore-ssl-errors')
                chrome_options.add_argument('--disable-notifications')
                chrome_options.add_argument('--disable-popup-blocking')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-web-security')
                chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
                chrome_options.add_argument('--disable-site-isolation-trials')
                chrome_options.add_argument('--disable-webgl')
                chrome_options.add_argument('--disable-software-rasterizer')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-logging')
                chrome_options.add_argument('--log-level=3')
                chrome_options.add_argument('--silent')
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
                chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

                # Initialize the Chrome driver
                logging.info("Initializing Chrome driver")
                driver = webdriver.Chrome(options=chrome_options)
                driver.set_page_load_timeout(60)

                # Add CDP commands to modify browser behavior
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                })
                driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': '''
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        })
                    '''
                })

                try:
                    # Navigate to the movie page
                    driver.get(url)
                    WebDriverWait(driver, 30).until(
                        lambda driver: driver.execute_script('return document.readyState') == 'complete'
                    )
                    time.sleep(5)

                    # Get movie details
                    movie_details = get_movie_details(driver)
                    if not movie_details:
                        logging.warning(f"Failed to get details for {title}")
                        continue

                    # Try to close any popups
                    try:
                        driver.execute_script("""
                            document.querySelectorAll("[id^='lkdjl'], .overlay, .popup").forEach(function(element) {
                                element.remove();
                            });
                        """)
                        time.sleep(2)
                    except Exception as e:
                        logging.warning(f"No overlays found or error removing them: {str(e)}")

                    # Find and click dropdown
                    dropdown_button = wait_for_element(driver, By.CSS_SELECTOR, "div.H_ndV_0.fa.fa-chevron-down", timeout=20)
                    for attempt in range(3):
                        try:
                            driver.execute_script("""
                                arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});
                                arguments[0].click();
                            """, dropdown_button)
                            time.sleep(2)
                            break
                        except ElementClickInterceptedException:
                            if attempt == 2:
                                raise
                            time.sleep(2)

                    # Find and click video option
                    success, is_netu = find_and_click_video_option(driver)
                    if not success:
                        logging.warning(f"Failed to find video option for {title}")
                        continue

                    time.sleep(5)

                    # Check for iframes
                    final_url = check_and_handle_iframe(driver)
                    if final_url:
                        video_links = find_m3u8_links(driver, False)
                    else:
                        time.sleep(10)
                        video_links = find_m3u8_links(driver, is_netu)

                    if not video_links:
                        logging.warning(f"No video links found for {title}")
                        continue

                    # Find working video link
                    working_link = None
                    for link in video_links:
                        if try_play_in_vlc([link], auto_test=True):
                            working_link = link
                            logging.info(f"Found working link for {title}: {link}")
                            break

                    if not working_link:
                        logging.warning(f"No working video links found for {title}")
                        continue

                    # Format and add to Roku XML
                    roku_xml = format_roku_xml(movie_details, [working_link])
                    if roku_xml:
                        # Add to Roku XML immediately
                        with open('RokuChannelList.xml', 'w', encoding='utf-8') as f:
                            f.write(content + '\n' + roku_xml + '\n</Content>')
                        
                        # Update content for next iteration
                        content = content + '\n' + roku_xml
                        
                        # Add to history with working link
                        with open('MainHistory.txt', 'a', encoding='utf-8') as f:
                            f.write(f"{title} | {working_link}\n")
                        
                        logging.info(f"Successfully processed {title}")
                    else:
                        logging.warning(f"Failed to create Roku XML for {title}")

                finally:
                    driver.quit()

            except Exception as e:
                logging.error(f"Error processing movie {title}: {str(e)}")
                continue

        logging.info("Completed processing all movies")

    except Exception as e:
        logging.error(f"Error in process_all_movies_for_roku: {str(e)}")
        raise

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Scrape movie details and video links from cuevana3.is')
    parser.add_argument('url', nargs='?', help='URL of the movie page on cuevana3.is')
    parser.add_argument('-VLC', '--vlc', action='store_true', help='Open the first m3u8 link in VLC player')
    parser.add_argument('-S', '--search', help='Search for a movie in movie_links.txt by title')
    parser.add_argument('-rokuoutput', '--rokuoutput', action='store_true', help='Output movie details in Roku XML format')
    parser.add_argument('-rokuall', '--rokuall', action='store_true', help='Process all movies from movie_links.txt for Roku output')
    parser.add_argument('-r', '--random', action='store_true', help='Randomize the order of movies when using -rokuall')
    parser.add_argument('-rokufailed', '--rokufailed', action='store_true', help='Save the best working m3u8 link to a text file named after the movie title')
    
    # Add source-specific flags
    parser.add_argument('--vidhide-hd', action='store_true', help='Only try vidhide HD source')
    parser.add_argument('--filemoon-hd', action='store_true', help='Only try filemoon HD source')
    parser.add_argument('--voesx-hd', action='store_true', help='Only try voesx HD source')
    
    parser.add_argument('--vidhide-cam', action='store_true', help='Only try vidhide CAM source')
    parser.add_argument('--filemoon-cam', action='store_true', help='Only try filemoon CAM source')
    parser.add_argument('--voesx-cam', action='store_true', help='Only try voesx CAM source')
    
    args = parser.parse_args()

    # Handle rokuall option
    if args.rokuall:
        process_all_movies_for_roku(randomize=args.random)
        return

    # Handle search functionality
    if args.search:
        matches = search_movie_by_title(args.search)
        if matches:
            print("\nFound matches:")
            for i, (title, url) in enumerate(matches, 1):
                print(f"{i}. {title}")
                print(f"   URL: {url}")
            
            # Ask user if they want to proceed with a specific match
            while True:
                try:
                    choice = input("\nEnter the number of the movie you want to process (or 'q' to quit): ")
                    if choice.lower() == 'q':
                        return
                    
                    choice = int(choice)
                    if 1 <= choice <= len(matches):
                        selected_title, selected_url = matches[choice - 1]
                        print(f"\nProcessing: {selected_title}")
                        args.url = selected_url
                        break
                    else:
                        print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a valid number or 'q' to quit.")
        else:
            print("No matches found.")
            return

    # If no URL is provided and no search was performed, show help
    if not args.url:
        parser.print_help()
        return

    # Create source flags dictionary
    source_flags = {
        'vidhide_hd': args.vidhide_hd,
        'filemoon_hd': args.filemoon_hd,
        'voesx_hd': args.voesx_hd,
        'vidhide_cam': args.vidhide_cam,
        'filemoon_cam': args.filemoon_cam,
        'voesx_cam': args.voesx_cam
    }

    start_time = datetime.now()
    logging.info("Starting the scraping process")
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Re-enable headless for AWS
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
    chrome_options.add_argument('--disable-site-isolation-trials')
    chrome_options.add_argument('--disable-webgl')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument('--silent')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    # Initialize the Chrome driver
    logging.info("Initializing Chrome driver")
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(120)
    
    # Add CDP commands to modify browser behavior
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    })
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })

    try:
        # Navigate to the webpage
        logging.info(f"Navigating to URL: {args.url}")
        driver.get(args.url)
        
        # Wait for page load with a longer timeout
        logging.info("Waiting for page to load")
        WebDriverWait(driver, 60).until(
            lambda driver: driver.execute_script('return document.readyState') == 'complete'
        )
        
        # Additional wait for dynamic content
        time.sleep(10)
        
        # Always get movie details first
        logging.info("Getting movie details...")
        movie_details = get_movie_details(driver)
        if movie_details:
            logging.info("Successfully scraped movie details")
        else:
            logging.warning("Failed to scrape movie details")
        
        # Try to close any popups or overlays if they exist
        try:
            logging.info("Attempting to remove overlays")
            driver.execute_script("""
                document.querySelectorAll("[id^='lkdjl'], .overlay, .popup").forEach(function(element) {
                    element.remove();
                });
            """)
            logging.info("Successfully removed overlays")
            time.sleep(2)
        except Exception as e:
            logging.warning(f"No overlays found or error removing them: {str(e)}")
        
        # Find and interact with dropdown button
        logging.info("Looking for dropdown button")
        dropdown_button = wait_for_element(driver, By.CSS_SELECTOR, "div.H_ndV_0.fa.fa-chevron-down", timeout=20)
        
        # Scroll and click with retry mechanism
        for attempt in range(3):
            try:
                logging.info(f"Attempting to click dropdown button (Attempt {attempt + 1}/3)")
                driver.execute_script("""
                    arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});
                    arguments[0].click();
                """, dropdown_button)
                time.sleep(2)
                break
            except ElementClickInterceptedException:
                if attempt == 2:
                    raise
                logging.warning("Click intercepted, retrying...")
                time.sleep(2)
        
        # Find and click video option with source flags
        success, is_netu = find_and_click_video_option(driver, source_flags)
        if not success:
            raise Exception("Failed to find and click any video option")
        
        # Wait for video to load
        time.sleep(5)
        
        # Now check for iframes after selecting the video option
        final_url = check_and_handle_iframe(driver)
        
        if final_url:
            # If we got a final URL from iframe handling, get m3u8 links from there
            logging.info("Found iframe and got final URL, getting m3u8 links...")
            video_links = find_m3u8_links(driver, False)  # False because we're not in netu mode
        else:
            # No iframe found, proceed with normal video link scraping
            logging.info("No iframe found, proceeding with normal video link scraping...")
            
            # Wait longer for video to load and network requests to complete
            time.sleep(10)
            
            # Find all m3u8 links or waaw.to link
            logging.info("Searching for video links")
            video_links = find_m3u8_links(driver, is_netu)
        
        if video_links:
            logging.info(f"Found {len(video_links)} video links:")
            for i, link in enumerate(video_links, 1):
                logging.info(f"Link {i}: {link}")
            
            # If VLC flag is set, try to play the links in VLC
            if args.vlc and video_links:
                logging.info("VLC flag detected, attempting to play links in VLC...")
                if not try_play_in_vlc(video_links):
                    logging.error("Failed to play any of the links in VLC")
        else:
            logging.warning("No video links found")
        
        # Calculate and log total execution time
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        logging.info(f"Successfully completed all steps in {execution_time:.2f} seconds")
        
        # Return both movie details and video links
        result = {
            'movie_details': movie_details,
            'video_links': video_links
        }
        
        # If Roku output is requested, format and save the XML
        if args.rokuoutput and movie_details and video_links:
            logging.info("Roku output requested, testing video links...")
            roku_xml = format_roku_xml(movie_details, video_links)
            if roku_xml:
                # Check if file exists
                file_exists = os.path.exists('RokuChannelList.xml')
                
                if file_exists:
                    # Read existing content
                    with open('RokuChannelList.xml', 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Remove closing Content tag
                    content = content.replace('</Content>', '')
                    
                    # Append new item and closing tag
                    with open('RokuChannelList.xml', 'w', encoding='utf-8') as f:
                        f.write(content + '\n' + roku_xml + '\n</Content>')
                else:
                    # Create new file with Content tags
                    with open('RokuChannelList.xml', 'w', encoding='utf-8') as f:
                        f.write('<Content>\n' + roku_xml + '\n</Content>')
                
                logging.info("Successfully saved Roku XML output to RokuChannelList.xml")
            else:
                logging.error("Failed to create Roku XML output - no working video links found")
        
        # Handle rokufailed option
        if args.rokufailed and movie_details and video_links:
            logging.info("Rokufailed option detected, testing video links...")
            working_link = None
            
            # Test each link until we find one that works
            for link in video_links:
                if try_play_in_vlc([link], auto_test=True):
                    working_link = link
                    logging.info(f"Found working link: {link}")
                    break
            
            if working_link:
                # Create filename from movie title (sanitize it to be filesystem safe)
                safe_title = "".join(c for c in movie_details['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
                filename = f"{safe_title}.txt"
                
                # Save the working link to the file
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(working_link)
                
                logging.info(f"Successfully saved working link to {filename}")
            else:
                logging.error("No working video links found to save")
        
        return result
        
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise
    
    finally:
        # Close the browser
        logging.info("Closing browser")
        driver.quit()
        logging.info("Browser closed")

if __name__ == "__main__":
    result = main()
    if result:
        print("\nMovie Details:")
        if result['movie_details']:
            for key, value in result['movie_details'].items():
                print(f"{key}: {value}")
        
        print("\nVideo Links:")
        if result['video_links']:
            for link in result['video_links']:
                print(link)
        else:
            print("No video links found")
