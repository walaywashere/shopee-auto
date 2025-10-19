"""Analyze network responses and page state to classify card attempts."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Tuple

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
    """Wait until the result page loads and contains visible text."""
    timeouts = config.get("timeouts", {})
    target_url = config.get("urls", {}).get("result_page", "")
    xpath = config.get("xpaths", {}).get("result_page_element", "")
    timeout = float(timeouts.get("page_load", 10))
    stabilization_delay = 0.5
    end_time = time.time() + timeout

    while time.time() < end_time:
        try:
            if target_url and tab.url and target_url in tab.url:
                text = await _get_xpath_text_js(tab, xpath)
                if text and not _is_loading_placeholder(text):
                    await async_sleep(stabilization_delay)
                    confirm_text = await _get_xpath_text_js(tab, xpath)
                    if confirm_text and not _is_loading_placeholder(confirm_text):
                        return True
            if xpath:
                text = await _get_xpath_text_js(tab, xpath)
                if text and not _is_loading_placeholder(text):
                    await async_sleep(stabilization_delay)
                    confirm_text = await _get_xpath_text_js(tab, xpath)
                    if confirm_text and not _is_loading_placeholder(confirm_text):
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


async def _get_xpath_text_js(tab, xpath: str) -> str:
    """Extract text from XPath using JavaScript evaluation."""
    if not xpath:
        return ""
    
    script = f"""
    (function() {{
        const element = document.evaluate(
            '{xpath}',
            document,
            null,
            XPathResult.FIRST_ORDERED_NODE_TYPE,
            null
        ).singleNodeValue;
        
        if (!element) return null;
        
        return {{
            textContent: element.textContent || '',
            innerText: element.innerText || '',
            innerHTML: element.innerHTML || ''
        }};
    }})();
    """
    
    try:
        text_data = await tab.evaluate(script)
        
        if text_data:
            # Handle different return formats
            if isinstance(text_data, dict):
                result = (text_data.get('textContent') or 
                         text_data.get('innerText') or 
                         text_data.get('innerHTML', '')).strip()
            elif isinstance(text_data, list):
                # Parse the list format returned by some browsers
                for item in text_data:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        key, value = item[0], item[1]
                        if isinstance(value, dict) and 'value' in value:
                            result = value['value'].strip()
                            if result:
                                return result
                return ""
            else:
                result = str(text_data).strip()
            
            return result
    except Exception:
        return ""
    
    return ""


async def _get_xpath_text(tab, xpath: str) -> str:
    if not xpath:
        return ""
    try:
        elements = await tab.xpath(xpath, timeout=1)
    except Exception:
        return ""
    if not elements:
        return ""
    element = elements[0]
    methods = [
        element.get_property("textContent"),
        element.get_property("innerText"),
        getattr(element, "text", None),
    ]
    for method in methods:
        if method is None:
            continue
        try:
            value = await method if hasattr(method, "__await__") else method
            if isinstance(value, str) and value.strip():
                return value.strip()
        except Exception:
            continue
    return ""


def _is_loading_placeholder(text: str) -> bool:
    """Return True when the extracted text still shows a loading placeholder."""
    if not text:
        return False

    normalized = " ".join(text.lower().split())
    if not normalized:
        return False

    # Exact placeholder matches (return True immediately)
    exact_placeholders = [
        "loading-payment-container",
        "loading payment container",
        "loading...",
        "loading …",
        "spinner",
    ]
    
    for placeholder in exact_placeholders:
        if placeholder in normalized:
            return True
    
    # Generic loading words - only reject if there's NO meaningful content
    generic_loading = ["loading", "processing", "please wait"]
    
    if any(word in normalized for word in generic_loading):
        # Check if there's actual meaningful content
        meaningful_keywords = [
            "bank",
            "failed",
            "error",
            "rejected",
            "declined",
            "invalid",
            "success",
            "linked",
            "card",
        ]
        # If no meaningful keywords, it's just a loading message
        if not any(keyword in normalized for keyword in meaningful_keywords):
            return True
    
    return False


async def _collect_candidate_messages(tab) -> List[str]:
    """Collect potential result messages from various DOM selectors."""
    selectors = [
        "div.txtNewline",
        "div[class*='result']",
        "div[class*='alert']",
        "div[class*='message']",
        "div[class*='status']",
        "p[class*='result']",
        "p[class*='alert']",
        "p[class*='message']",
        "p[class*='status']",
        "[role='alert']",
        "div[data-result]",
    ]

    script = f"""
    (function(selectors) {{
        const texts = new Set();
        const pushText = (value) => {{
            if (!value) return;
            const text = value.replace(/\\s+/g, ' ').trim();
            if (text && text.length >= 6) {{
                texts.add(text);
            }}
        }};

        for (const selector of selectors) {{
            try {{
                const nodes = document.querySelectorAll(selector);
                nodes.forEach((node) => {{
                    pushText(node.innerText || node.textContent || '');
                }});
            }} catch (err) {{
                // ignore selector errors
            }}
        }}

        if (texts.size === 0) {{
            const paragraphs = document.querySelectorAll('p, div, span');
            paragraphs.forEach((node) => {{
                const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                if (!text || text.length < 6 || text.length > 280) return;
                const lower = text.toLowerCase();
                const keywords = ['payment', 'card', 'bank', 'failed', 'success', 'rejected', 'invalid', 'declined'];
                if (keywords.some((kw) => lower.includes(kw))) {{
                    texts.add(text);
                }}
            }});
        }}

        return Array.from(texts);
    }})({json.dumps(selectors)});
    """

    try:
        result = await tab.evaluate(script)
    except Exception as exc:
        log_info(f"Candidate message collection failed: {exc}")
        return []

    if not isinstance(result, list):
        return []

    cleaned: List[str] = []
    for item in result:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or _is_loading_placeholder(text):
            continue
        cleaned.append(text)

    return cleaned


def _choose_best_message(messages: List[str]) -> str:
    """Choose the most relevant message from the candidate list."""
    if not messages:
        return ""

    def score_message(message: str) -> int:
        lower = message.lower()
        score = 0
        keyword_weights = {
            "payment": 5,
            "bank": 4,
            "rejected": 4,
            "failed": 3,
            "error": 2,
            "success": 2,
            "card": 2,
            "invalid": 2,
            "declined": 3,
        }
        for keyword, weight in keyword_weights.items():
            if keyword in lower:
                score += weight
        score += min(len(message), 200) // 10
        return score

    best = max(messages, key=score_message)
    return _first_sentence(best.strip())


def _extract_sentence_from_content(content: str) -> str:
    """Extract a meaningful sentence from raw HTML content."""
    if not content:
        return "Card validation failed"

    # Remove HTML tags quickly
    text = []
    inside_tag = False
    for char in content:
        if char == "<":
            inside_tag = True
            text.append(" ")
        elif char == ">":
            inside_tag = False
        elif not inside_tag:
            text.append(char)

    cleaned = "".join(text)
    cleaned = " ".join(cleaned.split())

    if not cleaned:
        return "Card validation failed"

    raw_sentences = [segment.strip() for segment in cleaned.split(".") if segment.strip()]
    failure_keywords = ["payment", "card", "bank", "fail", "reject", "decline", "invalid"]

    for idx, sentence in enumerate(raw_sentences):
        lower = sentence.lower()
        if any(keyword in lower for keyword in failure_keywords):
            result = sentence + "."
            if idx + 1 < len(raw_sentences):
                next_sentence = raw_sentences[idx + 1]
                next_lower = next_sentence.lower()
                if next_sentence and len(next_sentence) <= 120 and any(
                    kw in next_lower for kw in ["please", "contact", "use", "try", "within"]
                ):
                    result = result + " " + next_sentence + "."
            return _first_sentence(result)

    return "Card validation failed"


def _first_sentence(message: str) -> str:
    if not message:
        return ""
    cleaned = message.strip()
    if not cleaned:
        return ""
    match = re.match(r"(.+?[.!?])(?:\s|$)", cleaned)
    if match:
        return match.group(1).strip()
    # Fallback: split manually
    for delimiter in [".", "!", "?"]:
        if delimiter in cleaned:
            return cleaned.split(delimiter)[0].strip() + delimiter
    return cleaned


async def extract_result_message(tab, config: Dict[str, Any]) -> str:
    """Extract the result message from the result page element."""
    try:
        xpath = config.get("xpaths", {}).get("result_page_element", "")
        if not xpath:
            log_info("No result_page_element xpath configured")
            return ""
        
        log_info(f"Attempting to extract result message using xpath: {xpath}")
        
        # Use JavaScript evaluation to extract text
        text = await _get_xpath_text_js(tab, xpath)
        
        if text and not _is_loading_placeholder(text):
            log_info(f"Extracted result message: '{text}'")
            return _first_sentence(text)
        
        log_info(f"XPath extraction returned empty or placeholder, trying fallback...")

        # If we reach here, fallback to a broader DOM scan
        messages = await _collect_candidate_messages(tab)
        if messages:
            chosen = _choose_best_message(messages)
            if chosen:
                log_info(f"Extracted message from candidate scan: '{chosen}'")
                return _first_sentence(chosen)

        log_info("No result message extracted from DOM candidates")
        return ""
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
            await wait_for_result_page(tab, config)
            # Already on result page, extract and check the message
            result_message = await extract_result_message(tab, config)
            
            # If extraction failed, try to get page content as fallback
            if not result_message:
                log_info("Direct extraction failed, trying DOM/page content fallback...")
                candidates = await _collect_candidate_messages(tab)
                if candidates:
                    result_message = _choose_best_message(candidates)
                else:
                    page_content = await fetch_page_content(tab)
                    lowered = page_content.lower()
                    if any(keyword in lowered for keyword in ["linked", "successfully", "success"]):
                        result_message = "Card successfully linked"
                    elif any(keyword in lowered for keyword in ["fail", "error", "declined", "rejected", "invalid"]):
                        # Extract a meaningful sentence if possible
                        result_message = _extract_sentence_from_content(page_content)
                    else:
                        result_message = "Unknown result"
            
            result_message = _first_sentence(result_message)
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
        log_info("Direct extraction failed, trying DOM/page content fallback...")
        candidates = await _collect_candidate_messages(tab)
        if candidates:
            result_message = _choose_best_message(candidates)
        else:
            page_content = await fetch_page_content(tab)
            lowered = page_content.lower()
            if any(keyword in lowered for keyword in ["linked", "successfully", "success"]):
                result_message = "Card successfully linked"
            elif any(keyword in lowered for keyword in ["fail", "error", "declined", "rejected", "invalid"]):
                result_message = _extract_sentence_from_content(page_content)
            else:
                result_message = "Unknown result"
    
    result_message = _first_sentence(result_message)
    if check_is_success(result_message):
        log_info(f"Card addition succeeded: {result_message}")
        return "[SUCCESS]", result_message or "Result page indicates success"
    else:
        log_info(f"Card addition failed: {result_message}")
        return "[FAILED]", result_message or "Result page indicates failure"
