# ============================================================================
# IIStudio — Аутентификация (JWT + API токены)
# ============================================================================

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Хранилище пользователей в JSON (simple, без PostgreSQL)
USERS_FILE = Path(".iistudio/users.json")
TOKENS_FILE = Path(".iistudio/api_tokens.json")


def _load_db(path: Path) -> Dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def _save_db(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _hash_password(password: str) -> str:
    """SHA-256 хэш пароля с солью."""
    salt = os.urandom(16).hex()
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == h
    except Exception:
        return False


def _generate_token() -> str:
    """Генерировать API токен в формате sk-iis-xxxx."""
    rand = secrets.token_hex(24)
    return f"sk-iis-{rand}"


class UserDB:
    """Простая файловая БД пользователей."""

    def __init__(self) -> None:
        self._users = _load_db(USERS_FILE)
        self._tokens = _load_db(TOKENS_FILE)

    def _save(self) -> None:
        _save_db(USERS_FILE, self._users)
        _save_db(TOKENS_FILE, self._tokens)

    # ── Пользователи ─────────────────────────────────────────────────────────

    def register(self, email: str, password: str, username: str = "") -> Dict[str, Any]:
        """Зарегистрировать нового пользователя."""
        email = email.lower().strip()
        if email in self._users:
            raise ValueError("Email уже используется")

        user_id = secrets.token_hex(16)
        user = {
            "id": user_id,
            "email": email,
            "username": username or email.split("@")[0],
            "password_hash": _hash_password(password),
            "is_active": True,
            "is_admin": False,
            "plan": "free",
            "balance_usd": 2000.0,  # $2000 приветственный бонус
            "free_tokens": 500000,  # 500K токенов приветственный бонус
            "total_spent": 0.0,
            "requests_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None,
        }
        self._users[email] = user

        # Создаём первый API токен автоматически
        token = self.create_token(user_id, email, name="Default")
        self._save()
        return {**user, "token": token["token"]}

    def login(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Войти. Возвращает пользователя или None."""
        email = email.lower().strip()
        user = self._users.get(email)
        if not user:
            return None
        if not _verify_password(password, user["password_hash"]):
            return None
        user["last_login"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return user

    def get_user(self, email: str) -> Optional[Dict]:
        return self._users.get(email.lower())

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        for user in self._users.values():
            if user["id"] == user_id:
                return user
        return None

    # ── API Токены ────────────────────────────────────────────────────────────

    def create_token(self, user_id: str, email: str, name: str = "Default") -> Dict:
        token_str = _generate_token()
        prefix = token_str[:14]  # sk-iis-xxxxxx
        token = {
            "id": secrets.token_hex(8),
            "user_id": user_id,
            "email": email,
            "name": name,
            "token": token_str,
            "prefix": prefix,
            "is_active": True,
            "requests_count": 0,
            "last_used": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if user_id not in self._tokens:
            self._tokens[user_id] = []
        self._tokens[user_id].append(token)
        self._save()
        return token

    def get_tokens(self, user_id: str) -> list:
        return self._tokens.get(user_id, [])

    def verify_token(self, token_str: str) -> Optional[Dict]:
        """Проверить API токен. Возвращает user dict или None."""
        for user_id, tokens in self._tokens.items():
            for t in tokens:
                if t["token"] == token_str and t["is_active"]:
                    t["last_used"] = datetime.now(timezone.utc).isoformat()
                    t["requests_count"] += 1
                    self._save()
                    return self.get_user_by_id(user_id)
        return None

    def revoke_token(self, user_id: str, token_id: str) -> bool:
        tokens = self._tokens.get(user_id, [])
        for t in tokens:
            if t["id"] == token_id:
                t["is_active"] = False
                self._save()
                return True
        return False

    def delete_token(self, user_id: str, token_id: str) -> bool:
        tokens = self._tokens.get(user_id, [])
        new_tokens = [t for t in tokens if t["id"] != token_id]
        if len(new_tokens) != len(tokens):
            self._tokens[user_id] = new_tokens
            self._save()
            return True
        return False

    # ── Баланс и использование ────────────────────────────────────────────────

    def deduct_tokens(self, user_id: str, tokens: int, model: str, cost_usd: float) -> bool:
        """Списать токены за использование API."""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        # Сначала используем бесплатные токены
        if user["free_tokens"] >= tokens:
            user["free_tokens"] -= tokens
        else:
            remaining = tokens - user["free_tokens"]
            user["free_tokens"] = 0
            if user["balance_usd"] < cost_usd:
                return False  # Недостаточно баланса
            user["balance_usd"] -= cost_usd

        user["total_spent"] += cost_usd
        user["requests_count"] += 1
        self._save()
        return True

    def topup(self, user_id: str, amount_usd: float, description: str = "Пополнение") -> bool:
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        user["balance_usd"] += amount_usd
        self._save()
        return True


# Singleton
_db: Optional[UserDB] = None


def get_db() -> UserDB:
    global _db
    if _db is None:
        _db = UserDB()
    return _db
