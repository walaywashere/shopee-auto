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


async def extract_result_message(tab, config: Dict[str, Any]) -> str:
    """Extract the result message from the result page element."""
    try:
        xpath = config.get("xpaths", {}).get("result_page_element", "")
        if not xpath:
            log_info("No result_page_element xpath configured")
            return ""
        
        log_info(f"Attempting to extract result message using xpath: {xpath}")
        
        # First try to find the specific txtNewline div
        try:
            txtNewline_elements = await tab.select_all("div.txtNewline")
            if txtNewline_elements:
                log_info(f"Found {len(txtNewline_elements)} div.txtNewline elements")
                text = await txtNewline_elements[0].get_property("textContent")
                if text:
                    result = text.strip()
                    log_info(f"Extracted from txtNewline: '{result}'")
                    return result
        except Exception as e:
            log_info(f"txtNewline extraction failed: {e}")
        
        # Fallback to the main result element
        elements = await tab.xpath(xpath, timeout=3)
        if not elements:
            log_info("Result page element not found")
            return ""
        
        log_info(f"Found {len(elements)} elements, extracting text...")
        
        # Try multiple methods to get text
        text = None
        
        # Method 1: textContent property
        try:
            text = await elements[0].get_property("textContent")
            log_info(f"Got text via textContent: {text}")
        except Exception as e1:
            log_info(f"textContent failed: {e1}")
            
            # Method 2: innerText property
            try:
                text = await elements[0].get_property("innerText")
                log_info(f"Got text via innerText: {text}")
            except Exception as e2:
                log_info(f"innerText failed: {e2}")
                
                # Method 3: Direct text attribute
                try:
                    text = await elements[0].text
                    log_info(f"Got text via .text: {text}")
                except Exception as e3:
                    log_info(f".text failed: {e3}")
        
        result = (text or "").strip()
        log_info(f"Final extracted message: '{result}'")
        return result
    except Exception as exc:
        log_error(f"Failed to extract result message: {exc}")
        return ""


def check_is_success(text: str) -> bool:
    """Check if the result text indicates success."""
    if not text:
        return False
    text_lower = text.lower()
    success_keywords = ["linked", "successfully", "success"]
    return any(keyword in text_lower for keyword in success_keywords)


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
            # Already on result page, extract and check the message
            result_message = await extract_result_message(tab, config)
            
            # If extraction failed, try to get page content as fallback
            if not result_message:
                log_info("Direct extraction failed, trying page content fallback...")
                page_content = await fetch_page_content(tab)
                # Look for common success/failure patterns in the HTML
                if any(keyword in page_content.lower() for keyword in ["linked", "successfully", "success"]):
                    result_message = "Card successfully linked"
                elif "fail" in page_content.lower() or "error" in page_content.lower():
                    result_message = "Card validation failed"
                else:
                    result_message = "Unknown result"
            
            if check_is_success(result_message):
                log_info(f"Card addition succeeded: {result_message}")
                return "[SUCCESS]", result_message or "Result page indicates success"
            else:
                log_info(f"Card addition failed: {result_message}")
                return "[FAILED]", result_message or "Result page indicates failure"
        else:
            # Not on result page, likely 3DS or still on payment form
            log_info(f"Page navigated but not to result page (URL: {current_url}), likely 3DS challenge")
            return "[3DS]", "Page redirected but not to result page"

    # Body was available - wait for navigation to result page
    if not await wait_for_result_page(tab, config):
        log_error("Timeout waiting for result page")
        return "[FAILED]", "Result page timeout"

    # Extract the result message from the result page element
    result_message = await extract_result_message(tab, config)
    
    # If extraction failed, try to get page content as fallback
    if not result_message:
        log_info("Direct extraction failed, trying page content fallback...")
        page_content = await fetch_page_content(tab)
        # Look for common success/failure patterns in the HTML
        if any(keyword in page_content.lower() for keyword in ["linked", "successfully", "success"]):
            result_message = "Card successfully linked"
        elif "fail" in page_content.lower() or "error" in page_content.lower():
            result_message = "Card validation failed"
        else:
            result_message = "Unknown result"
    
    if check_is_success(result_message):
        log_info(f"Card addition succeeded: {result_message}")
        return "[SUCCESS]", result_message or "Result page indicates success"
    else:
        log_info(f"Card addition failed: {result_message}")
        return "[FAILED]", result_message or "Result page indicates failure"
