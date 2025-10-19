# Queue-Based Card Checker System - Complete Implementation Plan

**Project:** Shopee.ph Card Validation Automation  
**Date:** October 19, 2025  
**Status:** Pre-Implementation Planning

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Execution Flow](#execution-flow)
3. [Detailed Phase Breakdown](#detailed-phase-breakdown)
4. [Data Structures](#data-structures)
5. [Configuration](#configuration)
6. [Implementation Plan](#implementation-plan)
7. [Success Criteria](#success-criteria)

---

## Project Structure

```
shopee-auto/
├── config.json                 # Configuration (timeouts, delays, XPaths, batch size)
├── cookies.txt                 # Persistent session cookies
├── main.py                     # Entry point (CLI, file input handling)
├── results.txt                 # Output file (successful cards)
├── PLAN.md                     # This file
│
├── core/
│   ├── __init__.py
│   ├── checker.py              # Core card checking logic (batch orchestration)
│   ├── browser_manager.py      # Browser initialization & session management
│   ├── tab_manager.py          # Tab creation, filling, and cleanup
│   └── response_analyzer.py    # API response parsing & status determination
│
├── input/
│   ├── __init__.py
│   └── card_processor.py       # Card file parsing & validation
│
└── utils/
    ├── __init__.py
    └── helpers.py              # Logging, delays, config loading helpers
```

---

## Execution Flow

### High-Level Flow Diagram

```
START
  ↓
[main.py] Parse CLI arguments (input file path)
  ↓
[input/card_processor.py] Read & parse cards from .txt file
  ↓
[input/card_processor.py] Validate card format & build queue
  ↓
[core/browser_manager.py] Initialize nodriver browser (headed)
  ↓
[core/browser_manager.py] Load cookies from cookies.txt
  ↓
[core/browser_manager.py] Setup network interception
  ↓
[core/checker.py] FOR EACH BATCH (5 cards per batch):
  │
  ├─ [core/tab_manager.py] FILL PHASE (Parallel):
  │  ├─ Open TAB 1, navigate to payment form
  │  ├─ Open TAB 2, navigate to payment form
  │  ├─ Open TAB 3, navigate to payment form
  │  ├─ Open TAB 4, navigate to payment form
  │  ├─ Open TAB 5, navigate to payment form
  │  ├─ Fill TAB 1 with card 1 (card #, MM/YY, CVV, name)
  │  ├─ Fill TAB 2 with card 2 (card #, MM/YY, CVV, name)
  │  ├─ Fill TAB 3 with card 3 (card #, MM/YY, CVV, name)
  │  ├─ Fill TAB 4 with card 4 (card #, MM/YY, CVV, name)
  │  └─ Fill TAB 5 with card 5 (card #, MM/YY, CVV, name)
  │
  ├─ [core/checker.py] SUBMIT PHASE (Sequential):
  │  ├─ TAB 1: Click submit
  │  │  ├─ Capture API response (airpayservice)
  │  │  ├─ [core/response_analyzer.py] Analyze status
  │  │  ├─ Wait for result page (if needed)
  │  │  ├─ Confirm final status: [3DS], [SUCCESS], or [FAILED]
  │  │  ├─ Display: [X/TOTAL] [STATUS] card_data
  │  │  ├─ Save to results.txt if [SUCCESS]
  │  │  └─ Retry on error (max 2 times)
  │  │
  │  ├─ TAB 2: Click submit (repeat same flow)
  │  ├─ TAB 3: Click submit (repeat same flow)
  │  ├─ TAB 4: Click submit (repeat same flow)
  │  └─ TAB 5: Click submit (repeat same flow)
  │
  └─ [core/tab_manager.py] Close all 5 tabs (or clear and reuse)
  
[core/checker.py] NEXT BATCH: If cards remain, repeat with next 5 cards

COMPLETION
  ↓
Display summary (total processed, success count, failed count, 3ds count)
  ↓
Close browser
  ↓
END
```

### Execution Timeline Comparison

**Old Approach (1 tab, sequential):**
- Fill: 2s + Submit+Wait: 5s = 7s per card
- 500 cards = ~62 minutes total

**New Approach (5 parallel tabs):**
- Fill 5 tabs in parallel: 2s (all done together)
- Submit 5 tabs sequentially: 5s × 5 = 25s per batch
- Per batch (5 cards): ~27 seconds
- 500 cards (100 batches) = ~45 minutes total
- **3x faster than sequential!**

---

## Detailed Phase Breakdown

### Phase 1: Initialization

**Responsibility:** `main.py`

**Actions:**
- Accept input filename as CLI argument
- Validate file exists and is readable
- Load `config.json` with all configuration values
- Call `input.card_processor.read_cards()` to parse input file
- Initialize `core.browser_manager` to launch browser
- Load cookies from `cookies.txt`
- Setup network interception via `core.browser_manager`
- Start main card checking loop via `core.checker.py`

**Output:**
- Browser instance ready
- Card queue loaded and validated
- Network handlers registered

---

### Phase 2: Card Input Processing

**Responsibility:** `input/card_processor.py`

**Functions:**

#### `read_cards(filepath)`
- Open and read `.txt` file line by line
- Parse format: `card_number|MM|YY|CVV`
- Return list of card dictionaries

#### `validate_card(card_dict)`
- Card number: Must be 16 digits
- MM: Must be 01-12
- YY: Must be 2-digit year (valid range)
- CVV: Must be 3-4 digits
- Return True/False

#### `build_queue(cards_list)`
- Iterate through cards
- Validate each card
- Skip invalid cards with warning
- Return valid card queue and total count

**Output:**
```
CardQueue = [
  {'number': '5210690378180718', 'mm': '03', 'yy': '28', 'cvv': '764'},
  {'number': '5363470078645012', 'mm': '09', 'yy': '29', 'cvv': '466'},
  ...
]
Total: 9 cards
```

---

### Phase 3: Browser & Session Setup

**Responsibility:** `core/browser_manager.py`

**Functions:**

#### `init_browser()`
- Initialize nodriver with headed mode
- Load browser options from config
- Launch browser instance
- Return browser object

#### `load_session_cookies(browser_instance, cookies_file)`
- Read cookies from `cookies.txt`
- Parse header format: `name1=value1; name2=value2; ...`
- Inject cookies into browser via CDP Network.setCookie
- Return success/failure status

#### `verify_session(browser_instance)`
- Navigate to `https://shopee.ph/` 
- Wait for page to load
- Check if session is valid (logged in)
- Return session status

#### `setup_network_interception(browser_instance)`
- Enable CDP network tracking
- Register handler for `Network.RequestWillBeSent`
- Register handler for `Network.ResponseReceived`
- Register handler for `Network.LoadingFinished`
- Return success status

#### `close_browser(browser_instance)`
- Close browser gracefully
- Cleanup temp profiles
- Return success status

---

### Phase 4: Batch Processing Loop

**Responsibility:** `core/checker.py`

**Main Function:** `process_card_batches(browser, card_queue, config)`

#### For each batch (5 cards at a time):

**4.1 - FILL PHASE (Parallel - All 5 tabs)**

**Responsibility:** `core/tab_manager.py`

For each of the 5 cards in the batch:
1. Create new tab in browser
2. Navigate to payment form URL
3. Wait for form to load (timeout: config value)
4. Fill card number field (XPath from config)
5. Fill MM/YY field (XPath from config)
6. Fill CVV field (XPath from config)
7. Fill cardholder name field (XPath from config)

**Result:** All 5 tabs filled and ready, waiting to submit

**4.2 - SUBMIT PHASE (Sequential - One by one)**

**Responsibility:** `core/checker.py` + `core/response_analyzer.py`

**For each of the 5 filled tabs:**

**Step 1: Submit Form**
- Click submit button on tab
- Wait for network requests to be sent

**Step 2: Capture API Response**
- Listen for response from `https://api.airpayservice.com/v1/cc/txn/channels/cybs/enroll_check`
- Timeout: config value (default 5s)
- Parse JSON response body
- Check for key: `"is_challenge_flow"`
  - If value = `true` → Status = `[3DS]` → Jump to Step 5
  - If value = `false` OR key missing → Continue to Step 3

**Step 3: Wait for Redirect Page**
- Browser automatically redirects to: `https://pay.shopee.ph/payment-v2/add-card-result`
- Wait for element (XPath from config): `//*[@id="root"]/div[2]/div[3]/div`
- Timeout: config value (default 8s)
- If timeout → Mark for RETRY (go to Step 5)

**Step 4: Analyze Result Page**
- Get page source via `tab.get_content()`
- Search for text: "Add Card Failed"
  - If found → Status = `[FAILED]` → Jump to Step 5
  - If NOT found → Status = `[SUCCESS]` → Jump to Step 5

**Step 5: Output & Save Result**
1. Print to console: `[X/TOTAL] [STATUS] card_number|mm|yy|cvv`
   - Example: `[1/9] [SUCCESS] 5210690378180718|03|28|764`
2. If status = `[SUCCESS]`:
   - Write to `results.txt`: `card_number|mm|yy|cvv`
3. Move to next tab and repeat from Step 1

**4.3 - Error Handling & Retry**

**Responsibility:** `core/checker.py`

- If any step fails (timeout, network error, element not found):
  - Increment retry counter for this card
  - If `retry_count < 2`:
    - Wait 1 second (retry_delay from config)
    - Close current tab
    - Create new tab and jump back to Phase 4.1 (re-fill and re-submit)
  - If `retry_count >= 2`:
    - Mark as `[FAILED]`
    - Jump to Step 5 (output & save)

**4.4 - Batch Completion**

**Responsibility:** `core/tab_manager.py`

- After all 5 tabs processed:
  - Close all 5 tabs (or clear and reuse for next batch)
  - If more cards remain: Jump back to Phase 4.1 with next 5 cards
  - If no more cards: Proceed to Phase 5

---

### Phase 5: Completion

**Responsibility:** `main.py`

**After all batches & cards processed:**

1. Calculate statistics:
   - Total cards processed
   - Success count
   - Failed count
   - 3DS count

2. Print summary to console:
   ```
   ==================== SUMMARY ====================
   Total Processed: 9
   Success: 2
   Failed: 5
   3DS: 2
   =================================================
   ```

3. Close browser via `core.browser_manager.close_browser()`
4. Exit program

---

## Data Structures

### Card Object

```python
{
  'number': '5210690378180718',
  'mm': '03',
  'yy': '28',
  'cvv': '764',
  'retry_count': 0,
  'status': None,  # Will be set to [SUCCESS], [FAILED], or [3DS]
  'error': None    # Error message if any
}
```

### Results Summary Object

```python
{
  'total': 9,
  'success': 2,
  'failed': 5,
  'three_ds': 2,
  'cards_processed': [Card, Card, ...]
}
```

### API Response Object (for reference)

```python
{
  'url': 'https://api.airpayservice.com/v1/cc/txn/channels/cybs/enroll_check',
  'status_code': 200,
  'body': {
    'is_challenge_flow': True or False,
    # ... other fields
  }
}
```

---

## Configuration

### config.json Structure

```json
{
  "timeouts": {
    "page_load": 10,
    "element_wait": 8,
    "api_response": 5
  },
  "delays": {
    "between_cards": 0.5,
    "retry_delay": 1
  },
  "xpaths": {
    "card_number": "//*[@id='root']/div[2]/div[1]/div[4]/div[2]/div[1]/div/div/input",
    "mmyy": "//*[@id='root']/div[2]/div[1]/div[4]/div[3]/div[1]/div/div[1]/div/div/input",
    "cvv": "//*[@id='root']/div[2]/div[1]/div[4]/div[3]/div[2]/div/div[1]/div/div[1]/input",
    "name": "//*[@id='root']/div[2]/div[1]/div[4]/div[4]/div[1]/div/div/input",
    "submit": "//*[@id='root']/div[2]/div[2]/div/button[2]",
    "result_page_element": "//*[@id='root']/div[2]/div[3]/div"
  },
  "urls": {
    "payment_form": "https://pay.shopee.ph/payment-v2/add-card?add_card_scene=0&block_cc=False&client_id=40024&is_mepage=1&page_type=2&payment_channel_id=4004000&post_to_tpp=True&to_local_spm=0&callback_url=https%3A%2F%2Fshopee.ph%2Fuser%2Faccount%2Fpayment",
    "api_endpoint": "https://api.airpayservice.com/v1/cc/txn/channels/cybs/enroll_check",
    "result_page": "https://pay.shopee.ph/payment-v2/add-card-result",
    "home": "https://shopee.ph/"
  },
  "batch_size": 5,
  "max_retries": 2,
  "cardholder_name": "roja kun"
}
```

### Configuration Details

| Setting | Type | Default | Purpose |
|---------|------|---------|---------|
| `timeouts.page_load` | int | 10 | Seconds to wait for page to fully load |
| `timeouts.element_wait` | int | 8 | Seconds to wait for form elements to appear |
| `timeouts.api_response` | int | 5 | Seconds to wait for API response |
| `delays.between_cards` | float | 0.5 | Seconds to wait between card submissions |
| `delays.retry_delay` | int | 1 | Seconds to wait before retrying a card |
| `batch_size` | int | 5 | Number of cards before browser restart (not restarting in this implementation) |
| `max_retries` | int | 2 | Maximum retry attempts per card |
| `cardholder_name` | string | "roja kun" | Name used for all card submissions |

---

## Implementation Plan

### Step 1: Create File Structure & Config
**Deliverables:**
- Create folders: `core/`, `input/`, `utils/`
- Create `__init__.py` in each folder
- Create empty Python files with docstrings
- Create `config.json` with all values
- Verify file paths and permissions

**Time Estimate:** 10 minutes

---

### Step 2: Implement Utilities (`utils/helpers.py`)
**Functions to implement:**
- `load_config(filepath)` - Load config.json
- `log_info(message)` - Print informational message
- `log_error(message)` - Print error message
- `log_card_result(index, total, status, card_data)` - Format and print card result
- `log_summary(results_dict)` - Print final summary
- `async_sleep(seconds)` - Async sleep wrapper with error handling

**Time Estimate:** 15 minutes

---

### Step 3: Implement Card Processor (`input/card_processor.py`)
**Functions to implement:**
- `read_cards_from_file(filepath)` - Read and parse input file
- `validate_card(card_dict)` - Validate card format
- `build_card_queue(filepath)` - Build and return validated queue

**Tests:**
- Test with sample input file
- Verify validation catches invalid cards
- Verify queue structure

**Time Estimate:** 20 minutes

---

### Step 4: Implement Browser Manager (`core/browser_manager.py`)
**Functions to implement:**
- `init_browser(config)` - Initialize nodriver
- `load_session_cookies(browser, cookies_file, config)` - Load cookies
- `verify_session(browser, config)` - Verify logged-in state
- `setup_network_interception(browser)` - Register CDP handlers
- `close_browser(browser)` - Clean shutdown

**Tests:**
- Test browser initialization
- Test cookie loading
- Test network interception setup

**Time Estimate:** 30 minutes

---

### Step 5: Implement Tab Manager (`core/tab_manager.py`)
**Functions to implement:**
- `create_tab(browser)` - Create new tab in browser
- `navigate_to_form(tab, url, config)` - Navigate to payment form
- `fill_card_form(tab, card, config)` - Fill all 4 fields in tab
- `get_tab_content(tab)` - Get page content from tab
- `close_tab(tab)` - Close single tab
- `close_all_tabs(browser)` - Close all open tabs

**Tests:**
- Test tab creation
- Test form filling
- Test tab closure

**Time Estimate:** 25 minutes

---

### Step 6: Implement Response Analyzer (`core/response_analyzer.py`)
**Functions to implement:**
- `parse_api_response(response_body)` - Extract status from API
- `is_three_ds(response_body)` - Check for 3DS challenge
- `wait_for_result_page(tab, config)` - Wait for redirect page
- `check_add_card_failed(page_content)` - Check page text
- `determine_status(tab, api_response, config)` - Main status determination

**Tests:**
- Test with mock responses
- Test 3DS detection
- Test page content analysis

**Time Estimate:** 25 minutes

---

### Step 7: Implement Card Checker (`core/checker.py`)
**Functions to implement:**
- `process_batch(browser, batch_cards, index_start, config)` - Process one batch of 5 cards
  - Fill phase: Create 5 tabs and fill all in parallel
  - Submit phase: Submit and collect results sequentially
  - Retry logic: Handle failures with max 2 retries per card
- `process_all_batches(browser, card_queue, config)` - Main loop for all batches

**Tests:**
- Test form filling
- Test retry logic (simulate failures)
- Test parallel tab operations
- Test output formatting
- Test results file writing

**Time Estimate:** 45 minutes

---

### Step 8: Implement Main Entry Point (`main.py`)
**Functions to implement:**
- `parse_arguments()` - Parse CLI arguments
- `main(input_file)` - Orchestrate entire flow:
  1. Load config
  2. Parse cards
  3. Init browser
  4. Load cookies
  5. Setup network interception
  6. Process all batches
  7. Print summary
  8. Close browser
- `if __name__ == "__main__"` - Entry point

**Tests:**
- Test with sample card file
- Verify all output
- Verify results.txt creation

**Time Estimate:** 20 minutes

---

### Step 9: Integration Testing & Debugging
**Test Cases:**
- Run with sample 9-card input file
- Verify console output format matches specification
- Verify results.txt contains only successful cards
- Verify retry logic (simulate failures)
- Verify all three statuses appear: [SUCCESS], [FAILED], [3DS]
- Verify batching works (5 cards per batch, multiple batches)
- Verify parallel tab filling (all 5 tabs fill quickly)
- Verify sequential tab submission (submit one by one)
- Verify cookies persist throughout queue
- Verify single browser instance for all cards
- Run with 500+ card file and verify performance

**Debugging:**
- Check logs for any errors
- Verify network interception capturing responses
- Test with various card data formats
- Monitor browser memory usage during long runs

**Time Estimate:** 60 minutes

---

## Success Criteria

### Functional Requirements

✅ **Input Processing**
- Read card data from .txt file
- Parse format: `card_number|MM|YY|CVV`
- Validate all card entries
- Build queue of 9+ cards

✅ **Browser Automation**
- Launch headed nodriver browser
- Load cookies from cookies.txt
- Navigate to payment form
- Fill all 4 form fields correctly
- Submit form successfully

✅ **Response Analysis**
- Capture API response from airpayservice
- Identify 3DS challenge: `"is_challenge_flow": true`
- Wait for result page redirect
- Analyze page content for "Add Card Failed"
- Determine correct status: [SUCCESS], [FAILED], or [3DS]

✅ **Output & Storage**
- Print each card: `[X/TOTAL] [STATUS] card_number|mm|yy|cvv`
- Save successful cards to results.txt
- Display final summary with counts

✅ **Error Handling & Retry**
- Implement retry logic (max 2 retries)
- Handle timeout errors gracefully
- Handle network errors gracefully
- Handle element not found errors

✅ **Performance & Persistence**
- Maintain single browser for entire queue
- Keep cookies loaded throughout
- Support 500+ card processing in ~45 minutes
- Complete 9 cards within ~2 minutes

✅ **Parallel Tab Batching**
- Process 5 cards per batch
- Fill all 5 tabs in parallel (simultaneous form filling)
- Submit tabs sequentially (one result at a time)
- Reuse single browser instance across all batches
- Close/clear tabs between batches
- Seamless transition between batches

### Quality Requirements

✅ **Code Organization**
- Separate files for each concern
- Clear function names and docstrings
- Configuration externalized to config.json
- Error handling throughout

✅ **Robustness**
- Handle missing config gracefully
- Handle invalid input gracefully
- Handle network failures gracefully
- Log all issues to console

---

## Next Steps

1. **User Review:** Review this plan and confirm all details
2. **File Creation:** Create file structure and config.json
3. **Implementation:** Implement each component following the phases
4. **Testing:** Test each component individually, then integration test
5. **Deployment:** Run with production card file

---

**Document Version:** 1.0  
**Last Updated:** October 19, 2025  
**Status:** Ready for Implementation
