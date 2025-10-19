# Shopee Card Validation Automation

Fast, parallel credit card validation system for Shopee.ph with automatic invalid card detection and cleanup.

## ⚡ Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Cookies

Create a `cookies.txt` file with your Shopee session cookies in this format:
```
cookie_name1=value1; cookie_name2=value2; cookie_name3=value3
```

**How to get cookies:**
1. Log in to shopee.ph in your browser
2. Open Developer Tools (F12)
3. Go to Application/Storage → Cookies → https://shopee.ph
4. Copy all cookie values in the format above

### 3. Prepare Card File

Create a text file (e.g., `cards.txt`) with one card per line:
```
5210690378180718|03|28|764
5363470078645012|09|29|466
4162950195300712|03|27|017
```

Format: `card_number|MM|YY|CVV`

### 4. Run

```bash
# Basic usage
python main.py cards.txt

# With headless mode (faster, no browser window)
python main.py cards.txt --headless

# With verbose logging
python main.py cards.txt -v

# Custom output files
python main.py cards.txt --results success.txt --failed failures.txt
```

## � Output

The script creates two output files:

- **`results.txt`** - Successfully linked cards (format: `card|mm|yy|cvv`)
- **`failed.txt`** - Failed cards with reasons (format: `card|mm|yy|cvv | reason`)

## 🚀 Features

- **Parallel Processing**: Multiple browser instances (configurable workers)
- **Smart Detection**: Auto-detects 3DS, success, failures, and invalid cards
- **Auto Cleanup**: Removes invalid/expired cards from input file
- **Error Popup Detection**: Catches invalid card popups immediately
- **Progress Tracking**: Real-time colored console output
- **Headless Mode**: Run without visible browser windows

## ⚙️ Configuration

Edit `config.json` to customize:

```json
{
  "browser": { "headless": true },
  "workers": 5,
  "timeouts": {
    "api_response": 15,
    "error_popup_check": 1
  },
  "max_retries": 2,
  "cardholder_name": "roja kun"
}
```

**Key Settings:**
- `workers`: Number of parallel browser instances (1-10)
- `headless`: true = faster, no browser window visible
- `max_retries`: How many times to retry failed cards

## 📊 Status Indicators

| Status | Description |
|--------|-------------|
| `[SUCCESS]` 🟢 | Card successfully linked |
| `[FAILED]` 🔴 | Card rejected (reason provided) |
| `[3DS]` 🔵 | 3D Secure challenge (requires manual verification) |

## 📈 Example Output

```
[INFO] Validated 100 cards out of 105
[INFO] Processing 100 cards with 5 concurrent workers
[1/100] [SUCCESS] 5210690378180718|03|28|764 - Card successfully linked
[2/100] [FAILED] 5363470078645012|09|29|466 - Payment declined
[3/100] [3DS] 4162950195300712|03|27|017 - Challenge flow triggered
...
==================== SUMMARY ====================
Total Processed: 100
Success: 45
Failed: 50
3DS: 5
=================================================
```

## 🔧 Troubleshooting

**Session verification failed?**
- Your cookies may be expired
- Log in to shopee.ph and get fresh cookies

**Browser crashes?**
- Reduce workers in config.json
- Try headless mode: `--headless`

**Cards not processing?**
- Check card format: `number|MM|YY|CVV`
- Ensure cards are not expired
- Invalid cards are auto-removed from input file

## 📄 License

Educational purposes only. Use responsibly and in accordance with Shopee's Terms of Service.

---

**⚠️ Disclaimer**: This tool is for educational and testing purposes only. Users are responsible for ensuring their usage complies with applicable laws and terms of service.
````
