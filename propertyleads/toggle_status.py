"""
Keeps PropertyLeads ACTIVE only Mon-Fri, 10 AM to 6 PM Central,
and STOPPED at all other times, including US federal holidays.

Usage:  python toggle_status.py auto    (normal scheduled run: works out what it should be)
        python toggle_status.py stop    (force stop)
        python toggle_status.py start   (force start)

Needs env vars PL_EMAIL and PL_PASSWORD (set as GitHub secrets).
If the status is already what it should be, it does nothing.
"""
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import holidays
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://leads.propertyleads.com"
TZ = ZoneInfo("America/Chicago")
OPEN_HOUR = 10    # 10 AM
CLOSE_HOUR = 18   # 6 PM
WORKDAYS = {0, 1, 2, 3, 4}  # Mon-Fri


def should_be_active(now):
    if now.weekday() not in WORKDAYS:
        return False, "weekend"
    us_holidays = holidays.US(years=now.year)
    if now.date() in us_holidays:
        return False, f"holiday ({us_holidays.get(now.date())})"
    if not (OPEN_HOUR <= now.hour < CLOSE_HOUR):
        return False, "after hours"
    return True, "business hours"


def read_status(page):
    """Return the text in the Status box, e.g. 'Temporarily Stopped' or 'Active'."""
    link = page.locator("a", has_text="Status:").first
    link.wait_for(timeout=30000)
    return link.inner_text().replace("Status:", "").strip()


def is_stopped(status_text):
    return "stop" in status_text.lower()


def main():
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"
    if action == "auto":
        now = datetime.now(TZ)
        active, why = should_be_active(now)
        want_stopped = not active
        print(f"{now:%a %b %d %I:%M %p %Z}: {why}, should be {'ACTIVE' if active else 'STOPPED'}")
    elif action in ("stop", "start"):
        want_stopped = action == "stop"
    else:
        sys.exit("Say 'auto', 'stop' or 'start'.")

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
