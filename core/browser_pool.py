"""Browser pool management for improved performance."""

import asyncio
from typing import List, Optional
from nodriver import Browser
from core.browser_manager import init_browser, close_browser, load_session_cookies, verify_session
from utils.helpers import log_info, log_error


class BrowserPool:
    """Manages a pool of reusable browser instances."""
    
    def __init__(self, config: dict, max_size: int = 10):
        self.config = config
        self.max_size = max_size
        self.available: asyncio.Queue = asyncio.Queue()
        self.in_use: set = set()
        self.total_created = 0
        
    async def get_browser(self, cookies_path: str) -> Optional[Browser]:
        """Get an available browser from the pool."""
        try:
            # Try to get from pool first
            browser = await asyncio.wait_for(self.available.get(), timeout=0.1)
            self.in_use.add(browser)
            return browser
        except asyncio.TimeoutError:
            # Pool empty, create new if under limit
            if self.total_created < self.max_size:
                browser = await self._create_browser(cookies_path)
                if browser:
                    self.in_use.add(browser)
                    self.total_created += 1
                return browser
            return None
    
    async def return_browser(self, browser: Browser):
        """Return browser to pool for reuse."""
        if browser in self.in_use:
            self.in_use.remove(browser)
            await self.available.put(browser)
    
    async def _create_browser(self, cookies_path: str) -> Optional[Browser]:
        """Create and initialize a new browser."""
        try:
            browser = await init_browser(self.config)
            if await load_session_cookies(browser, cookies_path, self.config):
                if await verify_session(browser, self.config):
                    return browser
            await close_browser(browser)
        except Exception as e:
            log_error(f"Failed to create browser: {e}")
        return None
    
    async def cleanup(self):
        """Close all browsers in the pool."""
        # Close available browsers
        while not self.available.empty():
            try:
                browser = self.available.get_nowait()
                await close_browser(browser)
            except asyncio.QueueEmpty:
                break
        
        # Close in-use browsers
        for browser in list(self.in_use):
            await close_browser(browser)
        
        self.in_use.clear()
        self.total_created = 0