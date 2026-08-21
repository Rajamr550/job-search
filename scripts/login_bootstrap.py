#!/usr/bin/env python3
"""One-time visible-browser login; saves Playwright storage_state to .auth/<portal>.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PORTALS = {
    "linkedin": "https://www.linkedin.com/login",
    "indeed": "https://secure.indeed.com/auth",
    "welcome_jungle": "https://www.welcometothejungle.com/en/login",
    "apec": "https://www.apec.fr/",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap portal login session")
    parser.add_argument(
        "portal",
        choices=list(PORTALS.keys()),
        help="Portal to log into",
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install playwright first: pip install playwright && playwright install chromium")
        return 1

    auth_dir = ROOT / ".auth"
    auth_dir.mkdir(exist_ok=True)
    out = auth_dir / f"{args.portal}.json"
    url = PORTALS[args.portal]

    print(f"Opening {url}")
    print("Log in manually (2FA/CAPTCHA ok). Then return here and press Enter.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        input("Press Enter after you are fully logged in... ")
        context.storage_state(path=str(out))
        browser.close()

    print(f"Saved session → {out}")
    print("Do not commit this file. Upload via GitHub Actions cache / keep local.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
