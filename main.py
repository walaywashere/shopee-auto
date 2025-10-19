"""CLI entry point for Shopee card validation automation."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict

from nodriver import Browser

from core.browser_manager import (
    close_browser,
    init_browser,
    load_session_cookies,
    verify_session,
)
from core.checker import process_all_batches
from input.card_processor import build_card_queue
from utils.helpers import load_config, log_error, log_info, log_summary, set_verbose
from utils.telegram_sender import send_batch_summary, is_telegram_configured


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shopee card checker")
    parser.add_argument("card_file", help="Path to the card input file")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to configuration JSON file (default: config.json)",
    )
    parser.add_argument(
        "--cookies",
        default="cookies.txt",
        help="Path to cookies file (default: cookies.txt)",
    )
    parser.add_argument(
        "--results",
        default="results.txt",
        help="Path to results output (default: results.txt)",
    )
    parser.add_argument(
        "--failed",
        default="failed.txt",
        help="Path to failed cards output (default: failed.txt)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Override config to run browser headless",
    )
    parser.add_argument(
        "--keep-browser-open",
        action="store_true",
        help="Do not close the browser automatically when the run completes",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed [INFO] logs during execution",
    )
    return parser.parse_args()


async def _async_main(args: argparse.Namespace) -> int:
    import time
    start_time = time.time()
    
    # Set verbose mode based on CLI flag
    set_verbose(args.verbose)
    
    config_path = Path(args.config).resolve()
    cookies_path = Path(args.cookies).resolve()
    results_path = Path(args.results).resolve()
    failed_path = Path(args.failed).resolve()
    card_path = Path(args.card_file).resolve()

    if not card_path.exists():
        log_error(f"Card file does not exist: {card_path}")
        return 2

    try:
        config = load_config(str(config_path))
    except Exception as exc:
        log_error(f"Failed to load config: {exc}")
        return 3

    if args.headless:
        config.setdefault("browser", {})["headless"] = True

    try:
        card_queue = build_card_queue(str(card_path))
    except Exception as exc:
        log_error(f"Failed to build card queue: {exc}")
        return 4

    if not card_queue:
        log_error("No valid cards to process")
        return 5

    # Get number of workers from config
    num_workers = int(config.get("workers", 3))
    log_info(f"Initializing {num_workers} browser instances for parallel processing")
    
    browsers: list[Browser] = []
    try:
        # Initialize all browser instances
        for i in range(num_workers):
            log_info(f"Starting browser {i + 1}/{num_workers}")
            browser = await init_browser(config)
            cookies_loaded = await load_session_cookies(browser, str(cookies_path), config)
            if not cookies_loaded:
                log_error(f"Unable to load cookies for browser {i + 1}; aborting")
                # Close all browsers created so far
                for b in browsers:
                    await close_browser(b, keep_open=False)
                return 6
            if not await verify_session(browser, config):
                log_error(f"Shopee session verification failed for browser {i + 1}")
                # Close all browsers created so far
                for b in browsers:
                    await close_browser(b, keep_open=False)
                return 7
            browsers.append(browser)
        
        log_info(f"All {num_workers} browser instances ready")
        
        results_path.parent.mkdir(parents=True, exist_ok=True)
        if results_path.exists():
            results_path.unlink()
        results_path.touch()
        
        failed_path.parent.mkdir(parents=True, exist_ok=True)
        if failed_path.exists():
            failed_path.unlink()
        failed_path.touch()

        summary = await process_all_batches(
            browsers,
            card_queue,
            str(cookies_path),
            config,
            str(results_path),
            str(failed_path),
            str(card_path),
        )
        
        # Calculate duration
        duration = time.time() - start_time
        
        log_summary(summary)
        log_info(f"Total duration: {duration:.1f}s")
        
        # Send Telegram batch summary
        if is_telegram_configured():
            log_info("Sending batch summary to Telegram...")
            success = send_batch_summary(
                summary['total'],
                summary['success'],
                summary['failed'],
                duration
            )
            if success:
                log_info("✅ Batch summary sent to Telegram")
            else:
                log_info("❌ Failed to send batch summary to Telegram")
        
        return 0
    except Exception as exc:
        log_error(f"Fatal error: {exc}")
        return 1
    finally:
        # Close all browser instances
        for i, browser in enumerate(browsers):
            log_info(f"Closing browser {i + 1}/{len(browsers)}")
            await close_browser(browser, keep_open=args.keep_browser_open)


def main() -> int:
    args = parse_arguments()
    try:
        return asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        log_info("Interrupted by user")
        return 130
    except Exception as exc:
        log_error(f"Unhandled exception: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
