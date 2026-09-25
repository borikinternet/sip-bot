from __future__ import annotations

import asyncio
import socket

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from backend.url_fetch import UrlImportError, _PublicResolver, _checked_url, _document_name, download_document


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "http://localhost:11434/api/tags",
    "http://127.0.0.1/", "http://192.168.1.1/", "http://169.254.169.254/",
    "http://[::1]/", "https://user:password@example.org/page",
])
def test_rejects_local_and_non_http_urls(url: str) -> None:
    with pytest.raises(UrlImportError):
        _checked_url(url)


def test_accepts_public_url_and_mime_based_filename() -> None:
    assert _checked_url("https://example.org/articles/42") == "https://example.org/articles/42"
    assert _document_name("https://example.org/articles/42", "text/html") == "42.html"
    assert _document_name("https://example.org/paper.pdf", "application/pdf") == "paper.pdf"


def test_dns_result_with_private_address_is_rejected(monkeypatch) -> None:
    async def run() -> None:
        async def fake_getaddrinfo(*args, **kwargs):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
            ]

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)
        with pytest.raises(UrlImportError, match="внутренний"):
            await _PublicResolver().resolve("example.org", 443)

    asyncio.run(run())


def test_bounded_url_download_and_private_redirect(monkeypatch) -> None:
    async def run() -> None:
        app = web.Application()
        async def article(request):
            return web.Response(
                text='<html><meta charset="windows-1251"><body><p>Привет, SIP!</p></body></html>',
                content_type="text/html", charset="windows-1251",
            )

        async def large(request):
            return web.Response(body=b"x" * (640 * 1024 + 1), content_type="text/plain")

        async def redirect(request):
            return web.Response(status=302, headers={"Location": "http://127.0.0.1:11434/api/tags"})

        app.router.add_get("/article", article)
        app.router.add_get("/large", large)
        app.router.add_get("/redirect", redirect)
        async with TestServer(app) as server:
            base = str(server.make_url("/"))
            # Only the first test URL is allowed through; redirect targets still use the real guard.
            original_check = _checked_url
            monkeypatch.setattr("backend.url_fetch._checked_url", lambda url: url if url.startswith(base) else original_check(url))
            document = await download_document(base + "article")
            assert document.filename == "article.html"
            assert "Привет, SIP!" in document.data.decode("utf-8")
            with pytest.raises(UrlImportError, match="640 КиБ"):
                await download_document(base + "large")
            with pytest.raises(UrlImportError, match="Локальные"):
                await download_document(base + "redirect")

    asyncio.run(run())
