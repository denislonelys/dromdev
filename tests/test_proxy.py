# ============================================================================
# IIStudio — Тесты: proxy модуль
# ============================================================================

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from utils.helpers import parse_proxy, load_proxies
from pathlib import Path
import tempfile
import os


class TestParseProxy:
    def test_parse_socks5_with_auth(self):
        result = parse_proxy("socks5://user:pass@192.168.1.1:1080")
        assert result is not None
        assert result["type"] == "socks5"
        assert result["host"] == "192.168.1.1"
        assert result["port"] == 1080
        assert result["username"] == "user"
        assert result["password"] == "pass"

    def test_parse_socks5_without_auth(self):
        result = parse_proxy("socks5://95.81.99.82:1089")
        assert result is not None
        assert result["type"] == "socks5"
        assert result["host"] == "95.81.99.82"
        assert result["port"] == 1089
        assert "username" not in result

    def test_parse_mtproto(self):
        result = parse_proxy("tg.atomic-vpn.com:443:dd3f087f3f403449a2a9446de22b5bc3d1")
        assert result is not None
        assert result["type"] == "mtproto"
        assert result["host"] == "tg.atomic-vpn.com"
        assert result["port"] == 443
        assert result["secret"] == "dd3f087f3f403449a2a9446de22b5bc3d1"

    def test_parse_comment_line(self):
        result = parse_proxy("# это комментарий")
        assert result is None

    def test_parse_empty_line(self):
        result = parse_proxy("")
        assert result is None

    def test_parse_invalid_line(self):
        result = parse_proxy("not_a_proxy")
        assert result is None

    def test_parse_mtproto_ip(self):
        result = parse_proxy("193.39.15.115:443:dd585256032fd8a78a0602ddd90f9c981f")
        assert result is not None
        assert result["type"] == "mtproto"
        assert result["host"] == "193.39.15.115"
        assert result["port"] == 443


class TestLoadProxies:
    def test_load_from_file(self):
        content = """# Комментарий
tg.atomic-vpn.com:443:secret123
socks5://user:pass@1.2.3.4:1080
# ещё комментарий
invalid_line
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            tmp_path = Path(f.name)

        try:
            proxies = load_proxies(tmp_path)
            assert len(proxies) == 2
            types = {p["type"] for p in proxies}
            assert "mtproto" in types
            assert "socks5" in types
        finally:
            os.unlink(tmp_path)

    def test_load_nonexistent_file(self):
        proxies = load_proxies(Path("/nonexistent/path/proxy.txt"))
        assert proxies == []

    def test_all_comments_returns_empty(self):
        content = "# только комментарии\n# ещё один\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            tmp_path = Path(f.name)

        try:
            proxies = load_proxies(tmp_path)
            assert proxies == []
        finally:
            os.unlink(tmp_path)


class TestProxyChecker:
    @pytest.mark.asyncio
    async def test_check_mtproto_returns_alive(self):
        from proxy.checker import check_proxy
        proxy = {"type": "mtproto", "host": "tg.atomic-vpn.com", "port": 443, "secret": "abc"}
        result = await check_proxy(proxy, timeout=5)
        # MTProto помечается как alive без проверки (нет mtg)
        assert result["type"] == "mtproto"
        assert "alive" in result

    @pytest.mark.asyncio
    async def test_check_dead_proxy(self):
        from proxy.checker import check_proxy
        proxy = {
            "type": "socks5",
            "host": "127.0.0.1",
            "port": 19999,  # заведомо несуществующий порт
        }
        result = await check_proxy(proxy, timeout=3)
        assert result["alive"] is False
        assert result.get("error") is not None

    @pytest.mark.asyncio
    async def test_bulk_check(self):
        from proxy.checker import check_proxies_bulk
        proxies = [
            {"type": "mtproto", "host": "host1.com", "port": 443, "secret": "abc"},
            {"type": "socks5", "host": "127.0.0.1", "port": 19998},
        ]
        results = await check_proxies_bulk(proxies, concurrency=2, timeout=3)
        assert len(results) == 2
        assert all("alive" in r for r in results)


class TestProxyManager:
    @pytest.mark.asyncio
    async def test_get_current_no_proxies(self):
        from proxy.manager import ProxyManager
        manager = ProxyManager(
            proxy_file=Path("/nonexistent.txt"),
            check_interval=9999,
        )
        # Не запускаем — нет прокси
        assert manager.get_current() is None

    @pytest.mark.asyncio
    async def test_report_failure_increments(self):
        from proxy.manager import ProxyManager
        manager = ProxyManager(
            proxy_file=Path("/nonexistent.txt"),
            max_failures=3,
        )
        proxy = {"type": "socks5", "host": "1.2.3.4", "port": 1080, "alive": True}
        manager._proxies = [proxy]

        manager.report_failure(proxy)
        assert manager._failures.get("1.2.3.4:1080") == 1

        manager.report_failure(proxy)
        manager.report_failure(proxy)
        # После 3 ошибок прокси помечается мёртвым
        assert proxy.get("alive") is False

    def test_proxy_id(self):
        from proxy.manager import ProxyManager
        pid = ProxyManager._proxy_id({"host": "1.2.3.4", "port": 443})
        assert pid == "1.2.3.4:443"

    def test_get_status_empty(self):
        from proxy.manager import ProxyManager
        manager = ProxyManager(proxy_file=Path("/nonexistent.txt"))
        status = manager.get_status()
        assert status == []
