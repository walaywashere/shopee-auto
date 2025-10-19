"""Browser initialization and session management utilities."""

from __future__ import annotations

import asyncio
import base64
import os
from typing import Any, Dict, Optional, Set

import nodriver
from nodriver import Browser, cdp

from utils.helpers import async_sleep, log_error, log_info


class NetworkInterceptor:
    """Handle network interception for target endpoints."""

    def __init__(self, target_endpoint: str):
        self.target_endpoint = target_endpoint.lower()
        self._pending_ids: Set[str] = set()
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()

    def clear_queue(self) -> int:
        """Clear all pending responses from the queue and return count cleared."""
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        return count

    def track_request(self, request_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._pending_ids.add(request_id)
        if metadata:
            self._metadata[request_id] = metadata

    def is_tracking(self, request_id: str) -> bool:
        return request_id in self._pending_ids

    def untrack(self, request_id: str) -> Dict[str, Any]:
        self._pending_ids.discard(request_id)
        return self._metadata.pop(request_id, {})

    def push_payload(self, payload: Dict[str, Any]) -> None:
        self._queue.put_nowait(payload)

    async def wait_for_response(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        if timeout is None:
            return await self._queue.get()
        return await asyncio.wait_for(self._queue.get(), timeout=timeout)


async def init_browser(config: Dict[str, Any]) -> Browser:
    """Initialize and return a nodriver browser instance."""
    browser_cfg = config.get("browser", {})
    headless = browser_cfg.get("headless", False)

    log_info(f"Starting browser (headless={headless})")
    try:
        browser = await nodriver.start(
            headless=headless,
            browser_args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-notifications",
            ],
            lang="en-US",
        )
    except Exception as exc:
        log_error(f"Failed to start browser: {exc}")
        raise

    log_info("Browser initialized")
    return browser


async def load_session_cookies(browser: Browser, cookies_file: str, config: Dict[str, Any]) -> bool:
    """Inject cookies from a header-format file into the browser."""
    if not os.path.exists(cookies_file):
        log_error(f"Cookie file not found: {cookies_file}")
        return False

    home_url = config.get("urls", {}).get("home", "https://shopee.ph/")

    try:
        with open(cookies_file, "r", encoding="utf-8") as file:
            cookie_string = file.read().strip()
    except Exception as exc:
        log_error(f"Failed to read cookie file: {exc}")
        return False

    if not cookie_string:
        log_error("Cookie file is empty")
        return False

    tab = await browser.get("about:blank")
    try:
        await tab.send(cdp.network.enable())
    except Exception as exc:
        log_error(f"Could not enable network domain: {exc}")

    loaded = 0
    for chunk in cookie_string.split(";"):
        pair = chunk.strip()
        if not pair or "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        try:
            await tab.send(
                cdp.network.set_cookie(
                    name=name.strip(),
                    value=value.strip(),
                    domain=".shopee.ph",
                    path="/",
                    secure=True,
                    http_only=False,
                    url=home_url,
                )
            )
            loaded += 1
        except Exception as exc:
            log_error(f"Failed to set cookie {name}: {exc}")

    log_info(f"Loaded {loaded} cookies into browser session")
    return loaded > 0


async def verify_session(browser: Browser, config: Dict[str, Any]) -> bool:
    """Verify that the Shopee session is authenticated."""
    home_url = config.get("urls", {}).get("home", "https://shopee.ph/")
    timeout = config.get("timeouts", {}).get("page_load", 10)

    tab = await browser.get(home_url)
    await async_sleep(min(timeout, 5))
    current_url = (tab.url or "").lower()
    if "login" in current_url:
        log_error("Shopee session is not authenticated; login page detected")
        return False
    log_info("Shopee session verified")
    # Do NOT close the verification tab - it keeps the browser window alive
    # The first batch will reuse this tab
    return True


async def setup_network_interception(
    tab,
    config: Dict[str, Any],
    interceptor: Optional[NetworkInterceptor] = None,
) -> NetworkInterceptor:
    """Enable CDP network interception for the provided tab."""
    target_endpoint = config.get("urls", {}).get("api_endpoint", "").lower()
    interceptor = interceptor or NetworkInterceptor(target_endpoint)

    already_configured = getattr(tab, "_interception_configured", False)

    enable_attempts = 3
    for attempt in range(1, enable_attempts + 1):
        try:
            await tab.send(cdp.network.enable())
            break
        except Exception as exc:
            log_error(
                f"Failed to enable network tracking (attempt {attempt}/{enable_attempts}): {exc}"
            )
            if attempt == enable_attempts:
                break
            await async_sleep(0.5)

    if already_configured:
        return interceptor

    async def on_request(event, tab_ref=None):
        try:
            request_url = event.request.url.lower()
            if "airpayservice.com" in request_url:
                log_info(f"Request: {event.request.url}")
            if interceptor.target_endpoint and interceptor.target_endpoint in request_url:
                interceptor.track_request(event.request_id)
        except Exception as exc:
            log_error(f"Request handler error: {exc}")

    async def on_response(event, tab_ref=None):
        try:
            response_url = event.response.url.lower()
            if "airpayservice.com" in response_url:
                log_info(
                    f"Response: {event.response.url} status={event.response.status}"
                )
            if interceptor.target_endpoint and interceptor.target_endpoint in response_url:
                interceptor.track_request(
                    event.request_id,
                    {
                        "url": event.response.url,
                        "status": event.response.status,
                        "headers": dict(event.response.headers or {}),
                    },
                )
        except Exception as exc:
            log_error(f"Response handler error: {exc}")

    async def on_loading_finished(event, tab_ref=None):
        if not interceptor.is_tracking(event.request_id):
            return
        metadata = interceptor.untrack(event.request_id)
        try:
            body, is_base64 = await tab.send(cdp.network.get_response_body(event.request_id))
            if is_base64:
                try:
                    decoded = base64.b64decode(body).decode("utf-8", errors="replace")
                except Exception:
                    decoded = body
            else:
                decoded = body
            payload = {
                "request_id": event.request_id,
                "body": decoded,
                **metadata,
            }
            interceptor.push_payload(payload)
        except Exception as exc:
            error_msg = str(exc)
            # "No resource with given identifier" means the page navigated away
            # This happens for both 3DS and successful redirects - let response_analyzer decide
            if "No resource with given identifier" in error_msg or "-32000" in error_msg:
                log_info(f"Response body unavailable (page navigated): {error_msg}")
                # Push empty body payload - let response_analyzer check the page URL
                payload = {
                    "request_id": event.request_id,
                    "body": "",
                    "body_unavailable": True,
                    **metadata,
                }
                interceptor.push_payload(payload)
            else:
                log_error(f"Failed to obtain response body: {exc}")

    tab.add_handler(cdp.network.RequestWillBeSent, on_request)
    tab.add_handler(cdp.network.ResponseReceived, on_response)
    tab.add_handler(cdp.network.LoadingFinished, on_loading_finished)

    log_info("Network interception configured")
    setattr(tab, "_interception_configured", True)
    return interceptor


async def close_browser(browser: Optional[Browser], *, keep_open: bool = False) -> None:
    """Gracefully close the provided browser instance."""
    if not browser:
        return
    if keep_open:
        log_info("Browser left open per request")
        return
    try:
        browser.stop()
        log_info("Browser closed")
    except Exception as exc:
        log_error(f"Error while closing browser: {exc}")
