import time
import logging
import os
from .ai_engine import NexusPrime
from .platforms.curated_investors import CuratedInvestorsScraper
from .platforms.high_friction_investors import HighFrictionScraper
from .platforms.social_communities import SocialCommunitiesScraper
from .platforms.osint_dorker import OSINTDorker
from .llm_parser import LLMParser

log = logging.getLogger("nexus.leads")

class InvestorLeadEngine(NexusPrime):
    """
    Subclasses NexusPrime from v1014 to reuse the robust Emergency Deadend Watchdog,
    Self Healer, and Rebirth logic. 
    Overrides run_forever to run the Omni-Platform Scrapers instead of default bot logic.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.curated_scraper = CuratedInvestorsScraper(self.browser, self.memory)
        self.high_friction_scraper = HighFrictionScraper(self.browser, self.memory)
        self.social_scraper = SocialCommunitiesScraper(self.browser, self.memory)
        self.osint_dorker = OSINTDorker(self.browser, self.memory)

    def run_forever(self, hours_per_run: float = 8.0) -> dict:
        """
        Main Loop for Investor Scraping.
        """
        run_started_at = time.time()
        max_hours_raw = os.environ.get("NEXUS_MAX_RUNTIME_HOURS", "").strip()
        try:
            max_hours = float(max_hours_raw) if max_hours_raw else 4.25
        except ValueError:
            max_hours = 4.25
        effective_hours = min(hours_per_run, max_hours) if os.environ.get("GITHUB_ACTIONS") == "true" else hours_per_run
        
        log.info(f"Starting InvestorLeadEngine (v1014 base) iteration {self.iteration} | effective_hours={effective_hours}")
        
        shutdown_margin = max(900, int(os.environ.get("NEXUS_SHUTDOWN_MARGIN_SECONDS", "2100")))
        end_at = run_started_at + (effective_hours * 3600) - shutdown_margin
        
        self.browser.start()
        self.llm_parser = LLMParser(self.browser.driver)

        while time.time() < end_at:
            log.info("Starting a full Omni-Platform scraping cycle...")
            
            try:
                self.curated_scraper.scrape_and_parse(self.llm_parser)
            except Exception as e:
                log.error(f"Error in CuratedInvestorsScraper: {e}")
                
            if time.time() >= end_at: break
                
            try:
                self.high_friction_scraper.scrape_and_parse(self.llm_parser)
            except Exception as e:
                log.error(f"Error in HighFrictionScraper: {e}")
                
            if time.time() >= end_at: break
                
            try:
                self.social_scraper.scrape_and_parse(self.llm_parser)
            except Exception as e:
                log.error(f"Error in SocialCommunitiesScraper: {e}")
                
            if time.time() >= end_at: break
                
            try:
                self.osint_dorker.scrape_and_parse(self.llm_parser)
            except Exception as e:
                log.error(f"Error in OSINTDorker: {e}")
                
            log.info("Cycle complete. Sleeping for 120 seconds to stay stealthy before repeating.")
            time.sleep(120)
            
        log.info("Approaching timeout bound. Breaking loop for rebirth.")
        
        self.browser.stop()
        
        log.info("Preparing for Autonomous Rebirth...")
        rebirth_data = self.prepare_for_rebirth()
        self._complete_rebirth(rebirth_data)
        self.memory.close()
        
        return {
            "mode": "investor_leads_v1014",
            "iteration": self.iteration,
            "current_repo": self.current_repo,
            "next_repo": rebirth_data.get("new_repo_name")
        }
