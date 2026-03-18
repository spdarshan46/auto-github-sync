#!/usr/bin/env python3
"""
Automatic GitHub Sync with Safe Workflow
Monitors file changes, auto-commits to dev branch, and creates pull requests
"""

import os
import sys
import time
import json
import logging
import subprocess
import codecs
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests

# ==================== FIX WINDOWS CONSOLE ENCODING ====================
if sys.platform == "win32":
    # Try to set stdout to UTF-8
    if sys.stdout.encoding != 'utf-8':
        try:
            # Python 3.7+
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            # Older Python fallback
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    # If still not UTF-8, show a hint
    if sys.stdout.encoding != 'utf-8':
        print("⚠️ For proper emoji display, run: chcp 65001")

# ==================== CONFIGURATION ====================

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "github": {
        "username": "your-username",
        "repo": "auto-github-sync",
        "token": "your-github-token",
        "base_branch": "main",
        "dev_branch": "darshan-dev"
    },
    "monitoring": {
        "folder_to_watch": "test_project",
        "commit_delay": 5,  # seconds to wait before committing
        "ignore_patterns": [".git", "__pycache__", "*.pyc", ".DS_Store"]
    },
    "logging": {
        "log_file": "logs/activity.log",
        "log_level": "INFO"
    }
}

# ==================== LOGGING SETUP ====================

def setup_logging(log_file):
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# ==================== CONFIG MANAGER ====================

class ConfigManager:
    """Manage configuration loading and saving"""
    
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """Load configuration from file and merge with defaults to fill missing keys"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                print(f"✅ Configuration loaded from {self.config_file}")
                # Merge loaded config with defaults to ensure all keys exist
                config = self._merge_configs(DEFAULT_CONFIG, loaded_config)
                return config
            except Exception as e:
                print(f"⚠️ Error loading config: {e}")
                return DEFAULT_CONFIG.copy()
        else:
            # Save default config
            self.save_config(DEFAULT_CONFIG)
            print(f"⚠️ Please update {self.config_file} with your GitHub credentials")
            return DEFAULT_CONFIG.copy()
    
    def _merge_configs(self, default, loaded):
        """Recursively merge loaded config into default, preserving loaded values"""
        merged = default.copy()
        for key, value in loaded.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        return merged
    
    def save_config(self, config):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)
    
    def get(self, key, default=None):
        """Get config value by dot notation (e.g., 'github.username')"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

# ==================== GIT AUTOMATION ====================

class GitAutomation:
    """Handle Git operations"""
    
    def __init__(self, repo_path, config, logger):
        self.repo_path = repo_path
        self.config = config
        self.logger = logger
        self.dev_branch = config.get('github.dev_branch')
        self.base_branch = config.get('github.base_branch')
    
    def run_git_command(self, command):
        """Execute a git command and return output"""
        try:
            result = subprocess.run(
                command,
                cwd=self.repo_path,
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip()
    
    def is_git_repo(self):
        """Check if current directory is a git repository"""
        success, _ = self.run_git_command("git rev-parse --git-dir")
        return success
    
    def get_current_branch(self):
        """Get current branch name"""
        success, branch = self.run_git_command("git rev-parse --abbrev-ref HEAD")
        return branch if success else None
    
    def switch_to_dev_branch(self):
        """Switch to or create dev branch"""
        # Check if dev branch exists
        success, branches = self.run_git_command("git branch")
        
        if self.dev_branch in branches:
            # Switch to existing branch
            success, output = self.run_git_command(f"git checkout {self.dev_branch}")
            if success:
                self.logger.info(f"Switched to existing branch: {self.dev_branch}")
                return True
        else:
            # Create and switch to new branch
            success, output = self.run_git_command(f"git checkout -b {self.dev_branch}")
            if success:
                self.logger.info(f"Created and switched to branch: {self.dev_branch}")
                return True
        
        return False
    
    def commit_changes(self, message):
        """Commit all changes"""
        # Add all changes
        success, output = self.run_git_command("git add .")
        if not success:
            self.logger.error(f"Failed to add files: {output}")
            return False
        
        # Check if there's anything to commit
        success, status = self.run_git_command("git status --porcelain")
        if not status:  # No changes to commit
            self.logger.info("No changes to commit")
            return True
        
        # Commit changes
        success, output = self.run_git_command(f'git commit -m "{message}"')
        if success:
            self.logger.info(f"Committed: {message}")
            return True
        else:
            self.logger.error(f"Commit failed: {output}")
            return False
    
    def push_to_branch(self):
        """Push commits to remote dev branch"""
        success, output = self.run_git_command(f"git push -u origin {self.dev_branch}")
        if success:
            self.logger.info(f"Pushed to origin/{self.dev_branch}")
            return True
        else:
            self.logger.error(f"Push failed: {output}")
            return False

# ==================== GITHUB API ====================

class GitHubAPI:
    """Handle GitHub API operations"""
    
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.username = config.get('github.username')
        self.repo = config.get('github.repo')
        self.token = config.get('github.token')
        self.base_branch = config.get('github.base_branch')
        self.dev_branch = config.get('github.dev_branch')
        
        self.api_url = f"https://api.github.com/repos/{self.username}/{self.repo}"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def create_pull_request(self, title="Auto Sync Update"):
        """Create a pull request from dev branch to main"""
        if not self.token or self.token == "your-github-token":
            self.logger.warning("GitHub token not configured. Skipping PR creation.")
            return None
        
        pr_data = {
            "title": title,
            "head": self.dev_branch,
            "base": self.base_branch,
            "body": f"Automated pull request created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "maintainer_can_modify": True
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/pulls",
                headers=self.headers,
                json=pr_data
            )
            
            if response.status_code == 201:
                pr_url = response.json().get('html_url')
                self.logger.info(f"✅ Pull request created: {pr_url}")
                return pr_url
            elif response.status_code == 422:
                # PR might already exist
                self.logger.info("Pull request may already exist. Checking...")
                return self.check_existing_pr()
            else:
                self.logger.error(f"Failed to create PR: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating pull request: {e}")
            return None
    
    def check_existing_pr(self):
        """Check if a PR already exists for this branch"""
        try:
            response = requests.get(
                f"{self.api_url}/pulls",
                headers=self.headers,
                params={"head": f"{self.username}:{self.dev_branch}", "state": "open"}
            )
            
            if response.status_code == 200 and response.json():
                prs = response.json()
                if prs:
                    self.logger.info(f"Existing PR found: {prs[0].get('html_url')}")
                    return prs[0].get('html_url')
            
            return None
        except Exception as e:
            self.logger.error(f"Error checking existing PR: {e}")
            return None

# ==================== FILE WATCHER ====================

class ChangeHandler(FileSystemEventHandler):
    """Handle file system events"""
    
    def __init__(self, git_automation, github_api, logger, commit_delay=5):
        self.git_automation = git_automation
        self.github_api = github_api
        self.logger = logger
        self.commit_delay = commit_delay
        self.last_commit_time = 0
        self.pending_changes = False
        self.watched_folder = git_automation.config.get('monitoring.folder_to_watch')
        self.ignore_patterns = git_automation.config.get('monitoring.ignore_patterns', [])
    
    def should_ignore(self, path):
        """Check if path should be ignored"""
        for pattern in self.ignore_patterns:
            if pattern in path:
                return True
        return False
    
    def on_modified(self, event):
        """Called when a file is modified"""
        if event.is_directory:
            return
        
        # Check if we should ignore this path
        if self.should_ignore(event.src_path):
            return
        
        # Only watch files in the specified folder
        if self.watched_folder and self.watched_folder not in event.src_path:
            return
        
        self.logger.info(f"📝 File changed: {os.path.basename(event.src_path)}")
        self.pending_changes = True
        
        # Schedule commit after delay
        current_time = time.time()
        if current_time - self.last_commit_time > self.commit_delay:
            time.sleep(self.commit_delay)
            if self.pending_changes:
                self.commit_and_push()
    
    def on_created(self, event):
        """Called when a file is created"""
        if event.is_directory:
            return
        
        if self.should_ignore(event.src_path):
            return
        
        if self.watched_folder and self.watched_folder not in event.src_path:
            return
        
        self.logger.info(f"📄 File created: {os.path.basename(event.src_path)}")
        self.pending_changes = True
    
    def on_deleted(self, event):
        """Called when a file is deleted"""
        if event.is_directory:
            return
        
        if self.should_ignore(event.src_path):
            return
        
        if self.watched_folder and self.watched_folder not in event.src_path:
            return
        
        self.logger.info(f"🗑️ File deleted: {os.path.basename(event.src_path)}")
        self.pending_changes = True
    
    def commit_and_push(self):
        """Commit changes and push to remote"""
        self.logger.info("🔄 Processing pending changes...")
        
        # Ensure we're on dev branch
        if not self.git_automation.switch_to_dev_branch():
            self.logger.error("Failed to switch to dev branch")
            return
        
        # Commit changes
        commit_msg = f"Auto sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if self.git_automation.commit_changes(commit_msg):
            # Push to remote
            if self.git_automation.push_to_branch():
                # Create pull request
                self.github_api.create_pull_request()
                self.logger.info("✅ Sync completed successfully")
            else:
                self.logger.error("❌ Push failed")
        else:
            self.logger.error("❌ Commit failed")
        
        self.pending_changes = False
        self.last_commit_time = time.time()

# ==================== MAIN APPLICATION ====================

class AutoGitSync:
    """Main application class"""
    
    def __init__(self):
        self.config_manager = ConfigManager(CONFIG_FILE)
        self.config = self.config_manager.config
        
        # Setup logging
        log_file = self.config.get('logging', {}).get('log_file', 'logs/activity.log')
        self.logger = setup_logging(log_file)
        
        # Get repo path (current directory)
        self.repo_path = os.getcwd()
        
        # Initialize components
        self.git_automation = GitAutomation(self.repo_path, self.config_manager, self.logger)
        self.github_api = GitHubAPI(self.config_manager, self.logger)
        
        # Verify git repository
        if not self.git_automation.is_git_repo():
            self.logger.error("Not a git repository. Please run this script from the repo root.")
            exit(1)
        
        # Get folder to watch
        self.watch_folder = os.path.join(
            self.repo_path, 
            self.config.get('monitoring', {}).get('folder_to_watch', 'test_project')
        )
        
        # Create watch folder if it doesn't exist
        if not os.path.exists(self.watch_folder):
            os.makedirs(self.watch_folder)
            self.logger.info(f"Created watch folder: {self.watch_folder}")
    
    def run(self):
        """Start the file watcher"""
        self.logger.info("="*50)
        self.logger.info("🚀 Auto Git Sync Started")
        self.logger.info(f"📁 Watching folder: {self.watch_folder}")
        self.logger.info(f"🌿 Development branch: {self.config.get('github.dev_branch')}")
        self.logger.info(f"🎯 Base branch: {self.config.get('github.base_branch')}")
        self.logger.info(f"⏱️ Commit delay: {self.config.get('monitoring.commit_delay')} seconds")
        self.logger.info("="*50)
        
        # Setup event handler
        event_handler = ChangeHandler(
            self.git_automation, 
            self.github_api, 
            self.logger,
            commit_delay=self.config.get('monitoring.commit_delay', 5)
        )
        
        # Setup observer
        observer = Observer()
        observer.schedule(event_handler, self.watch_folder, recursive=True)
        observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("🛑 Stopping file watcher...")
            observer.stop()
        
        observer.join()
        self.logger.info("👋 Goodbye!")

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    # Check if running first time
    if not os.path.exists(CONFIG_FILE):
        print("\n" + "="*60)
        print("📋 FIRST TIME SETUP")
        print("="*60)
        print("\nPlease update config.json with your GitHub credentials:\n")
        print("1. Open config.json")
        print("2. Set your GitHub username")
        print("3. Set your repository name")
        print("4. Add your GitHub Personal Access Token")
        print("\n   How to get a token:")
        print("   - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)")
        print("   - Generate new token with 'repo' scope")
        print("   - Copy the token")
        print("\n5. Save the file and run this script again")
        print("="*60 + "\n")
        
        # Create default config
        ConfigManager(CONFIG_FILE)
        
        # Create test project files
        os.makedirs("test_project", exist_ok=True)
        with open("test_project/index.html", "w") as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Auto Sync Test</title>
</head>
<body>
    <h1>Hello from Auto Git Sync!</h1>
    <script src="script.js"></script>
</body>
</html>""")
        
        with open("test_project/script.js", "w") as f:
            f.write('console.log("Auto Git Sync is working!");')
        
        print("✅ Created test_project with sample files")
    else:
        # Run the application
        app = AutoGitSync()
        app.run()