---
applyTo: '**'
---
# Coding Preferences

# Project Architecture
- nodriver async browser automation (Chrome CDP)
- Sequential card processing with tab reuse per batch
- Network interception via CDP for API response capture

# Solutions Repository

## Fixed: Result Message Extraction with Loading Placeholders (2025-10-19)
**Problem**: Extracted failure messages showing CSS placeholder text "loading-payment-container" instead of actual result.

**Root Causes**:
1. Result page loads slowly with placeholder div initially visible
2. Previous extraction using `get_property()` failed silently (returned None)
3. No validation to reject loading placeholder text before parsing

**Solution**:
1. Created `_get_xpath_text_js()` using JavaScript `evaluate()` to extract DOM text
2. Added `_is_loading_placeholder()` helper to detect CSS/loading strings
3. Wait for stabilization (0.5s) + re-check text before accepting
4. Filter candidate messages to exclude placeholders before scoring
5. Added Luhn algorithm validation in `card_processor.py` to reject invalid cards

**Result**: Extracts actual failure messages like "Your payment has been rejected by your bank." instead of placeholder text.

## Fixed: Interceptor Queue Contamination (2025-10-19)
**Problem**: Card #1's API response arrived after timeout, then Card #2 received it from the queue, causing false 3DS detection.

**Root Causes**:
1. `api_response` timeout (5s) too short for Shopee's enroll_check endpoint
2. NetworkInterceptor queue persisted responses between cards

**Solution**:
1. Increased `config.json` `api_response` timeout from 5s to 15s
2. Added `NetworkInterceptor.clear_queue()` method
3. Clear stale responses before each form submission in `_process_single_card`

**Result**: Each card now waits for its own API response instead of consuming stale data.
