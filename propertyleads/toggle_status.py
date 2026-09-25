"""
Sets PropertyLeads status to STOPPED or ACTIVE.

Usage:  python toggle_status.py stop
        python toggle_status.py start

Needs env vars PL_EMAIL and PL_PASSWORD (set as GitHub secrets).
If the status is already what we want, it does nothing.
"""
import os
import sys
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://leads.propertyleads.com"


def read_status(page):
    """Return the text in the Status box, e.g. 'Temporarily Stopped' or 'Active'."""
    link = page.locator("a", has_text="Status:").first
    link.wait_for(timeout=30000)
    return link.inner_text().replace("Status:", "").strip()


def is_stopped(status_text):
    return "stop" in status_text.lower()


def main():
    action = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if action not in ("stop", "start"):
        sys.exit("Say 'stop' or 'start'.")
    want_stopped = action == "stop"

    email = os.environ["PL_EMAIL"]
    password = os.environ["PL_PASSWORD"]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        try:
            # Log in
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.fill("input[placeholder='Email']", email)
            page.fill("input[type='password']", password)
            page.check("input[type='checkbox']")
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle")

            before = read_status(page)
            print(f"Status before: {before}")

            if is_stopped(before) == want_stopped:
                print("Already where we want it. Nothing to do.")
                return

            # Click Status, then Yes on the confirm popup
            page.locator("a", has_text="Status:").first.click()
            yes = page.get_by_role("button", name="Yes")
            yes.wait_for(timeout=15000)
            yes.click()
            page.wait_for_timeout(3000)

            # Reload and confirm it actually changed
            page.reload(wait_until="networkidle")
            after = read_status(page)
            print(f"Status after: {after}")
            if is_stopped(after) != want_stopped:
                sys.exit(f"Status did not change as expected (still '{after}').")
            print("Done.")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
