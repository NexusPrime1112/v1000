import time
import json
import logging
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

log = logging.getLogger(__name__)

class CuratedInvestorsScraper:
    def __init__(self, browser, memory):
        self.browser = browser
        self.memory = memory
        self.targets = [
            "https://www.seedtable.com/investors",
            "https://rootdata.com/Investors",
            "https://cryptorank.io/funds"
        ]

    def scrape_and_parse(self, llm_parser):
        for target in self.targets:
            log.info(f"Navigating to curated VC list: {target}")
            try:
                self.browser.driver.get(target)
                
                # Advanced Waiting: Let JS frameworks load the actual lists
                log.info("Waiting for JavaScript lists to fully render...")
                time.sleep(7)
                
                # We will handle up to 5 pages per target to respect the 5-hour boundary
                for page_num in range(1, 6):
                    log.info(f"Scraping {target} - Page {page_num}")
                    
                    # Ensure we have actual body content
                    WebDriverWait(self.browser.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    
                    body_text = self.browser.driver.execute_script("return document.body.innerText;")
                    
                    if not body_text or len(body_text.strip()) < 100:
                        log.warning(f"Extracted empty or tiny text from {target} page {page_num}. Trying to scroll to trigger lazy loading.")
                        self.browser.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(4)
                        body_text = self.browser.driver.execute_script("return document.body.innerText;")
                        
                    chunk = body_text[:35000] # Fit into context window
                    
                    if not chunk or len(chunk.strip()) < 100:
                        log.error(f"Still no significant text on {target} page {page_num}. Breaking pagination loop.")
                        break
                        
                    prompt = (
                        "Extract all investor leads, VCs, and business owners from the following text. "
                        "Return ONLY a JSON array of objects. Each object must have these exact keys: "
                        "'name' (string), 'email' (string), 'role' (string), 'fund_name' (string), 'profile_url' (string), "
                        "'linkedin_url' (string), 'linkedin_id' (string), 'twitter_handle' (string). "
                        "You MUST aggressively extract emails and linkedin_ids. If a field is missing, leave the string empty."
                    )
                    
                    log.info("Sending scraped data to LLM Brain for extraction...")
                    json_str = llm_parser.parse_with_llm(chunk, prompt, llm_choice="chatgpt")
                    
                    if json_str:
                        self._save_leads(json_str, target)
                        
                    # Attempt Pagination Click (Generic Next Button Strategy)
                    try:
                        next_button = self.browser.driver.find_element(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')] | //a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]")
                        if next_button and next_button.is_displayed():
                            log.info("Found Next Page button. Clicking...")
                            next_button.click()
                            time.sleep(5) # Wait for page load
                        else:
                            break # No visible next button
                    except Exception:
                        log.info("No more pages found or generic pagination failed.")
                        break # Break pagination loop if we can't find 'Next'
                        
            except Exception as e:
                log.error(f"Failed to scrape {target}: {e}")

    def _save_leads(self, json_str: str, source_url: str):
        json_str = json_str.strip()
        if json_str.startswith("```json"): json_str = json_str[7:]
        if json_str.endswith("```"): json_str = json_str[:-3]
            
        try:
            leads = json.loads(json_str)
            if not isinstance(leads, list):
                log.warning("LLM did not return a JSON array.")
                return
                
            saved = 0
            for lead in leads:
                email = lead.get("email", "")
                name = lead.get("name", "")
                
                if not email and not name:
                    continue
                    
                platform = source_url.split("/")[2].replace("www.", "")
                
                contact_meta = json.dumps({
                    "linkedin_url": lead.get("linkedin_url", ""),
                    "linkedin_id": lead.get("linkedin_id", ""),
                    "twitter_handle": lead.get("twitter_handle", ""),
                    "profile_url": lead.get("profile_url", "")
                })
                
                success = self.memory.add_investor_lead(
                    platform=platform,
                    username=name.lower().replace(" ", ""),
                    email=email,
                    name=name,
                    role=lead.get("role", "Investor"),
                    fund_name=lead.get("fund_name", ""),
                    profile_url=contact_meta
                )
                if success:
                    saved += 1
                    
            log.info(f"Successfully saved {saved} new unique leads from {platform}! Duplicates were safely rejected.")
            
        except json.JSONDecodeError as e:
            log.error(f"Failed to decode LLM JSON: {e}\nRaw output: {json_str}")
