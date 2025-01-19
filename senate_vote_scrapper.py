from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import pandas as pd
import logging
import time
import re
from datetime import datetime
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SenateScraper:
    def __init__(self, year="2024"):
        """Initialize the scraper with the target year."""
        self.year = year
        self.base_url = "https://www.senate.gov"
        self.setup_driver()
        
    def setup_driver(self):
        """Set up Chrome WebDriver with appropriate options."""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)
        
    def close_driver(self):
        """Safely close the WebDriver."""
        if hasattr(self, 'driver'):
            self.driver.quit()

    def show_all_votes(self):
        """Select 'All' from the dropdown to display all votes."""
        try:
            dropdown = self.wait.until(
                EC.presence_of_element_located((By.NAME, "listOfVotes_length"))
            )
            Select(dropdown).select_by_value('-1')
            time.sleep(2)  # Wait for table to update
            return True
        except TimeoutException:
            logger.error("Timeout waiting for dropdown menu")
            return False
        except Exception as e:
            logger.error(f"Error showing all votes: {e}")
            return False

    def get_vote_links(self):
        """Extract all vote links from the main table."""
        try:
            table = self.wait.until(
                EC.presence_of_element_located((By.ID, "listOfVotes"))
            )
            links = table.find_elements(By.CSS_SELECTOR, "td:first-child a")
            return [link.get_attribute('href') for link in links]
        except Exception as e:
            logger.error(f"Error getting vote links: {e}")
            return []

    def parse_vote_details(self, soup):
        """Extract vote metadata from the page, handling various vote types."""
        vote_info = {
            'date': 'N/A',
            'result': 'N/A',
            'measure_number': 'N/A',
            'measure_title': 'N/A'
        }
        
        try:
            content_divs = soup.find_all('div', class_='contenttext')
            
            # First pass: Get basic vote information
            for div in content_divs:
                if div.find('b'):
                    b_text = div.find('b').text.strip()
                    if 'Vote Date:' in b_text:
                        vote_info['date'] = div.text.split('Vote Date:')[1].strip()
                    elif 'Vote Result:' in b_text:
                        vote_info['result'] = div.text.split('Vote Result:')[1].strip()
            
            # Second pass: Get measure number and title based on type
            for div in content_divs:
                if not div.find('b'):
                    continue
                    
                b_text = div.find('b').text.strip()
                
                # Handle Amendment
                if 'Amendment Number:' in b_text:
                    # Get amendment number
                    amdt_link = div.find('a')
                    if amdt_link:
                        vote_info['measure_number'] = amdt_link.text.strip()
                    else:
                        # Try to extract from text if no link
                        amdt_match = re.search(r'(?:Amdt\.|Amendment)\s*(?:No\.)?\s*(\d+)', div.text)
                        if amdt_match:
                            vote_info['measure_number'] = f"S.Amdt. {amdt_match.group(1)}"
                    
                    # Look for Statement of Purpose for amendment title
                    for purpose_div in content_divs:
                        if purpose_div.find('b') and 'Statement of Purpose:' in purpose_div.find('b').text:
                            vote_info['measure_title'] = purpose_div.text.split('Statement of Purpose:')[1].strip()
                            break
                
                # Handle Measure
                elif 'Measure Number:' in b_text:
                    measure_link = div.find('a')
                    if measure_link:
                        vote_info['measure_number'] = measure_link.text.strip()
                    
                    # Look for Measure Title
                    for title_div in content_divs:
                        if title_div.find('b') and 'Measure Title:' in title_div.find('b').text:
                            vote_info['measure_title'] = title_div.text.split('Measure Title:')[1].strip()
                            break
                
                # Handle Nomination
                elif 'Nomination:' in b_text or 'Nominee:' in b_text:
                    nomination_text = div.text.split(':', 1)[1].strip()
                    vote_info['measure_number'] = 'NOMINATION'
                    vote_info['measure_title'] = nomination_text
                
                # Handle Question (when no specific measure/amendment/nomination)
                elif 'Question:' in b_text:
                    question_text = div.text.split('Question:', 1)[1].strip()
                    if vote_info['measure_number'] == 'N/A':
                        vote_info['measure_number'] = 'QUESTION'
                        vote_info['measure_title'] = question_text
            
            # Clean up the results
            for key in vote_info:
                if vote_info[key] != 'N/A':
                    # Remove extra whitespace and normalize
                    vote_info[key] = ' '.join(vote_info[key].split())
                    # Remove trailing punctuation
                    vote_info[key] = vote_info[key].rstrip('.')
                    # Remove extra parentheses if they wrap the entire string
                    if vote_info[key].startswith('(') and vote_info[key].endswith(')'):
                        vote_info[key] = vote_info[key][1:-1].strip()
            
            return vote_info
            
        except Exception as e:
            logger.error(f"Error parsing vote details: {e}")
            return vote_info

    def parse_voting_records(self, soup):
        """Parse individual senator voting records."""
        try:
            voting_records = []
            voting_section = soup.find('div', class_='newspaperDisplay_3column')
            
            if not voting_section:
                return None
                
            content = voting_section.get_text()
            lines = content.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Pattern: Name (Party-State), Vote
                match = re.match(r'([^(]+?)\s*\(([DRI])-([A-Z]{2})\),\s*(Yea|Nay|Not Voting|Present)$', line)
                if match:
                    voting_records.append({
                        'Senator': match.group(1).strip(),
                        'Party': match.group(2).strip(),
                        'State': match.group(3).strip(),
                        'Vote': match.group(4).strip()
                    })
            
            return voting_records
            
        except Exception as e:
            logger.error(f"Error parsing voting records: {e}")
            return None

    def create_vote_dataset(self, voting_records, vote_info):
        """Create a structured dataset combining metadata and voting records."""
        try:
            if not voting_records:
                return None
            
            # Create metadata row
            metadata_row = {
                'Section': 'Metadata',
                'Date': vote_info['date'],
                'Result': vote_info['result'],
                'Measure_Number': vote_info['measure_number'],
                'Measure_Title': vote_info['measure_title'],
                'Senator': '',
                'Party': '',
                'State': '',
                'Vote': ''
            }
            
            # Convert voting records to DataFrame
            vote_rows = pd.DataFrame(voting_records)
            vote_rows.insert(0, 'Section', 'Vote')
            
            # Add empty columns for metadata
            vote_rows['Date'] = ''
            vote_rows['Result'] = ''
            vote_rows['Measure_Number'] = ''
            vote_rows['Measure_Title'] = ''
            
            # Combine metadata and votes
            metadata_df = pd.DataFrame([metadata_row])
            combined_df = pd.concat([metadata_df, vote_rows], ignore_index=True)
            
            # Ensure consistent column order
            column_order = [
                'Section', 'Date', 'Result', 'Measure_Number', 'Measure_Title',
                'Senator', 'Party', 'State', 'Vote'
            ]
            return combined_df[column_order]
            
        except Exception as e:
            logger.error(f"Error creating vote dataset: {e}")
            return None

    def scrape_votes(self, output_dir='senate_votes'):
        """Main function to scrape all Senate votes for the specified year."""
        try:
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Load main page for the specified year
            congress_num = "118"  # Update this based on the year if needed
            session_num = "2" if self.year == "2024" else "1"  # 2nd session for 2024
            url = f"{self.base_url}/legislative/LIS/roll_call_lists/vote_menu_{congress_num}_{session_num}.htm"
            
            logger.info(f"Accessing main vote page: {url}")
            self.driver.get(url)
            
            # Show all votes
            if not self.show_all_votes():
                return None
            
            # Get all vote links
            vote_links = self.get_vote_links()
            logger.info(f"Found {len(vote_links)} votes to process")
            
            all_votes_data = []
            
            # Process each vote
            for link in vote_links:
                try:
                    logger.info(f"Processing vote: {link}")
                    self.driver.get(link)
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    
                    # Get vote details and records
                    vote_info = self.parse_vote_details(soup)
                    voting_records = self.parse_voting_records(soup)
                    
                    if voting_records:
                        # Create dataset for this vote
                        vote_df = self.create_vote_dataset(voting_records, vote_info)
                        if vote_df is not None:
                            all_votes_data.append(vote_df)
                            logger.info(f"Successfully processed vote dated {vote_info['date']}")
                    
                    time.sleep(1)  # Be nice to the server
                    
                except Exception as e:
                    logger.error(f"Error processing vote {link}: {e}")
                    continue
            
            if all_votes_data:
                # Combine all votes into one DataFrame
                combined_df = pd.concat(all_votes_data, ignore_index=True)
                
                # Save to both CSV and Excel
                csv_path = os.path.join(output_dir, f'senate_votes_{self.year}.csv')
                #excel_path = os.path.join(output_dir, f'senate_votes_{self.year}.xlsx')
                
                combined_df.to_csv(csv_path, index=False)
                #combined_df.to_excel(excel_path, index=False)
                
                logger.info(f"Saved {len(all_votes_data)} votes to {csv_path}")
                return combined_df
            
            return None
            
        except Exception as e:
            logger.error(f"Error scraping votes: {e}")
            return None
        finally:
            self.close_driver()

if __name__ == "__main__":
    try:
        # Create scraper for 2024
        scraper = SenateScraper(year="2024")
        
        # Scrape votes
        df = scraper.scrape_votes()
        
        if df is not None:
            # Display summary statistics
            print("\nDataset Summary:")
            print(f"Total votes processed: {len(df[df['Section'] == 'Metadata'])}")
            print(f"Total voting records: {len(df[df['Section'] == 'Vote'])}")
            print("\nVotes by party:")
            print(df[df['Section'] == 'Vote']['Party'].value_counts())
            print("\nVotes by result:")
            print(df[df['Section'] == 'Metadata']['Result'].value_counts())
        else:
            print("No data was collected")
            
    except Exception as e:
        logger.error(f"Program failed: {e}")