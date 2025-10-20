# 🚀 Quick Start Guide

## For Complete Beginners (Windows)

### Step 1: Install Python (One-Time Setup)
1. Go to https://www.python.org/downloads/
2. Download the latest Python 3.x version
3. Run the installer
4. ⚠️ **CRITICAL**: Check the box "Add Python to PATH"
5. Click "Install Now"
6. Wait for installation to complete

### Step 2: Download
1. Click the green **"Code"** button on GitHub
2. Click **"Download ZIP"**
3. Extract the ZIP file to a folder (e.g., `C:\shopee-auto`)

### Step 3: Launch
1. Double-click **`start_gui.bat`**
2. The script will automatically:
   - ✅ Detect your Python installation
   - ✅ Install all required packages (first run only)
   - ✅ Launch the beautiful GUI

### Step 4: Setup
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

**"Python is not installed or not in PATH"?**
- Install Python from https://www.python.org/downloads/
- During installation, CHECK the box "Add Python to PATH"
- Restart your computer after installation
- Run `start_gui.bat` again

**Dependencies failed to install?**
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
