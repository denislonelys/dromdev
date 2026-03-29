"""
IIStudio — Автопереподключение KiroAI через Playwright
Запускается как фоновая задача если KiroAI не отвечает
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

EMAIL = os.environ.get("ARENA_EMAIL", "denislonelys.business@gmail.com")
PASSWORD_AWS = "Denis3110@aws1!"  # AWS Builder ID пароль


async def reconnect_kiro(cdp_url: str = "http://localhost:9222") -> bool:
    """Переподключить KiroAI в OmniRoute через Playwright."""
    from playwright.async_api import async_playwright
    from utils.logger import logger

    logger.info("Переподключение KiroAI...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0]
            page = await context.new_page()
            page.set_default_timeout(20000)

            # Логин OmniRoute
            await page.goto("http://localhost:20128/login", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            pwd = page.locator('input[type=password]').first
            if await pwd.count():
                await pwd.fill("iistudio2024")
                await page.keyboard.press("Enter")
                await asyncio.sleep(2)

            # KiroAI страница
            await page.goto("http://localhost:20128/dashboard/providers/kiro", wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Удаляем старое соединение
            await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const del = btns.find(b => b.textContent.includes('Delete') || b.textContent.includes('Remove') || b.textContent.includes('delete'));
                if(del) del.click();
            }""")
            await asyncio.sleep(1)
            await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const confirm = btns.find(b => b.textContent.includes('Confirm') || b.textContent.includes('Yes'));
                if(confirm) confirm.click();
            }""")
            await asyncio.sleep(2)

            # Добавляем новое соединение
            await page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Add Connection'));
                if(b) b.click();
            }""")
            await asyncio.sleep(1)
            await page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('AWS Builder'));
                if(b) b.click();
            }""")
            logger.info("Ожидаем AWS OAuth...")
            await asyncio.sleep(10)

            # Обрабатываем AWS страницы
            for pg in context.pages:
                if 'awsapps.com' in pg.url or 'amazonaws' in pg.url or 'profile.aws' in pg.url:
                    logger.info("AWS страница: {}", pg.url[:60])
                    await pg.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Accept'));if(b)b.click();}")
                    await asyncio.sleep(2)
                    # Email если нужен
                    email_inp = pg.locator('input[placeholder="username@example.com"]').first
                    if await email_inp.count():
                        await email_inp.fill(EMAIL)
                        await pg.evaluate("""() => {
                            const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Continue'));
                            if(b) b.click();
                        }""")
                        await asyncio.sleep(5)
                    await pg.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Confirm'));if(b)b.click();}")
                    await asyncio.sleep(3)
                    await pg.evaluate("()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Allow'));if(b)b.click();}")
                    await asyncio.sleep(8)

            await asyncio.sleep(5)

            # Проверяем что соединение появилось
            import httpx
            omni_key = os.environ.get("OMNI_API_KEY", "")
            try:
                r = await httpx.AsyncClient(timeout=10).get(
                    "http://localhost:20128/v1/models",
                    headers={"Authorization": f"Bearer {omni_key}"},
                )
                if r.status_code == 200 and r.json().get("data"):
                    logger.info("✅ KiroAI переподключён!")
                    await page.close()
                    return True
            except Exception:
                pass

            await page.close()
            return False

    except Exception as e:
        from utils.logger import logger
        logger.error("Ошибка переподключения KiroAI: {}", e)
        return False


async def health_check_loop(interval: int = 120):
    """Фоновый цикл проверки KiroAI каждые N секунд."""
    import httpx
    from utils.logger import logger

    omni_key = os.environ.get("OMNI_API_KEY", "")
    if not omni_key:
        logger.warning("OMNI_API_KEY не задан — health check отключён")
        return

    logger.info("KiroAI health check запущен (каждые {}с)", interval)
    fail_count = 0

    while True:
        await asyncio.sleep(interval)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "http://localhost:20128/v1/chat/completions",
                    headers={"Authorization": f"Bearer {omni_key}", "Content-Type": "application/json"},
                    json={"model": "kr/claude-sonnet-4.5", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 3},
                )
                if r.status_code == 200:
                    fail_count = 0
                    logger.debug("KiroAI health check ✅")
                else:
                    fail_count += 1
                    logger.warning("KiroAI health check ❌ ({}/3): status={}", fail_count, r.status_code)
        except Exception as e:
            fail_count += 1
            logger.warning("KiroAI health check ❌ ({}/3): {}", fail_count, e)

        if fail_count >= 3:
            logger.warning("KiroAI недоступен 3 раза подряд — запускаем переподключение...")
            success = await reconnect_kiro()
            if success:
                fail_count = 0
            else:
                logger.error("Переподключение не удалось — жди пока ключ не появится снова")
                fail_count = 0  # Сбрасываем чтобы не спамить


if __name__ == "__main__":
    asyncio.run(health_check_loop(60))
