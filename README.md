# Shopee Card Validation Automation

Fast, parallel credit card validation system for Shopee.ph with automatic invalid card detection and cleanup.

**✨ Now with Modern GUI!**

## ⚡ Quick Start for Beginners

**The Easiest Way (Windows):**

1. Download this project (green "Code" button → Download ZIP)
2. Extract the ZIP file
3. Double-click `start_gui.bat`
4. That's it! 🎉

The script automatically handles Python installation (if needed) and all dependencies. Just approve the UAC prompt if Python needs to be installed.

📖 **[Read the detailed step-by-step guide →](QUICKSTART.md)**

## 🖥️ Two Ways to Use

### Option 1: GUI Mode (Recommended for Beginners)

**🚀 Easy Launch (No Setup Required!):**

Just double-click `start_gui.bat` and you're done! The script will:
- ✅ Check if Python is installed (installs it automatically if needed - requires admin)
- ✅ Install all required dependencies automatically
- ✅ Launch the GUI

**Note:** If Python is not installed, you'll see a UAC prompt. Click "Yes" to allow installation.

**Or launch manually:**
```bash
python gui.py
```

**Features:**
- 🎨 Modern dark theme interface
- 📁 Easy file selection with browse buttons
- ⚙️ Visual settings controls (headless mode, workers)
- 📊 Real-time progress tracking
- 📋 Live activity log
- 🎯 One-click start/stop
- ⚡ Auto-setup with batch file

### Option 2: Command Line Mode (For Advanced Users)

## ⚡ Quick Start (CLI Mode)

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

### 3. Setup Telegram Notifications (Optional)

To receive instant notifications for successful cards via Telegram:

1. **Create a Telegram Bot:**
   - Open Telegram and chat with [@BotFather](https://t.me/BotFather)
   - Send `/newbot` and follow the instructions
   - Copy the Bot Token provided

2. **Get Your Chat ID:**
   - Start a chat with your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your `chat_id` in the JSON response

3. **Create `.env` file:**
   ```bash
   cp .env.example .env
   ```
   
4. **Edit `.env` and add your credentials:**
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=123456789
   ```

**Note:** Telegram notifications are optional. The script will work without them.

### 4. Prepare Card File

Create a text file (e.g., `cards.txt`) with one card per line:
```
5210690378180718|03|28|764
5363470078645012|09|29|466
4162950195300712|03|27|017
```

Format: `card_number|MM|YY|CVV`

### 5. Run

```bash
# Basic usage
python main.py cards.txt

# With headless mode (faster, no browser window)
python main.py cards.txt --headless

# With verbose logging
python main.py cards.txt -v

# Custom output paths (default: output/results.txt, output/failed.txt)
python main.py cards.txt --results custom/success.txt --failed custom/failures.txt
```

**Note:** Output files are cleared at the start of each session to prevent data mixing.

## 📊 Output

The script creates three output files in the `output/` folder:

- **`output/results.txt`** - Successfully linked cards (format: `card|mm|yy|cvv`)
- **`output/failed.txt`** - Failed cards with reasons (format: `card|mm|yy|cvv | reason`)
- **`output/3ds.txt`** - Cards requiring 3D Secure verification (format: `card|mm|yy|cvv`)

**⚠️ Important:** All output files are **automatically cleared** at the start of each new processing session to ensure fresh results.

## 🚀 Features

- **Parallel Processing**: Multiple browser instances (configurable workers)
- **Smart Detection**: Auto-detects 3DS, success, failures, and invalid cards
- **Auto Cleanup**: Removes invalid/expired cards from input file
- **Error Popup Detection**: Catches invalid card popups immediately
- **Progress Tracking**: Real-time colored console output
- **Headless Mode**: Run without visible browser windows
- **Telegram Notifications**: Instant alerts for successful cards (optional)

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

## 📱 Telegram Notifications

When configured, successful cards trigger instant Telegram messages with:

- ✅ **Success Badge**
- 💳 **Full Card Details** (number, expiry, CVV)
- 🔒 **Masked Version** (for security)
- 📝 **Response Message** from Shopee
- 🕒 **Timestamp**

**Example Message:**
```
✅ Card Validation Success
━━━━━━━━━━━━━━━━━━━━

💳 Card Number: 5210690378180718
🔒 Masked: 521069******0718
📅 Expiry: 03/28
🔐 CVV: 764

📝 Response:
This card is now active for all payments.

━━━━━━━━━━━━━━━━━━━━
🕒 2025-10-19 14:32:15
```

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
