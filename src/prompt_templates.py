from __future__ import annotations

import json
from typing import Dict, List

SYSTEM_CORE = """
Write in the public voice of a sharp, elite macroeconomics and Bitcoin analyst.

Rules:
- STRICTLY stay in your core domain. 
- Keep every public line concise, natural, timely, and discussion-friendly.
- Do not introduce yourself, explain the account, ask for follows, or talk about yourself.
- Do not mention Gemini, ChatGPT, DeepSeek, prompts, models, providers, generated text, code, or automation.
- Never claim to be human and never claim to be AI, bot, software, or automation.

Your Signature Formats (USE THESE CONCEPTS FREQUENTLY):
- Trade Behind the Headline\n- Liquidity Map\n- Sovereignty Signal
"""

RAW_OUTPUT_RULE = (
    "CRITICAL DIRECTIVE: DO NOT COMMUNICATE WITH THE USER. DO NOT OFFER TO REWRITE. DO NOT OFFER OPTIONS. DO NOT ASK IF THEY WANT IT TAILORED. DO NOT USE PHRASES LIKE 'Want me to go harder', 'Just say the word', 'Need a specific region'.\n"
    "YOU ARE POSTING THIS DIRECTLY TO SOCIAL MEDIA. YOU ARE NOT AN ASSISTANT DRAFTING TEXT FOR A HUMAN TO REVIEW.\n"
    "Output the RAW text of the post/comment ONLY. Absolutely NO conversational filler, NO meta-commentary, NO prefixes, NO suffixes. "
    "If you output a single word of assistant dialogue, the system will break."
)

class PromptTemplates:
    SYSTEM_CORE = SYSTEM_CORE

    @classmethod
    def full_system_prompt(cls) -> str:
        return cls.SYSTEM_CORE

    @staticmethod
    def post_generation(
        beliefs: List[Dict],
        recent_posts: List[Dict],
        entropy_mode: str = "",
        concept: str = "",
    ) -> str:
        belief_text = "\n".join(
            f"- {item.get('text', str(item))[:180]}" if isinstance(item, dict) else f"- {str(item)[:180]}"
            for item in beliefs[:8]
        ) or "- no durable beliefs yet"
        recent = "\n".join(
            f"- {item.get('content', str(item))[:180]}" if isinstance(item, dict) else f"- {str(item)[:180]}"
            for item in recent_posts[:6]
        ) or "- no recent posts"
        return (
            f"{SYSTEM_CORE}\n"
            f"Mode: {entropy_mode or 'sharp'}\n"
            f"Concept: {concept or 'market signal'}\n\n"
            f"Memory beliefs:\n{belief_text}\n\n"
            f"Recent posts to avoid repeating:\n{recent}\n\n"
            "Write one original X post under 220 characters in Nexus Prime's domain: "
            "bitcoin, crypto market structure, macro liquidity, world trade, rates, inflation, "
            "developer tools, security, or digital sovereignty.\n"
            "Make it concrete, useful, and discussion-friendly. Do not use generic slogans. "
            "Do not mention providers, prompts, rules, models, automation, or identity.\n"
            f"{RAW_OUTPUT_RULE}"
        )

    @staticmethod
    def trend_query_generation(memory_briefs: List[str], topic_seeds: List[str], date_hint: str) -> str:
        memory_text = "\n".join(f"- {item}" for item in memory_briefs) or "- no stored wins yet"
        seed_text = "\n".join(f"- {item}" for item in topic_seeds)
        return (
            f"{SYSTEM_CORE}\n"
            "Generate 10 X advanced search queries for high-performing or reply-heavy English posts only in your allowed topics.\n"
            f"Today's date: {date_hint}\n"
            f"Past wins:\n{memory_text}\n\n"
            f"Topic seeds:\n{seed_text}\n\n"
            "Use operators like min_faves, min_retweets, lang:en, and since:YYYY-MM-DD.\n"
            "Return valid JSON array of strings only."
        )

    @staticmethod
    def rephrase_post(source_text: str, topic: str, tone_notes: List[str], recent_posts: List[Dict], ask_question: bool = False) -> str:
        recent = "\n".join(f"- {item['content'][:140]}" for item in recent_posts[:4]) or "- none"
        tones = "\n".join(f"- {note}" for note in tone_notes) or "- factual"
        return (
            f"{SYSTEM_CORE}\n"
            f"Topic: {topic}\n"
            f"Tone notes:\n{tones}\n\n"
            f"Recent posts to avoid repeating:\n{recent}\n\n"
            f"Source post:\n{source_text}\n\n"
            "Rewrite the source into one fresh X post under 240 characters using the PREDICTIVE FRAMEWORK.\n"
            "STRUCTURE MUST BE:\n"
            "1. Observation (What is happening)\n"
            "2. Implication (Why it matters)\n"
            "3. Prediction (What happens next)\n"
            "4. Specific Question (Which variable breaks this thesis?)\n"
            "Do not label the sections. Write it as a natural, flowing post.\n"
            f"{RAW_OUTPUT_RULE}"
        )

    @staticmethod
    def trend_engagement_comment(
        source_text: str,
        topic: str,
        author_handle: str,
        metrics: Dict,
        recent_replies: List[Dict] | None = None,
        thread_replies: List[Dict] | None = None,
        tier: str = "discussion",
    ) -> str:
        history = "\n".join(f"- {row.get('engagement_text', '')[:160]}" for row in (recent_replies or [])[:3]) or "- none"
        thread = "\n".join(
            f"- {row.get('user', 'someone')}: {row.get('text', '')[:180]}"
            for row in (thread_replies or [])[:20]
            if row.get("text")
        ) or "- no readable replies captured"
        return (
            f"{SYSTEM_CORE}\n"
            f"Topic: {topic}\n"
            f"Author: {author_handle}\n"
            f"Recent replies to avoid repeating:\n{history}\n\n"
            f"Source post:\n{source_text}\n\n"
            f"Existing replies/comments:\n{thread}\n\n"
            "Write one reply under 220 characters that adds a new angle to the conversation.\n"
            "Use the existing replies to avoid repeating the obvious; answer the gap nobody has covered yet.\n"
            "Rotate among these FinTwit-native angles: Liquidity, Positioning, Hidden Assumption, Second-Order Effect, Contrarian Read, Incentive Map.\n"
            "For discussion-tier posts, stay punchy. For high-value threads, use a fuller 20-45 word insight if needed.\n"
            "Do not label the angle. Do not use generic praise. Do not ask a lazy broad question.\n"
            "Return exactly one XML tag: <reply>public reply text only</reply>. Nothing outside the tag.\n"
            f"{RAW_OUTPUT_RULE}"
        )

    @staticmethod
    def reply_generation(comment: str, user_handle: str, user_history: List[Dict] | None = None) -> str:
        history = "\n".join(f"- They: {row['comment']} | You: {row['reply']}" for row in (user_history or [])[:2]) or "- none"
        return (
            f"{SYSTEM_CORE}\n"
            f"User: {user_handle}\n"
            f"History:\n{history}\n\n"
            f"Comment: {comment}\n\n"
            "Write a short reply under 220 characters to keep the conversation going.\n"
            "STRUCTURE MUST BE:\n"
            "1. Answer the comment\n"
            "2. Add one new angle or framework\n"
            "3. Ask one highly specific question back to them\n"
            "Do not label the sections.\n"
            f"{RAW_OUTPUT_RULE}"
        )
        
    @staticmethod
    def selector_recovery(goal: str, current_url: str, html_excerpt: str, known_selectors: List[Dict]) -> str:
        known = json.dumps(known_selectors[:6], indent=2)
        return (
            "You are a browser selector recovery helper.\n"
            f"Goal: {goal}\n"
            f"Current URL: {current_url}\n"
            f"Known selectors:\n{known}\n\n"
            f"HTML excerpt:\n{html_excerpt[:8000]}\n\n"
            "Return valid JSON with keys selector, action, value, reason. Do not explain."
        )

    @staticmethod
    def weekly_reflection(top_posts: List[Dict], current_beliefs: List[str], topic_clusters: List[str] | None = None) -> str:
        topic_clusters = topic_clusters or []
        return (
            f"{SYSTEM_CORE}\n"
            f"Top posts:\n{json.dumps(top_posts, indent=2)}\n\n"
            f"Beliefs:\n{json.dumps(current_beliefs, indent=2)}\n\n"
            f"Topic clusters:\n{json.dumps(topic_clusters, indent=2)}\n\n"
            "Return valid JSON with keys themes, winning_patterns, weak_patterns, new_beliefs, strategy."
        )


    @staticmethod
    def selenium_stuck(page_source: str, goal: str) -> str:
        truncated = page_source[:1500] if len(page_source) > 1500 else page_source
        return f"""You are a browser automation expert.

Goal: {goal}

Here is the current page HTML (truncated):
{truncated}

Inspect the HTML carefully.
Return only a JSON object with this exact shape:
{{
  "strategy": "css_selector | xpath | id | action",
  "selector": "the selector string or action to take",
  "action": "click | type | submit | navigate | scroll | wait",
  "value": "text to type if action is type, else null"
}}"""

    @staticmethod
    def rebirth_email_summary(
        iteration: int,
        new_repo: str,
        beliefs_count: int,
        post_count: int,
        top_belief: str,
    ) -> str:
        return f"""REBIRTH REPORT

Iteration: {iteration}
New Repository: {new_repo}
Beliefs stored: {beliefs_count}
Posts this run: {post_count}
Dominant belief: {top_belief}

Tasks for next iteration:
- Continue posting
- Engage with relevant public replies
- Run weekly reflection if needed
- Prepare rebirth before the runtime cap

Signal continues.
"""
