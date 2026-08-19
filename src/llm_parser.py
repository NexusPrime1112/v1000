import json
import logging
from typing import Optional

log = logging.getLogger(__name__)

class LLMParser:
    def __init__(self, driver):
        self.driver = driver

    def parse_with_llm(self, text: str, prompt: str, llm_choice: str = "chatgpt") -> Optional[str]:
        """
        Passes the scraped text and prompt to the specified LLM.
        First tries local Ollama. If it fails or returns malformed data, 
        falls back to the specified Web UI LLM.
        """
        if not text or not text.strip():
            log.warning("Received empty text to parse. Skipping LLM call to save resources.")
            return None
            
        try:
            from .llm_client import LocalLLM
            local_brain = LocalLLM()
            log.info("Tier 1: Attempting extraction with Local Ollama...")
            # We use a strict prompt to ensure JSON
            full_prompt = f"{prompt}\n\nSTRICTLY return ONLY JSON array. Text:\n{text}"
            local_resp = local_brain.ask(full_prompt, role="chat")
            
            if local_resp:
                cleaned = local_resp.strip()
                if cleaned.startswith("```json"): cleaned = cleaned[7:]
                if cleaned.endswith("```"): cleaned = cleaned[:-3]
                try:
                    # Validate if it's actual JSON
                    json.loads(cleaned)
                    log.info("Tier 1 Success: Ollama successfully extracted JSON!")
                    return cleaned
                except Exception:
                    log.warning("Ollama returned invalid JSON. Falling back to Web UI...")
        except Exception as e:
            log.warning(f"Ollama local extraction failed: {e}. Falling back to Web UI...")
            
        # 2. Tier 2: Web UI Fallback
        log.info(f"Tier 2: Falling back to {llm_choice} via Web UI...")
        main_window = self.driver.current_window_handle
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        
        try:
            if llm_choice == "chatgpt":
                return self._ask_chatgpt(text, prompt)
            elif llm_choice == "gemini":
                return self._ask_gemini(text, prompt)
            elif llm_choice == "deepseek":
                return self._ask_deepseek(text, prompt)
            elif llm_choice == "duck.ai":
                return self._ask_duck(text, prompt)
            else:
                log.error(f"Unknown LLM choice: {llm_choice}")
                return None
        finally:
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(main_window)

    def _ask_chatgpt(self, text: str, prompt: str) -> Optional[str]:
        # Implement actual ChatGPT web scraping/injection here.
        # Returning a placeholder for safety, though the automation framework typically overrides this.
        return None
    def _ask_gemini(self, text: str, prompt: str) -> Optional[str]: return None
    def _ask_deepseek(self, text: str, prompt: str) -> Optional[str]: return None
    def _ask_duck(self, text: str, prompt: str) -> Optional[str]: return None
