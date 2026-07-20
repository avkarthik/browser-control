"""Browser session factory — mirrors sample-agent.py's working pattern."""

from browser_use import BrowserProfile, BrowserSession
from browser_use.browser.profile import ViewportSize


# ---------------------------------------------------------------------------
# Chrome 148 Windows user-agent — realistic, avoids bot detection
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Browser profile
# ---------------------------------------------------------------------------
def create_browser_profile(
    headless: bool = False,
    viewport_width: int = 1280,
    viewport_height: int = 800,
    wait_between_actions: float = 2.5,
    minimum_wait_page_load_time: float = 2.5,
) -> BrowserProfile:
    """Create a BrowserProfile tuned to avoid bot detection.

    Mirrors sample-agent.py's working configuration:
    - headless=False — visible browser avoids fingerprinting
    - disable_security=False — no detectable automation flags
    - Realistic Chrome 148 user-agent
    - Human-like delays between actions
    """
    return BrowserProfile(
        headless=headless,
        disable_security=False,
        user_agent=USER_AGENT,
        window_size=ViewportSize(width=viewport_width, height=viewport_height),
        wait_between_actions=wait_between_actions,
        minimum_wait_page_load_time=minimum_wait_page_load_time,
    )


# ---------------------------------------------------------------------------
# Browser session — synchronous, Agent handles start/stop internally
# ---------------------------------------------------------------------------
def create_browser_session(
    profile: BrowserProfile | None = None,
) -> BrowserSession:
    """Create a BrowserSession. Agent.run() initializes it internally.

    Mirrors sample-agent.py: BrowserSession(browser_profile=browser_profile)
    — no async, no manual start(), no stealth plugin needed.
    """
    if profile is None:
        profile = create_browser_profile()
    return BrowserSession(browser_profile=profile)