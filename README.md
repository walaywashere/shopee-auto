# Shopee Card Validation Automation

A high-performance, parallel card validation system for Shopee.ph that automates credit card enrollment checking using multiple browser instances.

## 🚀 Features

- **Parallel Processing**: Multi-worker architecture with dedicated browser instances (default: 3 workers)
- **Smart Status Detection**: Automatically identifies 3DS challenges, successful links, and failures
- **Robust Form Filling**: CDP-based input without window focus requirements
- **Network Intelligence**: Intercepts and analyzes API responses for accurate status determination
- **Automatic Retry**: Up to 2 retries per card with intelligent error handling
- **Session Management**: Persistent cookies for authenticated sessions
- **Progress Tracking**: Real-time color-coded console output with card-by-card results
- **Auto Cleanup**: Removes processed cards from input file to prevent reprocessing

## 📋 Requirements

- Python 3.8+
- Chrome/Chromium browser
- Required Python packages:
  - `nodriver` - Undetected Chrome automation
  - `colorama` - Colored terminal output

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/walaywashere/shopee-auto.git
cd shopee-auto
```

2. Install dependencies:
```bash
pip install nodriver colorama
```

3. Prepare your session cookies in `cookies.txt` (header format):
```
name1=value1; name2=value2; ...
```

## 📝 Usage

### Basic Usage

```bash
python main.py cards.txt
```

### Advanced Options

```bash
python main.py cards.txt --config config.json --cookies cookies.txt --results results.txt --verbose
```

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `card_file` | Path to input card file (required) | - |
| `--config` | Configuration file path | `config.json` |
| `--cookies` | Session cookies file | `cookies.txt` |
| `--results` | Output file for successful cards | `results.txt` |
| `--headless` | Run browser in headless mode | `False` |
| `--keep-browser-open` | Keep browser open after completion | `False` |
| `--verbose` / `-v` | Show detailed INFO logs | `False` |

## 📂 Project Structure

```
shopee-auto/
├── main.py                     # CLI entry point
├── config.json                 # Configuration (XPaths, timeouts, URLs)
├── cookies.txt                 # Session authentication cookies
├── results.txt                 # Output for successful cards
├── PLAN.md                     # Detailed implementation plan
├── README.md                   # This file
│
├── core/
│   ├── browser_manager.py      # Browser lifecycle & session management
│   ├── checker.py              # Queue-based parallel worker orchestration
│   ├── tab_manager.py          # Form filling using CDP
│   └── response_analyzer.py    # API response parsing & status detection
│
├── input/
│   └── card_processor.py       # Card validation & file management
│
├── utils/
│   └── helpers.py              # Logging, config loading, async utilities
│
└── tests/
    ├── test_card_processor.py  # Card processing tests
    ├── test_checker.py         # Checker orchestration tests
    ├── test_extraction.py      # Response extraction tests
    └── test_xpath_escape.py    # XPath escaping tests
```

## 💳 Card Input Format

Cards should be formatted as: `card_number|MM|YY|CVV`

**Example (`cards.txt`):**
```
5210690378180718|03|28|764
5363470078645012|09|29|466
4162950195300712|03|27|017
```

### Card Validation

Each card is validated before processing:
- **Luhn algorithm** checksum verification
- Month: 01-12
- Year: 2-digit, not expired
- CVV: 3-4 digits

## ⚙️ Configuration

Edit `config.json` to customize behavior:

```json
{
  "browser": {
    "headless": false
  },
  "workers": 3,
  "timeouts": {
    "page_load": 10,
    "element_wait": 8,
    "api_response": 15
  },
  "delays": {
    "between_cards": 0.5,
    "retry_delay": 1
  },
  "batch_size": 5,
  "max_retries": 2,
  "cardholder_name": "roja kun"
}
```

### Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `browser.headless` | boolean | Run browser in headless mode |
| `workers` | int | Number of parallel browser instances |
| `timeouts.page_load` | int | Seconds to wait for page load |
| `timeouts.element_wait` | int | Seconds to wait for form elements |
| `timeouts.api_response` | int | Seconds to wait for API response |
| `delays.between_cards` | float | Delay between card submissions |
| `delays.retry_delay` | int | Delay before retrying failed card |
| `batch_size` | int | Cards per batch (legacy setting) |
| `max_retries` | int | Maximum retry attempts per card |
| `cardholder_name` | string | Name used for all submissions |

## 📊 Status Indicators

The system identifies three main statuses:

| Status | Color | Description |
|--------|-------|-------------|
| `[SUCCESS]` | 🟢 Green | Card successfully linked to account |
| `[FAILED]` | 🔴 Red | Card rejected (with detailed reason) |
| `[3DS]` | 🔵 Cyan | 3D Secure challenge triggered |

## 📈 Output Format

### Console Output

```
[INFO] Worker 1 processing card 1/100
[1/100] [SUCCESS] 5210690378180718|03|28|764 - Card successfully linked
[2/100] [FAILED] 5363470078645012|09|29|466 - Payment declined by bank
[3/100] [3DS] 4162950195300712|03|27|017 - Challenge flow triggered
```

### Results File

Only successful cards are written to `results.txt`:
```
5210690378180718|03|28|764
5496272026009998|04|27|444
5363470075654959|02|29|633
```

### Summary

After processing all cards:
```
==================== SUMMARY ====================
Total Processed: 100
Success: 45
Failed: 50
3DS: 5
=================================================
```

## 🔍 How It Works

### 1. Initialization
- Loads configuration and validates input file
- Initializes multiple browser instances (one per worker)
- Loads session cookies into each browser
- Verifies Shopee session authentication

### 2. Parallel Processing
- Cards are added to a shared asyncio queue
- Each worker pulls cards from the queue independently
- Workers process cards concurrently for maximum speed

### 3. Card Processing
Each card goes through:
1. **Tab Creation**: Opens payment form in new tab
2. **Network Interception**: Sets up CDP listeners for API responses
3. **Form Filling**: Fills card number, expiry, CVV, and name using CDP
4. **Submission**: Clicks submit button
5. **Response Analysis**: Intercepts API response or analyzes result page
6. **Status Determination**: Identifies SUCCESS/FAILED/3DS status

### 4. Status Detection Logic

```
API Response Available?
├─ Yes: Check "is_challenge_flow"
│   ├─ true → [3DS]
│   └─ false → Wait for result page → Analyze text → [SUCCESS] or [FAILED]
└─ No (page navigated): Check current URL
    ├─ Result page → Extract message → [SUCCESS] or [FAILED]
    └─ Other → [3DS]
```

### 5. Error Handling
- Retries failed attempts (up to 2 times)
- Clears stale responses from queue
- Logs detailed error information
- Continues processing remaining cards

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
python -m unittest discover tests

# Run specific test file
python -m unittest tests.test_card_processor

# Run with verbose output
python -m unittest discover tests -v
```

## 🛠️ Development

### Adding New Features

1. **New Status Detection**: Modify `core/response_analyzer.py`
2. **Form Field Changes**: Update XPaths in `config.json`
3. **Timeout Adjustments**: Modify timeouts in `config.json`
4. **New Validation Rules**: Edit `input/card_processor.py`

### Debug Mode

Enable verbose logging to see detailed execution flow:

```bash
python main.py cards.txt --verbose
```

## ⚠️ Important Notes

1. **Session Cookies**: Ensure your `cookies.txt` contains valid, authenticated session cookies
2. **Rate Limiting**: The system includes delays to avoid triggering rate limits
3. **Proxy Support**: Currently not implemented, add if needed
4. **Headless Mode**: Some sites detect headless browsers; use headed mode if issues occur
5. **Card Security**: Handle card data responsibly and securely

## 🔒 Security Considerations

- Never commit `cookies.txt` or card files to version control
- Use `.gitignore` to exclude sensitive files
- Store card data encrypted at rest
- Follow PCI DSS guidelines when handling card information
- Rotate session cookies regularly

## 📌 Performance

- **Speed**: ~3x faster than sequential processing
- **Throughput**: ~100-120 cards per hour (3 workers)
- **Resource Usage**: ~500MB RAM per worker
- **Browser Overhead**: Each worker requires a Chrome instance

### Optimization Tips

1. **Increase Workers**: More workers = faster processing (up to CPU limit)
2. **Reduce Delays**: Lower `between_cards` delay (risk: rate limiting)
3. **Headless Mode**: Slightly faster, uses less resources
4. **SSD Storage**: Faster for Chrome profile operations

## 🐛 Troubleshooting

### Common Issues

**"Cookie file not found"**
- Ensure `cookies.txt` exists in project root
- Check file path in command line arguments

**"Session verification failed"**
- Cookies may be expired or invalid
- Log in to Shopee.ph and extract fresh cookies

**"Element not found" errors**
- Shopee may have updated their UI
- Update XPaths in `config.json`
- Run with `--verbose` to see detailed logs

**Browser crashes**
- Reduce number of workers
- Increase system RAM
- Close other applications

**Rate limiting**
- Increase `delays.between_cards`
- Reduce number of workers
- Add proxy rotation (requires code modification)

## 📄 License

This project is for educational purposes only. Use responsibly and in accordance with Shopee's Terms of Service.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📧 Contact

Project Link: [https://github.com/walaywashere/shopee-auto](https://github.com/walaywashere/shopee-auto)

---

**⚠️ Disclaimer**: This tool is for educational and testing purposes only. Users are responsible for ensuring their usage complies with applicable laws and terms of service.
