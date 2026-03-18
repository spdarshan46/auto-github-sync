🚀 Auto GitHub Sync

Auto GitHub Sync is a Python automation tool that monitors file changes and automatically commits and pushes updates to a development branch on GitHub.

This project demonstrates a developer workflow automation system similar to a lightweight CI/CD pipeline.

---

📌 Project Overview

The system watches a specific folder for file changes.
When a file is modified, created, or deleted, the script will automatically:

1. Detect the file change
2. Stage the changes
3. Commit with an automatic timestamp message
4. Push the update to a development branch
5. Optionally create a Pull Request to the main branch

This removes the need for manual Git commands during development.

---

🧠 Workflow

Developer edits files
        ↓
test_project folder
        ↓
Python watcher detects change
        ↓
Auto commit
        ↓
Push → dev branch
        ↓
Pull request created

---

📁 Project Structure

auto-github-sync
│
├── watcher
│   ├── auto_sync.py        # Main automation script
│   ├── config.json         # Configuration settings
│   │
│   ├── logs
│   │   └── activity.log    # Activity logs
│   │
│   └── test_project        # Folder monitored for changes
│       ├── index.html
│       └── script.js
│
└── .gitignore

---

⚙️ Requirements

- Python 3.8+
- Git installed
- GitHub repository
- GitHub Personal Access Token

Python libraries used:

watchdog
requests

Install dependencies:

pip install watchdog requests

---

⚙️ Configuration

The project uses a configuration file:

watcher/config.json

Example configuration:

{
  "github": {
    "username": "your-username",
    "repo": "auto-github-sync",
    "token": "your-github-token",
    "base_branch": "main",
    "dev_branch": "darshan-dev"
  },
  "monitoring": {
    "folder_to_watch": "test_project",
    "commit_delay": 5
  },
  "logging": {
    "log_file": "logs/activity.log",
    "log_level": "INFO"
  }
}

Update the following fields before running:

- "username" → your GitHub username
- "repo" → repository name
- "token" → GitHub Personal Access Token

---

▶️ Running the Project

Navigate to the watcher folder and run:

cd watcher
python auto_sync.py

The script will start monitoring the test_project folder.

---

🔄 Example Output

When a file is changed:

File changed: index.html
Processing pending changes...
Switched to existing branch: darshan-dev
Committed: Auto sync: 2026-03-17
Pushed to origin/darshan-dev
Pull request created
Sync completed successfully

---

🎯 Purpose of the Project

This project demonstrates:

- Git automation
- File system monitoring
- Automated commit workflows
- Dev branch management
- Basic CI/CD principles

---

👨‍💻 Author

S P Darshan
Backend & AI Engineer

GitHub
https://github.com/spdarshan46

---

📜 License

This project is for educational and experimentation purposes.
