import requests
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm
import urllib3
import ssl
from selenium.common.exceptions import WebDriverException
import random

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_movie_links_from_page(driver, url, max_retries=3):
    for attempt in range(max_retries):
        try:
            driver.get(url)
            
            # Wait for the page to load (up to 20 seconds)
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Get the page source after JavaScript execution
            page_source = driver.page_source
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Look for ul elements with the exact class combination
            movie_list = soup.find('ul', class_=['MovieList', 'Rows'])
            
            if movie_list:
                # Find all movie links
                movie_links = movie_list.find_all('a', href=lambda x: x and x.startswith('/ver-pelicula/'))
                return movie_links
            return []
            
        except WebDriverException as e:
            if "SSL" in str(e) and attempt < max_retries - 1:
                print(f"SSL error on attempt {attempt + 1}, retrying...")
                time.sleep(random.uniform(2, 5))  # Random delay between retries
                continue
            else:
                print(f"Error processing page {url}: {e}")
                return []
        except Exception as e:
            print(f"Error processing page {url}: {e}")
            return []

def check_movielist_rows():
    base_url = "https://www.cuevana3.is"
    total_pages = 347
    all_movie_links = []
    
    # Configure Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--ignore-ssl-errors")
    chrome_options.add_argument("--allow-insecure-localhost")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    chrome_options.add_argument("--disable-site-isolation-trials")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        # Initialize the Chrome driver
        driver = webdriver.Chrome(options=chrome_options)
        
        print(f"Starting to collect links from {total_pages} pages...")
        
        # Process each page
        for page_num in tqdm(range(1, total_pages + 1), desc="Processing pages"):
            url = f"{base_url}/peliculas/publicadas/page/{page_num}"
            
            # Get links from current page with retry logic
            page_links = get_movie_links_from_page(driver, url)
            
            if not page_links:
                print(f"No links found on page {page_num}, retrying...")
                time.sleep(random.uniform(2, 5))
                page_links = get_movie_links_from_page(driver, url)
            
            # Add links to our collection
            for link in page_links:
                href = link.get('href', '')
                full_url = f"{base_url}{href}"
                title = link.get_text(strip=True)
                all_movie_links.append((title, full_url))
            
            # Save progress after each page
            with open('movie_links.txt', 'w', encoding='utf-8') as f:
                for title, url in all_movie_links:
                    f.write(f"{title} | {url}\n")
            
            # Random delay between pages to avoid detection
            time.sleep(random.uniform(1, 3))
        
        print("\nFinal Results:")
        print(f"Total movies found: {len(all_movie_links)}")
        print("All links have been saved to 'movie_links.txt'")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    check_movielist_rows()
