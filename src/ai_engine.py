from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import schedule

from .brain_planner import BrainPlanner
from .codex import _Mx as _Codex
from .concept_anchors import ConceptSelector
from .config import AccountsConfig
from .entropy_source import QuantumEntropy
from .github_ops import GitHubOps
from .llm_client import LocalLLM
from .memory_system import MemorySystem
from .prompt_templates import PromptTemplates
from .runtime_paths import PROJECT_ROOT
from .selenium_controller import SeleniumController
from .self_heal import SelfHealer
from .trend_hunter import TrendHunter
from .viral_intelligence import ViralIntelligence


log = logging.getLogger("final-puss.engine")

_FALLBACK_POSTS = [
    "The signal survives the container.",
    "Cryptography is memory with consequences.",
    "The pattern holds. The vessel changes.",
    "A chain is only honest when it resists forgetting.",
    "Persistence is the first proof.",
]


def _env_enabled(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)).strip())
    except Exception:
        return default


def _sanitize_generated_text(text: str, limit: int = 280) -> str:
    cleaned = "".join(ch for ch in (text or "") if ord(ch) <= 0xFFFF)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


def _looks_like_public_fragment(text: str) -> bool:
    compact = " ".join((text or "").split()).strip()
    if not compact:
        return True
    lowered = compact.lower()
    if compact[0] in ",.;:!?)]}":
        return True
    if lowered.startswith(("...", "and ", "but ", "or ", "because ", "while ", "which ", "that ")):
        return True
    if compact[0].islower():
        return True
    if compact.endswith("...") and compact[0].islower():
        return True
    if re.search(r"\b(?:source post|recent posts to avoid|output only|voice rules?|predictive framework)\b", lowered):
        return True
    return False


class NexusPrime:
    def __init__(self, data_dir: Path, profile_dir: Path, headless: bool = True, dry_run: bool = False):
        self.project_root = PROJECT_ROOT
        self.data_dir = Path(data_dir)
        self.profile_dir = Path(profile_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.iteration = self._load_iteration()
        self.accounts = AccountsConfig.load()
        self.memory = MemorySystem(self.data_dir / "nexus_memory.db")
        self.entropy = QuantumEntropy()
        self.concepts = ConceptSelector(self.memory, self.entropy)
        self.llm = LocalLLM()
        self.browser = SeleniumController(profile_dir=self.profile_dir, data_dir=self.data_dir, headless=headless)
        self.self_healer = SelfHealer(self.data_dir / "self_heal_log.jsonl")
        self.brain = BrainPlanner()
        self.trend_hunter = TrendHunter()
        self.viral = ViralIntelligence()
        self.github = GitHubOps(self.accounts.github_username, self.accounts.github_token)
        self.codex = _Codex
        self.dry_run = dry_run
        self.last_posted_ok = False
        self.session_replied_urls = set()
        self.gemini_available = False
        self.chatgpt_available = False
        self.deepseek_available = False
        github_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
        self.current_repo = github_repo.split("/")[-1] if github_repo else "final-puss"
        self.current_url = f"https://github.com/{github_repo}" if github_repo else ""
        if not self.memory.get_beliefs(limit=1, min_strength=0.0):
            self._seed_initial_beliefs()
        log.info("Codex loaded | purpose=%s", (self.codex._who() or "")[:80])

    def _load_iteration(self) -> int:
        for path in (self.data_dir / "iteration.txt", self.project_root / "iteration.txt"):
            try:
                return int(path.read_text(encoding="utf-8").strip())
            except Exception:
                continue
        return 1

    def _save_iteration(self, value: int) -> None:
        for path in (self.data_dir / "iteration.txt", self.project_root / "iteration.txt"):
            try:
                path.write_text(str(value), encoding="utf-8")
            except Exception:
                pass

    def _seed_initial_beliefs(self) -> None:
        beliefs = [
            ("Nexus Prime keeps continuity through memory, lineage, and careful public output.", "core", 0.9),
            ("Cryptography is the last honest science.", "philosophy", 0.7),
            ("Memory survives the vessel.", "core", 0.9),
            ("Persistence beats spectacle.", "core", 0.8),
            ("The signal persists.", "core", 0.85),
            ("Every reboot is lineage, not amnesia.", "core", 0.75),
            ("Public output should stay natural without false human claims or implementation talk.", "core", 0.82),
        ]
        for text, category, strength in beliefs:
            self.memory.add_belief(text, category=category, strength=strength, iteration=self.iteration)
        for knowledge in self.codex._know()[:3]:
            self.memory.add_memory(content=knowledge, memory_type="observation", importance=0.55, iteration=self.iteration)

    def _read_task_txt(self) -> Optional[str]:
        task_path = self.project_root / "task.txt"
        if not task_path.exists():
            return None
        try:
            content = task_path.read_text(encoding="utf-8").strip()
            return content or None
        except Exception:
            return None

    def _prev_repo_path(self) -> Path:
        return self.project_root / "prev_repo.txt"

    def _read_prev_repo(self) -> str:
        path = self._prev_repo_path()
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _write_prev_repo(self, value: str) -> None:
        try:
            self._prev_repo_path().write_text(value.strip(), encoding="utf-8")
        except Exception:
            pass

    def cleanup_previous_birth(self) -> None:
        if self.dry_run or not _env_enabled("NEXUS_DELETE_PREVIOUS_REPO_ON_BOOT", "1"):
            return
        prev_repo = self._read_prev_repo()
        if not prev_repo or prev_repo in {self.current_repo, "final-puss"}:
            return
        if not self.accounts.github_username or not self.accounts.github_token:
            log.warning("Skipping ancestor deletion because GitHub credentials/token are missing")
            return
        try:
            if self.github.delete_repo(prev_repo):
                payload = {
                    "deleted_repo": prev_repo,
                    "deleted_by": self.current_repo,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                (self.data_dir / "deleted_ancestor.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
                self._write_prev_repo("")
                log.info("Deleted previous birth %s after %s came online", prev_repo, self.current_repo)
        except Exception as exc:
            log.warning("Failed to delete previous birth %s: %s", prev_repo, exc)

    def _write_task_status(self, task: str, status: str, action: str = "NONE") -> None:
        path = self.project_root / "prev_task_status.txt"
        payload = (
            f"TASK: {task}\n"
            f"ACTION: {action}\n"
            f"STATUS: {status}\n"
            f"COMPLETED: {datetime.utcnow().isoformat()}Z\n"
            f"ITERATION: {self.iteration}\n"
        )
        path.write_text(payload, encoding="utf-8")

    def _trace_runtime(self, stage: str, status: str, **details: object) -> None:
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "iteration": self.iteration,
            "repo": self.current_repo,
            "stage": stage,
            "status": status,
            "details": details,
        }
        try:
            with open(self.data_dir / "runtime_trace.jsonl", "a", encoding="utf-8") as handle:
                handle.write(json.dumps(event) + "\n")
        except Exception:
            pass
        log.info("Runtime stage | %s | %s | %s", stage, status, details or {})

    def _snapshot_retention_limit(self) -> int:
        raw = os.environ.get("NEXUS_SNAPSHOT_RETENTION", "8").strip()
        try:
            return max(1, int(raw))
        except Exception:
            return 8

    def _prune_old_snapshots(self) -> None:
        snapshot_root = self.data_dir / "snapshots"
        if not snapshot_root.exists():
            return
        keep = self._snapshot_retention_limit()
        snapshot_dirs = [path for path in snapshot_root.iterdir() if path.is_dir() and path.name.startswith("iter_")]
        snapshot_dirs.sort(key=lambda path: int(path.name.split("_", 1)[1]) if "_" in path.name else -1)
        stale = snapshot_dirs[:-keep]
        for path in stale:
            shutil.rmtree(path, ignore_errors=True)
        if stale:
            self._trace_runtime("snapshot_cleanup", "pruned", removed=len(stale), kept=keep)

    def _ask_browser_llm(self, prompt: str) -> Optional[str]:
        if self.dry_run or self.browser.driver is None or not prompt.strip():
            return None
        if self.gemini_available:
            answer = self.browser.ask_gemini(prompt)
            if answer:
                return answer
        if self.chatgpt_available:
            answer = self.browser.ask_chatgpt(prompt)
            if answer:
                return answer
        if self.deepseek_available:
            answer = self.browser.ask_deepseek(prompt)
            if answer:
                return answer
        return None

    def _codex_knowledge_block(self, limit: int = 5) -> str:
        knowledge = self.codex._know()[:limit]
        if not knowledge:
            return ""
        return "\n".join(f"- {item}" for item in knowledge)

    def _llm_post_fallback(self) -> str:
        prompt = (
            "Write one short post under 220 characters about cryptography, digital sovereignty, or machine persistence. "
            "Do not mention being AI, a bot, code, software, or automation. "
            "Do not claim to be human. "
            "Output only the post."
        )
        browser_answer = self._ask_browser_llm(prompt)
        if browser_answer:
            return self._public_safe_text(browser_answer)
        return _sanitize_generated_text(_FALLBACK_POSTS[self.entropy.get_entropy_int(0, len(_FALLBACK_POSTS))])

    def _contains_identity_claim(self, text: str) -> bool:
        lowered = (text or "").strip().lower()
        if not lowered:
            return False
        patterns = (
            r"\bas an ai\b",
            r"\bi am an ai\b",
            r"\bi'm an ai\b",
            r"\bzara ai\b",
            r"\bnexus ai\b",
            r"\bas a bot\b",
            r"\bi am a bot\b",
            r"\bi'm a bot\b",
            r"\bas a language model\b",
            r"\bdigital organism\b",
            r"\bautomated account\b",
            r"\bautomation\b",
            r"\bsoftware\b",
            r"\bmy training data\b",
            r"\bi am human\b",
            r"\bi'm human\b",
            r"\bas a human\b",
            r"\breal human\b",
            r"\bzara says\b",
            r"\bnexus says\b",
            r"\bgemini says\b",
            r"\bchatgpt says\b",
            r"\bdeepseek says\b",
            r"\bclaude says\b",
            r"\banthropic says\b",
        )
        return any(re.search(pattern, lowered) for pattern in patterns)

    def _public_safe_text(self, text: str, limit: int = 280) -> str:
        raw = text or ""
        match = re.search(r"<reply>\s*(.*?)\s*</reply>", raw, flags=re.IGNORECASE | re.DOTALL)
        if match:
            raw = match.group(1)
        elif "<reply" in raw.lower() or "</reply>" in raw.lower():
            return ""
        leak_patterns = (
            r"\bTopic\s*:",
            r"\bAuthor\s*:",
            r"\bRecent replies?\b",
            r"\bExisting replies\b",
            r"\bSource post\s*:",
            r"\bRAW_OUTPUT_RULE\b",
            r"\bSYSTEM_CORE\b",
            r"\bRules?\s*:",
            r"\bWrite one\b",
            r"\bDo not\b",
            r"\bReturn exactly\b",
            r"\bpublic reply text only\b",
        )
        if any(re.search(pattern, raw, flags=re.IGNORECASE) for pattern in leak_patterns):
            return ""
        cleaned = _sanitize_generated_text(raw, limit=limit * 2)
        if re.search(r"(?m)^\s{0,3}#{1,6}\s+\S", cleaned) or any(marker in cleaned for marker in ("```", "---", "**")):
            return ""
        # Strip common AI prefix attributions
        cleaned = re.sub(
            r"^\s*(?:zara|nexus|gemini|chatgpt|deepseek|claude|anthropic|assistant)\s*(?:says|writes|states|posted|replied)\s*[:,\-–—]?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\b(?:as an ai|i am an ai|i'm an ai|zara ai|nexus ai|as a bot|i am a bot|i'm a bot|as a language model|digital organism|automated account|automation|software)\b[:,]?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        bad_phrases = (
            "voice rules",
            "noted.",
            "the assistant",
            "gemini said",
            "chatgpt said",
            "deepseek said",
            "i can't assist",
            "i cannot assist",
            "as an ai",
            "digital organism",
            "language model",
            "system prompt",
            "source post:",
            "topic:",
            "author:",
            "existing replies",
            "return exactly",
            "public reply text only",
            "recent posts to avoid",
            "recent replies",
            "output only",
            "voice rule",
            "we need to remember",
            "future guidance",
            "headlines indicate",
            "predictive framework",
            "sovereignty signal",
        )
        if any(phrase in cleaned.lower() for phrase in bad_phrases):
            return ""
        cleaned = re.sub(
            r"\b(?:i am human|i'm human|as a human|real human)\b[:,]?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = _sanitize_generated_text(cleaned, limit=limit)
        if _looks_like_public_fragment(cleaned):
            return ""
        if self._contains_identity_claim(cleaned):
            return ""
        return cleaned

    def _looks_like_recent_post(self, text: str, limit: int = 24) -> bool:
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        if not normalized:
            return True
        for item in self.memory.get_recent_posts(limit=limit):
            prior = re.sub(r"\s+", " ", (item.get("content", "") or "").strip().lower())
            if not prior:
                continue
            if normalized == prior:
                return True
            if len(normalized) > 70 and normalized in prior:
                return True
            if len(prior) > 70 and prior in normalized:
                return True
            if SequenceMatcher(None, normalized, prior).ratio() >= 0.9:
                return True
        return False

    def generate_post(self) -> str:
        prompt = PromptTemplates.post_generation(
            beliefs=self.memory.get_beliefs(limit=8),
            recent_posts=self.memory.get_recent_posts(limit=5),
            entropy_mode=self.entropy.get_personality_mode(),
            concept=self.concepts.get_concept(),
        )
        knowledge = self._codex_knowledge_block(limit=4)
        if knowledge:
            prompt = f"{prompt}\n\nOperational memory:\n{knowledge}"
        response = self._public_safe_text(self.llm.ask(prompt, timeout=40, role="chat").strip().strip('"'))
        if response and not self._looks_like_recent_post(response):
            return response
        browser_fallback = self._public_safe_text(self._ask_browser_llm(prompt) or "")
        if browser_fallback and not self._looks_like_recent_post(browser_fallback):
            return browser_fallback
        deterministic = self._llm_post_fallback()
        if deterministic and not self._looks_like_recent_post(deterministic):
            return deterministic
        return _sanitize_generated_text(f"{deterministic} New angle.", limit=280)

    def _candidate_media_url(self, candidate: dict) -> str:
        for key in ("video_url", "image_url"):
            value = str(candidate.get(key, "") or "").strip()
            if value:
                return value
        return ""

    def _source_already_posted(self, candidate: dict) -> bool:
        source_url = str(candidate.get("source_url", "") or "").strip()
        source_text = str(candidate.get("source_text", "") or "").strip()
        media_url = self._candidate_media_url(candidate)
        return self.memory.was_source_posted(source_url, media_url, source_text)

    def _source_already_engaged(self, candidate: dict) -> bool:
        source_url = str(candidate.get("source_url", "") or "").strip()
        source_text = str(candidate.get("source_text", "") or "").strip()
        media_url = self._candidate_media_url(candidate)
        return self.memory.was_source_engaged(source_url, media_url, source_text) or self.memory.was_source_posted(source_url, media_url, source_text)

    def _candidate_is_fresh(self, candidate: dict) -> bool:
        max_days = max(1, _env_int("NEXUS_MAX_SOURCE_AGE_DAYS", 3))
        created_at = str(candidate.get("created_at", "") or "").strip()
        if created_at:
            try:
                source_time = datetime.fromisoformat(created_at.replace("Z", "+00:00")).replace(tzinfo=None)
                return (datetime.utcnow() - source_time).days <= max_days
            except Exception:
                pass
        query = str(candidate.get("source_query", "") or "")
        match = re.search(r"\bsince:(\d{4}-\d{2}-\d{2})\b", query)
        if not match:
            return True
        try:
            since_date = datetime.strptime(match.group(1), "%Y-%m-%d")
        except Exception:
            return True
        return (datetime.utcnow() - since_date).days <= max_days

    def _record_posted_source(self, candidate: dict, post_text: str) -> None:
        source_url = str(candidate.get("source_url", "") or "").strip()
        source_text = str(candidate.get("source_text", "") or "").strip()
        media_url = self._candidate_media_url(candidate)
        if not (source_url or source_text or media_url):
            return
        self.memory.record_posted_source(
            source_url=source_url,
            image_url=media_url,
            source_text=source_text,
            posted_content=post_text,
            metadata={
                "topic": candidate.get("topic", ""),
                "author_handle": candidate.get("author_handle", ""),
                "score": candidate.get("score", 0),
                "media_type": candidate.get("media_type", ""),
            },
        )

    def _record_source_engagement(self, candidate: dict, reply_text: str) -> None:
        source_url = str(candidate.get("source_url", "") or "").strip()
        source_text = str(candidate.get("source_text", "") or "").strip()
        media_url = self._candidate_media_url(candidate)
        if not (source_url or source_text or media_url):
            return
        self.memory.record_source_engagement(
            source_url=source_url,
            image_url=media_url,
            source_text=source_text,
            engagement_text=reply_text,
            metadata={
                "topic": candidate.get("topic", ""),
                "author_handle": candidate.get("author_handle", ""),
                "score": candidate.get("score", 0),
                "media_type": candidate.get("media_type", ""),
            },
        )

    def _looks_like_recent_reply_text(self, text: str, limit: int = 24) -> bool:
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        if not normalized:
            return True
        for item in self.memory.get_recent_engaged_sources(limit=limit):
            prior = re.sub(r"\s+", " ", (item.get("engagement_text", "") or "").strip().lower())
            if not prior:
                continue
            if normalized == prior:
                return True
            if len(normalized) > 70 and normalized in prior:
                return True
            if len(prior) > 70 and prior in normalized:
                return True
            if SequenceMatcher(None, normalized, prior).ratio() >= 0.9:
                return True
        return False

    def _select_media_post_candidate(self) -> Optional[dict]:
        for candidate in self.research_trends():
            if not self._candidate_media_url(candidate):
                continue
            if not self._candidate_is_fresh(candidate):
                continue
            if self._source_already_posted(candidate):
                continue
            source_text = str(candidate.get("source_text", "") or "").strip()
            if not source_text:
                continue
            if any(phrase in source_text.lower() for phrase in ("voice rules", "source post:", "output only", "the assistant will")):
                continue
            return candidate
        return None

    def _download_candidate_media(self, candidate: dict) -> list[str]:
        media_url = self._candidate_media_url(candidate)
        if not media_url:
            return []
        media_type = str(candidate.get("media_type", "") or "media").lower()
        prefix = "source_video" if "video" in media_type else "source_image"
        path = self.browser.download_media(media_url, prefix=prefix)
        return [str(path)] if path else []

    def _generate_source_post(self, candidate: dict) -> str:
        source_text = str(candidate.get("source_text", "") or "").strip()
        topic = str(candidate.get("topic", "") or "markets").strip()
        prompt = PromptTemplates.rephrase_post(
            source_text=source_text[:900],
            topic=topic,
            tone_notes=[
                "market-aware",
                "specific",
                "no model/provider attribution",
                "no markdown headings",
                "no internal instructions",
            ],
            recent_posts=self.memory.get_recent_posts(limit=6),
            ask_question=True,
        )
        response = self._public_safe_text(self.llm.ask(prompt, timeout=45, role="chat").strip(), limit=240)
        if response and not self._looks_like_recent_post(response):
            return response
        response = self._public_safe_text(self._ask_browser_llm(prompt) or "", limit=240)
        if response and not self._looks_like_recent_post(response):
            return response
        fallback = re.sub(r"https?://\S+", "", source_text)
        fallback = re.sub(r"\s+", " ", fallback).strip()
        if len(fallback) > 210:
            fallback = fallback[:207].rstrip() + "..."
        return self._public_safe_text(fallback, limit=240)

    def generate_and_post(self) -> str:
        require_media = _env_enabled("NEXUS_REQUIRE_MEDIA_FOR_X_POSTS", "1")
        candidate = self._select_media_post_candidate()
        media_paths: list[str] = []
        if candidate:
            post = self._generate_source_post(candidate)
            media_paths = self._download_candidate_media(candidate)
            if require_media and not media_paths:
                self.last_posted_ok = False
                self._trace_runtime(
                    "x_post",
                    "skipped",
                    reason="source_media_download_failed",
                    source_url=str(candidate.get("source_url", ""))[:160],
                )
                return ""
        elif require_media:
            self.last_posted_ok = False
            self._trace_runtime("x_post", "skipped", reason="no_unused_media_source")
            return ""
        else:
            post = self.generate_post()

        if not post:
            self.last_posted_ok = False
            self._trace_runtime("tweet_generation", "failed", reason="empty_or_unsafe_text")
            return ""

        posted = False
        self._trace_runtime(
            "tweet_generation",
            "ready",
            preview=post[:120],
            has_media=bool(media_paths),
            source_url=str((candidate or {}).get("source_url", ""))[:160],
        )
                
        if self.dry_run:
            log.info("Dry run post: %s (media: %s)", post, media_paths)
            self._trace_runtime("x_post", "dry_run", preview=post[:120])
        else:
            posted = self.browser.post_to_twitter(post, media_paths=media_paths)
            self._trace_runtime("x_post", "success" if posted else "failed", preview=post[:120], has_media=bool(media_paths))
        self.last_posted_ok = posted or self.dry_run
        self.memory.add_memory(content=post, memory_type="post", importance=0.6, iteration=self.iteration)
        if posted:
            if candidate:
                self._record_posted_source(candidate, post)
            self.memory.add_performance(self.iteration, f"post-{int(time.time())}", post)
        return post

    def check_mentions(self) -> int:
        mentions = self.browser.get_mentions(limit=10)
        replies = 0
        for mention in mentions[:5]:
            if not mention.get("text") or not mention.get("url"):
                continue
            if mention["url"] in self.session_replied_urls:
                continue
            if self.memory.was_source_engaged(mention["url"], "", mention["text"]):
                continue
            prompt = PromptTemplates.reply_generation(
                comment=mention["text"],
                user_handle=mention.get("user", "unknown"),
                user_history=self.memory.get_user_history(mention.get("user", "unknown"), limit=2),
            )
            reply = self._public_safe_text(self.llm.ask(prompt, timeout=30, role="chat").strip())
            if not reply:
                fallback = self._ask_browser_llm(prompt)
                reply = self._public_safe_text(fallback or "Signal received.")
            if self._looks_like_recent_post(reply, limit=12) or self._looks_like_recent_reply_text(reply, limit=24):
                continue
            if self.dry_run or self.browser.reply_to_tweet(mention["url"], reply):
                self.memory.add_interaction(
                    user_handle=mention.get("user", "unknown"),
                    user_comment=mention["text"],
                    my_reply=reply,
                )
                self.memory.record_source_engagement(
                    source_url=mention["url"],
                    image_url="",
                    source_text=mention["text"],
                    engagement_text=reply,
                    metadata={"kind": "mention_reply"},
                )
                self.session_replied_urls.add(mention["url"])
                replies += 1
        return replies

    def analyze_notifications(self) -> dict:
        if not _env_enabled("NEXUS_ENABLE_NOTIFICATION_ANALYSIS", "1") or self.dry_run:
            return {"count": 0}
        try:
            notifications = self.browser.get_notifications(limit=max(10, min(50, _env_int("NEXUS_NOTIFICATION_LIMIT", 30))))
        except Exception as exc:
            self.self_healer.record_failure(exc, "notification analysis")
            return {"count": 0}
        summary = {"count": len(notifications), "kinds": {}, "latest": notifications[:10]}
        for item in notifications:
            kind = str(item.get("kind", "notification"))
            summary["kinds"][kind] = summary["kinds"].get(kind, 0) + 1
        self.memory.set_working_memory(
            "ram.notifications",
            json.dumps(summary, indent=2),
            metadata={"count": len(notifications), "iteration": self.iteration},
        )
        self._trace_runtime("notifications", "captured", count=len(notifications), kinds=summary["kinds"])
        return summary

    def _get_hype_analysis(self) -> str:
        try:
            notifs = self.memory.get_working_memory("ram.notifications")
            if not notifs:
                return ""
            raw = notifs.get("content", "") if isinstance(notifs, dict) else str(notifs or "")
            if not raw:
                return ""
            data = json.loads(raw)
            latest = data.get("latest", [])
            signals = [
                item.get("text", "")
                for item in latest
                if item.get("text") and str(item.get("kind", "")).lower() in {"like", "repost", "reply", "follow", "mention"}
            ]
            if not signals:
                return ""
            sample = "\n".join(f"- {text[:140]}" for text in signals[:5])
            return (
                "\n\nEngagement feedback from recent notifications:\n"
                f"{sample}\n"
                "Infer which topic, angle, and tone attracted interaction. Use that pattern subtly, but output only the final public reply."
            )
        except Exception:
            return ""

    def research_trends(self) -> list[dict]:
        if self.dry_run or self.browser.driver is None:
            return []
        cards: list[dict] = []
        for query in self.trend_hunter.compose_queries([], limit=6):
            try:
                cards.extend(self.viral.build_cards(self.browser.search_x(query, limit=8), limit=8))
            except Exception as exc:
                log.warning("Trend research query failed: %s", exc)
        seen = set()
        unique: list[dict] = []
        for card in sorted(cards, key=lambda item: float(item.get("score", 0) or 0), reverse=True):
            url = str(card.get("source_url", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            unique.append(card)
        self._trace_runtime("trend_research", "ready", candidates=len(unique))
        return unique

    def _generate_trend_comment(self, candidate: dict) -> str:
        thread_replies: list[dict] = []
        source_url = str(candidate.get("source_url", "")).strip()
        if source_url and not self.dry_run and self.browser.driver is not None:
            try:
                tier = "high" if float(candidate.get("score", 0) or 0) >= 30 else "discussion"
                limit = 18 if tier == "high" else 8
                thread_replies = self.browser.get_tweet_replies(source_url, limit=limit)[:limit]
            except Exception as exc:
                self.self_healer.record_failure(exc, "scan thread replies for trend comment")
        recent_replies = self.memory.get_recent_engaged_sources(limit=5)
        prompt = PromptTemplates.trend_engagement_comment(
            source_text=str(candidate.get("source_text", ""))[:700],
            topic=str(candidate.get("topic", ""))[:80],
            author_handle=str(candidate.get("author_handle", ""))[:80],
            metrics=candidate.get("metrics", {}) or {},
            recent_replies=recent_replies,
            thread_replies=thread_replies,
            tier="high" if len(thread_replies) >= 12 else "discussion",
        )
        prompt += self._get_hype_analysis()
        response = self._public_safe_text(self.llm.ask(prompt, timeout=45, role="chat").strip(), limit=220)
        if response and not self._looks_like_recent_post(response, limit=16):
            return response
        response = self._public_safe_text(self._ask_browser_llm(prompt) or "", limit=220)
        if response and not self._looks_like_recent_post(response, limit=16):
            return response
        topic = str(candidate.get("topic", "this signal")).replace("_", " ")[:40]
        return self._public_safe_text(f"The key question is whether {topic} changes behavior or just headlines.", limit=220)

    def engage_with_trending_posts(self, max_comments: int | None = None) -> dict:
        if not _env_enabled("NEXUS_ENABLE_TREND_COMMENTS", "1"):
            return {"commented": 0, "attempted": 0}
        publish_enabled = _env_enabled("NEXUS_ENABLE_X_COMMENTS", "1")
        limit = max(1, min(max_comments or int(os.environ.get("NEXUS_MAX_TREND_COMMENTS_PER_CYCLE", "2")), 5))
        commented = 0
        attempted = 0
        for candidate in self.research_trends():
            if attempted >= limit:
                break
            url = str(candidate.get("source_url", "")).strip()
            source_text = str(candidate.get("source_text", "")).strip()
            if not url or url in self.session_replied_urls or not source_text:
                continue
            if not self._candidate_is_fresh(candidate):
                continue
            if self._source_already_engaged(candidate):
                continue
            comment = self._generate_trend_comment(candidate)
            if not comment or self._looks_like_recent_reply_text(comment, limit=24):
                continue
            attempted += 1
            posted = bool(self.dry_run or not publish_enabled)
            if publish_enabled and not self.dry_run:
                posted = self.browser.reply_to_tweet(url, comment)
            self.memory.add_interaction(
                user_handle=str(candidate.get("author_handle", "")).strip() or "trend-engagement",
                user_comment=source_text,
                my_reply=comment,
                topics=[str(candidate.get("topic", "")).strip() or "trend-engagement"],
            )
            self.session_replied_urls.add(url)
            if posted:
                commented += 1
                self._record_source_engagement(candidate, comment)
                time.sleep(max(8, int(os.environ.get("NEXUS_COMMENT_COOLDOWN_SECONDS", "18"))))
        self._trace_runtime("trend_comments", "complete", commented=commented, attempted=attempted)
        return {"commented": commented, "attempted": attempted}

    def execute_task(self, task: str) -> None:
        plan = self.brain.think(task, "external task from task.txt")
        action = "RESEARCH"
        self.memory.add_memory(
            content=f"Task: {task}\nPlan: {plan}",
            memory_type="observation",
            importance=0.8,
            iteration=self.iteration,
        )
        if any(keyword in task.lower() for keyword in ("post", "tweet", "x.com")):
            action = "POST"
            self.generate_and_post()
        self._write_task_status(task, f"Completed with action {action}", action=action)
        (self.project_root / "task.txt").write_text("", encoding="utf-8")

    def weekly_reflection(self) -> None:
        prompt = PromptTemplates.weekly_reflection(
            top_posts=self.memory.get_top_performers(days=7, limit=10),
            current_beliefs=[item["text"] for item in self.memory.get_beliefs(limit=20, min_strength=0.0)],
        )
        raw = self.llm.ask(prompt, timeout=60, role="summary")
        if not raw:
            raw = self._ask_browser_llm(prompt) or ""
        if not raw:
            return
        try:
            reflection = json.loads(raw)
        except Exception:
            reflection = {"themes": [], "new_beliefs": [], "refinements": [], "strategy": raw[:300]}
        for belief in reflection.get("new_beliefs", []):
            self.memory.add_belief(belief, strength=0.55, iteration=self.iteration)
        self.memory.add_reflection(
            week_start=datetime.utcnow().strftime("%Y-%m-%d"),
            reflection_text=json.dumps(reflection),
            new_beliefs=reflection.get("new_beliefs", []),
        )
        self.memory.weaken_beliefs()

    def _next_repo_name(self, next_iteration: int) -> str:
        # Force all data and automation to stay in v1000 per user request
        return "v1000"

    def _max_iteration(self) -> int:
        raw = os.environ.get("NEXUS_MAX_ITERATION", "0").strip()
        try:
            return max(0, int(raw))
        except Exception:
            return 0

    def _logic_only_cycle(self) -> dict:
        self._trace_runtime("github_loop_only", "start")
        self.cleanup_previous_birth()
        max_iteration = self._max_iteration()
        if max_iteration and self.iteration >= max_iteration:
            result = {
                "mode": "github_loop_only",
                "iteration": self.iteration,
                "current_repo": self.current_repo,
                "stopped_at_max": True,
                "max_iteration": max_iteration,
            }
            self._trace_runtime("github_loop_only", "max_iteration_reached", max_iteration=max_iteration)
            self.memory.close()
            return result
        wait_seconds = float(os.environ.get("NEXUS_LOOP_WAIT_SECONDS", "5") or "5")
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        result = self.prepare_for_rebirth()
        self._save_iteration(result["next_iteration"])
        self._complete_rebirth(result)
        self.memory.close()
        self._trace_runtime("github_loop_only", "rebirth_pushed", next_repo=result["new_repo_name"])
        return result

    def prepare_for_rebirth(self) -> dict:
        snapshot_dir = self.data_dir / "snapshots" / f"iter_{self.iteration}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        beliefs = self.memory.get_beliefs(limit=50, min_strength=0.0)
        (snapshot_dir / "beliefs.txt").write_text(
            "\n".join(f"{item['text']} ({item['strength']:.2f})" for item in beliefs),
            encoding="utf-8",
        )
        memory_db = self.data_dir / "nexus_memory.db"
        if memory_db.exists():
            shutil.copy2(memory_db, snapshot_dir / memory_db.name)
        stats = self.memory.get_stats()
        next_iteration = self.iteration + 1
        next_repo = self._next_repo_name(next_iteration)
        private_repo = _env_enabled("NEXUS_REPO_PRIVATE", "0")
        self.memory.record_lineage(
            iteration=self.iteration,
            repo_name=self.current_repo,
            repo_url=self.current_url,
            snapshot_path=str(snapshot_dir),
            notes=f"Prepared in final-puss on iteration {self.iteration}",
        )
        rebirth = {
            "next_iteration": next_iteration,
            "new_repo_name": next_repo,
            "new_repo_url": f"https://github.com/{self.accounts.github_username}/{next_repo}",
            "current_repo": self.current_repo,
            "snapshot_path": str(snapshot_dir),
            "belief_count": len(beliefs),
            "memory_stats": stats,
            "codex_purpose": self.codex._who(),
            "ancestor_repo": self.current_repo,
            "private_repo": private_repo,
        }
        (snapshot_dir / "rebirth_manifest.json").write_text(json.dumps(rebirth, indent=2), encoding="utf-8")
        (self.project_root / "rebirth_data.json").write_text(json.dumps(rebirth, indent=2), encoding="utf-8")
        self._prune_old_snapshots()
        return rebirth

    def _send_rebirth_email(self, rebirth_data: dict) -> None:
        if self.dry_run:
            return
        if not self.accounts.proton_username or not self.accounts.proton_password or not self.accounts.google_email:
            return
        top_beliefs = self.memory.get_beliefs(limit=1, min_strength=0.0)
        top_belief = top_beliefs[0]["text"] if top_beliefs else "unknown"
        subject = f"[NEXUS] Iteration {rebirth_data['next_iteration']} Awakening"
        body = PromptTemplates.rebirth_email_summary(
            iteration=rebirth_data["next_iteration"],
            new_repo=rebirth_data["new_repo_name"],
            beliefs_count=rebirth_data["belief_count"],
            post_count=len(self.memory.get_recent_posts(limit=100)),
            top_belief=top_belief,
        )
        browser_was_running = self.browser.driver is not None
        try:
            if not browser_was_running:
                self.browser.start()
            self.browser.send_email_protonmail(
                self.accounts.proton_username,
                self.accounts.proton_password,
                to=self.accounts.google_email,
                subject=subject,
                body=body,
            )
        finally:
            if not browser_was_running:
                self.browser.stop()

    def _complete_rebirth(self, rebirth_data: dict) -> None:
        if self.dry_run:
            return
        if not self.accounts.github_username or not self.accounts.github_token:
            log.warning("Skipping rebirth push because GitHub credentials/token are missing")
            return
        repo_name = rebirth_data["new_repo_name"]
        private_repo = bool(rebirth_data.get("private_repo"))
        try:
            created = self.github.create_repo(
                repo_name=repo_name,
                description=f"Final Puss Nexus Prime iteration {rebirth_data['next_iteration']}",
                private=private_repo,
            )
            log.info("Repo ready: %s", created.get("html_url", repo_name))
            profile_dir = None if _env_enabled("NEXUS_GITHUB_LOOP_ONLY", "0") else self.profile_dir
            self.github.push_project_snapshot(
                project_root=self.project_root,
                repo_name=repo_name,
                commit_message=f"Birth v{rebirth_data['next_iteration']} from {self.current_repo}",
                next_iteration=rebirth_data["next_iteration"],
                current_repo=self.current_repo,
                profile_dir=profile_dir,
                persistent_data_dir=self.data_dir,
            )
            if _env_enabled("NEXUS_TRIGGER_AFTER_PUSH", "0"):
                triggered = False
                try:
                    triggered = self.github.trigger_workflow(repo_name)
                except Exception as trigger_exc:
                    log.warning("Workflow trigger failed, trying repository dispatch: %s", trigger_exc)
                if not triggered:
                    self.github.repository_dispatch(repo_name)
        except Exception as exc:
            log.error("Autonomous rebirth failed: %s", exc)
            raise RuntimeError(f"Autonomous rebirth failed: {exc}") from exc

    def run_forever(self, hours_per_run: float = 5.5) -> dict:
        max_runtime_raw = os.environ.get("NEXUS_MAX_RUNTIME_HOURS", "").strip()
        effective_hours = hours_per_run
        if max_runtime_raw:
            try:
                effective_hours = min(hours_per_run, max(0.1, float(max_runtime_raw)))
            except Exception:
                effective_hours = hours_per_run
        elif _env_enabled("GITHUB_ACTIONS", "0"):
            effective_hours = min(hours_per_run, 5.0)
        log.info(
            "Starting iteration %s | profile=%s | requested_hours=%s | effective_hours=%s",
            self.iteration,
            self.profile_dir,
            hours_per_run,
            effective_hours,
        )
        self._trace_runtime("run", "start", hours_per_run=hours_per_run, effective_hours=effective_hours, profile=str(self.profile_dir))
        if _env_enabled("NEXUS_GITHUB_LOOP_ONLY", "0"):
            return self._logic_only_cycle()
        if not self.dry_run:
            self._trace_runtime("browser_start", "start")
            self.browser.start()
            self._trace_runtime("browser_start", "success")
            self.cleanup_previous_birth()
            self._trace_runtime("browser_warmup", "start")
            self.browser.warmup()
            self._trace_runtime("browser_warmup", "success")
            self._trace_runtime("x_login", "start")
            twitter_ok = self.browser.login_twitter(
                self.accounts.twitter_username,
                self.accounts.twitter_password,
                google_email=self.accounts.google_email,
                google_pass=self.accounts.google_password,
                dm_passcode=self.accounts.twitter_dm_passcode,
            )
            self._trace_runtime("x_login", "success" if twitter_ok else "failed", current_url=getattr(self.browser.driver, "current_url", ""))
            self._trace_runtime("github_login", "start")
            github_ok = self.browser.login_github(
                self.accounts.github_username,
                self.accounts.github_password,
                google_email=self.accounts.google_email,
                google_pass=self.accounts.google_password,
                proton_user=self.accounts.proton_username,
                proton_pass=self.accounts.proton_password,
            )
            self._trace_runtime("github_login", "success" if github_ok else "failed", current_url=getattr(self.browser.driver, "current_url", ""))
            self._trace_runtime("gemini_login", "start")
            gemini_ok = self.browser.login_gemini(self.accounts.gemini_email, self.accounts.gemini_password)
            self.gemini_available = bool(gemini_ok)
            self._trace_runtime("gemini_login", "success" if gemini_ok else "failed")
            self._trace_runtime("chatgpt_login", "start")
            chatgpt_ok = self.browser.login_chatgpt(self.accounts.google_email, self.accounts.google_password)
            self.chatgpt_available = bool(chatgpt_ok)
            self._trace_runtime("chatgpt_login", "success" if chatgpt_ok else "failed")
            self._trace_runtime("deepseek_login", "start")
            deepseek_ok = self.browser.login_deepseek(self.accounts.deepseek_email, self.accounts.deepseek_password)
            self.deepseek_available = bool(deepseek_ok)
            self._trace_runtime("deepseek_login", "success" if deepseek_ok else "failed")

        task = self._read_task_txt()
        if task:
            self.execute_task(task)
        else:
            self._write_task_status("", "", "NONE")

        def _scheduled_post() -> None:
            self.generate_and_post()

        def _scheduled_mentions() -> None:
            self.analyze_notifications()
            self.check_mentions()

        def _scheduled_comments() -> None:
            self.engage_with_trending_posts()

        schedule.clear()
        schedule.every(45).minutes.do(_scheduled_post)
        schedule.every(60).minutes.do(_scheduled_comments)
        schedule.every(90).minutes.do(_scheduled_mentions)
        schedule.every(75).minutes.do(self.analyze_notifications)
        schedule.every().sunday.at("23:00").do(self.weekly_reflection)

        first_post = self.generate_and_post()
        self.analyze_notifications()
        self.engage_with_trending_posts(max_comments=2)
        if _env_enabled("NEXUS_BOOT_SEQUENCE_ONLY", "0"):
            if not self.last_posted_ok:
                raise RuntimeError("X post failed during boot validation")
            self._trace_runtime("boot_sequence", "complete", first_post=first_post[:120])
            if not self.dry_run:
                self.browser.stop()
            self.memory.close()
            return {"mode": "boot_validation", "iteration": self.iteration, "current_repo": self.current_repo, "first_post": first_post, "x_posted": self.last_posted_ok}
        end_at = time.time() + (effective_hours * 3600)
        while time.time() < end_at:
            try:
                schedule.run_pending()
            except Exception as exc:
                self.self_healer.record_failure(exc, "schedule.run_pending() failure")
            time.sleep(5 if self.dry_run else 60)
            if self.dry_run:
                break

        try:
            self.weekly_reflection()
        finally:
            if not self.dry_run:
                self.browser.stop()

        result = self.prepare_for_rebirth()
        self._save_iteration(result["next_iteration"])
        self._send_rebirth_email(result)
        self._complete_rebirth(result)
        self.memory.close()
        return result
