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
    NetworkInterceptor,
    close_browser,
    init_browser,
    load_session_cookies,
    setup_network_interception,
    verify_session,
)
from core.checker import process_all_batches
from input.card_processor import build_card_queue
from utils.helpers import load_config, log_error, log_info, log_summary


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
        "--headless",
        action="store_true",
        help="Override config to run browser headless",
    )
    return parser.parse_args()


async def _async_main(args: argparse.Namespace) -> int:
    config_path = Path(args.config).resolve()
    cookies_path = Path(args.cookies).resolve()
    results_path = Path(args.results).resolve()
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

    browser: Browser | None = None
    try:
        browser = await init_browser(config)
        cookies_loaded = await load_session_cookies(browser, str(cookies_path), config)
        if not cookies_loaded:
            log_error("Unable to load cookies; aborting")
            return 6
        if not await verify_session(browser, config):
            log_error("Shopee session verification failed")
            return 7
        primary_tab = await browser.get("about:blank")
        interceptor: NetworkInterceptor = await setup_network_interception(primary_tab, config)

        results_path.parent.mkdir(parents=True, exist_ok=True)
        if results_path.exists():
            results_path.unlink()

        summary = await process_all_batches(
            browser,
            card_queue,
            interceptor,
            config,
            str(results_path),
        )
        log_summary(summary)
        return 0
    except Exception as exc:
        log_error(f"Fatal error: {exc}")
        return 1
    finally:
        await close_browser(browser)


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
