"""
NEXUS-PRIME-Ω  Dynamic Credential Store
========================================
This file is for NEW accounts/passwords created by the AI during runtime.
The main accounts (GitHub, Twitter, Gmail, ProtonMail) are in GitHub Secrets.
Only write here if AI creates something NEW (new email, new service, etc).

Format: add a new entry dict to NEW_ACCOUNTS list.
This file is transferred to every new repo at rebirth — AI always has its new accounts.
This file is gitignored but copied to next repo via the workflow rsync.
"""

# ── Main accounts (real only — real values) ──────
# gmail is same as google just url change for indbox its like ("https://mail.google.com/mail")
# github_username  = "NexusPrime1112"        → secret: GITHUB_USERNAME
# github_password  = "NEXUSPRIME--1112"      → secret: GITHUB_PASSWORD
# proton_email     = "nexusprime1112@proton.me" → secret: PROTON_USERNAME
# proton_password  = "NEXUSPRIME--1112k"     → secret: PROTON_PASSWORD
# google_email     = "dprjfacts@gmail.com" → secret: GOOGLE_EMAIL
# google_password  = "D4P16R18J10"      → secret: GOOGLE_PASSWORD
# twitter_username(x.com) = "NexusPrime1112"        → secret: TWITTER_USERNAME
# twitter_password(x.com) = "NEXUSPRIME--1112"      → secret: TWITTER_PASSWORD
# github_1st_repo = "https://github.com/NexusPrime1112/v1"      → secret: GITHUB 1ST REPOSETORY NAME (1ST VERSION LIVE CONTAINER REPO) 
# deepseek username(chat.deepseek.com) = "dprjfacts@gmail.com"
# deepseek password(chat.deepseek.com) = "D4P16R18J10"  
# chatgpt username(chat.openai.com) = "dprjfacts@gmail.com"
# chatgpt password(chat.openai.com) = "D4P16R18J10k"  





# ── OTP / Verification routing (AI must know this) ───────────────────────────
# GitHub   → verification code goes to BOTH Gmail AND ProtonMail. Try Gmail first.
# Twitter  → connected to gmail only.
# Primary  → Gmail is primary everywhere. ProtonMail is fallback.


# In src/logins.py (nexus_prime/ and puss/)
# GITHUB_TOKEN    = "REMOVED_FOR_SECURITY"        # classic, full access
# GITHUB_TOKEN_FG = "REMOVED_FOR_SECURITY"                        # fine-grained, backup




# ── Dynamically created accounts (AI adds entries here during runtime) ────────
NEW_ACCOUNTS = [
    # Example format — AI appends new dicts here:
    # {
    #   "url": "some-service.com",
    #   "username": "the-login",
    #   "password": "the-password",
    #   "purpose": "what this account was created for",
    #   "created_iter": 3,
    #   "notes": "any extra info"
    # },
]
