import time
import json
import logging
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

log = logging.getLogger(__name__)

class HighFrictionScraper:
    def __init__(self, browser, memory):
        self.browser = browser
        self.memory = memory
        self.targets = [
            "https://www.linkedin.com/search/results/people/?keywords=web3%20investor",
            "https://www.crunchbase.com/discover/contacts",
        ]
        
    def _human_jitter(self):
        delay = random.uniform(4.5, 9.2)
        log.info(f"Stealth Mode: Waiting for {delay:.2f} seconds...")
        time.sleep(delay)
        
    def _infinite_scroll_and_scrape(self, llm_parser, target_url, max_scrolls=5):
        """Scrolls down randomly to mimic human behavior and trigger lazy loading, scraping iteratively"""
        for scroll_cycle in range(max_scrolls):
            log.info(f"High-Friction Target {target_url} - Scroll Cycle {scroll_cycle + 1}/{max_scrolls}")
            
            # Stealth scroll
            for _ in range(random.randint(3, 5)):
                scroll_amt = random.randint(300, 800)
                self.browser.driver.execute_script(f"window.scrollBy(0, {scroll_amt});")
                self._human_jitter()
                
            # Rip the DOM at this scroll position
            body_text = self.browser.driver.execute_script("return document.body.innerText;")
            if not body_text or len(body_text.strip()) < 100:
                log.warning("Extracted empty text. Waiting longer for React/Angular to load DOM...")
                time.sleep(5)
                continue
                
            chunk = body_text[:35000]
            
            prompt = (
                "Extract all investor leads, VCs, family offices, and business owners from the following text. "
                "Return ONLY a JSON array of objects. Do not wrap it in markdown. Each object must have these exact keys: "
                "'name' (string), 'email' (string), 'role' (string), 'fund_name' (string), 'profile_url' (string), "
                "'linkedin_url' (string), 'linkedin_id' (string), 'twitter_handle' (string), 'calendly_link' (string). "
                "You MUST aggressively extract emails and linkedin_ids. "
                "If a contact method is missing, leave the string empty."
            )
            
            log.info("Sending scraped chunk to Hybrid LLM Brain for extraction...")
            json_str = llm_parser.parse_with_llm(chunk, prompt, llm_choice="chatgpt")
            
            if json_str:
                self._save_leads(json_str, target_url)

    def scrape_and_parse(self, llm_parser):
        for target in self.targets:
            log.info(f"Navigating to High-Friction target: {target}")
            try:
                self.browser.driver.get(target)
                self._human_jitter()
                
                # Wait for the main container to load
                try:
                    WebDriverWait(self.browser.driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                except Exception:
                    log.warning("Timeout waiting for body tag on high friction target. Proceeding anyway.")
                
                # Perform the infinite scrolling and scraping loop
                self._infinite_scroll_and_scrape(llm_parser, target)
                    
            except Exception as e:
                log.error(f"Failed to scrape {target}: {e}")

    def _save_leads(self, json_str: str, source_url: str):
        json_str = json_str.strip()
        if json_str.startswith("```json"): json_str = json_str[7:]
        if json_str.endswith("```"): json_str = json_str[:-3]
            
        try:
            leads = json.loads(json_str)
            if not isinstance(leads, list):
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
                    "calendly_link": lead.get("calendly_link", ""),
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
                    
            log.info(f"Successfully saved {saved} new unique leads from {platform}. Duplicates were safely rejected.")
            
        except json.JSONDecodeError as e:
            log.error(f"Failed to decode LLM JSON: {e}")
