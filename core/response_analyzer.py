"""Analyze network responses and page state to classify card attempts."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Tuple

from utils.helpers import async_sleep, log_error, log_info


def parse_api_response(response_body: str) -> Dict[str, Any]:
    """Parse API response body into JSON."""
    if not response_body:
        return {}
    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        log_error(f"Failed to parse API response JSON: {exc}")
        return {}


def is_three_ds(api_payload: Dict[str, Any]) -> bool:
    """Return True when the api payload indicates a 3DS challenge."""
    body = api_payload.get("body")
    if isinstance(body, dict):
        data = body
    elif isinstance(body, str):
        data = parse_api_response(body)
    else:
        data = {}
    return bool(data.get("is_challenge_flow"))


async def wait_for_result_page(tab, config: Dict[str, Any]) -> bool:
    """Wait until the result page loads or timeout occurs."""
    timeouts = config.get("timeouts", {})
    target_url = config.get("urls", {}).get("result_page", "")
    xpath = config.get("xpaths", {}).get("result_page_element", "")
    timeout = float(timeouts.get("page_load", 10))
    end_time = time.time() + timeout

    while time.time() < end_time:
        try:
            if target_url and tab.url and target_url in tab.url:
                return True
            if xpath:
                elements = await tab.xpath(xpath, timeout=1)
                if elements:
                    return True
        except Exception:
            pass
        await async_sleep(0.5)
    return False


async def fetch_page_content(tab) -> str:
    """Retrieve current page content for analysis."""
    try:
        return await tab.get_content()
    except AttributeError:
        script = "return document.documentElement.outerHTML;"
        return await tab.evaluate(script)


def check_add_card_failed(page_content: str) -> bool:
    """Check if the result page indicates a failure."""
    if not page_content:
        return True
    return "add card failed" in page_content.lower()


async def determine_status(tab, api_payload: Dict[str, Any], config: Dict[str, Any]) -> Tuple[str, str]:
    """Determine final status label and reason."""
    # Log received payload for debugging
    log_info(f"Analyzing API payload: url={api_payload.get('url')}, has_body={bool(api_payload.get('body'))}")
    
    # If body is available, check for 3DS challenge flag
    if api_payload.get("body") and is_three_ds(api_payload):
        log_info("3DS challenge detected via API response")
        return "[3DS]", "Challenge flow triggered"

    # If body unavailable (page navigated), wait a bit then check current tab URL
    if api_payload.get("body_unavailable"):
        log_info("Response body unavailable - waiting for navigation to complete")
        await async_sleep(2)  # Wait for redirect to complete
        
        current_url = (tab.url or "").lower()
        result_page_url = config.get("urls", {}).get("result_page", "").lower()
        
        if result_page_url and result_page_url in current_url:
            log_info(f"Navigated to result page: {current_url}")
            # Already on result page, check content
            page_content = await fetch_page_content(tab)
            if check_add_card_failed(page_content):
                log_info("Detected failure text on result page")
                return "[FAILED]", "Result page indicates failure"
            log_info("Card addition succeeded")
            return "[SUCCESS]", "Result page indicates success"
        else:
            # Not on result page, likely 3DS or still on payment form
            log_info(f"Page navigated but not to result page (URL: {current_url}), likely 3DS challenge")
            return "[3DS]", "Page redirected but not to result page"

    # Body was available - wait for navigation to result page
    if not await wait_for_result_page(tab, config):
        log_error("Timeout waiting for result page")
        return "[FAILED]", "Result page timeout"

    page_content = await fetch_page_content(tab)
    if check_add_card_failed(page_content):
        log_info("Detected failure text on result page")
        return "[FAILED]", "Result page indicates failure"

    log_info("Card addition succeeded")
    return "[SUCCESS]", "Result page indicates success"
