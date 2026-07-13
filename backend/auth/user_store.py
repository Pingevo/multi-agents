"""UserStore — JSON-backed user profile storage at data/users.json."""

import hashlib
import json
import os
from datetime import datetime

from backend.auth.base import User


def _hash_password(password: str) -> str:
    """Hash password with SHA-256 + salt."""
    salt = "my_agent_app_2026"  # Fixed salt for dev — will improve with bcrypt later
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def _verify_password(password: str, hashed: str) -> bool:
    return _hash_password(password) == hashed


class UserStore:
    """เก็บข้อมูล user profile + password hash ใน JSON file"""

    def __init__(self, filepath: str | None = None):
        if filepath is None:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data",
            )
            os.makedirs(data_dir, exist_ok=True)
            filepath = os.path.join(data_dir, "users.json")
        self.filepath = filepath
        self.users: list[dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.users = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.users = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)

    def register(self, username: str, password: str) -> dict | None:
        """Register a new user. Returns profile if success, None if username taken."""
        user_id = f"dev_{username.lower()}"
        if self.get_by_id(user_id):
            return None  # Username already exists
        profile = {
            "user_id": user_id,
            "username": username,
            "email": "",
            "provider": "dev",
            "avatar_url": "",
            "password_hash": _hash_password(password),
            "created_at": datetime.now().isoformat(),
            "last_login": datetime.now().isoformat(),
        }
        self.users.append(profile)
        self._save()
        return profile

    def verify_password(self, user_id: str, password: str) -> bool:
        """Verify password for a user."""
        u = self.get_by_id(user_id)
        if not u:
            return False
        stored_hash = u.get("password_hash", "")
        if not stored_hash:
            return False  # No password set (legacy user)
        return _verify_password(password, stored_hash)

    def get_or_create(self, user: User) -> dict:
        """Get existing user profile or create new one (for OAuth — no password)."""
        existing = self.get_by_id(user.user_id)
        if existing:
            existing["last_login"] = datetime.now().isoformat()
            existing["username"] = user.username
            if user.email:
                existing["email"] = user.email
            if user.avatar_url:
                existing["avatar_url"] = user.avatar_url
            self._save()
            return existing

        profile = {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "provider": user.provider,
            "avatar_url": user.avatar_url,
            "created_at": datetime.now().isoformat(),
            "last_login": datetime.now().isoformat(),
        }
        self.users.append(profile)
        self._save()
        return profile

    def get_by_id(self, user_id: str) -> dict | None:
        for u in self.users:
            if u.get("user_id") == user_id:
                return u
        return None

    def update_last_login(self, user_id: str):
        u = self.get_by_id(user_id)
        if u:
            u["last_login"] = datetime.now().isoformat()
            self._save()
