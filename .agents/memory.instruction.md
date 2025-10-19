---
applyTo: '**'
---
# Coding Preferences

# Project Architecture
- nodriver async browser automation (Chrome CDP)
- Sequential card processing with tab reuse per batch
- Network interception via CDP for API response capture

# Solutions Repository

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
