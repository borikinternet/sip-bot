"""Bounded public-URL downloads for the unauthenticated conference demo."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, TCPConnector
from aiohttp.abc import AbstractResolver

from .models import MAX_UPLOAD_BYTES


class UrlImportError(ValueError):
    """The remote document cannot safely be imported."""


@dataclass(frozen=True, slots=True)
class DownloadedDocument:
    filename: str
    data: bytes
    url: str


def _checked_url(url: str) -> str:
    if not url or len(url) > 2048 or any(ord(char) < 32 for char in url):
        raise UrlImportError("Укажите корректную ссылку длиной до 2048 символов")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise UrlImportError("Некорректный адрес документа") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not host or parsed.username or parsed.password:
        raise UrlImportError("Разрешены только публичные ссылки http:// и https:// без учётных данных")
    if port == 0:
        raise UrlImportError("Некорректный порт в ссылке")
    if host.casefold() == "localhost" or host.casefold().endswith((".localhost", ".local")):
        raise UrlImportError("Локальные и внутренние адреса недоступны для загрузки")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise UrlImportError("Локальные и внутренние адреса недоступны для загрузки")
    return url


def validate_document_url(url: str) -> str:
    return _checked_url(url.strip())


class _PublicResolver(AbstractResolver):
    """Pin each connection to DNS results after rejecting private addresses."""

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> list[dict]:
        try:
            answers = await asyncio.get_running_loop().getaddrinfo(
                host, port, family=family, type=socket.SOCK_STREAM,
            )
        except OSError as exc:
            raise UrlImportError(f"Не удалось найти адрес сайта: {host}") from exc
        if not answers or any(not ipaddress.ip_address(answer[4][0]).is_global for answer in answers):
            raise UrlImportError("Ссылка ведёт на локальный или внутренний адрес")
        return [
            {"hostname": host, "host": address[0], "port": address[1], "family": af,
             "proto": proto, "flags": 0}
            for af, _, proto, _, address in answers
        ]

    async def close(self) -> None:
        return None


def _document_name(url: str, content_type: str) -> str:
    suffix_by_type = {
        "text/html": ".html", "application/xhtml+xml": ".html",
        "text/plain": ".txt", "text/markdown": ".md", "text/x-markdown": ".md",
        "application/pdf": ".pdf",
    }
    path_name = PurePosixPath(unquote(urlsplit(url).path)).name
    path_suffix = PurePosixPath(path_name).suffix.casefold()
    if content_type in suffix_by_type:
        suffix = suffix_by_type[content_type]
    elif content_type in {"application/octet-stream", "binary/octet-stream"} and path_suffix in {".md", ".txt", ".pdf", ".html", ".htm"}:
        suffix = path_suffix
    else:
        raise UrlImportError("По ссылке нужен документ HTML, Markdown, TXT или текстовый PDF")
    stem = re.sub(r"[^\w.-]+", "-", PurePosixPath(path_name).stem, flags=re.UNICODE).strip(".-")[:60]
    return f"{stem or 'web-page'}{suffix}"


def _normalize_text_encoding(data: bytes, charset: str | None, filename: str) -> bytes:
    if filename.endswith(".pdf"):
        return data
    if not charset and filename.endswith((".html", ".htm")):
        match = re.search(rb"<meta\b[^>]*\bcharset\s*=\s*['\"]?([\w.-]+)", data[:4096], re.I)
        if match:
            charset = match.group(1).decode("ascii", errors="ignore")
    try:
        return data.decode(charset or "utf-8-sig").encode("utf-8")
    except (LookupError, UnicodeError) as exc:
        raise UrlImportError("Не удалось прочитать текст: проверьте кодировку страницы") from exc


async def _download_document(url: str) -> DownloadedDocument:
    """Follow a few checked redirects, then download at most 640 KiB of content."""

    current_url = validate_document_url(url)
    timeout = ClientTimeout(total=20, sock_connect=5, sock_read=10)
    connector = TCPConnector(resolver=_PublicResolver(), use_dns_cache=False)
    async with ClientSession(connector=connector, timeout=timeout, trust_env=False) as client:
        for _ in range(4):
            _checked_url(current_url)
            async with client.get(current_url, allow_redirects=False, headers={"Accept": "text/html, text/plain, text/markdown, application/pdf"}) as response:
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        raise UrlImportError("Сайт перенаправил запрос без нового адреса")
                    current_url = _checked_url(urljoin(current_url, location))
                    continue
                if response.status != 200:
                    raise UrlImportError(f"Сайт вернул HTTP {response.status}")
                filename = _document_name(current_url, response.content_type.lower())
                if response.content_length and response.content_length > MAX_UPLOAD_BYTES:
                    raise UrlImportError("Документ превышает лимит 640 КиБ")
                body = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_UPLOAD_BYTES:
                        raise UrlImportError("Документ превышает лимит 640 КиБ")
                if not body:
                    raise UrlImportError("По ссылке получен пустой документ")
                data = _normalize_text_encoding(bytes(body), response.charset, filename)
                if len(data) > MAX_UPLOAD_BYTES:
                    raise UrlImportError("Текст после преобразования превышает лимит 640 КиБ")
                return DownloadedDocument(filename, data, current_url)
    raise UrlImportError("Слишком много перенаправлений по ссылке")


async def download_document(url: str) -> DownloadedDocument:
    try:
        return await _download_document(url)
    except (ClientError, asyncio.TimeoutError, OSError) as exc:
        raise UrlImportError("Не удалось загрузить документ: сайт недоступен или ответил слишком медленно") from exc
