# ============================================================================
# IIStudio — Проверка доступности прокси
# ============================================================================

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

import aiohttp
from utils.logger import logger


# URL для проверки (проверяем что arena.ai доступен)
CHECK_URL = "https://arena.ai"
FALLBACK_CHECK_URL = "https://httpbin.org/ip"
CHECK_TIMEOUT = 15  # секунд


async def check_proxy(proxy: Dict[str, Any], timeout: int = CHECK_TIMEOUT) -> Dict[str, Any]:
    """Проверить доступность одного прокси.

    Args:
        proxy: словарь с полями type, host, port, [username, password, secret]
        timeout: таймаут в секундах

    Returns:
        proxy dict обогащённый полями: alive, latency_ms, error
    """
    result = proxy.copy()
    result["alive"] = False
    result["latency_ms"] = None
    result["error"] = None
    result["checked_at"] = time.time()

    proxy_url = _build_proxy_url(proxy)
    if proxy_url is None and proxy.get("type") == "mtproto":
        # MTProto прокси используются через SOCKS5 туннель mtg
        # — помечаем как живой, проверка будет через туннель
        result["alive"] = True
        result["latency_ms"] = 0
        result["note"] = "mtproto_unchecked"
        return result

    connector_kwargs: Dict[str, Any] = {}
    if proxy_url:
        # aiohttp поддерживает socks5 через aiohttp_socks, но у нас его нет
        # используем env-прокси через connector
        connector_kwargs["proxy"] = proxy_url

    start = time.perf_counter()
    try:
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            timeout=timeout_obj,
        ) as session:
            url = CHECK_URL
            kwargs: Dict[str, Any] = {}
            if proxy_url:
                kwargs["proxy"] = proxy_url

            async with session.get(url, **kwargs, allow_redirects=True) as resp:
                latency = (time.perf_counter() - start) * 1000
                result["alive"] = resp.status < 500
                result["latency_ms"] = round(latency, 1)
                result["http_status"] = resp.status
    except asyncio.TimeoutError:
        result["error"] = "timeout"
        logger.debug("Прокси {}:{} — таймаут", proxy.get("host"), proxy.get("port"))
    except Exception as e:
        result["error"] = str(e)
        logger.debug("Прокси {}:{} — ошибка: {}", proxy.get("host"), proxy.get("port"), e)

    return result


async def check_proxies_bulk(
    proxies: list[Dict[str, Any]],
    concurrency: int = 10,
    timeout: int = CHECK_TIMEOUT,
) -> list[Dict[str, Any]]:
    """Проверить список прокси параллельно.

    Args:
        proxies: список прокси
        concurrency: максимум одновременных проверок
        timeout: таймаут одной проверки

    Returns:
        список обогащённых результатами словарей
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _check(p: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            return await check_proxy(p, timeout)

    tasks = [asyncio.create_task(_check(p)) for p in proxies]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    alive = sum(1 for r in results if r.get("alive"))
    logger.info(
        "Проверка прокси: {}/{} живых из {}",
        alive, len(results), len(proxies),
    )
    return list(results)


def _build_proxy_url(proxy: Dict[str, Any]) -> Optional[str]:
    """Построить URL прокси для aiohttp."""
    ptype = proxy.get("type", "")
    host = proxy.get("host", "")
    port = proxy.get("port", 0)

    if ptype == "socks5":
        user = proxy.get("username", "")
        pwd = proxy.get("password", "")
        if user and pwd:
            return f"socks5://{user}:{pwd}@{host}:{port}"
        return f"socks5://{host}:{port}"

    if ptype == "http":
        return f"http://{host}:{port}"

    return None  # MTProto — нельзя напрямую через aiohttp
