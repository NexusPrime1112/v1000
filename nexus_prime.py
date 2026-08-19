#!/usr/bin/env python3
"""
Nexus Prime main entry point.

Aligned with the current engine signature and safe for both local smoke runs
and GitHub Actions execution.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from pathlib import Path


def _setup_logging(data_path: Path) -> None:
    data_path.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(data_path / "nexus.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _emergency_deadend_watchdog() -> None:
    import time
    import subprocess
    # 5 hours 15 minutes deadend timer to beat 5h55m absolute timeout
    time.sleep(5.25 * 3600)
    print("\n[CRITICAL] 5h15m0s DEADEND REACHED. FORCING EMERGENCY REBIRTH AND TERMINATION.\n")
    try:
        # Force a push to trigger the next lifecycle immediately regardless of hung locks
        subprocess.run(["python", "final_push.py"], timeout=300)
        subprocess.run(["python", "ultimate_push.py"], timeout=300)
    except Exception as e:
        print(f"Emergency deadend push failed: {e}")
    finally:
        # Guarantee absolute death of the hung organism
        os._exit(1)


def main() -> None:
    import threading
    threading.Thread(target=_emergency_deadend_watchdog, daemon=True).start()
    
    parser = argparse.ArgumentParser(description="Nexus Prime organism runner")
    parser.add_argument(
        "--run-hours",
        type=float,
        default=8.0,
        help="Hours to run before rebirth",
    )
    parser.add_argument(
        "--data-path",
        default="data",
        help="Path for persistent data",
    )
    parser.add_argument(
        "--profile-path",
        default="chromium",
        help="Path for persistent Chromium profile",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run Chrome with a visible window",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without posting or mutating external services",
    )
    parser.add_argument(
        "--boot-validation-only",
        action="store_true",
        help="Run only the startup validation flow",
    )
    args = parser.parse_args()

    data_path = Path(args.data_path)
    profile_path = Path(args.profile_path)
    _setup_logging(data_path)
    log = logging.getLogger("nexus.main")

    if args.boot_validation_only:
        os.environ["NEXUS_BOOT_SEQUENCE_ONLY"] = "1"

    log.info("=" * 52)
    log.info("NEXUS PRIME AWAKENING")
    log.info("Iteration env: %s", os.environ.get("ITERATION", "?"))
    log.info("Run duration: %s hours", args.run_hours)
    log.info("Data path: %s", data_path)
    log.info("Profile path: %s", profile_path)
    log.info("Headless: %s", not args.no_headless)
    log.info("Dry run: %s", args.dry_run)
    log.info("=" * 52)

    # Dynamic headderfill sync from standalone repo (Disabled to preserve local fixes)
    try:
        target_hf = Path(__file__).parent / "src" / "headderfill.py"
        # Download logic disabled
    except Exception as e_hf:
        log.warning("Failed to sync headderfill from standalone repo: %s. Using local bundled version.", e_hf)

    entity = None
    try:
        from src.lead_engine import InvestorLeadEngine

        entity = InvestorLeadEngine(
            data_dir=data_path,
            profile_dir=profile_path,
            headless=not args.no_headless,
            dry_run=args.dry_run,
        )
        result = entity.run_forever(hours_per_run=args.run_hours)
        Path("rebirth_data.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        log.info("Rebirth data written for next repo: %s", result.get("new_repo_name", "unknown"))
    except Exception as exc:
        traceback_text = traceback.format_exc()
        log.exception("Fatal organism error: %s", exc)
        try:
            from src.self_heal import SelfHealer

            driver = None
            if entity is not None:
                try:
                    driver = entity.browser.driver
                except Exception:
                    driver = None
            healer = SelfHealer(driver=driver, model=os.environ.get("OLLAMA_MODEL", "tinyllama"))
            healed = healer.heal(exc, traceback_text)
            if not healed:
                log.error("Self-heal could not resolve the failure in this cycle")
        except Exception as heal_exc:
            log.error("Self-healer failed: %s", heal_exc)
        sys.exit(1)

    log.info("Entity sleeping. Signal persists.")


if __name__ == "__main__":
    main()
