"""Tab management utilities for batch card processing."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterable, Optional, Tuple

from nodriver import Browser, cdp

from utils.helpers import async_sleep, log_error, log_info

CardDict = Dict[str, Any]


async def create_tab(browser: Browser) -> Tuple[Any, str]:
    """Create and return a fresh tab along with its creation mode."""
    try:
        tab = await browser.get("about:blank", new_tab=True)
        return tab, "new_tab"
    except Exception as exc:
        log_error(f"Unable to open new tab: {exc}; retrying in new window")
        await async_sleep(0.5)
        try:
            tab = await browser.get("about:blank", new_window=True)
            return tab, "new_window"
        except Exception as window_exc:
            log_error(
                f"New window attempt failed: {window_exc}; attempting to reuse existing tab"
            )
            # Try to get the first available tab from browser
            try:
                tabs = getattr(browser, "tabs", None) or getattr(browser, "contexts", None)
                if tabs and len(tabs) > 0:
                    log_info(f"Reusing existing tab from browser (found {len(tabs)} tabs)")
                    return tabs[0], "reuse"
                else:
                    log_error("No existing tabs found; attempting browser.get without flags")
                    tab = await browser.get("about:blank")
                    return tab, "reuse"
            except Exception as final_exc:
                log_error(f"All tab creation methods failed: {final_exc}")
                raise RuntimeError(f"Cannot create or access any browser tab: {final_exc}") from final_exc


async def navigate_to_form(tab, url: str, timeout: float) -> None:
    """Navigate the given tab to the payment form with retry handling."""
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            await tab.get(url)
            log_info("Payment form loaded")
            return
        except Exception as exc:
            log_error(f"Attempt {attempt} to load payment form failed: {exc}")
            if attempt == attempts:
                raise
            await async_sleep(2)


async def _wait_for_elements_ready(tab, xpaths: Iterable[str], timeout: float, poll_interval: float = 0.2) -> None:
    """Ensure all provided XPaths resolve to interactive elements."""
    relevant_xpaths = [xp for xp in xpaths if xp]
    if not relevant_xpaths:
        return

    deadline = time.monotonic() + timeout
    js_xpaths = json.dumps(relevant_xpaths)

    while True:
        ready = await tab.evaluate(
            f"""
            (function(xpaths) {{
                for (const xp of xpaths) {{
                    const el = document.evaluate(xp, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (!el) {{
                        return false;
                    }}
                    if (el instanceof HTMLInputElement) {{
                        if (el.disabled || el.readOnly) {{
                            return false;
                        }}
                    }}
                    const rect = el.getBoundingClientRect();
                    if (!rect || (rect.width === 0 && rect.height === 0)) {{
                        return false;
                    }}
                }}
                return true;
            }})({js_xpaths});
            """
        )

        if ready:
            return

        if time.monotonic() >= deadline:
            raise RuntimeError("Timed out waiting for form inputs to become ready")

        await async_sleep(poll_interval)


async def _fill_input(tab, xpath: str, value: str, timeout: float, field_name: str = "") -> None:
    """Fill an input field without window focus using CDP insert_text with verification."""
    elements = await tab.xpath(xpath, timeout=timeout)
    if not elements:
        raise RuntimeError(f"Element not found for {field_name or xpath}")

    element = elements[0]

    await element.scroll_into_view()

    try:
        await tab.send(cdp.emulation.set_focus_emulation_enabled(True))
    except Exception:
        pass

    await element.apply("(el) => el.focus()")
    await async_sleep(0.1)

    await element.apply(
        """
        function(el) {
            const proto = Object.getPrototypeOf(el);
            const descriptor = proto ? Object.getOwnPropertyDescriptor(proto, 'value') : null;
            if (descriptor && typeof descriptor.set === 'function') {
                descriptor.set.call(el, '');
            } else {
                el.value = '';
            }
            if (typeof el.dispatchEvent === 'function') {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        """
    )

    await async_sleep(0.05)

    await tab.send(cdp.input_.insert_text(value))

    await async_sleep(0.05)

    await element.apply(
        """
        function(el) {
            if (typeof el.dispatchEvent === 'function') {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        """
    )

    state = await element.apply(
        """
        function(el) {
            if (!el) {
                return { value: '', nativeValue: '', attrValue: '' };
            }

            const proto = Object.getPrototypeOf(el);
            const descriptor = proto ? Object.getOwnPropertyDescriptor(proto, 'value') : null;
            const htmlInputProto = typeof HTMLInputElement !== 'undefined' ? HTMLInputElement.prototype : null;
            const nativeDescriptor = htmlInputProto ? Object.getOwnPropertyDescriptor(htmlInputProto, 'value') : null;

            let current = '';
            if (descriptor && typeof descriptor.get === 'function') {
                try {
                    current = descriptor.get.call(el);
                } catch (err) {
                    current = '';
                }
            } else if (typeof el.value !== 'undefined') {
                current = el.value;
            }

            let nativeValue = current;
            if (nativeDescriptor && typeof nativeDescriptor.get === 'function') {
                try {
                    nativeValue = nativeDescriptor.get.call(el);
                } catch (err) {
                    nativeValue = current;
                }
            }

            const attrValue = typeof el.getAttribute === 'function' ? (el.getAttribute('value') || '') : '';

            return { value: current || '', nativeValue: nativeValue || '', attrValue };
        }
        """
    )

    def _normalize(val: str) -> str:
        base = val or ""
        if field_name in {"card_number", "cvv"}:
            return "".join(ch for ch in base if ch.isdigit())
        return base.replace(" ", "")

    expected_norm = _normalize(value)
    observed_values = [state.get("value", ""), state.get("nativeValue", ""), state.get("attrValue", "")]
    normalized = {_normalize(val) for val in observed_values if val is not None}

    if expected_norm and expected_norm not in normalized:
        message = (
            "Focusless fill verification mismatch for "
            f"{field_name or xpath}; expected '{value}' but observed values="
            f"{state}"
        )
        log_info(message)

    log_info(f"Filled {field_name or 'field'} using focusless CDP insert_text")


async def fill_card_form(tab, card: CardDict, config: Dict[str, Any]) -> None:
    """Fill the payment form inputs for the provided card - optimized for speed."""
    xpaths = config.get("xpaths", {})
    timeouts = config.get("timeouts", {})
    element_timeout = timeouts.get("element_wait", 8)

    mm = card.get("mm", "")
    yy = card.get("yy", "")
    expiry = f"{mm}/{yy}"
    name = config.get("cardholder_name", "")

    card_last4 = card.get("number", "")[-4:]
    
    try:
        # Wait for all form elements to be present
        log_info(f"Waiting for form elements for card ending {card_last4}")
        await tab.xpath(xpaths.get("card_number", ""), timeout=element_timeout)
        await tab.xpath(xpaths.get("mmyy", ""), timeout=element_timeout)
        await tab.xpath(xpaths.get("cvv", ""), timeout=element_timeout)
        if name:
            await tab.xpath(xpaths.get("name", ""), timeout=element_timeout)

        readiness_xpaths = [
            xpaths.get("card_number", ""),
            xpaths.get("mmyy", ""),
            xpaths.get("cvv", ""),
        ]
        if name:
            readiness_xpaths.append(xpaths.get("name", ""))

        readiness_timeout = max(element_timeout, 6)
        log_info(f"Verifying form inputs are interactable (timeout {readiness_timeout}s)")
        await _wait_for_elements_ready(tab, readiness_xpaths, readiness_timeout)

        # Wait 1.5 seconds after all elements are ready
        log_info("Inputs ready; waiting 1.5s before filling")
        await async_sleep(1.5)
        
        # Fill form fields
        log_info(f"Filling card form for card ending {card_last4}")
        
        await _fill_input(tab, xpaths.get("card_number", ""), card.get("number", ""), element_timeout, "card_number")
        await _fill_input(tab, xpaths.get("mmyy", ""), expiry, element_timeout, "expiry")
        await _fill_input(tab, xpaths.get("cvv", ""), card.get("cvv", ""), element_timeout, "cvv")
        
        if name:
            await _fill_input(tab, xpaths.get("name", ""), name, element_timeout, "name")
        
        log_info(f"All fields filled for card ending {card_last4}")
    except Exception as exc:
        log_error(f"Failed to fill form for card ending {card_last4}: {exc}")
        raise


async def submit_form(tab, config: Dict[str, Any]) -> None:
    """Click the configured submit button."""
    xpaths = config.get("xpaths", {})
    timeouts = config.get("timeouts", {})
    element_timeout = timeouts.get("element_wait", 8)

    elements = await tab.xpath(xpaths.get("submit", ""), timeout=element_timeout)
    if not elements:
        raise RuntimeError("Submit button not found")
    await elements[0].scroll_into_view()
    await elements[0].click()


async def get_tab_content(tab) -> str:
    """Return the outer HTML content of the current tab."""
    try:
        return await tab.get_content()
    except AttributeError:
        # Fallback to evaluate script if direct method missing
        script = "return document.documentElement.outerHTML;"
        return await tab.evaluate(script)


async def close_tab(tab) -> None:
    """Close an individual tab."""
    try:
        await tab.close()
    except Exception as exc:
        log_error(f"Failed to close tab: {exc}")


async def close_all_tabs(browser: Browser, exclude: Optional[Iterable] = None) -> None:
    """Close all open tabs on the browser, optionally excluding provided ones."""
    exclusions = set(exclude or [])
    candidates = []
    for attr in ("contexts", "tabs", "pages"):
        tabs = getattr(browser, attr, None)
        if tabs:
            candidates = list(tabs)
            break
    if not candidates:
        return
    for tab in candidates:
        if tab in exclusions:
            continue
        await close_tab(tab)
