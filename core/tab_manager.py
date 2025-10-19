"""Tab management utilities for batch card processing."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from nodriver import Browser

from utils.helpers import async_sleep, log_error, log_info

CardDict = Dict[str, Any]


async def create_tab(browser: Browser) -> Any:
    """Create and return a fresh tab."""
    return await browser.get("about:blank")


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


async def _fill_input(tab, xpath: str, value: str, timeout: float) -> None:
    elements = await tab.xpath(xpath, timeout=timeout)
    if not elements:
        raise RuntimeError(f"Element not found for xpath {xpath}")
    element = elements[0]
    await element.scroll_into_view()
    await element.focus()
    try:
        await element.clear_input()
    except Exception:
        pass
    await element.send_keys(value)


async def fill_card_form(tab, card: CardDict, config: Dict[str, Any]) -> None:
    """Fill the payment form inputs for the provided card."""
    xpaths = config.get("xpaths", {})
    timeouts = config.get("timeouts", {})
    element_timeout = timeouts.get("element_wait", 8)

    mm = card.get("mm", "")
    yy = card.get("yy", "")
    expiry = f"{mm}/{yy}"
    name = config.get("cardholder_name", "")

    try:
        await _fill_input(tab, xpaths.get("card_number", ""), card.get("number", ""), element_timeout)
        await _fill_input(tab, xpaths.get("mmyy", ""), expiry, element_timeout)
        await _fill_input(tab, xpaths.get("cvv", ""), card.get("cvv", ""), element_timeout)
        if name:
            await _fill_input(tab, xpaths.get("name", ""), name, element_timeout)
    except Exception as exc:
        log_error(f"Failed to fill form for card ending {card.get('number', '')[-4:]}: {exc}")
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
