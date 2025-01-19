from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import re
import logging
from datetime import datetime
import os
import multiprocessing
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial
import queue
import threading
import time
from senate_vote_scrapper import SenateScraper

# Configure logging with thread safety
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(processName)s - %(threadName)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_driver():
    """Create a new browser instance with appropriate options."""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    return webdriver.Chrome(options=options)

def scrape_single_vote(vote_url, year_info):
    """Scrape a single vote page."""
    driver = setup_driver()
    try:
        driver.get(vote_url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Parse vote details and records
        vote_info = SenateScraper.parse_vote_details(None, soup)
        voting_records = SenateScraper.parse_voting_records(None, soup)
        
        if voting_records:
            df = SenateScraper.create_vote_dataset(None, voting_records, vote_info)
            return df
        return None
    except Exception as e:
        logger.error(f"Error scraping vote {vote_url}: {e}")
        return None
    finally:
        driver.quit()

def get_vote_links(driver, url):
    """Get all vote links from a year page."""
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        
        # Wait for and select 'All' from dropdown
        dropdown = wait.until(
            EC.presence_of_element_located((By.NAME, "listOfVotes_length"))
        )
        Select(dropdown).select_by_value('-1')
        time.sleep(2)  # Wait for table update
        
        # Get all vote links
        table = wait.until(EC.presence_of_element_located((By.ID, "listOfVotes")))
        links = table.find_elements(By.CSS_SELECTOR, "td:first-child a")
        return [link.get_attribute('href') for link in links]
    except Exception as e:
        logger.error(f"Error getting vote links from {url}: {e}")
        return []

class ParallelSenateScraper:
    def __init__(self, max_workers=None):
        """Initialize the parallel scraper with configurable workers."""
        self.base_url = "https://www.senate.gov"
        self.max_workers = max_workers or multiprocessing.cpu_count()
        
    def get_year_links(self):
        """Get all available year links from the main votes page."""
        driver = setup_driver()
        try:
            driver.get(f"{self.base_url}/legislative/votes_new.htm")
            select_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "menu"))
            )
            
            year_links = {}
            options = select_element.find_elements(By.TAG_NAME, "option")[1:]  # Skip first option
            
            for option in options:
                value = option.get_attribute("value")
                text = option.text
                match = re.search(r'(\d{4})\s+\((\d+)(?:st|nd|rd|th),\s+(\d)(?:st|nd|rd|th)\)', text)
                
                if match and value:
                    year, congress, session = match.groups()
                    if not value.startswith('http'):
                        value = f"{self.base_url}/legislative/LIS/roll_call_lists/vote_menu_{congress}_{session}.htm"
                    
                    year_links[year] = {
                        'url': value,
                        'congress': congress,
                        'session': session
                    }
            
            return year_links
        finally:
            driver.quit()

    def process_year(self, year, year_info, output_dir):
        """Process all votes for a specific year."""
        driver = setup_driver()
        try:
            # Create year directory
            year_dir = os.path.join(output_dir, year)
            os.makedirs(year_dir, exist_ok=True)
            
            # Get vote links for the year
            vote_links = get_vote_links(driver, year_info['url'])
            logger.info(f"Found {len(vote_links)} votes for year {year}")
            
            if not vote_links:
                return None
            
            # Process votes in parallel using ThreadPoolExecutor
            all_votes_data = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_url = {
                    executor.submit(scrape_single_vote, url, year_info): url 
                    for url in vote_links
                }
                
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        df = future.result()
                        if df is not None:
                            all_votes_data.append(df)
                            logger.info(f"Successfully processed vote from {url}")
                    except Exception as e:
                        logger.error(f"Error processing {url}: {e}")
            
            if all_votes_data:
                # Combine all votes and save
                combined_df = pd.concat(all_votes_data, ignore_index=True)
                
                # Save to both CSV and Excel
                csv_path = os.path.join(year_dir, f'senate_votes_{year}')
                #excel_path = os.path.join(year_dir, f'senate_votes_{year}.xlsx')
                
                combined_df.to_csv(csv_path, index=False)
                #combined_df.to_excel(excel_path, index=False)
                
                logger.info(f"Saved {len(all_votes_data)} votes for year {year}")
                return combined_df
            
            return None
            
        finally:
            driver.quit()

    def scrape_years(self, start_year, end_year, output_dir="senate_votes"):
        """Scrape multiple years in parallel."""
        try:
            # Get available years
            year_links = self.get_year_links()
            if not year_links:
                logger.error("Failed to get year links")
                return
            
            # Filter years within range
            years_to_scrape = {
                year: info for year, info in year_links.items()
                if str(start_year) <= year <= str(end_year)
            }
            
            if not years_to_scrape:
                logger.error(f"No valid years found between {start_year} and {end_year}")
                return
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Process years in parallel using ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=min(len(years_to_scrape), self.max_workers)) as executor:
                future_to_year = {
                    executor.submit(self.process_year, year, info, output_dir): year
                    for year, info in years_to_scrape.items()
                }
                
                for future in concurrent.futures.as_completed(future_to_year):
                    year = future_to_year[future]
                    try:
                        df = future.result()
                        if df is not None:
                            vote_count = len(df[df['Section'] == 'Metadata'])
                            record_count = len(df[df['Section'] == 'Vote'])
                            logger.info(f"\nYear {year} Summary:")
                            logger.info(f"  Total votes: {vote_count}")
                            logger.info(f"  Total voting records: {record_count}")
                    except Exception as e:
                        logger.error(f"Error processing year {year}: {e}")
            
        except Exception as e:
            logger.error(f"Error in scrape_years: {e}")

def main():
    try:
        # Create scraper with default number of workers (CPU count)
        scraper = ParallelSenateScraper()
        
        # Or specify number of workers
        scraper = ParallelSenateScraper(max_workers=4)
        
        # Scrape votes for multiple years
        scraper.scrape_years(2015, 2025)
        
    except Exception as e:
        logger.error(f"Main program failed: {e}")

if __name__ == "__main__":
    main()