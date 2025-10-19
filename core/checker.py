"""Batch orchestration for Shopee card validation."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Optional, Tuple

from nodriver import Browser

from core.browser_manager import NetworkInterceptor, setup_network_interception
from core import response_analyzer
from core import tab_manager
from input.card_processor import format_card_string, remove_card_from_file
from utils.helpers import (
    async_sleep,
    log_card_result,
    log_error,
    log_info,
)
from utils.telegram_sender import send_telegram_notification, is_telegram_configured

CardDict = Dict[str, Any]

# Global card queue for workers
_card_queue: asyncio.Queue = None
_total_cards = 0


async def _prepare_tab(
    browser: Browser,
    card: CardDict,
    config: Dict[str, Any],
    interceptor: NetworkInterceptor,
    reusable_tab_info: Optional[Tuple[Any, str]] = None,
) -> Tuple[Any, str]:
    card_suffix = card.get("number", "")[-4:]
    stage = "reuse_tab" if reusable_tab_info else "create_tab"
    tab = None
    creation_mode = "reuse" if reusable_tab_info else "new_tab"
    try:
        log_info(f"Preparing tab for card ending {card_suffix} - {stage}")
        if reusable_tab_info:
            tab, creation_mode = reusable_tab_info
        else:
            tab, creation_mode = await tab_manager.create_tab(browser)

        stage = "interception"
        log_info(f"Preparing tab for card ending {card_suffix} - {stage}")
        await setup_network_interception(tab, config, interceptor)

        stage = "navigate"
        log_info(f"Preparing tab for card ending {card_suffix} - {stage}")
        form_url = config.get("urls", {}).get("payment_form", "")
        timeouts = config.get("timeouts", {})
        await tab_manager.navigate_to_form(tab, form_url, timeouts.get("page_load", 10))

        stage = "fill_form"
        log_info(f"Preparing tab for card ending {card_suffix} - {stage}")
        await tab_manager.fill_card_form(tab, card, config)
        log_info(f"Preparing tab for card ending {card_suffix} - complete")
        return tab, creation_mode
    except Exception as exc:
        log_error(
            f"Preparation failed for card ending {card_suffix} during stage '{stage}': {exc}"
        )
        if tab and creation_mode != "reuse":
            await tab_manager.close_tab(tab)
        raise


async def _await_target_response(
    interceptor: NetworkInterceptor,
    timeout: float,
) -> Optional[Dict[str, Any]]:
    if timeout <= 0:
        timeout = 5
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            log_error(f"API response timeout after {timeout}s waiting for {interceptor.target_endpoint}")
            return None
        try:
            payload = await interceptor.wait_for_response(timeout=remaining)
        except asyncio.TimeoutError:
            log_error(f"API response timeout after {timeout}s waiting for {interceptor.target_endpoint}")
            return None
        if not payload:
            continue
        url = (payload.get("url") or "").lower()
        if interceptor.target_endpoint in url:
            log_info(f"Received target API response: {url}")
            return payload
        else:
            log_info(f"Skipping non-target response: {url}")


async def _append_success_result(results_path: str, card_str: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write_success_line, results_path, card_str)


def _write_success_line(results_path: str, card_str: str) -> None:
    with open(results_path, "a", encoding="utf-8") as file:
        file.write(f"{card_str}\n")


async def _append_failed_result(failed_path: str, card_str: str, reason: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write_failed_line, failed_path, card_str, reason)


def _write_failed_line(failed_path: str, card_str: str, reason: str) -> None:
    with open(failed_path, "a", encoding="utf-8") as file:
        file.write(f"{card_str} | {reason}\n")


async def _process_single_card(
    browser: Browser,
    prepared_tab,
    creation_mode: str,
    card: CardDict,
    interceptor: NetworkInterceptor,
    config: Dict[str, Any],
    results_path: str,
    failed_path: str,
    card_index: int,
    total_cards: int,
) -> Tuple[Dict[str, Any], Optional[Any]]:
    max_retries = int(config.get("max_retries", 2))
    delays = config.get("delays", {})
    between_cards = float(delays.get("between_cards", 0))
    retry_delay = float(delays.get("retry_delay", 1))
    timeouts = config.get("timeouts", {})
    api_timeout = float(timeouts.get("api_response", 5))

    attempt = 0
    status = "[FAILED]"
    reason = "Max retries exceeded"
    current_tab = prepared_tab
    current_mode = creation_mode

    while attempt <= max_retries:
        try:
            # Clear any stale responses from previous cards/attempts
            cleared = interceptor.clear_queue()
            if cleared > 0:
                log_info(f"Cleared {cleared} stale response(s) from interceptor queue")
            
            await tab_manager.submit_form(current_tab, config)
            payload = await _await_target_response(interceptor, api_timeout)
            payload = payload or {}
            status, reason = await response_analyzer.determine_status(current_tab, payload, config)
            card_str = format_card_string(card)
            log_card_result(card_index, total_cards, status, card_str, reason)
            if status == "[SUCCESS]":
                await _append_success_result(results_path, card_str)
                # Send Telegram notification for successful card
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, send_telegram_notification, card_str, reason)
            elif status == "[FAILED]":
                await _append_failed_result(failed_path, card_str, reason)
            card["status"] = status
            card["error"] = reason
            if between_cards:
                await async_sleep(between_cards)
            return card, current_tab
        except Exception as exc:
            attempt += 1
            card["retry_count"] = attempt
            card["error"] = str(exc)
            log_error(
                f"Attempt {attempt} failed for card ending {card.get('number', '')[-4:]}: {exc}"
            )
            if current_tab and current_mode != "reuse":
                await tab_manager.close_tab(current_tab)
                current_tab = None
            if attempt > max_retries:
                break
            reusable_info = (current_tab, "reuse") if current_tab else None
            current_tab, current_mode = await _prepare_tab(
                browser,
                card,
                config,
                interceptor,
                reusable_tab_info=reusable_info,
            )
            await async_sleep(retry_delay)
    card["status"] = status
    card["error"] = reason
    card_str = format_card_string(card)
    log_card_result(card_index, total_cards, status, card_str, reason)
    if status == "[FAILED]":
        await _append_failed_result(failed_path, card_str, reason)
    if between_cards:
        await async_sleep(between_cards)
    return card, current_tab


async def _remove_card_entry(card_file_path: str, card: CardDict) -> None:
    """Remove the processed card from the input file to avoid reprocessing."""
    raw_entry = card.get("raw")
    if not raw_entry:
        return
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, remove_card_from_file, card_file_path, raw_entry)


async def _worker(
    worker_id: int,
    browser: Browser,
    cookies_path: str,
    config: Dict[str, Any],
    results_path: str,
    failed_path: str,
    results_list: List[CardDict],
    results_lock: asyncio.Lock,
    card_file_path: str,
    file_lock: asyncio.Lock,
) -> None:
    """Worker that processes cards from the global queue with its own browser instance."""
    global _card_queue, _total_cards
    
    log_info(f"Worker {worker_id} started with dedicated browser instance")
    
    # Each worker gets its own interceptor
    interceptor = NetworkInterceptor(config.get("urls", {}).get("api_endpoint", ""))
    worker_tab = None
    creation_mode = "new_tab"
    
    try:
        while True:
            try:
                # Get a card from the queue (non-blocking with timeout)
                card, card_index = await asyncio.wait_for(_card_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # Queue is empty, worker is done
                break
            
            result_record: Optional[CardDict] = None
            try:
                log_info(f"Worker {worker_id} processing card {card_index}/{_total_cards}")
                
                # Prepare tab for this card
                reusable_info = (worker_tab, creation_mode) if worker_tab else None
                try:
                    prepared_tab, creation_mode = await _prepare_tab(
                        browser,
                        card,
                        config,
                        interceptor,
                        reusable_tab_info=reusable_info,
                    )
                    worker_tab = prepared_tab
                except Exception as exc:
                    log_error(f"Worker {worker_id} failed to prepare card ending {card.get('number', '')[-4:]}: {exc}")
                    card["status"] = "[FAILED]"
                    card["error"] = str(exc)
                    card_str = format_card_string(card)
                    log_card_result(card_index, _total_cards, card["status"], card_str, card["error"])
                    worker_tab = None
                    result_record = card
                    continue
                
                # Process the card
                card_result, final_tab = await _process_single_card(
                    browser,
                    prepared_tab,
                    creation_mode,
                    card,
                    interceptor,
                    config,
                    results_path,
                    failed_path,
                    card_index,
                    _total_cards,
                )
                
                worker_tab = final_tab
                result_record = card_result
            except Exception as exc:
                log_error(f"Worker {worker_id} encountered error processing card: {exc}")
                card["status"] = "[FAILED]"
                card["error"] = str(exc)
                result_record = card
            finally:
                if result_record:
                    async with results_lock:
                        results_list.append(result_record)
                if card:
                    async with file_lock:
                        try:
                            await _remove_card_entry(card_file_path, card)
                        except Exception as removal_exc:
                            log_error(f"Failed to remove processed card from file: {removal_exc}")
                _card_queue.task_done()
    
    finally:
        if worker_tab:
            await tab_manager.close_tab(worker_tab)
        log_info(f"Worker {worker_id} finished")


async def process_all_batches(
    browsers: List[Browser],
    card_list: List[CardDict],
    cookies_path: str,
    config: Dict[str, Any],
    results_path: str,
    failed_path: str,
    card_file_path: str,
) -> Dict[str, Any]:
    """Process all cards using concurrent workers, each with their own browser instance."""
    global _card_queue, _total_cards
    
    _total_cards = len(card_list)
    _card_queue = asyncio.Queue()
    
    # Populate the queue with (card, index) tuples
    for index, card in enumerate(card_list, start=1):
        await _card_queue.put((card, index))
    
    num_workers = len(browsers)
    log_info(f"Processing {_total_cards} cards with {num_workers} concurrent workers (each with dedicated browser)")
    
    # Shared results list
    results_list: List[CardDict] = []
    results_lock = asyncio.Lock()
    
    # Create workers, each with its own browser instance
    file_lock = asyncio.Lock()

    workers = [
        asyncio.create_task(
            _worker(
                i + 1,
                browsers[i],
                cookies_path,
                config,
                results_path,
                failed_path,
                results_list,
                results_lock,
                card_file_path,
                file_lock,
            )
        )
        for i in range(num_workers)
    ]
    
    # Wait for all workers to complete
    await asyncio.gather(*workers)
    
    # Calculate summary
    summary = {
        "total": _total_cards,
        "success": 0,
        "failed": 0,
        "three_ds": 0,
        "cards_processed": results_list,
    }
    
    for result in results_list:
        status = result.get("status")
        if status == "[SUCCESS]":
            summary["success"] += 1
        elif status == "[3DS]":
            summary["three_ds"] += 1
        else:
            summary["failed"] += 1
    
    return summary
