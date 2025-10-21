"""Optimized card processing with improved concurrency."""

import asyncio
from typing import List, Dict, Any
from pathlib import Path
import time

from core.browser_pool import BrowserPool
from core.checker import _process_single_card
from core.browser_manager import NetworkInterceptor
from input.card_processor import CardData
from utils.helpers import log_info, log_error


class OptimizedProcessor:
    """High-performance card processor with browser pooling."""
    
    def __init__(self, config: Dict[str, Any], cookies_path: str):
        self.config = config
        self.cookies_path = cookies_path
        self.browser_pool = BrowserPool(config, max_size=config.get("workers", 5) + 2)
        self.results = {
            "success": 0,
            "failed": 0,
            "three_ds": 0,
            "total": 0
        }
        
    async def process_cards_optimized(
        self,
        card_list: List[CardData],
        results_path: str,
        failed_path: str,
        three_ds_path: str,
        progress_callback=None
    ) -> Dict[str, Any]:
        """Process cards with optimized concurrency and browser pooling."""
        
        start_time = time.time()
        self.results["total"] = len(card_list)
        
        # Create semaphore to limit concurrent operations
        max_concurrent = self.config.get("workers", 5)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Create tasks for all cards
        tasks = []
        for i, card in enumerate(card_list):
            task = asyncio.create_task(
                self._process_card_with_pool(
                    card, i + 1, results_path, failed_path, 
                    three_ds_path, semaphore, progress_callback
                )
            )
            tasks.append(task)
        
        # Process with controlled concurrency
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            log_error(f"Processing error: {e}")
        finally:
            await self.browser_pool.cleanup()
        
        duration = time.time() - start_time
        log_info(f"Optimized processing completed in {duration:.1f}s")
        
        return self.results
    
    async def _process_card_with_pool(
        self,
        card: CardData,
        card_index: int,
        results_path: str,
        failed_path: str,
        three_ds_path: str,
        semaphore: asyncio.Semaphore,
        progress_callback=None
    ):
        """Process single card using browser pool."""
        
        async with semaphore:
            browser = None
            try:
                # Get browser from pool
                browser = await self.browser_pool.get_browser(self.cookies_path)
                if not browser:
                    log_error(f"No browser available for card {card_index}")
                    return
                
                # Create interceptor for this card
                interceptor = NetworkInterceptor(
                    self.config.get("urls", {}).get("api_endpoint", "")
                )
                
                # Process the card (reuse existing logic)
                result, _ = await _process_single_card(
                    browser, None, "pool", card, interceptor,
                    self.config, results_path, failed_path, three_ds_path,
                    card_index, self.results["total"]
                )
                
                # Update results
                status = result.get("status", "[FAILED]")
                if status == "[SUCCESS]":
                    self.results["success"] += 1
                elif status == "[3DS]":
                    self.results["three_ds"] += 1
                else:
                    self.results["failed"] += 1
                
                # Call progress callback if provided
                if progress_callback:
                    processed = self.results["success"] + self.results["failed"] + self.results["three_ds"]
                    progress_callback(processed, self.results["total"])
                
            except Exception as e:
                log_error(f"Error processing card {card_index}: {e}")
                self.results["failed"] += 1
            finally:
                # Return browser to pool
                if browser:
                    await self.browser_pool.return_browser(browser)