# 🛡️ AI Defender Bot

AI Defender Bot is a security-focused automation bot designed to protect communities and servers against various malicious activities such as spam, raids, nukes, and suspicious AI-generated content.

---

## 📦 Project Structure

```
ai_defender_bot/
├── main.py                  # Entry point of the bot
├── config.py                # Configuration settings
├── .env                     # Environment variables (e.g., API keys, tokens)
├── database.db              # SQLite database for persistent data
├── requirements.txt         # Python dependencies
├── modules/                 # Security modules
│   ├── ai_detector.py       # Detect AI-generated spam/content
│   ├── anti_nuke.py        # Protection against nuking attacks
│   ├── anti_raid.py        # Protection against coordinated raids
│   ├── anti_spam.py        # General spam detection
│   └── watchdog.py         # Monitoring & alerting
└── utils/                   # Utility scripts
    ├── backup.py           # Backups and data recovery
    └── logger.py           # Logging and debugging utilities
```

---

## ⚙️ Setup Instructions

### 1️⃣ Clone or Download

```bash
git clone https://your-repo-link.git
cd ai_defender_bot
```

### 2️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ Configure Environment

Create and edit the `.env` file with required values:

```
BOT_TOKEN=your_bot_token_here
DATABASE_URL=sqlite:///database.db
OTHER_SECRET_KEY=value
```

*(Replace placeholders with actual keys)*

---

## ▶️ Running the Bot

```bash
python main.py
```

This starts the bot and activates all modules.

---

## 🧩 Modules Explained

| Module      | File                     | Purpose                                                            |
| ----------- | ------------------------ | ------------------------------------------------------------------ |
| AI Detector | `modules/ai_detector.py` | Detects AI-generated spam or content to reduce fake activity.      |
| Anti-Nuke   | `modules/anti_nuke.py`   | Prevents large-scale deletions and bans (nuking attempts).         |
| Anti-Raid   | `modules/anti_raid.py`   | Blocks mass joins or suspicious account patterns typical of raids. |
| Anti-Spam   | `modules/anti_spam.py`   | Monitors message frequency and patterns to block spam.             |
| Watchdog    | `modules/watchdog.py`    | Keeps track of bot activity and suspicious events, alerts admins.  |

---

## 🛠 Utilities

* **Logger (**\`\`**)**: Adds logs for events and module activities.
* **Backup (**\`\`**)**: Automates database or config backup for disaster recovery.

---

## 🗃 Database

* Uses `database.db` (SQLite) to store user states, logs, and module data.

---

## 📌 Notes

* Keep `.env` private (do NOT share publicly).
* Adjust thresholds and settings in `config.py` to fit your community’s needs.
* Test modules in a test server before deploying live.

---

## 🤝 Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request
