"""Batch orchestration for Shopee card validation."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Optional

from nodriver import Browser

from core.browser_manager import NetworkInterceptor
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


async def _prepare_tab(browser: Browser, card: CardDict, config: Dict[str, Any]) -> Any:
    tab = await tab_manager.create_tab(browser)
    form_url = config.get("urls", {}).get("payment_form", "")
    timeouts = config.get("timeouts", {})
    await tab_manager.navigate_to_form(tab, form_url, timeouts.get("page_load", 10))
    await tab_manager.fill_card_form(tab, card, config)
    return tab


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
            return None
        try:
            payload = await interceptor.wait_for_response(timeout=remaining)
        except asyncio.TimeoutError:
            return None
        if not payload:
            continue
        url = (payload.get("url") or "").lower()
        if interceptor.target_endpoint in url:
            return payload


async def _append_success_result(results_path: str, card_str: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write_success_line, results_path, card_str)


def _write_success_line(results_path: str, card_str: str) -> None:
    with open(results_path, "a", encoding="utf-8") as file:
        file.write(f"{card_str}\n")


async def _process_single_card(
    browser: Browser,
    prepared_tab,
    card: CardDict,
    interceptor: NetworkInterceptor,
    config: Dict[str, Any],
    results_path: str,
    card_index: int,
    total_cards: int,
) -> Dict[str, Any]:
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

    while attempt <= max_retries:
        try:
            await tab_manager.submit_form(current_tab, config)
            payload = await _await_target_response(interceptor, api_timeout)
            payload = payload or {}
            status, reason = await response_analyzer.determine_status(current_tab, payload, config)
            card_str = format_card_string(card)
            log_card_result(card_index, total_cards, status, card_str)
            if status == "[SUCCESS]":
                await _append_success_result(results_path, card_str)
            card["status"] = status
            card["error"] = reason
            await tab_manager.close_tab(current_tab)
            if between_cards:
                await async_sleep(between_cards)
            return card
        except Exception as exc:
            attempt += 1
            card["retry_count"] = attempt
            card["error"] = str(exc)
            log_error(
                f"Attempt {attempt} failed for card ending {card.get('number', '')[-4:]}: {exc}"
            )
            if current_tab:
                await tab_manager.close_tab(current_tab)
            if attempt > max_retries:
                break
            current_tab = await _prepare_tab(browser, card, config)
            await async_sleep(retry_delay)
    card["status"] = status
    card["error"] = reason
    card_str = format_card_string(card)
    log_card_result(card_index, total_cards, status, card_str)
    if between_cards:
        await async_sleep(between_cards)
    return card


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
    fill_tasks = [_prepare_tab(browser, card, config) for card in batch_cards]
    prepared_tabs = await asyncio.gather(*fill_tasks, return_exceptions=True)

    first_error: Optional[BaseException] = None
    valid_tabs = []
    for item in prepared_tabs:
        if isinstance(item, BaseException):
            first_error = first_error or item
        else:
            valid_tabs.append(item)
    if first_error:
        for tab in valid_tabs:
            await tab_manager.close_tab(tab)
        log_error(f"Failed during fill phase: {first_error}")
        raise first_error

    prepared_tabs = valid_tabs

    index = batch_index_start
    for prepared_tab, card in zip(prepared_tabs, batch_cards):
        card_result = await _process_single_card(
            browser,
            prepared_tab,
            card,
            interceptor,
            config,
            results_path,
            index,
            total_cards,
        )
        results.append(card_result)
        index += 1
    return results


async def process_all_batches(
    browser: Browser,
    card_queue: List[CardDict],
    interceptor: NetworkInterceptor,
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
