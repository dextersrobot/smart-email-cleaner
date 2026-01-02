# 📧 Smart Email Cleaner

Automatically identify and clean up marketing emails, newsletters you never read, old unread messages, and inbox clutter — for both **Outlook** and **Gmail**.

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Mac%20%7C%20Linux-lightgrey.svg)

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📢 **Marketing Detection** | Identifies promotional emails, newsletters, and marketing campaigns |
| 🚫 **Never Opened** | Finds senders with 5+ emails you've never read |
| 😴 **Rarely Opened** | Detects senders with <20% read rate |
| 📆 **Old Unread** | Surfaces unread emails older than 30 days |
| 📬 **Bulk Senders** | Flags senders flooding your inbox (20+ emails) |
| 🔒 **Safe by Default** | Moves to trash (recoverable) instead of permanent deletion |

## 🚀 Quick Start

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/smart-email-cleaner.git
cd smart-email-cleaner

# Install dependencies
pip install -r requirements.txt
```

## 📮 Outlook / Hotmail Setup

The Outlook cleaner uses OAuth2 authentication — no app passwords needed!

```bash
python outlook/smart_email_cleaner.py
```

**First run:**
1. A browser window opens for Microsoft sign-in
2. Enter the code shown in the terminal
3. Sign in with your Outlook/Hotmail account
4. Approve the permissions
5. Return to terminal — you're in!

## 📬 Gmail Setup

Gmail requires a one-time Google Cloud setup (~5 minutes).

### Step 1: Create Google Cloud Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Navigate to **APIs & Services** → **Library**
4. Search for **Gmail API** and click **Enable**
5. Go to **APIs & Services** → **Credentials**
6. Click **Create Credentials** → **OAuth client ID**
7. Select **Desktop app** and give it a name
8. Click **Download JSON**
9. Rename the file to `credentials.json`
10. Place it in the `gmail/` folder

### Step 2: Run the Script

```bash
python gmail/smart_gmail_cleaner.py
```

**First run:**
1. A browser opens for Google sign-in
2. Sign in and approve permissions
3. Credentials are cached for future runs

## 🎯 Usage

Both scripts work the same way:

1. **Choose scan depth:**
   - Quick scan (1,000 emails)
   - Normal scan (5,000 emails)
   - Deep scan (10,000 emails)
   - Full scan (all emails)

2. **Review categories** — the script groups emails by:
   - Marketing/Promotional
   - Never Opened
   - Rarely Opened
   - Old Unread
   - Bulk Senders

3. **Clean up:**
   - Select specific categories
   - Pick individual senders
   - Or auto-clean everything

4. **Recover if needed** — all emails go to Trash first (30-day recovery window)

## 📁 Project Structure

```
smart-email-cleaner/
├── README.md
├── requirements.txt
├── LICENSE
├── outlook/
│   └── smart_email_cleaner.py    # Outlook/Hotmail cleaner
└── gmail/
    └── smart_gmail_cleaner.py    # Gmail cleaner
```

## 🔍 How Detection Works

### Marketing Email Detection

The script identifies marketing emails through:

- **Gmail Categories:** Uses Gmail's built-in Promotions/Social labels
- **Sender Patterns:** Detects `noreply@`, `newsletter@`, `marketing@`, etc.
- **Known Domains:** Recognizes major marketing platforms (Mailchimp, SendGrid, etc.)
- **Content Analysis:** Looks for "unsubscribe", "view in browser", promotional language

### Read Rate Analysis

For each sender, the script calculates:
- Total emails received
- How many you've opened
- Your "read rate" percentage

Senders with low read rates are flagged as potential cleanup candidates.

## ⚙️ Configuration

You can customize detection thresholds by editing the scripts:

```python
# Minimum emails to flag as "never opened"
NEVER_OPENED_THRESHOLD = 5

# Read rate below this = "rarely opened"
RARELY_OPENED_THRESHOLD = 0.2  # 20%

# Minimum emails to flag as "bulk sender"
BULK_SENDER_THRESHOLD = 20

# Days for "old unread" detection
OLD_EMAIL_DAYS = 30
```

## 🔒 Privacy & Security

- **Local Processing:** All analysis happens on your machine
- **No Data Collection:** Your emails are never sent to external servers
- **OAuth2 Authentication:** Secure, token-based authentication
- **Minimal Permissions:** Only requests necessary email access
- **Credentials Cached Locally:** Login tokens stored in your project folder

## 🤝 Contributing

Contributions are welcome! Feel free to:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Microsoft Graph API for Outlook integration
- Google Gmail API for Gmail integration
- Built with assistance from Claude AI

## 📧 Support

If you encounter any issues or have questions:
- Open an [Issue](https://github.com/YOUR_USERNAME/smart-email-cleaner/issues)
- Check existing issues for solutions

---

**⭐ If this project helped clean up your inbox, consider giving it a star!**
