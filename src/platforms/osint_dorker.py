import time
import json
import logging
import random
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

log = logging.getLogger(__name__)

class OSINTDorker:
    """
    Stealth Dorking Scraper: Extracts cached LinkedIn/Crunchbase profiles 
    from Google and DuckDuckGo using advanced search operators.
    """
    def __init__(self, browser, memory):
        self.browser = browser
        self.memory = memory
        
        self.dork_queries = [
            'site:linkedin.com/in "Web3 Investor" OR "Crypto VC" "@gmail.com" OR "@proton.me"',
            'site:linkedin.com/in "Managing Partner" "Crypto" "@gmail.com"',
            'site:crunchbase.com/person "Web3" OR "Blockchain Investor"',
        ]
        
    def _human_jitter(self):
        delay = random.uniform(4.5, 9.2)
        log.info(f"OSINT Stealth: Waiting {delay:.2f} seconds...")
        time.sleep(delay)

    def scrape_and_parse(self, llm_parser):
        for query in self.dork_queries:
            encoded_query = urllib.parse.quote_plus(query)
            target = f"https://www.google.com/search?q={encoded_query}&num=50"
            
            log.info(f"Executing OSINT Dork: {target}")
            try:
                self.browser.driver.get(target)
                self._human_jitter()
                
                # Google Pagination Loop (Max 3 pages per query to stay stealthy)
                for page_num in range(1, 4):
                    log.info(f"OSINT Dorking - Google Page {page_num}")
                    
                    try:
                        WebDriverWait(self.browser.driver, 10).until(
                            EC.presence_of_element_located((By.ID, "search"))
                        )
                    except Exception:
                        log.warning("Timeout waiting for Google search results container. Proceeding anyway.")
                    
                    # Scroll to simulate human reading SERP
                    for _ in range(3):
                        self.browser.driver.execute_script(f"window.scrollBy(0, {random.randint(200, 600)});")
                        time.sleep(1.5)
                        
                    body_text = self.browser.driver.execute_script("return document.body.innerText;")
                    if not body_text or len(body_text.strip()) < 100:
                        log.error("Empty text from Google SERP. Stopping pagination for this query.")
                        break
                        
                    chunk = body_text[:30000]
                    
                    prompt = (
                        "Extract all human profiles and leads from these Google search engine results (SERP). "
                        "Return ONLY a JSON array of objects. Do not wrap it in markdown. Each object must have these exact keys: "
                        "'name' (string), 'email' (string), 'role' (string), 'fund_name' (string), 'profile_url' (string), "
                        "'linkedin_url' (string), 'linkedin_id' (string), 'twitter_handle' (string), 'calendly_link' (string). "
                        "You MUST aggressively hunt for emails in the text snippets and extract linkedin_ids. "
                        "If a contact method is missing, leave the string empty."
                    )
                    
                    log.info("Sending OSINT SERP data to Hybrid LLM Brain...")
                    json_str = llm_parser.parse_with_llm(chunk, prompt, llm_choice="chatgpt")
                    
                    if json_str:
                        self._save_leads(json_str, target)
                        
                    # Google Next Page click logic
                    try:
                        next_btn = self.browser.driver.find_element(By.ID, "pnnext")
                        if next_btn and next_btn.is_displayed():
                            log.info("Clicking to next Google SERP page...")
                            next_btn.click()
                            time.sleep(6)
                        else:
                            break
                    except Exception:
                        log.info("No 'Next' button on Google SERP. End of results.")
                        break
                        
            except Exception as e:
                log.error(f"Failed to OSINT scrape {target}: {e}")

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
                name = lead.get("name", "")
                email = lead.get("email", "")
                
                if not name and not email:
                    continue
                    
                contact_meta = json.dumps({
                    "linkedin_url": lead.get("linkedin_url", ""),
                    "linkedin_id": lead.get("linkedin_id", ""),
                    "twitter_handle": lead.get("twitter_handle", ""),
                    "calendly_link": lead.get("calendly_link", ""),
                    "profile_url": lead.get("profile_url", "")
                })
                
                success = self.memory.add_investor_lead(
                    platform="osint_dork",
                    username=name.lower().replace(" ", "") if name else email.split('@')[0],
                    email=email,
                    name=name,
                    role=lead.get("role", "Investor"),
                    fund_name=lead.get("fund_name", ""),
                    profile_url=contact_meta
                )
                if success:
                    saved += 1
                    
            log.info(f"Successfully saved {saved} hidden OSINT leads! Duplicates safely rejected.")
            
        except json.JSONDecodeError as e:
            log.error(f"Failed to decode OSINT JSON: {e}")
