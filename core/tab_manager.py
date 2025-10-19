"""Tab management utilities for batch card processing."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple

from nodriver import Browser

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
            await async_sleep(1.5)  # Wait for form to fully load and render
            log_info("Payment form loaded")
            return
        except Exception as exc:
            log_error(f"Attempt {attempt} to load payment form failed: {exc}")
            if attempt == attempts:
                raise
            await async_sleep(2)


async def _fill_input(tab, xpath: str, value: str, timeout: float, field_name: str = "") -> None:
    """Fill an input field with retry logic."""
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            elements = await tab.xpath(xpath, timeout=timeout)
            if not elements:
                if attempt < max_retries:
                    log_info(f"Element {field_name or xpath} not found (attempt {attempt}/{max_retries}), retrying...")
                    await async_sleep(1)
                    continue
                raise RuntimeError(f"Element not found for xpath {xpath}")
            
            element = elements[0]
            await element.scroll_into_view()
            await async_sleep(0.3)  # Wait for scroll to complete
            await element.focus()
            await async_sleep(0.2)  # Wait for focus
            
            try:
                await element.clear_input()
                await async_sleep(0.1)
            except Exception:
                pass
            
            await element.send_keys(value)
            await async_sleep(0.2)  # Wait for input to register
            
            # Verify the value was actually entered
            try:
                entered_value = await element.get_property("value")
                if entered_value != value:
                    if attempt < max_retries:
                        log_info(f"Value mismatch for {field_name} (attempt {attempt}/{max_retries}), retrying...")
                        await async_sleep(0.5)
                        continue
                    log_error(f"Failed to verify input for {field_name}: expected '{value}', got '{entered_value}'")
            except Exception:
                pass  # Verification failed, but input might still be OK
            
            log_info(f"Successfully filled {field_name or 'field'}")
            return  # Success
            
        except Exception as exc:
            if attempt < max_retries:
                log_info(f"Error filling {field_name} (attempt {attempt}/{max_retries}): {exc}, retrying...")
                await async_sleep(1)
            else:
                log_error(f"Failed to fill {field_name} after {max_retries} attempts: {exc}")
                raise


async def fill_card_form(tab, card: CardDict, config: Dict[str, Any]) -> None:
    """Fill the payment form inputs for the provided card."""
    xpaths = config.get("xpaths", {})
    timeouts = config.get("timeouts", {})
    element_timeout = timeouts.get("element_wait", 8)

    mm = card.get("mm", "")
    yy = card.get("yy", "")
    expiry = f"{mm}/{yy}"
    name = config.get("cardholder_name", "")

    card_last4 = card.get("number", "")[-4:]
    
    try:
        log_info(f"Filling card number for card ending {card_last4}")
        await _fill_input(tab, xpaths.get("card_number", ""), card.get("number", ""), element_timeout, "card_number")
        
        log_info(f"Filling expiry date for card ending {card_last4}")
        await _fill_input(tab, xpaths.get("mmyy", ""), expiry, element_timeout, "expiry")
        
        log_info(f"Filling CVV for card ending {card_last4}")
        await _fill_input(tab, xpaths.get("cvv", ""), card.get("cvv", ""), element_timeout, "cvv")
        
        if name:
            log_info(f"Filling name for card ending {card_last4}")
            await _fill_input(tab, xpaths.get("name", ""), name, element_timeout, "name")
        
        log_info(f"All fields filled successfully for card ending {card_last4}")
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
