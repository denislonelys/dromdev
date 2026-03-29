# ============================================================================
# IIStudio — Пул аккаунтов arena.ai с авторегистрацией
#
# При достижении дневного лимита (429 "prompt failed") автоматически:
# 1. Получает temp email через guerrillamail.com
# 2. Регистрирует новый аккаунт на arena.ai
# 3. Переключается на него
# ============================================================================

from __future__ import annotations

import asyncio
import json
import random
import string
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from utils.logger import logger

ACCOUNTS_FILE = Path(".iistudio/arena_accounts.json")


def _random_password(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits + "!@#"
    return "".join(random.choices(chars, k=length))


class AccountPool:
    """Пул аккаунтов arena.ai с авторегистрацией при rate limit."""

    def __init__(self) -> None:
        self._accounts: List[Dict[str, Any]] = []
        self._current_idx: int = 0
        self._load()

    # ── Загрузка/сохранение ───────────────────────────────────────────────────

    def _load(self) -> None:
        ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if ACCOUNTS_FILE.exists():
            try:
                self._accounts = json.loads(ACCOUNTS_FILE.read_text())
                logger.debug("Загружено {} аккаунтов", len(self._accounts))
            except Exception:
                self._accounts = []

    def _save(self) -> None:
        ACCOUNTS_FILE.write_text(json.dumps(self._accounts, indent=2, ensure_ascii=False))

    # ── Текущий аккаунт ───────────────────────────────────────────────────────

    @property
    def current(self) -> Optional[Dict[str, Any]]:
        if not self._accounts:
            return None
        return self._accounts[self._current_idx % len(self._accounts)]

    @property
    def current_email(self) -> str:
        acc = self.current
        return acc["email"] if acc else ""

    @property
    def current_password(self) -> str:
        acc = self.current
        return acc["password"] if acc else ""

    def mark_rate_limited(self) -> None:
        """Отметить текущий аккаунт как исчерпанный (rate limit)."""
        acc = self.current
        if acc:
            acc["rate_limited_at"] = time.time()
            acc["rate_limited"] = True
            self._save()
            logger.warning("Аккаунт {} помечен как rate-limited", acc["email"])

    def mark_working(self) -> None:
        """Отметить текущий аккаунт как рабочий."""
        acc = self.current
        if acc:
            acc["rate_limited"] = False
            acc["last_used"] = time.time()
            self._save()

    def switch_next(self) -> Optional[Dict[str, Any]]:
        """Переключиться на следующий незаблокированный аккаунт."""
        for _ in range(len(self._accounts)):
            self._current_idx = (self._current_idx + 1) % len(self._accounts)
            acc = self._accounts[self._current_idx]
            # Rate limit сбрасывается через 24 часа
            if not acc.get("rate_limited") or (time.time() - acc.get("rate_limited_at", 0)) > 86400:
                acc["rate_limited"] = False
                logger.info("Переключено на аккаунт: {}", acc["email"])
                return acc
        return None

    def add_account(self, email: str, password: str) -> Dict[str, Any]:
        acc = {
            "email": email,
            "password": password,
            "created_at": time.time(),
            "rate_limited": False,
            "rate_limited_at": 0,
            "last_used": 0,
        }
        self._accounts.append(acc)
        self._current_idx = len(self._accounts) - 1
        self._save()
        logger.info("Добавлен аккаунт: {}", email)
        return acc

    # ── Авторегистрация ───────────────────────────────────────────────────────

    async def get_temp_email(self) -> tuple[str, str]:
        """Получить временный email через guerrillamail.com."""
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.get("https://www.guerrillamail.com/ajax.php?f=get_email_address")
                data = r.json()
                return data.get("email_addr", ""), data.get("sid_token", "")
            except Exception as e:
                logger.warning("guerrillamail недоступен: {}, генерируем случайный email", e)
                # Fallback: случайный email (может не работать без подтверждения)
                rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
                return f"{rand}@guerrillamailblock.com", ""

    async def register_new_account(self, page: Any) -> Optional[Dict[str, Any]]:
        """Зарегистрировать новый аккаунт arena.ai через браузер.

        Args:
            page: Playwright page (уже должна быть на arena.ai)

        Returns:
            dict с email/password или None при ошибке
        """
        try:
            email, sid = await self.get_temp_email()
            password = _random_password()
            logger.info("Регистрируем новый аккаунт: {}", email)

            # Выходим из текущего аккаунта (тихо, без перезагрузки)
            await page.evaluate("""async () => {
                try { await fetch('/nextjs-api/sign-out', {method: 'POST'}); } catch(e) {}
            }""")
            await asyncio.sleep(1)

            # Идём на /text/direct
            await page.goto("https://arena.ai/text/direct", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)

            # Убираем оверлеи
            await page.evaluate("""() => {
                document.querySelectorAll('[role=dialog],[aria-hidden=true],[data-aria-hidden=true]')
                    .forEach(e => { if(e.getAttribute('role')==='dialog'||window.getComputedStyle(e).position==='fixed') e.remove(); });
            }""")
            await asyncio.sleep(1)

            # Нажимаем Login
            await page.evaluate("""() => {
                const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Login');
                if(b)b.click();
            }""")
            await asyncio.sleep(2)

            # Email
            escaped_email = email.replace("'", "\\'")
            await page.evaluate(f"""() => {{
                const i=document.querySelector('input[type=email]');if(!i)return;
                const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                s.call(i,'{escaped_email}');i.dispatchEvent(new Event('input',{{bubbles:true}}));
            }}""")
            await asyncio.sleep(0.3)

            # Continue with email
            await page.evaluate("""() => {
                const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Continue with email');
                if(b)b.click();
            }""")
            await asyncio.sleep(2.5)

            # Password
            escaped_pwd = password.replace("'", "\\'")
            await page.evaluate(f"""() => {{
                const i=document.querySelector('input[type=password]');if(!i)return;
                const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                s.call(i,'{escaped_pwd}');i.dispatchEvent(new Event('input',{{bubbles:true}}));
            }}""")
            await asyncio.sleep(0.3)

            # Submit
            await page.evaluate("""() => {
                const p=document.querySelector('input[type=password]');if(!p)return;
                const f=p.closest('form');const b=f&&(f.querySelector('button[type=submit]')||f.querySelector('button'));
                if(b)b.click();
            }""")
            await asyncio.sleep(5)

            # Проверяем успех
            body = await page.evaluate("() => document.body.innerText")
            if "Login" not in body[:300] and ("New Chat" in body or "Direct" in body):
                # ToS
                await page.evaluate("""() => {
                    const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Agree');
                    if(b)b.click();
                }""")
                await asyncio.sleep(2)
                await page.evaluate("""() => {
                    document.querySelectorAll('[role=dialog],[aria-hidden=true],[data-aria-hidden=true]')
                        .forEach(e=>{if(e.getAttribute('role')==='dialog'||window.getComputedStyle(e).position==='fixed')e.remove();});
                }""")

                acc = self.add_account(email, password)
                logger.info("✅ Новый аккаунт зарегистрирован: {}", email)
                return acc
            else:
                logger.warning("Регистрация не удалась для {}", email)
                return None

        except Exception as e:
            logger.error("Ошибка регистрации аккаунта: {}", e)
            return None

    async def ensure_working_account(self, page: Any) -> bool:
        """Убедиться что есть рабочий аккаунт (переключить или зарегистрировать новый)."""
        # Пробуем переключить на другой аккаунт
        acc = self.switch_next()
        if acc:
            logger.info("Переключаемся на аккаунт: {}", acc["email"])
            # Логинимся через браузер
            return await self._login_account(page, acc["email"], acc["password"])

        # Нет свободных аккаунтов — регистрируем новый
        logger.info("Регистрируем новый аккаунт (все исчерпаны)...")
        new_acc = await self.register_new_account(page)
        return new_acc is not None

    async def _login_account(self, page: Any, email: str, password: str) -> bool:
        """Залогиниться с конкретным аккаунтом."""
        try:
            # Выход
            await page.evaluate("async () => { try { await fetch('/nextjs-api/sign-out', {method:'POST'}); } catch(e) {} }")
            await asyncio.sleep(1)

            await page.goto("https://arena.ai/text/direct", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)

            await page.evaluate("""() => {
                document.querySelectorAll('[role=dialog],[aria-hidden=true],[data-aria-hidden=true]')
                    .forEach(e=>{if(e.getAttribute('role')==='dialog'||window.getComputedStyle(e).position==='fixed')e.remove();});
            }""")
            await asyncio.sleep(1)

            await page.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Login');if(b)b.click();}")
            await asyncio.sleep(2)

            esc_email = email.replace("'", "\\'")
            await page.evaluate(f"""()=>{{const i=document.querySelector('input[type=email]');if(!i)return;
                const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                s.call(i,'{esc_email}');i.dispatchEvent(new Event('input',{{bubbles:true}}));}}""")
            await asyncio.sleep(0.3)
            await page.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Continue with email');if(b)b.click();}")
            await asyncio.sleep(2)

            esc_pwd = password.replace("'", "\\'")
            await page.evaluate(f"""()=>{{const i=document.querySelector('input[type=password]');if(!i)return;
                const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                s.call(i,'{esc_pwd}');i.dispatchEvent(new Event('input',{{bubbles:true}}));}}""")
            await asyncio.sleep(0.3)
            await page.evaluate("()=>{const p=document.querySelector('input[type=password]');if(!p)return;const f=p.closest('form');const b=f&&(f.querySelector('button[type=submit]')||f.querySelector('button'));if(b)b.click();}")
            await asyncio.sleep(5)

            body = await page.evaluate("() => document.body.innerText")
            success = "Login" not in body[:300]
            if success:
                await page.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Agree');if(b)b.click();}")
                await asyncio.sleep(2)
                await page.evaluate("""()=>{document.querySelectorAll('[role=dialog],[aria-hidden=true],[data-aria-hidden=true]').forEach(e=>{if(e.getAttribute('role')==='dialog'||window.getComputedStyle(e).position==='fixed')e.remove();});}""")
                logger.info("✅ Вошли в аккаунт: {}", email)
            return success
        except Exception as e:
            logger.error("Ошибка входа в аккаунт {}: {}", email, e)
            return False
