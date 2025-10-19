"""Batch orchestration for Shopee card validation."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Optional, Tuple

from nodriver import Browser

from core.browser_manager import NetworkInterceptor, setup_network_interception
from core import response_analyzer
from core import tab_manager
from input.card_processor import format_card_string
from utils.helpers import (
    async_sleep,
    log_card_result,
    log_error,
    log_info,
)

CardDict = Dict[str, Any]


def _chunk_cards(cards: List[CardDict], batch_size: int) -> Iterable[List[CardDict]]:
    for index in range(0, len(cards), batch_size):
        yield cards[index : index + batch_size]


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


async def _process_single_card(
    browser: Browser,
    prepared_tab,
    creation_mode: str,
    card: CardDict,
    interceptor: NetworkInterceptor,
    config: Dict[str, Any],
    results_path: str,
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
    if between_cards:
        await async_sleep(between_cards)
    return card, current_tab


async def process_batch(
    browser: Browser,
    batch_cards: List[CardDict],
    batch_index_start: int,
    total_cards: int,
    interceptor: NetworkInterceptor,
    config: Dict[str, Any],
    results_path: str,
) -> List[CardDict]:
    results: List[CardDict] = []
    reusable_tab_info: Optional[Tuple[Any, str]] = None
    index = batch_index_start

    for card in batch_cards:
        try:
            prepared_tab, creation_mode = await _prepare_tab(
                browser,
                card,
                config,
                interceptor,
                reusable_tab_info=reusable_tab_info,
            )
        except Exception as exc:
            log_error(
                f"Failed to prepare card ending {card.get('number', '')[-4:]}: {exc}"
            )
            card["status"] = "[FAILED]"
            card["error"] = str(exc)
            card_str = format_card_string(card)
            log_card_result(index, total_cards, card["status"], card_str, card["error"])
            results.append(card)
            reusable_tab_info = None
            index += 1
            continue

        card_result, final_tab = await _process_single_card(
            browser,
            prepared_tab,
            creation_mode,
            card,
            interceptor,
            config,
            results_path,
            index,
            total_cards,
        )
        results.append(card_result)
        reusable_tab_info = (final_tab, "reuse") if final_tab is not None else None
        index += 1

    if reusable_tab_info and reusable_tab_info[0]:
        await tab_manager.close_tab(reusable_tab_info[0])

    return results


async def process_all_batches(
    browser: Browser,
    card_queue: List[CardDict],
    interceptor: Optional[NetworkInterceptor],
    config: Dict[str, Any],
    results_path: str,
) -> Dict[str, Any]:
    total_cards = len(card_queue)
    batch_size = int(config.get("batch_size", 5))
    summary = {
        "total": total_cards,
        "success": 0,
        "failed": 0,
        "three_ds": 0,
        "cards_processed": [],
    }

    interceptor = interceptor or NetworkInterceptor(
        config.get("urls", {}).get("api_endpoint", "")
    )

    current_index = 1
    for batch in _chunk_cards(card_queue, batch_size):
        log_info(f"Processing batch starting at card {current_index}")
        batch_results = await process_batch(
            browser,
            batch,
            current_index,
            total_cards,
            interceptor,
            config,
            results_path,
        )
        for result in batch_results:
            status = result.get("status")
            if status == "[SUCCESS]":
                summary["success"] += 1
            elif status == "[3DS]":
                summary["three_ds"] += 1
            else:
                summary["failed"] += 1
        summary["cards_processed"].extend(batch_results)
        current_index += len(batch)
    return summary
