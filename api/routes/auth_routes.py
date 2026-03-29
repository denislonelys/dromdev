# ============================================================================
# IIStudio — API роуты: /api/auth, /api/tokens, /api/balance
# ============================================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, EmailStr, Field

from api.auth import get_db

router = APIRouter(prefix="/auth", tags=["auth"])
tokens_router = APIRouter(prefix="/tokens", tags=["tokens"])
balance_router = APIRouter(prefix="/balance", tags=["balance"])
user_router = APIRouter(prefix="/user", tags=["user"])


# ── Схемы ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(..., description="Email адрес")
    password: str = Field(..., min_length=6, description="Пароль (мин. 6 символов)")
    username: Optional[str] = Field(None, description="Имя пользователя")

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenCreateRequest(BaseModel):
    name: str = Field("Default", description="Название токена")


# ── Middleware: проверка токена ───────────────────────────────────────────────

def require_auth(authorization: Optional[str] = Header(None)) -> Dict:
    """Проверить Bearer токен из заголовка Authorization."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация. Заголовок: Authorization: Bearer sk-iis-...")
    token = authorization[7:]
    db = get_db()
    user = db.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный или истёкший API токен")
    return user


# ── Регистрация ───────────────────────────────────────────────────────────────

@router.post("/register", summary="Зарегистрироваться")
async def register(body: RegisterRequest) -> Dict[str, Any]:
    """
    Создать аккаунт IIStudio.
    При регистрации автоматически:
    - Создаётся API токен (sk-iis-...)
    - Начисляется $2000 USD и 500,000 токенов (бесплатный бонус для новых пользователей)
    """
    db = get_db()
    try:
        user = db.register(
            email=body.email,
            password=body.password,
            username=body.username or "",
        )
        token = user.pop("token", "")
        
        # Начисляем приветственный бонус
        welcome_bonus = {
            "balance_usd": 2000.0,           # $2000 USD
            "tokens": 500000,                 # 500,000 токенов для использования
            "bonus_applied": True,
            "bonus_message": "🎉 Приветственный бонус: $2000 USD + 500,000 токенов!"
        }
        
        return {
            "success": True,
            "message": "✅ Аккаунт создан! Получи приветственный бонус.",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "username": user["username"],
                "plan": user["plan"],
                "balance_usd": user.get("balance_usd", 2000.0),
                "free_tokens": user.get("free_tokens", 500000),
            },
            "api_token": token,
            "welcome_bonus": welcome_bonus,
            "free_tokens": user.get("free_tokens", 500000),
            "balance_usd": user.get("balance_usd", 2000.0),
            "note": "Сохрани токен — он показывается ОДИН РАЗ. Используй его в CLI: iis auth login --token sk-iis-..."
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Вход ─────────────────────────────────────────────────────────────────────

@router.post("/login", summary="Войти")
async def login(body: LoginRequest) -> Dict[str, Any]:
    """Войти в аккаунт. Возвращает полный токен первого активного ключа."""
    db = get_db()
    user = db.login(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    tokens = db.get_tokens(user["id"])
    active_tokens = [t for t in tokens if t.get("is_active")]

    # Возвращаем полный токен первого активного ключа
    first_token = active_tokens[0]["token"] if active_tokens else None

    # Если нет токенов — создаём новый
    if not first_token:
        new_token = db.create_token(user["id"], user["email"], name="Default")
        first_token = new_token["token"]
        active_tokens = [new_token]

    return {
        "success": True,
        "api_token": first_token,  # Полный токен для localStorage
        "user": {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "plan": user["plan"],
            "balance_usd": user["balance_usd"],
            "free_tokens": user["free_tokens"],
        },
        "tokens": [
            {
                "id": t["id"],
                "name": t["name"],
                "prefix": t["prefix"] + "...",
                "created_at": t["created_at"],
                "last_used": t.get("last_used"),
                "requests_count": t.get("requests_count", 0),
            }
            for t in active_tokens
        ],
    }


# ── Токены ────────────────────────────────────────────────────────────────────

@tokens_router.get("", summary="Список API токенов")
async def list_tokens(authorization: Optional[str] = Header(None)) -> Dict:
    user = require_auth(authorization)
    db = get_db()
    tokens = db.get_tokens(user["id"])
    return {
        "tokens": [
            {
                "id": t["id"],
                "name": t["name"],
                "prefix": t["prefix"] + "...",
                "is_active": t["is_active"],
                "requests_count": t.get("requests_count", 0),
                "last_used": t.get("last_used"),
                "created_at": t["created_at"],
            }
            for t in tokens
        ]
    }


@tokens_router.post("", summary="Создать новый API токен")
async def create_token(
    body: TokenCreateRequest,
    authorization: Optional[str] = Header(None)
) -> Dict:
    user = require_auth(authorization)
    db = get_db()
    token = db.create_token(user["id"], user["email"], name=body.name)
    return {
        "success": True,
        "message": "✅ Новый токен создан. Сохрани его — показывается один раз!",
        "token": token["token"],
        "name": token["name"],
        "prefix": token["prefix"] + "...",
    }


@tokens_router.delete("/{token_id}", summary="Удалить токен")
async def delete_token(token_id: str, authorization: Optional[str] = Header(None)) -> Dict:
    user = require_auth(authorization)
    db = get_db()
    ok = db.delete_token(user["id"], token_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Токен не найден")
    return {"success": True, "message": "Токен удалён"}


# ── Баланс ────────────────────────────────────────────────────────────────────

@balance_router.get("", summary="Мой баланс")
async def get_balance(authorization: Optional[str] = Header(None)) -> Dict:
    user = require_auth(authorization)
    return {
        "balance_usd": round(user.get("balance_usd", 0), 6),
        "free_tokens": user.get("free_tokens", 0),
        "plan": user.get("plan", "free"),
        "total_spent": round(user.get("total_spent", 0), 6),
        "requests_count": user.get("requests_count", 0),
        "note": "50 000 бесплатных токенов при регистрации. После — пополни баланс.",
    }


# ── Профиль ───────────────────────────────────────────────────────────────────

@user_router.get("/me", summary="Мой профиль")
async def get_me(authorization: Optional[str] = Header(None)) -> Dict:
    user = require_auth(authorization)
    db = get_db()
    tokens = db.get_tokens(user["id"])
    return {
        "id": user["id"],
        "email": user["email"],
        "username": user["username"],
        "plan": user["plan"],
        "balance_usd": round(user.get("balance_usd", 0), 6),
        "free_tokens": user.get("free_tokens", 0),
        "requests_count": user.get("requests_count", 0),
        "created_at": user.get("created_at"),
        "tokens_count": len([t for t in tokens if t.get("is_active")]),
    }
