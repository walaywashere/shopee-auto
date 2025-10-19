# 🚀 Quick Start Guide

## For Complete Beginners (Windows)

### Step 1: Download
1. Click the green **"Code"** button on GitHub
2. Click **"Download ZIP"**
3. Extract the ZIP file to a folder (e.g., `C:\shopee-auto`)

### Step 2: Launch
1. Double-click **`start_gui.bat`**
2. If Python is not installed:
   - The script will download it automatically
   - Click **"Yes"** when Windows asks for permission (UAC prompt)
   - Wait for installation (1-2 minutes)
   - **Close the window** and run `start_gui.bat` again

3. The script will automatically:
   - ✅ Install all required packages
   - ✅ Launch the beautiful GUI

### Step 3: Setup
1. **Get Cookies** (Required):
   - Open Chrome and go to https://shopee.ph
   - Log in to your account
   - Press **F12** to open Developer Tools
   - Go to: **Application** → **Cookies** → **https://shopee.ph**
   - Copy all cookies into `cookies.txt` (one per line or semicolon-separated)

2. **Prepare Card File**:
   - Create a text file (e.g., `cards.txt`)
   - Add cards in this format: `4111111111111111|01|25|123`
   - One card per line

3. **Optional - Telegram Notifications**:
   - Click the **Settings** button in the GUI
   - Enter your Bot Token and Chat ID
   - Get these from @BotFather and @userinfobot on Telegram

### Step 4: Run
1. In the GUI, click **Browse** to select your card file
2. Adjust settings if needed (workers, headless mode)
3. Click **Start Processing**
4. Watch the magic happen! ✨

## Troubleshooting

**"Python is not installed" even after installation?**
- Close ALL command windows and try again
- Restart your computer if needed

**"Dependencies failed to install"?**
- Open Command Prompt and run: `pip install -r requirements.txt`
- Make sure you have internet connection

**"Session verification failed"?**
- Your cookies are expired
- Get fresh cookies from shopee.ph

**GUI doesn't open?**
- Right-click `start_gui.bat` → **Run as Administrator**
- Check if Python 3.8+ is installed: `python --version`

## Output Files

All results are saved in the `output/` folder:
- **results.txt** - Successfully linked cards
- **failed.txt** - Failed cards with reasons
- **3ds.txt** - Cards requiring manual verification

**Important:** Files are cleared at the start of each new session!

## Need Help?

Check the main **README.md** for detailed documentation and advanced features.

---

**⚠️ Disclaimer**: Educational purposes only. Use responsibly.
